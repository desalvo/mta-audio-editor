"""DrumSep ONNX inference worker for the four kit components.

The converted model expects a time-domain stereo window and an external STFT
representation. Keep this isolated so that ONNX Runtime is optional for users.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

STEMS = ("kick", "snare", "cymbals", "toms")
SAMPLE_RATE = 44100
WINDOW = 1764000
HOP = 882000
NFFT = 4096
FFT_HOP = 1024
FRAMES = 1723


def stft_features(stereo: np.ndarray) -> np.ndarray:
    """Torch-compatible centred Hann STFT, real/imag channels, without Nyquist.

    The ONNX model expects the unnormalised complex STFT produced by
    torch.stft(..., n_fft=4096, hop_length=1024, center=True).
    """
    from scipy import signal
    hann = signal.windows.hann(NFFT, sym=False).astype('float32')
    features = []
    for channel in range(2):
        _, _, spectrum = signal.stft(stereo[channel], fs=SAMPLE_RATE,
                                     window=hann, nperseg=NFFT,
                                     noverlap=NFFT - FFT_HOP,
                                     boundary='even', padded=False)
        spectrum = spectrum[:NFFT // 2, :FRAMES] * hann.sum()
        if spectrum.shape != (NFFT // 2, FRAMES):
            raise RuntimeError(f'Unexpected DrumSep STFT dimensions: {spectrum.shape}')
        features.extend((spectrum.real, spectrum.imag))
    return np.stack(features, axis=0)[None].astype('float32')


def reconstruct_frequency(freq_output: np.ndarray) -> np.ndarray:
    """Inverse the ONNX spectral branch to 4 stereo time-domain stem windows.

    freq_out layout: [batch, stem, (L.real,L.imag,R.real,R.imag), bin, frame].
    The final hybrid prediction is frequency ISTFT + time-domain prediction.
    """
    from scipy import signal
    frequency = np.asarray(freq_output, dtype='float32')
    if frequency.shape != (1, 4, 4, NFFT // 2, FRAMES):
        raise RuntimeError(f'Unexpected DrumSep freq_out shape: {frequency.shape}')
    hann = signal.windows.hann(NFFT, sym=False).astype('float32')
    result = np.empty((4, 2, WINDOW), dtype='float32')
    for stem in range(4):
        for channel in range(2):
            real = frequency[0, stem, channel * 2]
            imag = frequency[0, stem, channel * 2 + 1]
            spectrum = np.empty((NFFT // 2 + 1, FRAMES), dtype='complex64')
            spectrum[:-1] = real + 1j * imag
            spectrum[-1] = 0  # Nyquist was excluded by the ONNX converter.
            _, samples = signal.istft(spectrum / hann.sum(), fs=SAMPLE_RATE,
                                     window=hann, nperseg=NFFT,
                                     noverlap=NFFT - FFT_HOP,
                                     input_onesided=True, boundary=True)
            # The model's frame count covers 1,763,328 samples; its final
            # 672 samples have no spectral prediction. Zero-pad that tail,
            # allowing the temporal branch to supply the end of the window.
            result[stem, channel] = np.pad(
                samples[:WINDOW], (0, max(0, WINDOW - len(samples)))
            )[:WINDOW]
    return result


def infer(source: Path, model: Path, output: Path) -> list[Path]:
    import soundfile as sf
    from scipy.signal import resample_poly
    import onnxruntime as ort
    from math import gcd
    data, rate = sf.read(str(source), dtype='float32', always_2d=True)
    if data.shape[1] == 1: data = np.repeat(data, 2, axis=1)
    if data.shape[1] > 2: data = data[:, :2]
    if rate != SAMPLE_RATE:
        div = gcd(int(rate), SAMPLE_RATE)
        data = resample_poly(data, SAMPLE_RATE//div, int(rate)//div, axis=0).astype('float32')
    original_length = len(data)
    if not original_length: raise ValueError('Empty drums WAV')
    session = ort.InferenceSession(str(model), providers=['CPUExecutionProvider'])
    input_names = {i.name for i in session.get_inputs()}
    output_names = {o.name for o in session.get_outputs()}
    if input_names != {'mix','mag'} or not {'time_out','freq_out'} <= output_names:
        raise RuntimeError(f'Unsupported DrumSep ONNX signature: {input_names} -> {output_names}')
    sums = np.zeros((4, original_length, 2), dtype='float32')
    weights = np.zeros(original_length, dtype='float32')
    for start in range(0, original_length, HOP):
        end = min(start+WINDOW, original_length)
        clip = np.zeros((WINDOW, 2), dtype='float32')
        clip[:end-start] = data[start:end]
        raw = clip.T[None]
        freq = stft_features(clip.T)
        predicted = dict(zip([o.name for o in session.get_outputs()],
                             session.run(None, {'mix':raw,'mag':freq})))
        time = np.asarray(predicted['time_out'])
        if time.shape != (1,4,2,WINDOW):
            raise RuntimeError(f'Unexpected DrumSep time_out shape {time.shape}')
        # Hybrid Demucs: combine both branches; time-only is incomplete.
        hybrid = time[0] + reconstruct_frequency(predicted['freq_out'])
        window = np.ones(end-start, dtype='float32')
        if start: window[:min(4096,len(window))] = np.linspace(0,1,min(4096,len(window)))
        if end < original_length: window[-min(4096,len(window)):] *= np.linspace(1,0,min(4096,len(window)))
        sums[:,start:end] += hybrid[:,:,:end-start].transpose(0,2,1) * window[None,:,None]
        weights[start:end] += window
    sums /= np.maximum(weights, 1e-6)[None,:,None]
    output.mkdir(parents=True, exist_ok=True)
    paths=[]
    for index, stem in enumerate(STEMS):
        path = output / f'{stem}.wav'
        sf.write(str(path), sums[index], SAMPLE_RATE, subtype='PCM_24')
        paths.append(path)
    return paths


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    infer(args.source,args.model,args.output)

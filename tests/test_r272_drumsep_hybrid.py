from pathlib import Path

from app import main
from app import drumsep_onnx_worker as worker


def test_stft_input_matches_onnx_manifest():
    assert (worker.SAMPLE_RATE, worker.WINDOW, worker.HOP) == (44100, 1764000, 882000)
    assert (worker.NFFT, worker.FFT_HOP, worker.FRAMES) == (4096, 1024, 1723)


def test_frequency_branch_is_combined_with_temporal_branch():
    source = Path(worker.__file__).read_text()
    assert "reconstruct_frequency(predicted['freq_out'])" in source
    assert "hybrid = time[0] +" in source
    assert "np.pad(" in source


def test_drumsep_does_not_copy_demucs_drums_as_kit():
    source = Path(main.__file__).read_text()
    region = source[source.index('elif percussion_method == "drumsep-onnx"'):source.index('else:', source.index('elif percussion_method == "drumsep-onnx"'))]
    assert "_np.sum(kit_parts, axis=0)" in region
    assert 'shutil.copyfile(drums_stem, kit_path)' not in region


def test_separate_nonkit_percussion_requires_sam():
    source = Path(main.__file__).read_text()
    assert 'For non-kit percussions select SAM Audio' in source

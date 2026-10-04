import Foundation
import UIKit
import AVFoundation
import CoreML
import CryptoKit

struct LocalStemCapabilities: Codable {
    let installedStemCounts: [Int]
    let recommendedStemCount: Int
    let physicalMemoryBytes: UInt64
    let canRunLocally: Bool
}

enum LocalStemError: LocalizedError {
    case unsupportedStemCount(Int)
    case modelMissing(Int)
    case modelContract(String)
    case audioDecode(String)
    case inference(String)
    case cancelled

    var errorDescription: String? {
        switch self {
        case .unsupportedStemCount(let count): return "Numero di stem locale non supportato: \(count)."
        case .modelMissing(let count): return "Modello Core ML Demucs \(count)-stem non installato."
        case .modelContract(let message): return "Modello Core ML incompatibile: \(message)"
        case .audioDecode(let message): return "Decodifica audio fallita: \(message)"
        case .inference(let message): return "Inferenza locale fallita: \(message)"
        case .cancelled: return "Separazione locale annullata."
        }
    }
}

final class LocalStemEngine {
    static let shared = LocalStemEngine()
    static let sampleRate: Double = 44_100
    static let minimumStemCount = 2
    static let maximumStemCount = 64

    static func supports(stemCount: Int) -> Bool {
        stemCount >= minimumStemCount && stemCount <= maximumStemCount
    }

    private let fm = FileManager.default
    private var cancellationRequested = false
    private let queue = DispatchQueue(label: "com.desalvo.mtaaudioeditor.localstems", qos: .userInitiated)

    private init() {}

    private var modelsDirectory: URL {
        let base = try! fm.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let dir = base.appendingPathComponent("MTA Audio Editor/Models", isDirectory: true)
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    private func safeModelId(_ modelId: String) -> String {
        let allowed = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
        let cleaned = modelId.unicodeScalars.map { allowed.contains($0) ? Character(String($0)) : Character("-") }
        return String(cleaned).trimmingCharacters(in: CharacterSet(charactersIn: "-."))
    }

    func compiledModelURL(modelId: String, stemCount: Int) -> URL {
        let safe = safeModelId(modelId)
        return modelsDirectory.appendingPathComponent("\(safe)-\(stemCount).mlmodelc", isDirectory: true)
    }

    func compiledModelURL(stemCount: Int) -> URL { compiledModelURL(modelId: "demucs", stemCount: stemCount) }

    func isModelInstalled(modelId: String, stemCount: Int) -> Bool {
        fm.fileExists(atPath: compiledModelURL(modelId: modelId, stemCount: stemCount).path)
    }

    func isModelInstalled(stemCount: Int) -> Bool {
        isModelInstalled(modelId: "demucs", stemCount: stemCount) || isModelInstalled(modelId: "demucs-\(stemCount)", stemCount: stemCount)
    }

    private func fingerprintKey(modelId: String, stemCount: Int) -> String { "mta.demucs.coreml.sha256.\(safeModelId(modelId)).\(stemCount)" }

    func modelFingerprint(modelId: String, stemCount: Int) -> String {
        UserDefaults.standard.string(forKey: fingerprintKey(modelId: modelId, stemCount: stemCount)) ?? ""
    }

    func modelFingerprint(stemCount: Int) -> String { modelFingerprint(modelId: "demucs", stemCount: stemCount) }

    private func setModelFingerprint(_ value: String, modelId: String, stemCount: Int) {
        UserDefaults.standard.set(value, forKey: fingerprintKey(modelId: modelId, stemCount: stemCount))
    }

    private func sha256(of url: URL) -> String {
        guard let data = try? Data(contentsOf: url, options: .mappedIfSafe) else { return "" }
        return SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    @discardableResult
    func installBundledDefaultModelIfNeeded() -> Bool {
        let stemCount = 4, modelId = "demucs-4"
        if isModelInstalled(modelId: modelId, stemCount: stemCount) { return true }
        do {
            if let compiled = Bundle.main.url(forResource: "demucs-default-4", withExtension: "mlmodelc", subdirectory: "Models") ?? Bundle.main.url(forResource: "demucs-default-4", withExtension: "mlmodelc") {
                let destination = compiledModelURL(modelId: modelId, stemCount: stemCount)
                try? fm.removeItem(at: destination)
                try fm.copyItem(at: compiled, to: destination)
                setModelFingerprint("bundled-default", modelId: modelId, stemCount: stemCount)
                return true
            }
            if let source = Bundle.main.url(forResource: "demucs-default-4", withExtension: "mlmodel", subdirectory: "Models") ?? Bundle.main.url(forResource: "demucs-default-4", withExtension: "mlmodel") {
                let compiled = try MLModel.compileModel(at: source)
                let destination = compiledModelURL(modelId: modelId, stemCount: stemCount)
                try? fm.removeItem(at: destination)
                try fm.copyItem(at: compiled, to: destination)
                setModelFingerprint(sha256(of: source), modelId: modelId, stemCount: stemCount)
                return true
            }
        } catch { return false }
        return false
    }

    func installedStemCounts() -> [Int] {
        guard let entries = try? fm.contentsOfDirectory(at: modelsDirectory, includingPropertiesForKeys: nil) else { return [] }
        let regex = try? NSRegularExpression(pattern: #"-(\d+)\.mlmodelc$"#)
        return Array(Set(entries.compactMap { url -> Int? in
            let name = url.lastPathComponent
            guard let match = regex?.firstMatch(in: name, range: NSRange(name.startIndex..., in: name)),
                  let range = Range(match.range(at: 1), in: name),
                  let count = Int(name[range]), Self.supports(stemCount: count) else { return nil }
            return count
        })).sorted()
    }

    func installedModelIds() -> [String] {
        guard let entries = try? fm.contentsOfDirectory(at: modelsDirectory, includingPropertiesForKeys: nil) else { return [] }
        return entries.filter { $0.pathExtension == "mlmodelc" }.compactMap { url in
            let base = url.deletingPathExtension().lastPathComponent
            guard let dash = base.lastIndex(of: "-") else { return nil }
            return String(base[..<dash])
        }.sorted()
    }

    func recommendedStemCount() -> Int {
        let gib = Double(ProcessInfo.processInfo.physicalMemory) / 1_073_741_824.0
        #if targetEnvironment(simulator)
        return 4
        #else
        if UIDevice.current.userInterfaceIdiom == .pad {
            if gib >= 12 { return 8 }
            if gib >= 8 { return 6 }
            return 4
        }
        if gib >= 8 { return 6 }
        if gib >= 5 { return 4 }
        return 2
        #endif
    }

    func capabilities() -> LocalStemCapabilities {
        LocalStemCapabilities(installedStemCounts: installedStemCounts(), recommendedStemCount: recommendedStemCount(), physicalMemoryBytes: ProcessInfo.processInfo.physicalMemory, canRunLocally: !installedStemCounts().isEmpty)
    }

    func cancel() { cancellationRequested = true }

    func installDownloadedModel(_ modelURL: URL, modelId: String, stemCount: Int, fingerprint: String = "") throws {
        guard Self.supports(stemCount: stemCount) else { throw LocalStemError.unsupportedStemCount(stemCount) }
        let compiled = try MLModel.compileModel(at: modelURL)
        let destination = compiledModelURL(modelId: modelId, stemCount: stemCount)
        try? fm.removeItem(at: destination)
        try fm.copyItem(at: compiled, to: destination)
        setModelFingerprint(fingerprint.isEmpty ? sha256(of: modelURL) : fingerprint, modelId: modelId, stemCount: stemCount)
    }

    func installDownloadedModel(_ modelURL: URL, stemCount: Int, fingerprint: String = "") throws {
        try installDownloadedModel(modelURL, modelId: "demucs-\(stemCount)", stemCount: stemCount, fingerprint: fingerprint)
    }

    func deleteInstalledModel(modelId: String, stemCount: Int) throws {
        let url = compiledModelURL(modelId: modelId, stemCount: stemCount)
        if fm.fileExists(atPath: url.path) { try fm.removeItem(at: url) }
        UserDefaults.standard.removeObject(forKey: fingerprintKey(modelId: modelId, stemCount: stemCount))
    }

    func deleteInstalledModel(stemCount: Int) throws {
        for id in installedModelIds() where isModelInstalled(modelId: id, stemCount: stemCount) { try deleteInstalledModel(modelId: id, stemCount: stemCount) }
    }

    func separate(
        inputURL: URL,
        modelId: String = "demucs",
        stemCount: Int,
        progress: @escaping (Int, String) -> Void,
        completion: @escaping (Result<[URL], Error>) -> Void
    ) {
        cancellationRequested = false
        queue.async { [weak self] in
            guard let self else { return }
            do {
                let urls = try self.separateSync(inputURL: inputURL, modelId: modelId, stemCount: stemCount, progress: progress)
                DispatchQueue.main.async { completion(.success(urls)) }
            } catch {
                DispatchQueue.main.async { completion(.failure(error)) }
            }
        }
    }

    private func separateSync(inputURL: URL, stemCount: Int, progress: @escaping (Int, String) -> Void) throws -> [URL] {
        guard Self.supports(stemCount: stemCount) else { throw LocalStemError.unsupportedStemCount(stemCount) }
        let modelURL = compiledModelURL(modelId: modelId, stemCount: stemCount)
        guard fm.fileExists(atPath: modelURL.path) else { throw LocalStemError.modelMissing(stemCount) }

        progress(3, "Caricamento modello Core ML")
        let configuration = MLModelConfiguration()
        configuration.computeUnits = .all
        let model = try MLModel(contentsOf: modelURL, configuration: configuration)
        let metadata = model.modelDescription.metadata[.creatorDefinedKey] as? [String: String] ?? [:]
        let expectedCount = Int(metadata["stem_count"] ?? "") ?? stemCount
        guard expectedCount == stemCount else { throw LocalStemError.modelContract("stem_count=\(expectedCount), richiesto \(stemCount)") }
        let labels = stemLabels(metadata: metadata, stemCount: stemCount)
        let chunkFrames = max(44_100, Int(metadata["chunk_frames"] ?? "") ?? 441_000)
        let inputName = metadata["input_name"] ?? "audio"
        let outputName = metadata["output_name"] ?? "stems"

        progress(6, "Preparazione PCM locale")
        let prepared = try convertToStereoPCM(inputURL: inputURL)
        defer { try? fm.removeItem(at: prepared.url) }
        let totalFrames = prepared.frames
        if totalFrames == 0 { throw LocalStemError.audioDecode("file vuoto") }

        // Local mode targets normal song-length material. Auto falls back to the
        // server beyond this conservative 12 minutes limit to avoid thermal throttling.
        let maxLocalFrames = Int(Self.sampleRate * 60 * 12)
        if totalFrames > maxLocalFrames { throw LocalStemError.audioDecode("brano oltre il limite locale di 12 minuti") }

        let hop = max(1, chunkFrames * 3 / 4)
        let overlap = max(0, chunkFrames - hop)
        let chunkStarts = stride(from: 0, to: totalFrames, by: hop).map { $0 }
        let format = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: Self.sampleRate, channels: 2, interleaved: false)!
        let pcmFile = try AVAudioFile(forReading: prepared.url)
        let outputDirectory = fm.temporaryDirectory.appendingPathComponent("mta-local-stems-\(UUID().uuidString)", isDirectory: true)
        try fm.createDirectory(at: outputDirectory, withIntermediateDirectories: true)

        var urls: [URL] = []
        var writers: [AVAudioFile] = []
        for stem in 0..<stemCount {
            let safeLabel = labels[stem].replacingOccurrences(of: "[^A-Za-z0-9_-]", with: "_", options: .regularExpression)
            let url = outputDirectory.appendingPathComponent("\(String(format: "%02d", stem + 1))-\(safeLabel).wav")
            writers.append(try AVAudioFile(forWriting: url, settings: format.settings))
            urls.append(url)
        }

        // Only one overlap-add tail per stem remains resident. Output audio is written
        // incrementally, so memory usage is largely independent of song duration.
        var previousTail = Array(
            repeating: Array(repeating: Array(repeating: Float(0), count: overlap), count: 2),
            count: stemCount
        )
        var previousTailLength = 0

        do {
            for (chunkIndex, start) in chunkStarts.enumerated() {
                if cancellationRequested { throw LocalStemError.cancelled }
                pcmFile.framePosition = AVAudioFramePosition(start)
                guard let sourceBuffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(chunkFrames)) else {
                    throw LocalStemError.audioDecode("buffer PCM chunk non allocabile")
                }
                let requested = AVAudioFrameCount(min(chunkFrames, totalFrames - start))
                try pcmFile.read(into: sourceBuffer, frameCount: requested)
                guard let channelData = sourceBuffer.floatChannelData else {
                    throw LocalStemError.audioDecode("PCM chunk non disponibile")
                }

                let input = try MLMultiArray(shape: [1, 2, NSNumber(value: chunkFrames)], dataType: .float32)
                for channel in 0..<2 {
                    for frame in 0..<chunkFrames {
                        let value: Float = frame < Int(sourceBuffer.frameLength) ? channelData[channel][frame] : 0
                        input[[0, NSNumber(value: channel), NSNumber(value: frame)]] = NSNumber(value: value)
                    }
                }

                let provider = try MLDictionaryFeatureProvider(dictionary: [inputName: input])
                let prediction = try model.prediction(from: provider)
                guard let output = prediction.featureValue(for: outputName)?.multiArrayValue else {
                    throw LocalStemError.modelContract("output '\(outputName)' assente")
                }
                guard output.shape.count == 4,
                      output.shape[1].intValue == stemCount,
                      output.shape[2].intValue == 2,
                      output.shape[3].intValue >= chunkFrames else {
                    throw LocalStemError.modelContract("output atteso [1,\(stemCount),2,\(chunkFrames)]")
                }

                let available = totalFrames - start
                let writeCount = min(hop, available)
                let blendCount = min(previousTailLength, writeCount, overlap)
                for stem in 0..<stemCount {
                    guard let outBuffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(writeCount)) else {
                        throw LocalStemError.inference("buffer output non allocabile")
                    }
                    outBuffer.frameLength = AVAudioFrameCount(writeCount)
                    guard let outData = outBuffer.floatChannelData else { throw LocalStemError.inference("output PCM non disponibile") }
                    for channel in 0..<2 {
                        for frame in 0..<writeCount {
                            let current = output[[0, NSNumber(value: stem), NSNumber(value: channel), NSNumber(value: frame)]].floatValue
                            if frame < blendCount {
                                let alpha = Float(frame + 1) / Float(blendCount + 1)
                                outData[channel][frame] = previousTail[stem][channel][frame] * (1 - alpha) + current * alpha
                            } else {
                                outData[channel][frame] = current
                            }
                        }
                    }
                    try writers[stem].write(from: outBuffer)
                }

                let tailStart = hop
                let tailLength = max(0, min(overlap, available - tailStart))
                if overlap > 0 {
                    for stem in 0..<stemCount {
                        for channel in 0..<2 {
                            for frame in 0..<overlap {
                                previousTail[stem][channel][frame] = frame < tailLength
                                    ? output[[0, NSNumber(value: stem), NSNumber(value: channel), NSNumber(value: tailStart + frame)]].floatValue
                                    : 0
                            }
                        }
                    }
                }
                previousTailLength = tailLength
                let pct = 10 + Int(Double(chunkIndex + 1) / Double(chunkStarts.count) * 82.0)
                progress(pct, "Separazione locale \(chunkIndex + 1)/\(chunkStarts.count)")
            }
        } catch {
            try? fm.removeItem(at: outputDirectory)
            throw error
        }

        progress(96, "Stem locali pronti")
        return urls
    }

    private func stemLabels(metadata: [String: String], stemCount: Int) -> [String] {
        if let raw = metadata["stem_labels"] {
            let labels = raw.split(separator: ",").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            if labels.count == stemCount { return labels }
        }
        switch stemCount {
        case 2: return ["vocals", "accompaniment"]
        case 4: return ["drums", "bass", "other", "vocals"]
        case 6: return ["drums", "bass", "other", "vocals", "guitar", "piano"]
        default: return (1...stemCount).map { "stem\($0)" }
        }
    }

    private func convertToStereoPCM(inputURL: URL) throws -> (url: URL, frames: Int) {
        do {
            let source = try AVAudioFile(forReading: inputURL)
            let sourceFormat = source.processingFormat
            guard let targetFormat = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: Self.sampleRate, channels: 2, interleaved: false),
                  let converter = AVAudioConverter(from: sourceFormat, to: targetFormat) else {
                throw LocalStemError.audioDecode("converter AVAudio non disponibile")
            }
            let tempURL = fm.temporaryDirectory.appendingPathComponent("mta-local-input-\(UUID().uuidString).caf")
            let target = try AVAudioFile(forWriting: tempURL, settings: targetFormat.settings)
            let sourceChunk: AVAudioFrameCount = 16_384
            var totalOutputFrames = 0

            while source.framePosition < source.length {
                if cancellationRequested { throw LocalStemError.cancelled }
                guard let inputBuffer = AVAudioPCMBuffer(pcmFormat: sourceFormat, frameCapacity: sourceChunk) else {
                    throw LocalStemError.audioDecode("buffer sorgente non allocabile")
                }
                let remaining = AVAudioFrameCount(min(Int64(sourceChunk), source.length - source.framePosition))
                try source.read(into: inputBuffer, frameCount: remaining)
                let ratio = Self.sampleRate / sourceFormat.sampleRate
                let capacity = AVAudioFrameCount(Double(inputBuffer.frameLength) * ratio + 256)
                guard let outputBuffer = AVAudioPCMBuffer(pcmFormat: targetFormat, frameCapacity: capacity) else {
                    throw LocalStemError.audioDecode("buffer conversione non allocabile")
                }
                var supplied = false
                var conversionError: NSError?
                let status = converter.convert(to: outputBuffer, error: &conversionError) { _, inputStatus in
                    if supplied {
                        inputStatus.pointee = .noDataNow
                        return nil
                    }
                    supplied = true
                    inputStatus.pointee = .haveData
                    return inputBuffer
                }
                if status == .error || conversionError != nil {
                    throw conversionError ?? LocalStemError.audioDecode("conversione PCM fallita")
                }
                if outputBuffer.frameLength > 0 {
                    try target.write(from: outputBuffer)
                    totalOutputFrames += Int(outputBuffer.frameLength)
                }
            }
            return (tempURL, totalOutputFrames)
        } catch let error as LocalStemError {
            throw error
        } catch {
            throw LocalStemError.audioDecode(error.localizedDescription)
        }
    }
}

import Foundation
import CryptoKit
import Security

// This registry is part of the signed application bundle, never a server reply,
// model header, WebView argument, UserDefaults value or downloaded sidecar.
struct LocalModelReview: Codable {
    let id: String
    let stemCount: Int
    let sourceFormat: String
    let sourceSHA256: String
    let licenseFile: String
    let licenseSHA256: String
    let noticeFile: String
    let noticeSHA256: String
    let authorizationBasis: String
    let reviewReference: String
    let reviewer: String
    let reviewedAt: Int64
    let expiresAt: Int64
    let localNoncommercialOnly: Bool
}

enum LocalModelRightsError: LocalizedError {
    case denied(String)
    var errorDescription: String? {
        let italian = Locale.current.languageCode?.lowercased() == "it"
        switch self {
        case .denied(let reason):
            switch reason {
            case "checkpoint has no bundled rights review", "bundled rights evidence missing":
                return italian ? "L’esecuzione locale richiede una revisione dei diritti di questo checkpoint inclusa nell’app." : "Local execution requires a rights review for this checkpoint included in the app."
            case "source bytes differ from the reviewed checkpoint", "server metadata does not match the reviewed checkpoint":
                return italian ? "Il modello scaricato non corrisponde alla versione autorizzata e non è stato installato." : "The downloaded model does not match the approved version and was not installed."
            case "loaded model permission revoked", "invalid, expired or incompatible rights review", "rights changed during compilation":
                return italian ? "L’autorizzazione del modello è scaduta o cambiata. Aggiorna l’app e reinstalla il modello autorizzato." : "Model authorization expired or changed. Update the app and reinstall the approved model."
            case "this checkpoint requires the reviewed bundled compiled model":
                return italian ? "Questo checkpoint richiede il modello compilato incluso nell’app revisionata." : "This checkpoint requires the compiled model included in the reviewed app."
            case "model is in use":
                return italian ? "Il modello è in uso. Riprova al termine della separazione locale." : "The model is in use. Retry when local separation finishes."
            case "protected receipt unavailable", "protected installation receipt missing":
                return italian ? "L’autorizzazione locale non è verificabile. Sblocca il dispositivo o reinstalla il modello autorizzato." : "Local authorization cannot be verified. Unlock the device or reinstall the approved model."
            default:
                return italian ? "La verifica del modello locale non è riuscita. Reinstalla la versione autorizzata." : "Local model verification failed. Reinstall the approved version."
            }
        }
    }
}

protocol LocalModelReceiptStore {
    func read(_ key: String) throws -> Data?
    func write(_ data: Data, key: String) throws
    func remove(_ key: String) throws
}

final class KeychainModelReceiptStore: LocalModelReceiptStore {
    private let service: String
    init(service: String = "com.desalvo.mtaaudioeditor.local-model-receipts.v1") { self.service = service }
    private func query(_ key: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
         kSecAttrAccount as String: key, kSecAttrSynchronizable as String: false]
    }
    func read(_ key: String) throws -> Data? {
        var item = query(key)
        item[kSecReturnData as String] = true
        item[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(item as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data else {
            throw LocalModelRightsError.denied("protected receipt unavailable")
        }
        return data
    }
    func write(_ data: Data, key: String) throws {
        let query = self.query(key)
        let status = SecItemUpdate(query as CFDictionary, [kSecValueData as String: data] as CFDictionary)
        if status == errSecSuccess { return }
        guard status == errSecItemNotFound else { throw LocalModelRightsError.denied("protected receipt update failed") }
        var item = query
        item[kSecValueData as String] = data
        item[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        guard SecItemAdd(item as CFDictionary, nil) == errSecSuccess else {
            throw LocalModelRightsError.denied("protected receipt creation failed")
        }
    }
    func remove(_ key: String) throws {
        let status = SecItemDelete(query(key) as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw LocalModelRightsError.denied("protected receipt removal failed")
        }
    }
}

final class LocalModelRights {
    struct Installation {
        fileprivate let review: LocalModelReview
        fileprivate let reviewSHA256: String
    }
    struct Admission {
        fileprivate let reviewSHA256: String
        let id: String
        let stemCount: Int
    }
    private struct Registry: Decodable { let schema: String; let models: [LocalModelReview] }
    private struct Receipt: Codable {
        let schema: String
        let id: String
        let stemCount: Int
        let sourceSHA256: String
        let reviewSHA256: String
        let compiledSHA256: String
    }
    private let registryData: () throws -> Data
    private let resourceData: (String) throws -> Data
    private let receipts: LocalModelReceiptStore
    private let now: () -> Int64
    private let fm = FileManager.default

    init(registryData: @escaping () throws -> Data, resourceData: @escaping (String) throws -> Data,
         receipts: LocalModelReceiptStore, now: @escaping () -> Int64 = { Int64(Date().timeIntervalSince1970) }) {
        self.registryData = registryData; self.resourceData = resourceData; self.receipts = receipts; self.now = now
    }
    static func bundled() -> LocalModelRights {
        func resource(_ name: String) throws -> Data {
            guard let url = Bundle.main.url(forResource: name, withExtension: nil, subdirectory: "Models") else {
                throw LocalModelRightsError.denied("bundled rights evidence missing")
            }
            return try Data(contentsOf: url)
        }
        return LocalModelRights(registryData: { try resource("model-rights.json") }, resourceData: resource,
                                receipts: KeychainModelReceiptStore())
    }
    static func safeID(_ id: String) -> Bool {
        guard let match = id.range(of: #"^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$"#, options: .regularExpression) else { return false }
        return match == id.startIndex..<id.endIndex
    }
    static func digest(_ data: Data) -> String { SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined() }
    private static func validDigest(_ value: String) -> Bool {
        value.count == 64 && value.utf8.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
    }
    private func reviewDigest(_ review: LocalModelReview) throws -> String {
        let encoder = JSONEncoder(); encoder.outputFormatting = [.sortedKeys]
        return Self.digest(try encoder.encode(review))
    }
    private func evidence(_ name: String, digest: String) throws {
        guard let match = name.range(of: #"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"#, options: .regularExpression),
              match == name.startIndex..<name.endIndex,
              Self.validDigest(digest) else {
            throw LocalModelRightsError.denied("invalid license or notice reference")
        }
        let data = try resourceData(name)
        guard !data.isEmpty, data.count <= 1_048_576, Self.digest(data) == digest else {
            throw LocalModelRightsError.denied("license or notice evidence mismatch")
        }
    }
    func review(modelID: String, stemCount: Int) throws -> LocalModelReview {
        guard Self.safeID(modelID), (2...64).contains(stemCount) else { throw LocalModelRightsError.denied("invalid model selection") }
        let data = try registryData()
        guard data.count <= 262_144 else { throw LocalModelRightsError.denied("rights registry too large") }
        let registry = try JSONDecoder().decode(Registry.self, from: data)
        guard registry.schema == "mta-ios-model-rights-1", registry.models.count <= 256,
              Set(registry.models.map { "\($0.id):\($0.stemCount)" }).count == registry.models.count,
              let review = registry.models.first(where: { $0.id == modelID && $0.stemCount == stemCount }) else {
            throw LocalModelRightsError.denied("checkpoint has no bundled rights review")
        }
        let instant = now()
        guard Self.validDigest(review.sourceSHA256), ["mlmodel", "mlmodelc"].contains(review.sourceFormat),
              review.localNoncommercialOnly, ["written_permission", "verified_license"].contains(review.authorizationBasis),
              (3...200).contains(review.reviewer.count), review.reviewedAt > 0,
              review.reviewedAt <= instant, review.expiresAt > instant, review.expiresAt > review.reviewedAt,
              review.reviewReference.count <= 2000,
              let reference = URLComponents(string: review.reviewReference), reference.scheme?.lowercased() == "https",
              reference.host?.isEmpty == false, reference.user == nil, reference.password == nil else {
            throw LocalModelRightsError.denied("invalid, expired or incompatible rights review")
        }
        try evidence(review.licenseFile, digest: review.licenseSHA256)
        try evidence(review.noticeFile, digest: review.noticeSHA256)
        return review
    }
    private func fileDigest(_ url: URL) throws -> (String, UInt64) {
        let values = try fm.attributesOfItem(atPath: url.path)
        guard values[.type] as? FileAttributeType == .typeRegular,
              (values[.referenceCount] as? NSNumber)?.intValue == 1,
              let size = values[.size] as? NSNumber, size.uint64Value <= 2_147_483_648 else {
            throw LocalModelRightsError.denied("unsafe or oversized model file")
        }
        let handle = try FileHandle(forReadingFrom: url); defer { try? handle.close() }
        var hasher = SHA256(); var count: UInt64 = 0
        while let block = try handle.read(upToCount: 1_048_576), !block.isEmpty {
            count += UInt64(block.count)
            guard count <= 2_147_483_648 else { throw LocalModelRightsError.denied("model file grew during verification") }
            hasher.update(data: block)
        }
        guard count == size.uint64Value else { throw LocalModelRightsError.denied("model file changed during verification") }
        return (hasher.finalize().map { String(format: "%02x", $0) }.joined(), count)
    }
    func compiledDigest(_ directory: URL) throws -> String {
        let attributes = try fm.attributesOfItem(atPath: directory.path)
        guard attributes[.type] as? FileAttributeType == .typeDirectory else {
            throw LocalModelRightsError.denied("unsafe compiled model directory")
        }
        let base = directory.standardizedFileURL
        var entries: [(String, URL)] = []; var traversalError: Error?
        guard let walker = fm.enumerator(at: base, includingPropertiesForKeys: nil, options: [], errorHandler: { _, error in
            traversalError = error; return false
        }) else { throw LocalModelRightsError.denied("compiled model cannot be enumerated") }
        for case let url as URL in walker {
            let attrs = try fm.attributesOfItem(atPath: url.path)
            guard attrs[.type] as? FileAttributeType != .typeSymbolicLink else { throw LocalModelRightsError.denied("symbolic model link") }
            if attrs[.type] as? FileAttributeType == .typeDirectory { continue }
            let name = String(url.path.dropFirst(base.path.count + 1))
            guard attrs[.type] as? FileAttributeType == .typeRegular, !name.isEmpty,
                  !name.contains("\n"), !name.contains("\u{0}"), entries.count < 8192 else {
                throw LocalModelRightsError.denied("invalid compiled model member")
            }
            entries.append((name, url))
        }
        guard traversalError == nil, !entries.isEmpty else { throw LocalModelRightsError.denied("incomplete compiled model inventory") }
        var hasher = SHA256(); var total: UInt64 = 0
        for (name, url) in entries.sorted(by: { $0.0.utf8.lexicographicallyPrecedes($1.0.utf8) }) {
            let (digest, size) = try fileDigest(url); total += size
            guard total <= 8_589_934_592 else { throw LocalModelRightsError.denied("compiled model exceeds verification budget") }
            hasher.update(data: Data("\(name)\u{0}\(size)\u{0}\(digest)\n".utf8))
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }
    func beginInstallation(source: URL, modelID: String, stemCount: Int, format: String,
                           advertisedFingerprint: String = "") throws -> Installation {
        let review = try self.review(modelID: modelID, stemCount: stemCount)
        let actual: String
        if format == "mlmodelc" { actual = try compiledDigest(source) }
        else {
            let file = try fileDigest(source)
            guard file.1 > 0 else { throw LocalModelRightsError.denied("empty model source") }
            actual = file.0
        }
        guard format == review.sourceFormat, actual == review.sourceSHA256,
              advertisedFingerprint.isEmpty || advertisedFingerprint == actual else {
            throw LocalModelRightsError.denied("source bytes differ from the reviewed checkpoint")
        }
        return Installation(review: review, reviewSHA256: try reviewDigest(review))
    }
    func finishInstallation(_ installation: Installation, compiled: URL,
                            publish: () throws -> Void, rollback: () throws -> Void) throws {
        let review = try self.review(modelID: installation.review.id, stemCount: installation.review.stemCount)
        guard try reviewDigest(review) == installation.reviewSHA256 else { throw LocalModelRightsError.denied("rights changed during compilation") }
        let receipt = Receipt(schema: "mta-ios-model-receipt-1", id: review.id, stemCount: review.stemCount,
                              sourceSHA256: review.sourceSHA256, reviewSHA256: installation.reviewSHA256,
                              compiledSHA256: try compiledDigest(compiled))
        let key = "\(review.id):\(review.stemCount)"
        let previous = try receipts.read(key)
        do {
            try publish()
            try receipts.write(JSONEncoder().encode(receipt), key: key)
        } catch {
            // A failed replacement preserves the old model/receipt when the
            // OS permits rollback;an unresolved rollback never authorizes it.
            try rollback()
            if let previous { try receipts.write(previous, key: key) }
            else { try receipts.remove(key) }
            throw error
        }
    }
    private func receipt(_ review: LocalModelReview) throws -> Receipt {
        guard let data = try receipts.read("\(review.id):\(review.stemCount)"), data.count <= 4096 else {
            throw LocalModelRightsError.denied("protected installation receipt missing")
        }
        let receipt = try JSONDecoder().decode(Receipt.self, from: data)
        let current = try reviewDigest(review)
        guard receipt.schema == "mta-ios-model-receipt-1", receipt.id == review.id, receipt.stemCount == review.stemCount,
              receipt.sourceSHA256 == review.sourceSHA256, receipt.reviewSHA256 == current,
              Self.validDigest(receipt.compiledSHA256) else {
            throw LocalModelRightsError.denied("installed model or rights changed")
        }
        return receipt
    }
    func hasReviewedReceipt(modelID: String, stemCount: Int) -> Bool {
        do { _ = try receipt(review(modelID: modelID, stemCount: stemCount)); return true }
        catch { return false }
    }
    func authorizeInstalled(_ directory: URL, modelID: String, stemCount: Int) throws -> Admission {
        let review = try self.review(modelID: modelID, stemCount: stemCount)
        let stored = try receipt(review)
        guard stored.compiledSHA256 == (try compiledDigest(directory)) else {
            throw LocalModelRightsError.denied("compiled checkpoint bytes changed")
        }
        return Admission(reviewSHA256: try reviewDigest(review), id: modelID, stemCount: stemCount)
    }
    func recheck(_ admission: Admission) throws {
        let review = try self.review(modelID: admission.id, stemCount: admission.stemCount)
        guard try reviewDigest(review) == admission.reviewSHA256 else { throw LocalModelRightsError.denied("loaded model permission revoked") }
    }
    func forget(modelID: String, stemCount: Int) throws { try receipts.remove("\(modelID):\(stemCount)") }
}

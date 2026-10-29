import Foundation

private enum Failure: Error { case expectedDenial; case assertion(String); case storage }
private func require(_ value: Bool, _ message: String) throws { if !value { throw Failure.assertion(message) } }
private func denied(_ work: () throws -> Void) throws {
    do { try work() } catch { return }
    throw Failure.expectedDenial
}
private final class MemoryReceipts: LocalModelReceiptStore {
    var rows: [String: Data] = [:]
    var failNextWrite = false
    var unreadable = false
    func read(_ key: String) throws -> Data? { if unreadable { throw Failure.storage }; return rows[key] }
    func write(_ data: Data, key: String) throws {
        if failNextWrite { failNextWrite = false; throw Failure.storage }
        rows[key] = data
    }
    func remove(_ key: String) throws { rows.removeValue(forKey: key) }
}
private final class Fixture {
    let root: URL
    let source: URL
    let compiled: URL
    let receipts = MemoryReceipts()
    var instant: Int64 = 1_800_000_000
    var entry: [String: Any]
    var evidence = ["LICENSE-test.txt": Data("Own generated test bytes;not a model grant".utf8),
                    "NOTICE-test.txt": Data("Synthetic native rights fixture".utf8)]
    var omit = false
    init() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent("mta-rights-test-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: false)
        source = root.appendingPathComponent("source.mlmodel")
        compiled = root.appendingPathComponent("compiled.mlmodelc")
        try Data("Own test source;never parsed as a neural model".utf8).write(to: source)
        try FileManager.default.createDirectory(at: compiled, withIntermediateDirectories: false)
        try Data("Own compiled fixture bytes".utf8).write(to: compiled.appendingPathComponent("weights.bin"))
        entry = ["id": "fixture-model", "stemCount": 4, "sourceFormat": "mlmodel",
                 "sourceSHA256": LocalModelRights.digest(try Data(contentsOf: source)),
                 "licenseFile": "LICENSE-test.txt", "licenseSHA256": LocalModelRights.digest(evidence["LICENSE-test.txt"]!),
                 "noticeFile": "NOTICE-test.txt", "noticeSHA256": LocalModelRights.digest(evidence["NOTICE-test.txt"]!),
                 "authorizationBasis": "written_permission", "reviewReference": "https://example.test/generated-fixture",
                 "reviewer": "Generated fixture reviewer", "reviewedAt": instant - 100, "expiresAt": instant + 100,
                 "localNoncommercialOnly": true]
    }
    deinit { try? FileManager.default.removeItem(at: root) }
    func rights() -> LocalModelRights {
        LocalModelRights(registryData: { try JSONSerialization.data(withJSONObject: ["schema": "mta-ios-model-rights-1", "models": self.omit ? [] : [self.entry]]) },
                         resourceData: { name in guard let data = self.evidence[name] else { throw Failure.storage }; return data },
                         receipts: receipts, now: { self.instant })
    }
    func install(_ rights: LocalModelRights) throws {
        let ticket = try rights.beginInstallation(source: source, modelID: "fixture-model", stemCount: 4, format: "mlmodel")
        try rights.finishInstallation(ticket, compiled: compiled, publish: {}, rollback: {})
    }
    func admission(_ rights: LocalModelRights) throws -> LocalModelRights.Admission {
        try rights.authorizeInstalled(compiled, modelID: "fixture-model", stemCount: 4)
    }
}

@main
struct LocalModelRightsAcceptance {
    static func main() throws {
        var checks: [[String: String]] = []
        func check(_ name: String, _ body: (Fixture, LocalModelRights) throws -> Void) throws {
            let fixture = try Fixture()
            do { try body(fixture, fixture.rights()); checks.append(["name": name, "status": "passed"]) }
            catch { checks.append(["name": name, "status": "failed", "error": String(describing: error)]) }
        }
        try check("empty registry denies") { f, r in f.omit = true; try denied { _ = try r.review(modelID: "fixture-model", stemCount: 4) } }
        try check("unknown checkpoint denies") { _, r in try denied { _ = try r.review(modelID: "foreign-model", stemCount: 4) } }
        try check("path selector denies") { _, r in try denied { _ = try r.review(modelID: "../fixture-model", stemCount: 4) } }
        try check("wrong stem count denies") { _, r in try denied { _ = try r.review(modelID: "fixture-model", stemCount: 6) } }
        try check("unknown source format denies") { f, r in f.entry["sourceFormat"] = "foreign"; try denied { _ = try r.review(modelID: "fixture-model", stemCount: 4) } }
        try check("expired permission denies") { f, r in f.entry["expiresAt"] = f.instant; try denied { _ = try r.review(modelID: "fixture-model", stemCount: 4) } }
        try check("future review denies") { f, r in f.entry["reviewedAt"] = f.instant + 1; try denied { _ = try r.review(modelID: "fixture-model", stemCount: 4) } }
        try check("commercial grant denies") { f, r in f.entry["localNoncommercialOnly"] = false; try denied { _ = try r.review(modelID: "fixture-model", stemCount: 4) } }
        try check("NC label is not authorization") { f, r in f.entry["authorizationBasis"] = "noncommercial_context"; try denied { _ = try r.review(modelID: "fixture-model", stemCount: 4) } }
        try check("credentialed reference denies") { f, r in f.entry["reviewReference"] = "https://user:secret@example.test/rights"; try denied { _ = try r.review(modelID: "fixture-model", stemCount: 4) } }
        try check("missing license denies") { f, r in f.evidence.removeValue(forKey: "LICENSE-test.txt"); try denied { _ = try r.review(modelID: "fixture-model", stemCount: 4) } }
        try check("changed notice denies") { f, r in f.evidence["NOTICE-test.txt"] = Data("changed".utf8); try denied { _ = try r.review(modelID: "fixture-model", stemCount: 4) } }
        try check("actual source bytes required") { f, r in try Data("different".utf8).write(to: f.source); try denied { _ = try r.beginInstallation(source: f.source, modelID: "fixture-model", stemCount: 4, format: "mlmodel") } }
        try check("server fingerprint is not authority") { f, r in try denied { _ = try r.beginInstallation(source: f.source, modelID: "fixture-model", stemCount: 4, format: "mlmodel", advertisedFingerprint: String(repeating: "0", count: 64)) } }
        try check("source link denies") { f, r in let link = f.root.appendingPathComponent("link.mlmodel"); try FileManager.default.createSymbolicLink(at: link, withDestinationURL: f.source); try denied { _ = try r.beginInstallation(source: link, modelID: "fixture-model", stemCount: 4, format: "mlmodel") } }
        try check("compiled root link denies") { f, r in let link = f.root.appendingPathComponent("link.mlmodelc"); try FileManager.default.createSymbolicLink(at: link, withDestinationURL: f.compiled); try denied { _ = try r.compiledDigest(link) } }
        try check("compiled member link denies") { f, r in try FileManager.default.createSymbolicLink(at: f.compiled.appendingPathComponent("link"), withDestinationURL: f.source); try denied { _ = try r.compiledDigest(f.compiled) } }
        try check("compiled bytes tampering denies") { f, r in try f.install(r); try Data("tampered".utf8).write(to: f.compiled.appendingPathComponent("weights.bin")); try denied { _ = try f.admission(r) } }
        try check("compiled extra member denies") { f, r in try f.install(r); try Data("extra".utf8).write(to: f.compiled.appendingPathComponent("extra.bin")); try denied { _ = try f.admission(r) } }
        try check("missing secure receipt denies") { f, r in try denied { _ = try f.admission(r) } }
        try check("disk receipt cannot grant rights") { f, r in try Data("{\"reviewSHA256\":\"forged\"}".utf8).write(to: f.root.appendingPathComponent("receipt.json")); try denied { _ = try f.admission(r) } }
        try check("foreign receipt identity denies") { f, r in try f.install(r); var row = try JSONSerialization.jsonObject(with: f.receipts.rows["fixture-model:4"]!) as! [String: Any]; row["id"] = "foreign-model"; f.receipts.rows["fixture-model:4"] = try JSONSerialization.data(withJSONObject: row); try denied { _ = try f.admission(r) } }
        try check("loaded review revocation denies") { f, r in try f.install(r); let a = try f.admission(r); f.omit = true; try denied { try r.recheck(a) } }
        try check("loaded review replacement denies") { f, r in try f.install(r); let a = try f.admission(r); f.entry["reviewer"] = "Different reviewer"; try denied { try r.recheck(a) } }
        try check("loaded grant expiry denies") { f, r in try f.install(r); let a = try f.admission(r); f.instant += 101; try denied { try r.recheck(a) } }
        try check("valid offline receipt survives object restart") { f, r in try f.install(r); _ = try f.admission(f.rights()) }
        try check("compiled member rename denies") { f, r in try f.install(r); try FileManager.default.moveItem(at: f.compiled.appendingPathComponent("weights.bin"), to: f.compiled.appendingPathComponent("renamed.bin")); try denied { _ = try f.admission(r) } }
        try check("receipt failure restores original installation") { f, r in
            try f.install(r)
            let original = try Data(contentsOf: f.compiled.appendingPathComponent("weights.bin"))
            let replacement = f.root.appendingPathComponent("replacement.mlmodelc"), backup = f.root.appendingPathComponent("old.mlmodelc")
            try FileManager.default.copyItem(at: f.compiled, to: replacement)
            try Data("different compiler output".utf8).write(to: replacement.appendingPathComponent("weights.bin"))
            let ticket = try r.beginInstallation(source: f.source, modelID: "fixture-model", stemCount: 4, format: "mlmodel")
            f.receipts.failNextWrite = true
            try denied { try r.finishInstallation(ticket, compiled: replacement, publish: {
                try FileManager.default.moveItem(at: f.compiled, to: backup)
                try FileManager.default.moveItem(at: replacement, to: f.compiled)
            }, rollback: {
                try FileManager.default.removeItem(at: f.compiled)
                try FileManager.default.moveItem(at: backup, to: f.compiled)
            }) }
            try require(try Data(contentsOf: f.compiled.appendingPathComponent("weights.bin")) == original, "old bytes lost")
            _ = try f.admission(r)
        }
        try check("publish failure is rolled back") { f, r in
            try f.install(r); var rolledBack = false
            let ticket = try r.beginInstallation(source: f.source, modelID: "fixture-model", stemCount: 4, format: "mlmodel")
            try denied { try r.finishInstallation(ticket, compiled: f.compiled, publish: { throw Failure.storage }, rollback: { rolledBack = true }) }
            try require(rolledBack, "rollback not called"); _ = try f.admission(r)
        }
        try check("missing source denies") { f, r in try FileManager.default.removeItem(at: f.source); try denied { _ = try r.beginInstallation(source: f.source, modelID: "fixture-model", stemCount: 4, format: "mlmodel") } }
        try check("real isolated keychain roundtrip") { _, _ in
            let service = "com.desalvo.mtaaudioeditor.rights-ci.\(UUID().uuidString)"
            let store = KeychainModelReceiptStore(service: service), payload = Data("own SDK receipt fixture".utf8)
            defer { try? store.remove("fixture") }
            try require(try store.read("fixture") == nil, "unexpected initial receipt")
            try store.write(payload, key: "fixture")
            try require(try KeychainModelReceiptStore(service: service).read("fixture") == payload, "secure receipt not persisted")
            try store.remove("fixture"); try require(try store.read("fixture") == nil, "receipt not removed")
        }
        try check("reviewed compiled source inventory accepted") { f, r in
            f.entry["sourceFormat"] = "mlmodelc"; f.entry["sourceSHA256"] = try r.compiledDigest(f.compiled)
            let ticket = try r.beginInstallation(source: f.compiled, modelID: "fixture-model", stemCount: 4, format: "mlmodelc")
            try r.finishInstallation(ticket, compiled: f.compiled, publish: {}, rollback: {}); _ = try f.admission(r)
        }
        let failed = checks.filter { $0["status"] != "passed" }.count
        let result: [String: Any] = ["schema": "mta-ios-rights-sdk-tests-1", "passed": checks.count - failed,
                                     "failed": failed, "skipped": 0, "checks": checks,
                                     "actual_keychain_test": true, "real_neural_model_inference": false]
        let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
        guard CommandLine.arguments.count == 2 else { throw Failure.assertion("output path required") }
        try data.write(to: URL(fileURLWithPath: CommandLine.arguments[1]), options: .atomic)
        guard failed == 0 && checks.count == 32 else { throw Failure.assertion("native rights checks failed") }
    }
}

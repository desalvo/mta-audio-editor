import Foundation
import UIKit

struct GitHubUpdateInfo {
    let channel: String
    let currentVersion: String
    let latestVersion: String
    let available: Bool
    let releaseURL: URL
    let assetURL: URL?
}

final class NativeUpdateManager {
    static let shared = NativeUpdateManager()
    static let repository = "desalvo/mta-audio-editor"
    static let updateChannelKey = "mta.update.channel"

    var channel: String {
        get { UserDefaults.standard.string(forKey: Self.updateChannelKey) == "early" ? "early" : "stable" }
        set { UserDefaults.standard.set(newValue == "early" ? "early" : "stable", forKey: Self.updateChannelKey) }
    }

    private init() {}

    private func versionKey(_ value: String) -> [Int] {
        value.split(whereSeparator: { !$0.isNumber }).compactMap { Int($0) }
    }

    private func isNewer(_ remote: String, than local: String) -> Bool {
        let a = versionKey(remote), b = versionKey(local)
        let count = max(a.count, b.count)
        for i in 0..<count {
            let av = i < a.count ? a[i] : 0
            let bv = i < b.count ? b[i] : 0
            if av != bv { return av > bv }
        }
        return false
    }

    func check(completion: @escaping (Result<GitHubUpdateInfo, Error>) -> Void) {
        let selected = channel
        let suffix = selected == "early" ? "releases/tags/early-main" : "releases/latest"
        let url = URL(string: "https://api.github.com/repos/\(Self.repository)/\(suffix)")!
        var request = URLRequest(url: url)
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("MTA-Audio-Editor-iOS-Updater", forHTTPHeaderField: "User-Agent")
        request.setValue("2022-11-28", forHTTPHeaderField: "X-GitHub-Api-Version")
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error { DispatchQueue.main.async { completion(.failure(error)) }; return }
            guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode), let data else {
                DispatchQueue.main.async { completion(.failure(URLError(.badServerResponse))) }; return
            }
            do {
                let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
                let tag = String(describing: object["tag_name"] ?? "")
                let name = String(describing: object["name"] ?? "")
                let remote = name.replacingOccurrences(of: "MTA Audio Editor ", with: "").isEmpty ? tag : name.replacingOccurrences(of: "MTA Audio Editor ", with: "")
                let current = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0"
                let release = URL(string: String(describing: object["html_url"] ?? "https://github.com/\(Self.repository)/releases"))!
                var assetURL: URL?
                if let assets = object["assets"] as? [[String: Any]] {
                    let ipa = assets.first { String(describing: $0["name"] ?? "").lowercased().hasSuffix(".ipa") }
                    if let raw = ipa?["browser_download_url"] as? String { assetURL = URL(string: raw) }
                }
                let info = GitHubUpdateInfo(channel: selected, currentVersion: current, latestVersion: remote, available: self.isNewer(remote, than: current), releaseURL: release, assetURL: assetURL)
                DispatchQueue.main.async { completion(.success(info)) }
            } catch {
                DispatchQueue.main.async { completion(.failure(error)) }
            }
        }.resume()
    }
}

import UIKit
import WebKit
import UniformTypeIdentifiers

final class MobileWebViewController: UIViewController, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, UIDocumentPickerDelegate {
    private enum Defaults {
        static let serverURL = "mta.server.url"
    }

    private var webView: WKWebView!
    private var openPanelCompletion: (([URL]?) -> Void)?
    private var pendingExportTempURL: URL?

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "MTA Audio Editor"
        view.backgroundColor = .systemBackground
        configureNavigation()
        configureWebView()

        if let value = UserDefaults.standard.string(forKey: Defaults.serverURL), !value.isEmpty {
            loadServer(value)
        } else {
            DispatchQueue.main.async { [weak self] in self?.promptServerURL(required: true) }
        }
    }

    private func configureNavigation() {
        navigationItem.rightBarButtonItems = [
            UIBarButtonItem(title: "Server", style: .plain, target: self, action: #selector(changeServer)),
            UIBarButtonItem(barButtonSystemItem: .refresh, target: self, action: #selector(reloadPage))
        ]
    }

    private func configureWebView() {
        let controller = WKUserContentController()
        controller.add(self, name: "mtaMobile")
        let bridge = """
        window.MtaMobile = {
          getPlatform: function(){ return 'ios'; },
          saveRemoteFile: function(url, filename, mime){
            window.webkit.messageHandlers.mtaMobile.postMessage({action:'saveRemoteFile',url:url,filename:filename,mime:mime});
          },
          shareRemoteFile: function(url, filename, mime){
            window.webkit.messageHandlers.mtaMobile.postMessage({action:'shareRemoteFile',url:url,filename:filename,mime:mime});
          },
          configureServer: function(){
            window.webkit.messageHandlers.mtaMobile.postMessage({action:'configureServer'});
          },
          setBusy: function(value){
            window.webkit.messageHandlers.mtaMobile.postMessage({action:'setBusy',value:!!value});
          }
        };
        """
        controller.addUserScript(WKUserScript(source: bridge, injectionTime: .atDocumentStart, forMainFrameOnly: true))

        let configuration = WKWebViewConfiguration()
        configuration.userContentController = controller
        configuration.websiteDataStore = .default()
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []

        webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.customUserAgent = "MTAEditorMobile/0.2.0-69 iOS"
        webView.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor),
            webView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])
    }

    @objc private func reloadPage() { webView.reload() }
    @objc private func changeServer() { promptServerURL(required: false) }

    private func promptServerURL(required: Bool) {
        let alert = UIAlertController(
            title: "Server MTA Audio Editor",
            message: "Inserisci l'URL HTTPS del backend Docker/Kubernetes. I server HTTP locali sono supportati dalla build mobile.",
            preferredStyle: .alert
        )
        alert.addTextField { field in
            field.placeholder = "https://mta.example.com"
            field.keyboardType = .URL
            field.autocapitalizationType = .none
            field.autocorrectionType = .no
            field.text = UserDefaults.standard.string(forKey: Defaults.serverURL)
        }
        alert.addAction(UIAlertAction(title: "Connetti", style: .default) { [weak self, weak alert] _ in
            guard let self, let raw = alert?.textFields?.first?.text, let normalized = self.normalizeServerURL(raw) else {
                self?.showMessage("URL non valido", "Inserisci un indirizzo http:// o https:// completo.")
                if required { self?.promptServerURL(required: true) }
                return
            }
            UserDefaults.standard.set(normalized, forKey: Defaults.serverURL)
            self.loadServer(normalized)
        })
        if !required {
            alert.addAction(UIAlertAction(title: "Annulla", style: .cancel))
        }
        present(alert, animated: true)
    }

    private func normalizeServerURL(_ raw: String) -> String? {
        var value = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        while value.hasSuffix("/") { value.removeLast() }
        guard let url = URL(string: value), ["http", "https"].contains(url.scheme?.lowercased() ?? ""), url.host != nil else {
            return nil
        }
        return value
    }

    private func loadServer(_ base: String) {
        guard let url = URL(string: base + "/") else { return }
        webView.load(URLRequest(url: url, cachePolicy: .reloadRevalidatingCacheData))
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let target = navigationAction.request.url else { decisionHandler(.cancel); return }
        if let host = webView.url?.host, host.caseInsensitiveCompare(target.host ?? "") == .orderedSame {
            decisionHandler(.allow)
            return
        }
        if ["http", "https"].contains(target.scheme?.lowercased() ?? "") {
            UIApplication.shared.open(target)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    @available(iOS 18.4, *)
    func webView(
        _ webView: WKWebView,
        runOpenPanelWith parameters: WKOpenPanelParameters,
        initiatedByFrame frame: WKFrameInfo,
        completionHandler: @escaping ([URL]?) -> Void
    ) {
        openPanelCompletion = completionHandler
        let types: [UTType] = [.audio, .data, .archive]
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: types, asCopy: false)
        picker.delegate = self
        picker.allowsMultipleSelection = parameters.allowsMultipleSelection
        present(picker, animated: true)
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        if let completion = openPanelCompletion {
            openPanelCompletion = nil
            completion(urls)
        }
        pendingExportTempURL = nil
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        if let completion = openPanelCompletion {
            openPanelCompletion = nil
            completion(nil)
        }
        pendingExportTempURL = nil
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "mtaMobile", let payload = message.body as? [String: Any], let action = payload["action"] as? String else { return }
        switch action {
        case "saveRemoteFile", "shareRemoteFile":
            guard let url = payload["url"] as? String else { return }
            let filename = (payload["filename"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "export.bin"
            let mime = payload["mime"] as? String ?? "application/octet-stream"
            downloadRemote(relativeURL: url, filename: filename, mime: mime, share: action == "shareRemoteFile")
        case "configureServer":
            promptServerURL(required: false)
        case "setBusy":
            UIApplication.shared.isIdleTimerDisabled = (payload["value"] as? Bool) ?? false
        default:
            break
        }
    }

    private func downloadRemote(relativeURL: String, filename: String, mime: String, share: Bool) {
        guard let base = webView.url, let remote = URL(string: relativeURL, relativeTo: base)?.absoluteURL else {
            showMessage("Download fallito", "URL di download non valido.")
            return
        }
        webView.configuration.websiteDataStore.httpCookieStore.getAllCookies { [weak self] cookies in
            guard let self else { return }
            var request = URLRequest(url: remote)
            request.httpMethod = "GET"
            let fields = HTTPCookie.requestHeaderFields(with: cookies)
            for (key, value) in fields { request.setValue(value, forHTTPHeaderField: key) }
            request.setValue(self.webView.customUserAgent, forHTTPHeaderField: "User-Agent")
            URLSession.shared.downloadTask(with: request) { [weak self] location, response, error in
                guard let self else { return }
                if let error {
                    DispatchQueue.main.async { self.showMessage("Download fallito", error.localizedDescription) }
                    return
                }
                guard let location, let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    DispatchQueue.main.async { self.showMessage("Download fallito", "Risposta HTTP non valida.") }
                    return
                }
                do {
                    let safeName = filename.replacingOccurrences(of: "/", with: "_")
                    let destination = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + "-" + safeName)
                    try? FileManager.default.removeItem(at: destination)
                    try FileManager.default.moveItem(at: location, to: destination)
                    DispatchQueue.main.async {
                        if share {
                            let activity = UIActivityViewController(activityItems: [destination], applicationActivities: nil)
                            if let pop = activity.popoverPresentationController {
                                pop.sourceView = self.view
                                pop.sourceRect = CGRect(x: self.view.bounds.midX, y: self.view.bounds.midY, width: 1, height: 1)
                            }
                            self.present(activity, animated: true)
                        } else {
                            self.pendingExportTempURL = destination
                            let picker = UIDocumentPickerViewController(forExporting: [destination], asCopy: true)
                            picker.delegate = self
                            self.present(picker, animated: true)
                        }
                    }
                } catch {
                    DispatchQueue.main.async { self.showMessage("Salvataggio fallito", error.localizedDescription) }
                }
            }.resume()
        }
    }

    private func showMessage(_ title: String, _ message: String) {
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    deinit {
        webView?.configuration.userContentController.removeScriptMessageHandler(forName: "mtaMobile")
        UIApplication.shared.isIdleTimerDisabled = false
    }
}

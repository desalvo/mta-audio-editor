import UIKit
import WebKit
import UniformTypeIdentifiers
import Network

final class MobileWebViewController: UIViewController, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, UIDocumentPickerDelegate {
    private enum Defaults {
        static let serverURL = "mta.server.url"
        static let defaultServerURL = "https://mta-audio-editor.apps.desalvo.eu"
        static let localStemMode = "mta.local.stems.mode"
        static let modelUpdatesWifiOnly = "mta.demucs.modelUpdatesWifiOnly"
        static let lastModelUpdateCheck = "mta.demucs.lastModelUpdateCheck"
        static let modelAccessToken = "mta.demucs.modelAccessToken"
        static let modelAccessTokenExpiresAt = "mta.demucs.modelAccessTokenExpiresAt"
    }

    private var webView: WKWebView!
    private var openPanelCompletion: (([URL]?) -> Void)?
    private var pendingExportTempURL: URL?
    private var lastPickedAudioURL: URL?
    private var activeLocalStemTask = false
    private var didOfferAppUpdate = false
    private var modelRefreshInFlight = false
    private let pathMonitor = NWPathMonitor()
    private let pathQueue = DispatchQueue(label: "mta.network.path")
    private var networkPath: NWPath?
    private var modelRefreshTimer: Timer?

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "MTA Audio Editor"
        view.backgroundColor = .systemBackground
        configureNavigation()
        configureWebView()
        if UserDefaults.standard.object(forKey: Defaults.modelUpdatesWifiOnly) == nil { UserDefaults.standard.set(true, forKey: Defaults.modelUpdatesWifiOnly) }
        pathMonitor.pathUpdateHandler = { [weak self] path in self?.networkPath = path }
        pathMonitor.start(queue: pathQueue)
        _ = LocalStemEngine.shared.installBundledDefaultModelIfNeeded()
        modelRefreshTimer = Timer.scheduledTimer(withTimeInterval: 21600, repeats: true) { [weak self] _ in self?.refreshCoreMLModelsIfNeeded() }

        let custom = UserDefaults.standard.string(forKey: Defaults.serverURL)
        loadServer((custom?.isEmpty == false ? custom : nil) ?? Defaults.defaultServerURL)
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if !didOfferAppUpdate {
            didOfferAppUpdate = true
            checkForAppUpdate(manual: false)
        }
    }

    private func configureNavigation() {
        navigationItem.rightBarButtonItems = [
            UIBarButtonItem(title: "Options", style: .plain, target: self, action: #selector(showOptions)),
            UIBarButtonItem(title: "Server", style: .plain, target: self, action: #selector(changeServer)),
            UIBarButtonItem(barButtonSystemItem: .refresh, target: self, action: #selector(reloadPage))
        ]
    }

    private func configureWebView() {
        let controller = WKUserContentController()
        controller.add(self, name: "mtaMobile")
        let bridge = """
        window.MtaMobile = {
          _callbacks: {},
          _request: function(action, payload){
            return new Promise((resolve,reject)=>{
              const id='mta-'+Date.now()+'-'+Math.random().toString(16).slice(2);
              this._callbacks[id]={resolve:resolve,reject:reject};
              window.webkit.messageHandlers.mtaMobile.postMessage(Object.assign({action:action,requestId:id},payload||{}));
            });
          },
          _resolve: function(id, payload){ const cb=this._callbacks[id]; if(!cb)return; delete this._callbacks[id]; cb.resolve(payload); },
          _reject: function(id, message){ const cb=this._callbacks[id]; if(!cb)return; delete this._callbacks[id]; cb.reject(new Error(message||'Errore mobile')); },
          getPlatform: function(){ return 'ios'; },
          saveRemoteFile: function(url, filename, mime){ window.webkit.messageHandlers.mtaMobile.postMessage({action:'saveRemoteFile',url:url,filename:filename,mime:mime}); },
          shareRemoteFile: function(url, filename, mime){ window.webkit.messageHandlers.mtaMobile.postMessage({action:'shareRemoteFile',url:url,filename:filename,mime:mime}); },
          configureServer: function(){ window.webkit.messageHandlers.mtaMobile.postMessage({action:'configureServer'}); },
          setBusy: function(value){ window.webkit.messageHandlers.mtaMobile.postMessage({action:'setBusy',value:!!value}); },
          localStemCapabilities: function(){ return this._request('localStemCapabilities',{}); },
          startLocalStemSeparation: function(projectId,stemCount,modelId,keepOriginal){ return this._request('startLocalStemSeparation',{projectId:projectId,stemCount:stemCount,modelId:modelId||'',keepOriginal:!!keepOriginal}); },
          cancelLocalStemSeparation: function(){ window.webkit.messageHandlers.mtaMobile.postMessage({action:'cancelLocalStemSeparation'}); }
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
        webView.customUserAgent = "MTAEditorMobile/0.2.0-r159 iOS"
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

    @objc private func showOptions() {
        let alert = UIAlertController(title: "Options", message: "Update channel: \(NativeUpdateManager.shared.channel == "early" ? "Early release" : "Stable")", preferredStyle: .actionSheet)
        alert.addAction(UIAlertAction(title: "Stable · tags/releases", style: .default) { _ in
            NativeUpdateManager.shared.channel = "stable"
            self.checkForAppUpdate(manual: true)
        })
        alert.addAction(UIAlertAction(title: "Early release · include main", style: .default) { _ in
            NativeUpdateManager.shared.channel = "early"
            self.checkForAppUpdate(manual: true)
        })
        alert.addAction(UIAlertAction(title: "Demucs model updates…", style: .default) { _ in self.showDemucsUpdatePreferences() })
        alert.addAction(UIAlertAction(title: "Demucs models…", style: .default) { _ in self.showDemucsModelManager() })
        alert.addAction(UIAlertAction(title: "Check for updates", style: .default) { _ in self.checkForAppUpdate(manual: true) })
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        if let popover = alert.popoverPresentationController { popover.barButtonItem = navigationItem.rightBarButtonItems?.first }
        present(alert, animated: true)
    }

    private func showDemucsUpdatePreferences() {
        let italian = Locale.current.languageCode?.lowercased() == "it"
        let alert = UIAlertController(title: italian ? "Aggiornamento modelli Demucs" : "Demucs model updates", message: "\n\n", preferredStyle: .alert)
        let label = UILabel(); label.translatesAutoresizingMaskIntoConstraints = false
        label.text = italian ? "Update solo con Wi-Fi" : "Update on Wi-Fi only"
        label.font = .preferredFont(forTextStyle: .body)
        let toggle = UISwitch(); toggle.translatesAutoresizingMaskIntoConstraints = false
        toggle.isOn = UserDefaults.standard.object(forKey: Defaults.modelUpdatesWifiOnly) == nil ? true : UserDefaults.standard.bool(forKey: Defaults.modelUpdatesWifiOnly)
        alert.view.addSubview(label); alert.view.addSubview(toggle)
        NSLayoutConstraint.activate([
            label.leadingAnchor.constraint(equalTo: alert.view.leadingAnchor, constant: 24),
            label.topAnchor.constraint(equalTo: alert.view.topAnchor, constant: 74),
            toggle.trailingAnchor.constraint(equalTo: alert.view.trailingAnchor, constant: -24),
            toggle.centerYAnchor.constraint(equalTo: label.centerYAnchor)
        ])
        alert.addAction(UIAlertAction(title: italian ? "Salva" : "Save", style: .default) { _ in
            UserDefaults.standard.set(toggle.isOn, forKey: Defaults.modelUpdatesWifiOnly)
            if !toggle.isOn { self.refreshCoreMLModelsIfNeeded() }
        })
        alert.addAction(UIAlertAction(title: italian ? "Annulla" : "Cancel", style: .cancel))
        present(alert, animated: true)
    }

    private func checkForAppUpdate(manual: Bool) {
        NativeUpdateManager.shared.check { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let error):
                if manual { self.showMessage("Update check failed", error.localizedDescription) }
            case .success(let info):
                if !info.available {
                    if manual { self.showMessage("No updates", "Installed version \(info.currentVersion) is current on the \(info.channel) channel.") }
                    return
                }
                let prompt = UIAlertController(title: "Update available", message: "MTA Audio Editor \(info.latestVersion) is available on the \(info.channel) channel. iOS/iPadOS requires installation through the authorized distribution flow (TestFlight/App Store or managed distribution).", preferredStyle: .alert)
                prompt.addAction(UIAlertAction(title: "Later", style: .cancel))
                prompt.addAction(UIAlertAction(title: "Open update", style: .default) { _ in UIApplication.shared.open(info.releaseURL) })
                self.present(prompt, animated: true)
            }
        }
    }

    private func promptServerURL(required: Bool) {
        let alert = UIAlertController(
            title: "Impostazioni server",
            message: "Inserisci un URL personalizzato solo per usare un server diverso da quello predefinito. I server HTTP locali sono supportati dalla build mobile.",
            preferredStyle: .alert
        )
        alert.addTextField { field in
            field.placeholder = "URL server personalizzato (opzionale)"
            field.keyboardType = .URL
            field.autocapitalizationType = .none
            field.autocorrectionType = .no
            let custom = UserDefaults.standard.string(forKey: Defaults.serverURL)
            field.text = custom == Defaults.defaultServerURL ? nil : custom
        }
        alert.addAction(UIAlertAction(title: "Salva", style: .default) { [weak self, weak alert] _ in
            guard let self else { return }
            let raw = alert?.textFields?.first?.text?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            if raw.isEmpty {
                UserDefaults.standard.removeObject(forKey: Defaults.serverURL)
                self.loadServer(Defaults.defaultServerURL)
                return
            }
            guard let normalized = self.normalizeServerURL(raw) else {
                self.showMessage("URL non valido", "Inserisci un indirizzo http:// o https:// completo.")
                return
            }
            if normalized == Defaults.defaultServerURL {
                UserDefaults.standard.removeObject(forKey: Defaults.serverURL)
            } else {
                UserDefaults.standard.set(normalized, forKey: Defaults.serverURL)
            }
            self.loadServer(normalized)
        })
        alert.addAction(UIAlertAction(title: "Usa predefinito", style: .default) { [weak self] _ in
            UserDefaults.standard.removeObject(forKey: Defaults.serverURL)
            self?.loadServer(Defaults.defaultServerURL)
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

    private func mayDownloadModelUpdate() -> Bool {
        let wifiOnly = UserDefaults.standard.object(forKey: Defaults.modelUpdatesWifiOnly) == nil ? true : UserDefaults.standard.bool(forKey: Defaults.modelUpdatesWifiOnly)
        guard wifiOnly else { return networkPath?.status == .satisfied }
        return networkPath?.status == .satisfied && networkPath?.usesInterfaceType(.wifi) == true
    }

    private func loadServer(_ base: String) {
        guard let url = URL(string: base + "/") else { return }
        webView.load(URLRequest(url: url, cachePolicy: .reloadRevalidatingCacheData))
        bootstrapDefaultCoreMLModelIfNeeded(base: base)
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) { [weak self] in self?.refreshCoreMLModelsIfNeeded() }
    }

    private func bootstrapDefaultCoreMLModelIfNeeded(base: String) {
        if LocalStemEngine.shared.isModelInstalled(stemCount: 4) { return }
        guard mayDownloadModelUpdate() else { return }
        if LocalStemEngine.shared.installBundledDefaultModelIfNeeded() { return }
        guard let endpoint = URL(string: base + "/api/mobile/demucs-coreml/bootstrap") else { return }
        modelAuthorizedRequest(url: endpoint) { request in
            URLSession.shared.downloadTask(with: request) { location, response, _ in
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode), let location else { return }
                do {
                    let temp = FileManager.default.temporaryDirectory.appendingPathComponent("demucs-bootstrap-\(UUID().uuidString).mlmodel")
                    try? FileManager.default.removeItem(at: temp)
                    try FileManager.default.copyItem(at: location, to: temp)
                    let fingerprint = http.value(forHTTPHeaderField: "X-MTA-Model-SHA256") ?? ""
                    try LocalStemEngine.shared.installDownloadedModel(temp, stemCount: 4, fingerprint: fingerprint)
                    try? FileManager.default.removeItem(at: temp)
                } catch { }
            }.resume()
        }
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
        if let first = urls.first { lastPickedAudioURL = first }
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
        case "localStemCapabilities":
            replyLocalStemCapabilities(requestId: payload["requestId"] as? String)
        case "startLocalStemSeparation":
            guard let requestId = payload["requestId"] as? String,
                  let projectId = payload["projectId"] as? String else { return }
            let requested = payload["stemCount"] as? Int ?? 0
            let modelId = (payload["modelId"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            let keepOriginal = payload["keepOriginal"] as? Bool ?? true
            startLocalStemSeparation(requestId: requestId, projectId: projectId, requestedStemCount: requested, modelId: modelId, keepOriginal: keepOriginal)
        case "cancelLocalStemSeparation":
            LocalStemEngine.shared.cancel()
        default:
            break
        }
    }

    private func evaluateMobileCallback(_ javascript: String) {
        DispatchQueue.main.async { [weak self] in self?.webView.evaluateJavaScript(javascript) }
    }

    private func replyLocalStemCapabilities(requestId: String?) {
        guard let requestId else { return }
        let caps = LocalStemEngine.shared.capabilities()
        let installed = caps.installedStemCounts.map(String.init).joined(separator: ",")
        let canRun = caps.canRunLocally ? "true" : "false"
        let json = "{installedStemCounts:[\(installed)],recommendedStemCount:\(caps.recommendedStemCount),physicalMemoryBytes:\(caps.physicalMemoryBytes),canRunLocally:\(canRun)}"
        evaluateMobileCallback("window.MtaMobile._resolve('\(requestId)',\(json));")
    }

    private func startLocalStemSeparation(requestId: String, projectId: String, requestedStemCount: Int, modelId: String, keepOriginal: Bool) {
        guard !activeLocalStemTask else {
            evaluateMobileCallback("window.MtaMobile._reject('\(requestId)','È già in corso una separazione locale.');")
            return
        }
        guard let input = lastPickedAudioURL else {
            evaluateMobileCallback("window.MtaMobile._reject('\(requestId)','Seleziona prima un file audio dal dispositivo.');")
            return
        }
        let caps = LocalStemEngine.shared.capabilities()
        let selected = requestedStemCount == 0 ? caps.recommendedStemCount : requestedStemCount
        guard LocalStemEngine.supports(stemCount: selected) else {
            evaluateMobileCallback("window.MtaMobile._reject('\(requestId)','Numero stem locale non supportato.');")
            return
        }
        activeLocalStemTask = true
        UIApplication.shared.isIdleTimerDisabled = true
        let requestedModelId = modelId.isEmpty ? "demucs-\(selected)" : modelId
        ensureLocalModel(modelId: requestedModelId, stemCount: selected) { [weak self] modelResult in
            guard let self else { return }
            switch modelResult {
            case .failure(let error):
                self.activeLocalStemTask = false
                UIApplication.shared.isIdleTimerDisabled = false
                self.evaluateMobileCallback("window.MtaMobile._reject('\(requestId)','\(self.jsEscaped(error.localizedDescription))');")
            case .success:
                self.LocalStemStart(input: input, projectId: projectId, modelId: requestedModelId, stemCount: selected, keepOriginal: keepOriginal, requestId: requestId)
            }
        }
    }

    private func LocalStemStart(input: URL, projectId: String, modelId: String, stemCount: Int, keepOriginal: Bool, requestId: String) {
        let beginInference = { [weak self] in
            guard let self else { return }
            let scoped = input.startAccessingSecurityScopedResource()
            LocalStemEngine.shared.separate(inputURL: input, modelId: modelId, stemCount: stemCount, progress: { [weak self] pct, message in
                guard let self else { return }
                let safe = self.jsEscaped(message)
                self.evaluateMobileCallback("window.dispatchEvent(new CustomEvent('mtaLocalStemProgress',{detail:{progress:\(pct),message:'\(safe)'}}));")
            }) { [weak self] result in
                if scoped { input.stopAccessingSecurityScopedResource() }
                guard let self else { return }
                switch result {
                case .failure(let error):
                    self.activeLocalStemTask = false
                    UIApplication.shared.isIdleTimerDisabled = false
                    self.evaluateMobileCallback("window.MtaMobile._reject('\(requestId)','\(self.jsEscaped(error.localizedDescription))');")
                case .success(let files):
                    self.uploadStemFiles(files, projectId: projectId, index: 0) { uploadResult in
                        if let directory = files.first?.deletingLastPathComponent() { try? FileManager.default.removeItem(at: directory) }
                        self.activeLocalStemTask = false
                        UIApplication.shared.isIdleTimerDisabled = false
                        switch uploadResult {
                        case .failure(let error):
                            self.evaluateMobileCallback("window.MtaMobile._reject('\(requestId)','\(self.jsEscaped(error.localizedDescription))');")
                        case .success:
                            self.evaluateMobileCallback("window.MtaMobile._resolve('\(requestId)',{ok:true,stemCount:\(stemCount)});")
                        }
                    }
                }
            }
        }
        let afterOriginalPreserved = { [weak self] in
            guard let self else { return }
            if keepOriginal {
                self.uploadProjectTrack(fileURL: input, projectId: projectId, name: "Original Mix", type: "other") { result in
                    switch result {
                    case .success: beginInference()
                    case .failure(let error):
                        self.activeLocalStemTask = false
                        UIApplication.shared.isIdleTimerDisabled = false
                        self.evaluateMobileCallback("window.MtaMobile._reject('\(requestId)','\(self.jsEscaped(error.localizedDescription))');")
                    }
                }
            } else {
                beginInference()
            }
        }
        uploadProjectOriginal(fileURL: input, projectId: projectId) { [weak self] result in
            switch result {
            case .success: afterOriginalPreserved()
            case .failure(let error):
                self?.activeLocalStemTask = false
                UIApplication.shared.isIdleTimerDisabled = false
                self?.evaluateMobileCallback("window.MtaMobile._reject('\(requestId)','\(self?.jsEscaped(error.localizedDescription) ?? "Salvataggio originale fallito")');")
            }
        }
    }

    private func fetchCoreMLCatalog(_ completion: @escaping ([[String: Any]]) -> Void) {
        guard let base = webView.url else { completion([]); return }
        let endpoint = URL(string: "/api/models/catalog?platform=ios", relativeTo: base)!.absoluteURL
        authenticatedRequest(url: endpoint, method: "GET") { request in
            URLSession.shared.dataTask(with: request) { data, response, _ in
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode), let data,
                      let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let models = root["models"] as? [[String: Any]] else { completion([]); return }
                completion(models)
            }.resume()
        }
    }

    private func refreshCoreMLModelsIfNeeded() {
        guard mayDownloadModelUpdate(), !modelRefreshInFlight else { return }
        modelRefreshInFlight = true
        fetchCoreMLCatalog { [weak self] models in
            guard let self else { return }
            defer { DispatchQueue.main.async { self.modelRefreshInFlight = false } }
            let installedIds = Set(LocalStemEngine.shared.installedModelIds())
            let wanted = models.filter { item in
                let id = item["id"] as? String ?? ""
                return id == "demucs-4" || installedIds.contains(id)
            }
            let semaphore = DispatchSemaphore(value: 0)
            for item in wanted {
                guard let id = item["id"] as? String, let count = item["stem_count"] as? Int else { continue }
                let sha = item["sha256"] as? String ?? ""
                if LocalStemEngine.shared.isModelInstalled(modelId: id, stemCount: count), !sha.isEmpty,
                   LocalStemEngine.shared.modelFingerprint(modelId: id, stemCount: count) == sha { continue }
                self.downloadAndInstallCoreMLModel(modelId: id, stemCount: count, fingerprint: sha) { _ in semaphore.signal() }
                _ = semaphore.wait(timeout: .now() + 300)
            }
        }
    }

    private func downloadAndInstallCoreMLModel(modelId: String, stemCount: Int, fingerprint: String = "", completion: @escaping (Result<Void, Error>) -> Void) {
        guard let base = webView.url else { completion(.failure(LocalStemError.modelMissing(stemCount))); return }
        let safeId = modelId.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? modelId
        let endpoint = URL(string: "/api/models/coreml/\(safeId)", relativeTo: base)!.absoluteURL
        modelAuthorizedRequest(url: endpoint) { request in
            URLSession.shared.downloadTask(with: request) { location, response, error in
                if let error { DispatchQueue.main.async { completion(.failure(error)) }; return }
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode), let location else {
                    DispatchQueue.main.async { completion(.failure(LocalStemError.modelMissing(stemCount))) }; return
                }
                do {
                    let temp = FileManager.default.temporaryDirectory.appendingPathComponent("\(modelId)-\(UUID().uuidString).mlmodel")
                    try? FileManager.default.removeItem(at: temp)
                    try FileManager.default.copyItem(at: location, to: temp)
                    try LocalStemEngine.shared.installDownloadedModel(temp, modelId: modelId, stemCount: stemCount, fingerprint: fingerprint)
                    try? FileManager.default.removeItem(at: temp)
                    DispatchQueue.main.async { completion(.success(())) }
                } catch { DispatchQueue.main.async { completion(.failure(error)) } }
            }.resume()
        }
    }

    private func showDemucsModelManager() {
        fetchCoreMLCatalog { [weak self] models in
            guard let self else { return }
            DispatchQueue.main.async {
                let italian = Locale.current.languageCode?.lowercased() == "it"
                let alert = UIAlertController(title: "Demucs models", message: italian ? "Scarica, aggiorna o elimina i modelli locali. I modelli mancanti vengono scaricati automaticamente quando richiesti." : "Download, update, or delete local models. Missing models are downloaded automatically when requested.", preferredStyle: .actionSheet)
                for item in models.sorted(by: { ($0["stem_count"] as? Int ?? 0) < ($1["stem_count"] as? Int ?? 0) }) {
                    guard let id = item["id"] as? String, let count = item["stem_count"] as? Int else { continue }
                    let title = item["display_name"] as? String ?? id
                    let installed = LocalStemEngine.shared.isModelInstalled(modelId: id, stemCount: count)
                    alert.addAction(UIAlertAction(title: "\(title) · \(count) stem · \(installed ? "installed" : "available")", style: .default) { _ in
                        let sub = UIAlertController(title: title, message: nil, preferredStyle: .actionSheet)
                        sub.addAction(UIAlertAction(title: installed ? "Force update" : "Download", style: .default) { _ in self.downloadAndInstallCoreMLModel(modelId: id, stemCount: count) { _ in } })
                        if installed { sub.addAction(UIAlertAction(title: "Delete local model", style: .destructive) { _ in try? LocalStemEngine.shared.deleteInstalledModel(modelId: id, stemCount: count) }) }
                        sub.addAction(UIAlertAction(title: "Cancel", style: .cancel)); self.present(sub, animated: true)
                    })
                }
                alert.addAction(UIAlertAction(title: "Cancel", style: .cancel)); self.present(alert, animated: true)
            }
        }
    }

    private func ensureLocalModel(modelId: String, stemCount: Int, completion: @escaping (Result<Void, Error>) -> Void) {
        if LocalStemEngine.shared.isModelInstalled(modelId: modelId, stemCount: stemCount) { completion(.success(())); return }
        if stemCount == 4, modelId == "demucs-4", LocalStemEngine.shared.installBundledDefaultModelIfNeeded() { completion(.success(())); return }
        downloadAndInstallCoreMLModel(modelId: modelId, stemCount: stemCount, completion: completion)
    }

    private func uploadStemFiles(_ files: [URL], projectId: String, index: Int, completion: @escaping (Result<Void, Error>) -> Void) {
        if index >= files.count { completion(.success(())); return }
        let file = files[index]
        let raw = file.deletingPathExtension().lastPathComponent.lowercased()
        let stem = raw.replacingOccurrences(of: "^\\d+-", with: "", options: .regularExpression)
        let typeMap = ["drums":"drums","bass":"bass","guitar":"guitars","piano":"keyboards","vocals":"melody","accompaniment":"other","other":"other"]
        uploadProjectTrack(fileURL: file, projectId: projectId, name: stem.capitalized, type: typeMap[stem] ?? "other") { [weak self] result in
            switch result {
            case .failure: completion(result)
            case .success: self?.uploadStemFiles(files, projectId: projectId, index: index + 1, completion: completion)
            }
        }
    }

    private func uploadProjectOriginal(fileURL: URL, projectId: String, completion: @escaping (Result<Void, Error>) -> Void) {
        guard let base = webView.url else { completion(.failure(URLError(.badURL))); return }
        guard let url = URL(string: "/api/projects/\(projectId)/files/upload", relativeTo: base)?.absoluteURL else {
            completion(.failure(URLError(.badURL))); return
        }
        authenticatedRequest(url: url, method: "POST") { request in
            var request = request
            let boundary = "Boundary-\(UUID().uuidString)"
            request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
            request.setValue("1", forHTTPHeaderField: "X-MTA-Request")
            do {
                let data = try Data(contentsOf: fileURL, options: .mappedIfSafe)
                var body = Data()
                body.append("--\(boundary)\r\n".data(using: .utf8)!)
                body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileURL.lastPathComponent)\"\r\n".data(using: .utf8)!)
                body.append("Content-Type: application/octet-stream\r\n\r\n".data(using: .utf8)!)
                body.append(data)
                body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
                request.httpBody = body
            } catch { completion(.failure(error)); return }
            URLSession.shared.dataTask(with: request) { _, response, error in
                if let error { DispatchQueue.main.async { completion(.failure(error)) }; return }
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    DispatchQueue.main.async { completion(.failure(URLError(.badServerResponse))) }; return
                }
                DispatchQueue.main.async { completion(.success(())) }
            }.resume()
        }
    }

    private func uploadProjectTrack(fileURL: URL, projectId: String, name: String, type: String, completion: @escaping (Result<Void, Error>) -> Void) {
        guard let base = webView.url else { completion(.failure(URLError(.badURL))); return }
        var components = URLComponents(url: URL(string: "/api/projects/\(projectId)/tracks", relativeTo: base)!.absoluteURL, resolvingAgainstBaseURL: true)!
        components.queryItems = [URLQueryItem(name: "name", value: name), URLQueryItem(name: "type", value: type)]
        guard let url = components.url else { completion(.failure(URLError(.badURL))); return }
        authenticatedRequest(url: url, method: "POST") { request in
            var request = request
            let boundary = "Boundary-\(UUID().uuidString)"
            request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
            request.setValue("1", forHTTPHeaderField: "X-MTA-Request")
            do {
                let data = try Data(contentsOf: fileURL, options: .mappedIfSafe)
                var body = Data()
                body.append("--\(boundary)\r\n".data(using: .utf8)!)
                body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileURL.lastPathComponent)\"\r\n".data(using: .utf8)!)
                body.append("Content-Type: audio/wav\r\n\r\n".data(using: .utf8)!)
                body.append(data)
                body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)
                request.httpBody = body
            } catch { completion(.failure(error)); return }
            URLSession.shared.dataTask(with: request) { _, response, error in
                if let error { DispatchQueue.main.async { completion(.failure(error)) }; return }
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    DispatchQueue.main.async { completion(.failure(URLError(.badServerResponse))) }
                    return
                }
                DispatchQueue.main.async { completion(.success(())) }
            }.resume()
        }
    }

    private func modelAuthorizedRequest(url: URL, completion: @escaping (URLRequest) -> Void) {
        let expiry = UserDefaults.standard.double(forKey: Defaults.modelAccessTokenExpiresAt)
        if let token = UserDefaults.standard.string(forKey: Defaults.modelAccessToken), !token.isEmpty, expiry > Date().timeIntervalSince1970 + 300 {
            var request = URLRequest(url: url)
            request.httpMethod = "GET"
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            request.setValue(webView.customUserAgent, forHTTPHeaderField: "User-Agent")
            completion(request)
            return
        }
        guard let base = webView.url, let tokenURL = URL(string: "/api/models/token", relativeTo: base)?.absoluteURL else {
            authenticatedRequest(url: url, method: "GET", completion: completion)
            return
        }
        authenticatedRequest(url: tokenURL, method: "POST") { request in
            var request = request
            request.setValue("1", forHTTPHeaderField: "X-MTA-Request")
            request.setValue("ios", forHTTPHeaderField: "X-MTA-Client")
            URLSession.shared.dataTask(with: request) { data, response, _ in
                if let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode), let data,
                   let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let token = root["token"] as? String, !token.isEmpty {
                    UserDefaults.standard.set(token, forKey: Defaults.modelAccessToken)
                    if let expires = root["expires_at"] as? Double { UserDefaults.standard.set(expires, forKey: Defaults.modelAccessTokenExpiresAt) }
                    else if let expires = root["expires_at"] as? Int { UserDefaults.standard.set(Double(expires), forKey: Defaults.modelAccessTokenExpiresAt) }
                    var authorized = URLRequest(url: url)
                    authorized.httpMethod = "GET"
                    authorized.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
                    authorized.setValue(self.webView.customUserAgent, forHTTPHeaderField: "User-Agent")
                    completion(authorized)
                } else {
                    self.authenticatedRequest(url: url, method: "GET", completion: completion)
                }
            }.resume()
        }
    }

    private func authenticatedRequest(url: URL, method: String, completion: @escaping (URLRequest) -> Void) {
        webView.configuration.websiteDataStore.httpCookieStore.getAllCookies { [weak self] cookies in
            guard let self else { return }
            var request = URLRequest(url: url)
            request.httpMethod = method
            for (key, value) in HTTPCookie.requestHeaderFields(with: cookies) { request.setValue(value, forHTTPHeaderField: key) }
            request.setValue(self.webView.customUserAgent, forHTTPHeaderField: "User-Agent")
            completion(request)
        }
    }

    private func jsEscaped(_ value: String) -> String {
        value.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "'", with: "\\'").replacingOccurrences(of: "\n", with: "\\n")
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

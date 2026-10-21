# r210 — zoom dell'interfaccia nativa / Native interface zoom

## Italiano

**Desktop Windows, macOS e Linux:** il controllo **Zoom interfaccia** è ora
visibile sulla barra superiore, prima del transport temporale, anche se la
sezione Vista della barra laterale è chiusa. I pulsanti −/+ cambiano la scala
fra 50% e 200%; **100%** ripristina la scala. Scorciatoie: Ctrl/Cmd `+` (o `=`),
`-`, `0`, inclusi +/−/0 del tastierino numerico. È lo zoom di tutta
l'interfaccia, indipendente dallo zoom della timeline.

Il valore viene conservato per utente e riapplicato all'avvio. Il recupero dei
controlli non dipende più dal successo del ripristino iniziale: se il motore
non era ancora pronto, −/+, oppure **100%**, consentono di riprovare senza
lasciare il controllo nascosto. Quando la scala iniziale è 100%, il bridge
attende il primo frame dei controlli e sincronizza esplicitamente il motore,
disabilitando lo zoom WebView2 autonomo. La chiamata a freddo rimane evitata;
un CoreWebView2 non ancora pronto produce un errore recuperabile, non un falso
successo. Le scelte successive restano serializzate dopo questa inizializzazione.
Errori e risposte non valide non diventano una
preferenza salvata. La scoperta del motore gestisce anche wrapper nativi
annidati, oltre alla proprietà `webview` diretta, e non interroga i controlli
WinForms fuori dal loro thread GUI.

**iPhone/iPad:** aprire **Options → Zoom interfaccia…**; scegliere una
percentuale 50–200%, oppure **100% · Ripristina**. Lo zoom usa
`WKWebView.pageZoom`, conservato nelle preferenze dell'app e riapplicato dopo
la navigazione.

**Android:** aprire il menu dell'app **⋮ → Zoom interfaccia…**; scegliere la
percentuale 50–200%, oppure **100% · Ripristina**. È zoom di pagina tramite
`WebView.zoomBy`, non ingrandimento del solo testo. Vengono mantenuti viewport
responsive, densità dello schermo e limiti di scala. Una WebView che rifiuta o
limita la percentuale richiesta produce un avviso, senza salvare una
percentuale falsa. Ricaricare la pagina ripristina la preferenza. Le richieste
superate da una scelta più recente non possono sovrascriverla.

La scala comprende editor, mixer, menu e finestre renderizzati dentro la
pagina MTA. Barra del sistema operativo, finestre di scelta file e interfacce
native dei plugin conservano la propria scala di sistema. Le normali sessioni
browser mantengono i controlli di zoom del browser senza intercettazione delle
scorciatoie native.

## English

Desktop Windows/macOS/Linux now expose **Interface zoom** directly in the top
bar, outside collapsed sidebar groups. −/+, 100% reset and Ctrl/Cmd +/−/0
(including numeric keypad variants) control the whole editor at 50–200%,
independently of timeline zoom. The native data directory retains an atomic,
bounded `native-ui-zoom.json`. Invalid/corrupt preferences fall back to 100%.
Engine calls stay on the GUI thread. Nested backend wrappers are resolved
before applying WebView2 ZoomFactor, WKWebView pageZoom, WebKitGTK zoom level
or Qt zoom factor. A failed initial restore leaves recovery controls available.

On iOS/iPadOS choose **Options → Interface zoom…**; `WKWebView.pageZoom` is
persisted in UserDefaults. On Android use **⋮ → Interface zoom…**;
`WebView.zoomBy` applies whole-page scale, accounts for display density and
checks the effective value before saving. Both offer 50–200% and 100% reset.
System chrome, OS file pickers and independently hosted native plugin windows
retain their own scaling.

## Verification / Verifica

`validation/r210-native-zoom-completion.log`: **39 passed, 1 warning**. These
are persistence/input/dispatch/backend contracts and actual Node execution of
the desktop controls and injected Android viewport JavaScript. They cover
nested Windows wrappers inspected on the GUI thread, GTK one-shot dispatch,
initial-restore failure/recovery, deferred default-scale synchronization, cold
WebView2 readiness, queued user choices, keypad shortcuts, reset, invalid replies,
visible placement and mobile source API/persistence contracts. Python
compilation, Ruff and JavaScript syntax checks passed.

**This is not a Windows/macOS/Linux graphical smoke test or an Android/iOS
build/device test.** No Android SDK/Java compiler or Apple SDK/Swift compiler is
installed in this execution environment. Target acceptance must verify 50%,
100%, 125%, 200%, restart/reload persistence, dialogs, pointer/canvas alignment,
keyboard shortcuts and restored values on the actual installed web engines.
The new mobile API source contracts do not substitute for those builds.
Version remains **0.3.0-r210**.

Implementation references:

- https://pywebview.flowrl.com/api/#window-native
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.winforms.webview2.zoomfactor
- https://developer.apple.com/documentation/webkit/wkwebview/pagezoom
- https://developer.android.com/reference/android/webkit/WebView#zoomBy(float)

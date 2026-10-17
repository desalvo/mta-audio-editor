# r210 — native main-window interface zoom

In the native desktop application, open **View / Vista** in the sidebar to find
**Interface zoom / Zoom interfaccia**. Minus/plus select levels from 50% to 200%;
100% restores the default. Keyboard shortcuts: Ctrl/Cmd `+` (or `=`), `-`, `0`.
The preference is restored on the next application launch and is independent
of project files and timeline/audio zoom.

The implementation uses full-page native-engine APIs: WebView2 ZoomFactor,
WKWebView pageZoom, WebKitGTK zoom level, and Qt WebEngine/WebKit zoom factor.
It does not inject CSS transforms into the editor or rewrite track geometry.
Native calls are dispatched to the GUI thread. The result includes the entire
web-rendered editor, mixer, menus and utility dialogs; operating-system file
pickers/window chrome retain their OS scaling.

The preference is atomically stored in a dedicated `native-ui-zoom.json` under
the native data directory. Ordinary native-settings saves cannot overwrite it.
Malformed preferences fall back to 100%. A failed engine operation does not
persist a new value. Bounds are validated in the Python bridge as well as the
JavaScript control. Rapid key presses are serialized. Main-window resize
listeners are notified after successful zoom changes.

Controls start hidden and are enabled only after initialization with the native
bridge. Web/browser sessions keep their existing browser zoom behavior and
receive no keyboard interception from this feature.

Validation includes persistence, bad input/corrupt preferences, symlink handling,
engine factor calls, mocked Windows/macOS GUI dispatch, bridge behavior, and an
executable JavaScript DOM harness covering keyboard shortcuts, rapid changes,
limits, reset and web-session inactivity. Actual graphical Windows/macOS/GTK/Qt
sessions and pointer interaction still require an on-device native smoke test.
Revision remains 0.3.0-r210. The cumulative package also fixes Early desktop
build discovery; see EARLY_NATIVE_BUILD_UPDATES_R210.md.

Implementation references:

- https://pywebview.flowrl.com/api/#window-native
- https://learn.microsoft.com/en-us/dotnet/api/microsoft.web.webview2.winforms.webview2.zoomfactor
- https://developer.apple.com/documentation/webkit/wkwebview/pagezoom

The pinned pywebview 6.2.1 wheel was inspected for native object ownership and
GUI dispatch. Cocoa/GTK use the backend instance when `.native.webview` is not
exposed by that version.

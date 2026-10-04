package com.desalvo.mtaaudioeditor.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.view.ViewGroup;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.Toast;

import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int REQUEST_OPEN_FILE = 1001;
    private static final int REQUEST_SAVE_FILE = 1002;
    private static final String PREFS = "mta_mobile";
    private static final String PREF_SERVER_URL = "server_url";
    private static final String PREF_UPDATE_CHANNEL = "update_channel";
    private static final String PREF_DEMUCS_WIFI_ONLY = DemucsModelManager.WIFI_ONLY;
    private static final String DEFAULT_SERVER_URL = "https://mta-audio-editor.apps.desalvo.eu";

    private final ExecutorService ioExecutor = Executors.newSingleThreadExecutor();
    private WebView webView;
    private ValueCallback<Uri[]> uploadCallback;
    private PendingDownload pendingDownload;

    private static final class PendingDownload {
        final String url;
        final String filename;
        final String mime;

        PendingDownload(String url, String filename, String mime) {
            this.url = url;
            this.filename = filename;
            this.mime = mime;
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setTitle("MTA Audio Editor");

        webView = new WebView(this);
        webView.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(webView);

        configureWebView();
        String configured = getPreferencesStore().getString(PREF_SERVER_URL, "");
        loadServer(configured == null || configured.trim().isEmpty() ? DEFAULT_SERVER_URL : configured);
        webView.postDelayed(() -> checkForAppUpdate(false), 1200);
        if (!getPreferencesStore().contains(PREF_DEMUCS_WIFI_ONLY)) getPreferencesStore().edit().putBoolean(PREF_DEMUCS_WIFI_ONLY, true).apply();
        webView.postDelayed(this::refreshDemucsModels, 2500);
    }

    private SharedPreferences getPreferencesStore() {
        return getSharedPreferences(PREFS, MODE_PRIVATE);
    }

    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setUserAgentString(settings.getUserAgentString() + " MTAEditorMobile/0.2.0-100 Android");

        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);
        webView.addJavascriptInterface(new MobileBridge(), "MtaMobile");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, android.webkit.WebResourceRequest request) {
                Uri target = request.getUrl();
                Uri current = Uri.parse(view.getUrl() == null ? "" : view.getUrl());
                if (("http".equals(target.getScheme()) || "https".equals(target.getScheme()))
                        && current.getHost() != null
                        && current.getHost().equalsIgnoreCase(target.getHost())) {
                    return false;
                }
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, target));
                } catch (ActivityNotFoundException ignored) {
                    Toast.makeText(MainActivity.this, "Nessuna app disponibile per aprire il link", Toast.LENGTH_LONG).show();
                }
                return true;
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {
                if (uploadCallback != null) {
                    uploadCallback.onReceiveValue(null);
                }
                uploadCallback = filePathCallback;
                Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                intent.addCategory(Intent.CATEGORY_OPENABLE);
                intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, fileChooserParams.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);
                String[] accepted = fileChooserParams.getAcceptTypes();
                if (accepted != null && accepted.length > 0 && !accepted[0].trim().isEmpty()) {
                    intent.putExtra(Intent.EXTRA_MIME_TYPES, accepted);
                }
                startActivityForResult(intent, REQUEST_OPEN_FILE);
                return true;
            }
        });

        webView.setDownloadListener((url, userAgent, contentDisposition, mimetype, contentLength) -> {
            String filename = android.webkit.URLUtil.guessFileName(url, contentDisposition, mimetype);
            beginSaveRemoteFile(url, filename, mimetype == null ? "application/octet-stream" : mimetype);
        });
    }

    private void promptServerUrl(boolean required) {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setHint("URL server personalizzato (opzionale)");
        String custom = getPreferencesStore().getString(PREF_SERVER_URL, "");
        input.setText(custom == null || DEFAULT_SERVER_URL.equals(custom) ? "" : custom);
        int pad = (int) (20 * getResources().getDisplayMetrics().density);
        input.setPadding(pad, pad / 2, pad, pad / 2);

        AlertDialog.Builder builder = new AlertDialog.Builder(this)
                .setTitle("Impostazioni server")
                .setMessage("Inserisci un URL personalizzato solo se vuoi usare un server diverso da quello predefinito. Per server LAN è supportato anche HTTP.")
                .setView(input)
                .setPositiveButton("Salva", null)
                .setNeutralButton("Usa predefinito", (d, which) -> {
                    getPreferencesStore().edit().remove(PREF_SERVER_URL).apply();
                    loadServer(DEFAULT_SERVER_URL);
                });
        if (!required) {
            builder.setNegativeButton("Annulla", null);
        }
        AlertDialog dialog = builder.create();
        dialog.setOnShowListener(unused -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String raw = input.getText().toString().trim();
            if (raw.isEmpty()) {
                getPreferencesStore().edit().remove(PREF_SERVER_URL).apply();
                dialog.dismiss();
                loadServer(DEFAULT_SERVER_URL);
                return;
            }
            String normalized = normalizeServerUrl(raw);
            if (normalized == null) {
                input.setError("Inserisci un URL http:// o https:// valido");
                return;
            }
            if (DEFAULT_SERVER_URL.equals(normalized)) {
                getPreferencesStore().edit().remove(PREF_SERVER_URL).apply();
            } else {
                getPreferencesStore().edit().putString(PREF_SERVER_URL, normalized).apply();
            }
            dialog.dismiss();
            loadServer(normalized);
        }));
        dialog.setCancelable(!required);
        dialog.show();
    }

    private String normalizeServerUrl(String raw) {
        String value = raw == null ? "" : raw.trim();
        if (!(value.startsWith("https://") || value.startsWith("http://"))) {
            return null;
        }
        while (value.endsWith("/")) {
            value = value.substring(0, value.length() - 1);
        }
        try {
            Uri parsed = Uri.parse(value);
            return parsed.getHost() == null ? null : value;
        } catch (Exception ignored) {
            return null;
        }
    }

    private void loadServer(String baseUrl) {
        webView.loadUrl(baseUrl + "/");
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.add("Impostazioni server").setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        menu.add("Canale aggiornamenti").setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        menu.add("Controlla aggiornamenti").setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        menu.add("Update modelli solo con Wi-Fi").setCheckable(true).setChecked(getPreferencesStore().getBoolean(PREF_DEMUCS_WIFI_ONLY,true)).setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        menu.add("Ricarica").setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        String title = String.valueOf(item.getTitle());
        if ("Impostazioni server".equals(title)) {
            promptServerUrl(false);
            return true;
        }
        if ("Canale aggiornamenti".equals(title)) {
            promptUpdateChannel();
            return true;
        }
        if ("Update modelli solo con Wi-Fi".equals(title)) {
            boolean value=!getPreferencesStore().getBoolean(PREF_DEMUCS_WIFI_ONLY,true); getPreferencesStore().edit().putBoolean(PREF_DEMUCS_WIFI_ONLY,value).apply(); item.setChecked(value); if(!value)refreshDemucsModels(); return true;
        }
        if ("Controlla aggiornamenti".equals(title)) {
            checkForAppUpdate(true);
            return true;
        }
        if ("Ricarica".equals(title)) {
            webView.reload();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }


    private void refreshDemucsModels() {
        String configured=getPreferencesStore().getString(PREF_SERVER_URL,""); String base=(configured==null||configured.trim().isEmpty())?DEFAULT_SERVER_URL:configured;
        DemucsModelManager.bootstrap(this,getPreferencesStore(),ioExecutor,base);
        DemucsModelManager.refresh(this,getPreferencesStore(),ioExecutor,base);
        webView.postDelayed(this::refreshDemucsModels,DemucsModelManager.PERIOD_MS);
    }

    private String updateChannel() {
        return "early".equals(getPreferencesStore().getString(PREF_UPDATE_CHANNEL, "stable")) ? "early" : "stable";
    }

    private void promptUpdateChannel() {
        String[] values = {"Stable · solo tag/release GitHub", "Early release · include i package di main"};
        int checked = "early".equals(updateChannel()) ? 1 : 0;
        new AlertDialog.Builder(this)
                .setTitle("Canale aggiornamenti")
                .setSingleChoiceItems(values, checked, (dialog, which) -> {
                    getPreferencesStore().edit().putString(PREF_UPDATE_CHANNEL, which == 1 ? "early" : "stable").apply();
                    dialog.dismiss();
                    checkForAppUpdate(true);
                })
                .setNegativeButton("Annulla", null)
                .show();
    }

    private void checkForAppUpdate(boolean manual) {
        GitHubUpdateManager.check(ioExecutor, BuildConfig.VERSION_NAME, updateChannel(), (info, error) -> runOnUiThread(() -> {
            if (error != null) {
                if (manual) Toast.makeText(this, "Controllo aggiornamenti fallito: " + error.getMessage(), Toast.LENGTH_LONG).show();
                return;
            }
            if (info == null || !info.available) {
                if (manual) Toast.makeText(this, "MTA Audio Editor è aggiornato (" + BuildConfig.VERSION_NAME + ")", Toast.LENGTH_LONG).show();
                return;
            }
            String channelLabel = "early".equals(info.channel) ? "Early release" : "Stable";
            new AlertDialog.Builder(this)
                    .setTitle("Aggiornamento disponibile")
                    .setMessage("MTA Audio Editor " + info.latestVersion + " è disponibile sul canale " + channelLabel + ".")
                    .setNegativeButton("Più tardi", null)
                    .setPositiveButton("Aggiorna", (d, which) -> {
                        if (info.assetUrl != null && !info.assetUrl.isEmpty()) {
                            Toast.makeText(this, "Download aggiornamento in corso…", Toast.LENGTH_SHORT).show();
                            GitHubUpdateManager.downloadAndInstall(this, ioExecutor, info.assetUrl, info.assetName, installError -> runOnUiThread(() -> {
                                if (installError != null) {
                                    Toast.makeText(this, "Installazione non avviata: " + installError.getMessage(), Toast.LENGTH_LONG).show();
                                    try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(info.releaseUrl))); } catch (Exception ignored) {}
                                }
                            }));
                        } else {
                            try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(info.releaseUrl))); } catch (Exception ignored) {}
                        }
                    })
                    .show();
        }));
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_OPEN_FILE) {
            if (uploadCallback == null) return;
            Uri[] result = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int count = data.getClipData().getItemCount();
                    result = new Uri[count];
                    for (int i = 0; i < count; i++) result[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) {
                    result = new Uri[]{data.getData()};
                }
            }
            uploadCallback.onReceiveValue(result);
            uploadCallback = null;
            return;
        }
        if (requestCode == REQUEST_SAVE_FILE) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null && pendingDownload != null) {
                downloadToUri(pendingDownload, data.getData());
            }
            pendingDownload = null;
        }
    }

    private void beginSaveRemoteFile(String url, String filename, String mime) {
        runOnUiThread(() -> {
            pendingDownload = new PendingDownload(url, filename, mime);
            Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType(mime == null || mime.trim().isEmpty() ? "application/octet-stream" : mime);
            intent.putExtra(Intent.EXTRA_TITLE, filename == null || filename.trim().isEmpty() ? "export.bin" : filename);
            startActivityForResult(intent, REQUEST_SAVE_FILE);
        });
    }

    private void downloadToUri(PendingDownload download, Uri destination) {
        Toast.makeText(this, "Download in corso…", Toast.LENGTH_SHORT).show();
        final String baseUrl = webView.getUrl();
        final String userAgent = webView.getSettings().getUserAgentString();
        final String remoteUrl;
        try {
            remoteUrl = new URL(new URL(baseUrl), download.url).toString();
        } catch (Exception exc) {
            Toast.makeText(this, "URL download non valido", Toast.LENGTH_LONG).show();
            return;
        }
        final String cookies = CookieManager.getInstance().getCookie(remoteUrl);
        ioExecutor.submit(() -> {
            HttpURLConnection connection = null;
            try {
                URL remote = new URL(remoteUrl);
                connection = (HttpURLConnection) remote.openConnection();
                connection.setConnectTimeout(20000);
                connection.setReadTimeout(120000);
                if (cookies != null && !cookies.trim().isEmpty()) connection.setRequestProperty("Cookie", cookies);
                connection.setRequestProperty("User-Agent", userAgent);
                connection.connect();
                if (connection.getResponseCode() < 200 || connection.getResponseCode() >= 300) {
                    throw new IllegalStateException("HTTP " + connection.getResponseCode());
                }
                try (InputStream in = connection.getInputStream();
                     OutputStream out = getContentResolver().openOutputStream(destination, "w")) {
                    if (out == null) throw new IllegalStateException("Impossibile aprire il file di destinazione");
                    byte[] buffer = new byte[128 * 1024];
                    int read;
                    while ((read = in.read(buffer)) >= 0) out.write(buffer, 0, read);
                    out.flush();
                }
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "File salvato", Toast.LENGTH_LONG).show());
            } catch (Exception exc) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Salvataggio fallito: " + exc.getMessage(), Toast.LENGTH_LONG).show());
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void shareRemoteFile(String url, String filename, String mime) {
        Toast.makeText(this, "Preparazione condivisione…", Toast.LENGTH_SHORT).show();
        final String baseUrl = webView.getUrl();
        final String userAgent = webView.getSettings().getUserAgentString();
        final String remoteUrl;
        try {
            remoteUrl = new URL(new URL(baseUrl), url).toString();
        } catch (Exception exc) {
            Toast.makeText(this, "URL condivisione non valido", Toast.LENGTH_LONG).show();
            return;
        }
        final String cookies = CookieManager.getInstance().getCookie(remoteUrl);
        ioExecutor.submit(() -> {
            HttpURLConnection connection = null;
            try {
                URL remote = new URL(remoteUrl);
                connection = (HttpURLConnection) remote.openConnection();
                connection.setConnectTimeout(20000);
                connection.setReadTimeout(120000);
                if (cookies != null && !cookies.trim().isEmpty()) connection.setRequestProperty("Cookie", cookies);
                connection.setRequestProperty("User-Agent", userAgent);
                connection.connect();
                if (connection.getResponseCode() < 200 || connection.getResponseCode() >= 300) {
                    throw new IllegalStateException("HTTP " + connection.getResponseCode());
                }
                File dir = new File(getCacheDir(), "exports");
                if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("Impossibile creare cache export");
                File target = new File(dir, filename.replace('/', '_'));
                try (InputStream in = connection.getInputStream(); FileOutputStream out = new FileOutputStream(target)) {
                    byte[] buffer = new byte[128 * 1024];
                    int read;
                    while ((read = in.read(buffer)) >= 0) out.write(buffer, 0, read);
                }
                Uri contentUri = FileProvider.getUriForFile(this, getPackageName() + ".files", target);
                runOnUiThread(() -> {
                    Intent send = new Intent(Intent.ACTION_SEND);
                    send.setType(mime == null || mime.trim().isEmpty() ? "application/octet-stream" : mime);
                    send.putExtra(Intent.EXTRA_STREAM, contentUri);
                    send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(Intent.createChooser(send, "Condividi export"));
                });
            } catch (Exception exc) {
                runOnUiThread(() -> Toast.makeText(MainActivity.this, "Condivisione fallita: " + exc.getMessage(), Toast.LENGTH_LONG).show());
            } finally {
                if (connection != null) connection.disconnect();
            }
        });
    }

    private void setBusy(boolean busy) {
        runOnUiThread(() -> {
            if (busy) getWindow().addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
            else getWindow().clearFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        });
    }

    private final class MobileBridge {
        @JavascriptInterface
        public String getPlatform() {
            return "android";
        }

        @JavascriptInterface
        public void saveRemoteFile(String url, String filename, String mime) {
            beginSaveRemoteFile(url, filename, mime);
        }

        @JavascriptInterface
        public void shareRemoteFile(String url, String filename, String mime) {
            MainActivity.this.shareRemoteFile(url, filename, mime);
        }

        @JavascriptInterface
        public void setBusy(boolean busy) {
            MainActivity.this.setBusy(busy);
        }

        @JavascriptInterface
        public void configureServer() {
            runOnUiThread(() -> promptServerUrl(false));
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        ioExecutor.shutdownNow();
        super.onDestroy();
    }
}

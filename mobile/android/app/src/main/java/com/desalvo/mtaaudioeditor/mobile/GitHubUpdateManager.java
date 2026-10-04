package com.desalvo.mtaaudioeditor.mobile;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;

import androidx.core.content.FileProvider;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;

final class GitHubUpdateManager {
    static final String REPOSITORY = "desalvo/mta-audio-editor";

    static final class UpdateInfo {
        final String channel, currentVersion, latestVersion, releaseUrl, assetUrl, assetName;
        final boolean available;
        UpdateInfo(String channel, String currentVersion, String latestVersion, boolean available, String releaseUrl, String assetUrl, String assetName) {
            this.channel = channel; this.currentVersion = currentVersion; this.latestVersion = latestVersion;
            this.available = available; this.releaseUrl = releaseUrl; this.assetUrl = assetUrl; this.assetName = assetName;
        }
    }

    interface Callback { void done(UpdateInfo info, Exception error); }
    interface InstallCallback { void done(Exception error); }

    static void check(ExecutorService executor, String currentVersion, String channel, Callback callback) {
        executor.submit(() -> {
            HttpURLConnection c = null;
            try {
                String suffix = "early".equals(channel) ? "releases/tags/early-main" : "releases/latest";
                URL url = new URL("https://api.github.com/repos/" + REPOSITORY + "/" + suffix);
                c = (HttpURLConnection) url.openConnection();
                c.setConnectTimeout(12000); c.setReadTimeout(12000);
                c.setRequestProperty("Accept", "application/vnd.github+json");
                c.setRequestProperty("User-Agent", "MTA-Audio-Editor-Android-Updater");
                JSONObject root;
                try (InputStream in = c.getInputStream()) { root = new JSONObject(new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8)); }
                String latest = root.optString("name", "").replace("MTA Audio Editor ", "").trim();
                if (latest.isEmpty()) latest = root.optString("tag_name", "");
                String release = root.optString("html_url", "https://github.com/" + REPOSITORY + "/releases");
                String assetUrl = "", assetName = "";
                JSONArray assets = root.optJSONArray("assets");
                if (assets != null) {
                    for (int i = 0; i < assets.length(); i++) {
                        JSONObject asset = assets.getJSONObject(i);
                        String name = asset.optString("name", "");
                        String low = name.toLowerCase();
                        if (low.endsWith(".apk") && low.contains("android") && (low.contains("release") || assetName.isEmpty())) {
                            assetName = name;
                            assetUrl = asset.optString("browser_download_url", "");
                            if (low.contains("release")) break;
                        }
                    }
                }
                callback.done(new UpdateInfo(channel, currentVersion, latest, isNewer(latest, currentVersion), release, assetUrl, assetName), null);
            } catch (Exception exc) { callback.done(null, exc); }
            finally { if (c != null) c.disconnect(); }
        });
    }

    static boolean isNewer(String remote, String local) {
        List<Integer> a = versionKey(remote), b = versionKey(local);
        int count = Math.max(a.size(), b.size());
        for (int i = 0; i < count; i++) {
            int av = i < a.size() ? a.get(i) : 0, bv = i < b.size() ? b.get(i) : 0;
            if (av != bv) return av > bv;
        }
        return false;
    }

    private static List<Integer> versionKey(String value) {
        List<Integer> out = new ArrayList<>();
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\d+").matcher(value == null ? "" : value);
        while (m.find()) out.add(Integer.parseInt(m.group()));
        return out;
    }

    static void downloadAndInstall(Context context, ExecutorService executor, String url, String name, InstallCallback callback) {
        executor.submit(() -> {
            HttpURLConnection c = null;
            try {
                File dir = new File(context.getCacheDir(), "exports");
                if (!dir.exists()) dir.mkdirs();
                File file = new File(dir, name == null || name.isBlank() ? "MTA-Audio-Editor-update.apk" : new File(name).getName());
                c = (HttpURLConnection) new URL(url).openConnection();
                c.setConnectTimeout(20000); c.setReadTimeout(180000);
                c.setRequestProperty("User-Agent", "MTA-Audio-Editor-Android-Updater");
                try (InputStream in = c.getInputStream(); FileOutputStream out = new FileOutputStream(file)) { in.transferTo(out); }
                Uri uri = FileProvider.getUriForFile(context, context.getPackageName() + ".files", file);
                Intent intent = new Intent(Intent.ACTION_VIEW);
                intent.setDataAndType(uri, "application/vnd.android.package-archive");
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
                context.startActivity(intent);
                callback.done(null);
            } catch (Exception exc) { callback.done(exc); }
            finally { if (c != null) c.disconnect(); }
        });
    }
}

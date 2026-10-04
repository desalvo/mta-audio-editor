package com.desalvo.mtaaudioeditor.mobile;

import android.content.*;
import android.net.*;
import android.webkit.CookieManager;
import java.io.*;
import java.net.*;
import java.security.*;
import java.util.*;
import java.util.concurrent.ExecutorService;
import org.json.*;

final class DemucsModelManager {
    // Legacy baseline filename retained for build/test compatibility: demucs-4.onnx
    static final String WIFI_ONLY="demucs_wifi_only";
    static final String MODEL_TOKEN="demucs_model_access_token";
    static final long PERIOD_MS=6L*60*60*1000;

    static boolean networkAvailable(Context c){
        ConnectivityManager cm=(ConnectivityManager)c.getSystemService(Context.CONNECTIVITY_SERVICE);
        Network n=cm.getActiveNetwork(); if(n==null)return false;
        NetworkCapabilities cap=cm.getNetworkCapabilities(n);
        return cap!=null&&cap.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
    }
    static boolean wifiAllowed(Context c,SharedPreferences p){
        boolean only=p.getBoolean(WIFI_ONLY,true); if(!networkAvailable(c))return false;
        ConnectivityManager cm=(ConnectivityManager)c.getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkCapabilities cap=cm.getNetworkCapabilities(cm.getActiveNetwork());
        return cap!=null&&(!only||cap.hasTransport(NetworkCapabilities.TRANSPORT_WIFI));
    }
    static File dir(Context c){File d=new File(c.getFilesDir(),"demucs-models");d.mkdirs();return d;}
    static String safeId(String value){String v=value==null?"":value.replaceAll("[^A-Za-z0-9._-]+","-").replaceAll("^[.-]+|[.-]+$","");if(v.isEmpty())throw new IllegalArgumentException("invalid model id");return v;}
    static File target(Context c,String modelId){return new File(dir(c),safeId(modelId)+".onnx");}
    static File metadata(Context c,String modelId){return new File(dir(c),safeId(modelId)+".json");}

    static SharedPreferences prefs(Context c){return c.getSharedPreferences("mta_mobile",Context.MODE_PRIVATE);}
    static String ensureModelToken(Context c,String base)throws Exception{
        String existing=prefs(c).getString(MODEL_TOKEN,"");if(existing!=null&&!existing.isEmpty())return existing;
        URL u=new URL(base+"/api/models/token");HttpURLConnection x=(HttpURLConnection)u.openConnection();x.setRequestMethod("POST");x.setRequestProperty("X-MTA-Request","1");x.setRequestProperty("X-MTA-Client","android");
        String ck=CookieManager.getInstance().getCookie(u.toString());if(ck!=null)x.setRequestProperty("Cookie",ck);
        if(x.getResponseCode()/100!=2)throw new IOException("model token HTTP "+x.getResponseCode());
        JSONObject root=new JSONObject(new String(x.getInputStream().readAllBytes()));String token=root.optString("token","");if(token.isEmpty())throw new IOException("missing model token");prefs(c).edit().putString(MODEL_TOKEN,token).apply();return token;
    }

    static JSONObject fetchCatalog(String base)throws Exception{
        URL u=new URL(base+"/api/models/catalog?platform=android");
        HttpURLConnection x=(HttpURLConnection)u.openConnection();
        String ck=CookieManager.getInstance().getCookie(u.toString());if(ck!=null)x.setRequestProperty("Cookie",ck);
        if(x.getResponseCode()/100!=2)throw new IOException("HTTP "+x.getResponseCode());
        return new JSONObject(new String(x.getInputStream().readAllBytes()));
    }
    static JSONArray models(JSONObject root){JSONArray a=root.optJSONArray("models");return a==null?new JSONArray():a;}
    static JSONObject find(JSONObject root,String modelId){JSONArray a=models(root);for(int i=0;i<a.length();i++){JSONObject m=a.optJSONObject(i);if(m!=null&&modelId.equals(m.optString("id")))return m;}return null;}

    static boolean installBundledDefault(Context c,File out){
        if(out.isFile())return true;
        try(InputStream in=c.getAssets().open("demucs-default-4.onnx");OutputStream os=new FileOutputStream(out)){in.transferTo(os);return true;}catch(Exception ignored){return false;}
    }
    static void bootstrap(Context c,SharedPreferences prefs,ExecutorService io,String base){
        File legacy=target(c,"demucs-4");if(legacy.isFile()||installBundledDefault(c,legacy)||!networkAvailable(c))return;
        io.submit(()->{try{JSONObject cat=fetchCatalog(base),m=find(cat,"demucs-4");if(m!=null)downloadItem(c,base,m,true);}catch(Exception ignored){}});
    }

    static void refresh(Context c,SharedPreferences prefs,ExecutorService io,String base){
        if(!wifiAllowed(c,prefs))return;
        io.submit(()->{try{
            JSONObject root=fetchCatalog(base);JSONArray a=models(root);
            Set<String> installed=new HashSet<>();for(JSONObject x:installed(c))installed.add(x.optString("id"));installed.add("demucs-4");
            for(int i=0;i<a.length();i++){
                JSONObject m=a.optJSONObject(i);if(m==null)continue;String id=m.optString("id");if(!installed.contains(id))continue;
                File f=target(c,id);String sha=m.optString("sha256");if(f.isFile()&&!sha.isEmpty()&&sha.equalsIgnoreCase(hash(f)))continue;
                downloadItem(c,base,m,true);
            }
            prefs.edit().putLong("demucs_last_check",System.currentTimeMillis()).apply();
        }catch(Exception ignored){}});
    }

    static void ensureRequested(Context c,ExecutorService io,String base,String modelId,int stemCount,Callback cb){
        File f=target(c,modelId);if(f.isFile()){cb.done(null);return;}
        if(!networkAvailable(c)){cb.done(new IOException("network unavailable"));return;}
        io.submit(()->{try{JSONObject root=fetchCatalog(base),m=find(root,modelId);if(m==null)throw new IOException("model not available");if(stemCount>0&&m.optInt("stem_count",stemCount)!=stemCount)throw new IOException("model/stem mismatch");downloadItem(c,base,m,true);cb.done(null);}catch(Exception e){cb.done(e);}});
    }
    static void forceUpdate(Context c,ExecutorService io,String base,String modelId,Callback cb){
        io.submit(()->{try{JSONObject root=fetchCatalog(base),m=find(root,modelId);if(m==null)throw new IOException("model not available");downloadItem(c,base,m,true);cb.done(null);}catch(Exception e){cb.done(e);}});
    }
    static boolean deleteLocal(Context c,String modelId){
        boolean ok=true;File f=target(c,modelId),meta=metadata(c,modelId);if(f.exists())ok=f.delete();if(meta.exists())ok=meta.delete()&&ok;return ok;
    }
    static List<JSONObject> installed(Context c){
        List<JSONObject> a=new ArrayList<>();File[]fs=dir(c).listFiles((d,n)->n.endsWith(".onnx"));if(fs!=null)for(File f:fs){JSONObject o=new JSONObject();try{o.put("id",f.getName().substring(0,f.getName().length()-5));o.put("size",f.length());o.put("sha256",hash(f));a.add(o);}catch(Exception ignored){}}return a;
    }

    static void downloadItem(Context c,String base,JSONObject m,boolean verify)throws Exception{
        String id=safeId(m.getString("id"));String relative=m.optString("download_url","/api/models/onnx/"+id);String expected=m.optString("sha256","");
        File f=target(c,id);download(c,new URL(new URL(base),relative).toString(),f,verify?expected:"");
        JSONObject meta=new JSONObject();meta.put("id",id);meta.put("display_name",m.optString("display_name",id));meta.put("stem_count",m.optInt("stem_count",0));meta.put("version",m.optString("version",""));meta.put("sha256",hash(f));try(FileOutputStream os=new FileOutputStream(metadata(c,id))){os.write(meta.toString(2).getBytes());}
    }
    static void download(Context c,String url,File target,String expected)throws Exception{
        HttpURLConnection x=(HttpURLConnection)new URL(url).openConnection();String ck=CookieManager.getInstance().getCookie(url);if(ck!=null)x.setRequestProperty("Cookie",ck);
        try{x.setRequestProperty("Authorization","Bearer "+ensureModelToken(c,new URL(url).getProtocol()+"://"+new URL(url).getAuthority()));}catch(Exception ignored){}
        if(x.getResponseCode()/100!=2)throw new IOException("HTTP "+x.getResponseCode());File tmp=new File(target.getParentFile(),target.getName()+".tmp");
        try(InputStream in=x.getInputStream();OutputStream out=new FileOutputStream(tmp)){in.transferTo(out);}if(!expected.isEmpty()&&!expected.equalsIgnoreCase(hash(tmp))){tmp.delete();throw new IOException("SHA-256 mismatch");}
        if(target.exists())target.delete();if(!tmp.renameTo(target))throw new IOException("Cannot install model");
    }
    static String hash(File f)throws Exception{MessageDigest d=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(f)){byte[]b=new byte[131072];for(int n;(n=in.read(b))>0;)d.update(b,0,n);}StringBuilder s=new StringBuilder();for(byte b:d.digest())s.append(String.format("%02x",b));return s.toString();}
    interface Callback{void done(Exception error);}
}

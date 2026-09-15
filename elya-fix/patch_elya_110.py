from pathlib import Path
import re

r=Path('.')

# ---------------- Version ----------------
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+10\b','versionCode 11',s,count=1)
s=re.sub(r"versionName\s+'1\.0\.9'","versionName '1.1.0'",s,count=1)
p.write_text(s,encoding='utf-8')

# ---------------- Native scanner 1.1.0 ----------------
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')

# Imports for public-folder fallback scan.
s=s.replace('import android.media.MediaMetadataRetriever;','import android.media.MediaMetadataRetriever;\nimport android.os.Environment;',1)
s=s.replace('import java.io.FilterInputStream;','import java.io.FilterInputStream;\nimport java.io.File;',1)

s=s.replace('// ELYA_NATIVE_CORE_109','// ELYA_NATIVE_CORE_109\n    // ELYA_NATIVE_CORE_110',1)
s=s.replace('return "elya-bridge-1.0.9";','return "elya-bridge-1.1.0";',1)
s=s.replace('o.put("core", "1.0.9");','o.put("core", "1.1.0");',1)

# Native bridge explicit deep scan action.
anchor='''        @JavascriptInterface public void scanAllDeviceMusic() {\n            main.post(() -> ensureAudioPermissionAndScan());\n        }'''
replacement='''        @JavascriptInterface public void scanAllDeviceMusic() {\n            main.post(() -> ensureAudioPermissionAndScan());\n        }\n\n        @JavascriptInterface public void deepScanDeviceMusic() {\n            main.post(() -> ensureAudioPermissionAndScan());\n        }'''
if anchor not in s:
    raise SystemExit('scan bridge anchor missing')
s=s.replace(anchor,replacement,1)

# MediaStore.Audio entries now carry a scan fingerprint so filesystem fallback can avoid duplicates.
a='''                    o.put("duration", durationMs > 0 ? durationMs / 1000.0 : 0);\n                    o.put("url", "https://" + MEDIA_HOST + "/audio/" + token);'''
b='''                    o.put("duration", durationMs > 0 ? durationMs / 1000.0 : 0);\n                    o.put("_scanFingerprint", scanFingerprint(fileName, size));\n                    o.put("_scanSource", "MediaStore.Audio");\n                    o.put("url", "https://" + MEDIA_HOST + "/audio/" + token);'''
if a not in s:
    raise SystemExit('MediaStore audio JSON anchor missing')
s=s.replace(a,b,1)

# Indexed-files pass: do not discard a valid MP3 just because metadata extraction fails.
a='''                JSONObject item = describeAudio(uri, "mediastore-files/" + id, fileName, mime, size);\n                if (item != null) {\n                    out.add(item);'''
b='''                JSONObject item = describeAudio(uri, "mediastore-files/" + id, fileName, mime, size);\n                if (item != null) {\n                    try {\n                        item.put("_scanFingerprint", scanFingerprint(fileName, size));\n                        item.put("_scanSource", "MediaStore.Files");\n                    } catch (Exception ignored) {}\n                    out.add(item);'''
if a not in s:
    raise SystemExit('MediaStore Files item anchor missing')
s=s.replace(a,b,1)

# Add public folder scan before deciding MediaStore failed.
a='''                if (successfulVolumes == 0) {\n                    lastScanError = "Android MediaStore returned no readable volumes.";\n                    emitScanError(lastScanError + " Check Music & Audio permission.");\n                    return;\n                }\n\n                lastScanCount = items.size();\n                deliverLibrary(items, "Device Music");\n                emitScanStatus("success", items.size() + " audio files found (music + extension scan).");'''
b='''                int mediaStoreCount = items.size();\n                int publicFolderAdded = scanPublicAudioFolders(items);\n\n                if (successfulVolumes == 0 && items.isEmpty()) {\n                    lastScanError = "No readable audio was returned by Android storage.";\n                    emitScanError(lastScanError + " Check Music & Audio permission or choose a folder.");\n                    return;\n                }\n\n                lastScanCount = items.size();\n                lastScanError = "";\n                deliverLibrary(items, "Device Music");\n                emitScanStatus("success", items.size() + " audio files found · " + mediaStoreCount +\n                        " indexed · " + publicFolderAdded + " public-folder fallback.");'''
if a not in s:
    raise SystemExit('scan completion anchor missing')
s=s.replace(a,b,1)

# If a URI is valid audio but MediaMetadataRetriever cannot read tags, return a basic song instead of dropping it.
a='''    private JSONObject describeAudio(Uri uri, String relPath, String fileName, String mime, long size) {\n        MediaMetadataRetriever mmr = new MediaMetadataRetriever();\n        try {\n            if (!setRetrieverSource(mmr, uri)) return null;'''
b='''    private JSONObject describeAudio(Uri uri, String relPath, String fileName, String mime, long size) {\n        MediaMetadataRetriever mmr = new MediaMetadataRetriever();\n        try {\n            if (!setRetrieverSource(mmr, uri)) return buildBasicAudioItem(uri, relPath, fileName, mime, size);'''
if a not in s:
    raise SystemExit('describeAudio start anchor missing')
s=s.replace(a,b,1)

# Replace describeAudio catch only (first matching catch after method body) with fallback.
old='''        } catch (Exception e) {\n            return null;\n        } finally {\n            try { mmr.release(); } catch (Exception ignored) {}\n        }\n    }\n\n    private boolean setRetrieverSource(MediaMetadataRetriever mmr, Uri uri) {'''
new='''        } catch (Exception e) {\n            return buildBasicAudioItem(uri, relPath, fileName, mime, size);\n        } finally {\n            try { mmr.release(); } catch (Exception ignored) {}\n        }\n    }\n\n    private boolean setRetrieverSource(MediaMetadataRetriever mmr, Uri uri) {'''
if old not in s:
    raise SystemExit('describeAudio catch anchor missing')
s=s.replace(old,new,1)

# File URI metadata works more reliably through direct path.
a='''    private boolean setRetrieverSource(MediaMetadataRetriever mmr, Uri uri) {\n        try {\n            mmr.setDataSource(this, uri);'''
b='''    private boolean setRetrieverSource(MediaMetadataRetriever mmr, Uri uri) {\n        try {\n            if (uri != null && "file".equalsIgnoreCase(uri.getScheme()) && uri.getPath() != null) {\n                mmr.setDataSource(uri.getPath());\n                return true;\n            }\n            mmr.setDataSource(this, uri);'''
if a not in s:
    raise SystemExit('retriever source anchor missing')
s=s.replace(a,b,1)

# Helpers: basic item fallback + direct public folder scan across primary/removable storage.
helpers=r'''
    private static String scanFingerprint(String fileName, long size) {
        String n = fileName == null ? "" : fileName.trim().toLowerCase(Locale.US);
        return n + "|" + Math.max(0, size);
    }

    private JSONObject buildBasicAudioItem(Uri uri, String relPath, String fileName, String mime, long size) {
        try {
            String name = fileName == null || fileName.trim().isEmpty() ? "Unknown Audio" : fileName.trim();
            String key = uri == null ? ("basic:" + relPath) : uri.toString();
            String token = Integer.toHexString(key.hashCode()) + "_" + Integer.toHexString((relPath == null ? name : relPath).hashCode());
            synchronized (mediaMap) {
                mediaMap.put(token, new MediaEntry(uri, normalizeMime(name, mime), size, name));
            }
            JSONObject o = new JSONObject();
            o.put("fileKey", key);
            o.put("fileName", name);
            o.put("title", stripExt(name));
            o.put("artist", "Unknown Artist");
            o.put("album", "Local Music");
            o.put("genre", "");
            o.put("year", "");
            o.put("trackNo", "");
            o.put("albumArtist", "");
            o.put("discNo", 1);
            o.put("duration", 0);
            o.put("_scanFingerprint", scanFingerprint(name, size));
            o.put("url", "https://" + MEDIA_HOST + "/audio/" + token);
            return o;
        } catch (Exception e) {
            return null;
        }
    }

    private int scanPublicAudioFolders(ArrayList<JSONObject> out) {
        Set<String> fingerprints = new HashSet<>();
        for (JSONObject o : out) {
            String fp = o.optString("_scanFingerprint", "");
            if (!fp.isEmpty()) fingerprints.add(fp);
        }

        ArrayList<File> roots = new ArrayList<>();
        Set<String> rootPaths = new HashSet<>();
        addPublicRoots(Environment.getExternalStorageDirectory(), roots, rootPaths);
        try {
            File[] ext = getExternalFilesDirs(null);
            if (ext != null) {
                for (File appDir : ext) {
                    if (appDir == null) continue;
                    File volume = appDir;
                    for (int i = 0; i < 4 && volume != null; i++) volume = volume.getParentFile();
                    addPublicRoots(volume, roots, rootPaths);
                }
            }
        } catch (Exception ignored) {}

        int before = out.size();
        int[] visited = new int[]{0};
        for (File root : roots) {
            if (out.size() - before >= 4000) break;
            scanPublicDir(root, 0, out, fingerprints, visited);
        }
        return out.size() - before;
    }

    private void addPublicRoots(File volumeRoot, ArrayList<File> roots, Set<String> seen) {
        if (volumeRoot == null) return;
        String[] names = new String[]{"Music", "Download", "Downloads", "Podcasts", "Audiobooks", "Ringtones", "Recordings", "Alarms", "Notifications"};
        for (String n : names) {
            try {
                File f = new File(volumeRoot, n);
                String p = f.getCanonicalPath();
                if (seen.add(p) && f.exists() && f.isDirectory() && f.canRead()) roots.add(f);
            } catch (Exception ignored) {}
        }
    }

    private void scanPublicDir(File dir, int depth, ArrayList<JSONObject> out,
                               Set<String> fingerprints, int[] visited) {
        if (dir == null || depth > 8 || visited[0] > 12000 || out.size() > 7000) return;
        File[] files;
        try { files = dir.listFiles(); } catch (Exception e) { return; }
        if (files == null) return;
        for (File f : files) {
            if (visited[0]++ > 12000 || out.size() > 7000) return;
            try {
                if (f.isDirectory()) {
                    if (!f.getName().startsWith(".")) scanPublicDir(f, depth + 1, out, fingerprints, visited);
                    continue;
                }
                if (!f.isFile() || !f.canRead() || !isAudio(f.getName(), null)) continue;
                String fp = scanFingerprint(f.getName(), f.length());
                if (!fingerprints.add(fp)) continue;
                Uri uri = Uri.fromFile(f);
                JSONObject item = describeAudio(uri, "public/" + f.getAbsolutePath(), f.getName(), null, f.length());
                if (item == null) continue;
                item.put("_scanFingerprint", fp);
                item.put("_scanSource", "PublicFolders");
                out.add(item);
                int found = out.size();
                if (found == 1 || found % 25 == 0) {
                    js("window.__elyaNativeScanProgress&&window.__elyaNativeScanProgress(" + found + ");");
                }
            } catch (Exception ignored) {}
        }
    }

'''
marker='''    private void scanTree(Uri treeUri, boolean userInitiated) {'''
if marker not in s:
    raise SystemExit('scanTree marker missing for helper insertion')
s=s.replace(marker,helpers+marker,1)

# Diagnostics includes scanner generation.
a='''            o.put("lastScanError", lastScanError);'''
b='''            o.put("lastScanError", lastScanError);\n            o.put("scanner", "MediaStore.Audio + MediaStore.Files + public folders");'''
if a not in s:
    raise SystemExit('diagnostics scan anchor missing')
s=s.replace(a,b,1)

p.write_text(s,encoding='utf-8')

# ---------------- UI / precise refresh / Scan Center ----------------
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')

# Remove the 1.0.9 pull implementation entirely. It watched window.scrollY instead of Elya's .main scroller.
h=re.sub(r'<style id="elya109PullStyle">.*?</style>','',h,flags=re.S)
h=re.sub(r'<div id="elya109PullRefresh".*?</div>','',h,flags=re.S)
h=re.sub(r'<script id="elya109PullScript">.*?</script>','',h,flags=re.S)

css=r'''<style id="elya110Style">
html,body{overscroll-behavior-y:contain!important}
#elya110Pull{position:fixed;left:50%;top:calc(8px + env(safe-area-inset-top));z-index:130000;transform:translate(-50%,-84px);opacity:0;pointer-events:none;display:flex;align-items:center;gap:9px;padding:10px 14px;border:1px solid rgba(255,255,255,.1);border-radius:999px;background:rgba(7,11,18,.94);backdrop-filter:blur(18px) saturate(1.25);box-shadow:0 16px 40px rgba(0,0,0,.38);font-size:12px;font-weight:750;color:var(--muted);transition:transform .16s ease,opacity .16s ease}
#elya110Pull.show{opacity:1}#elya110Pull.ready{color:var(--accent)}#elya110Pull.refreshing{color:var(--text)}
#elya110Pull .ring{width:18px;height:18px;border-radius:50%;border:2px solid currentColor;border-top-color:transparent}
#elya110Pull.refreshing .ring{animation:elya110spin .65s linear infinite}@keyframes elya110spin{to{transform:rotate(360deg)}}
#elya110ScanModal{position:fixed;inset:0;z-index:125000;display:none;align-items:flex-end;justify-content:center;background:rgba(0,0,0,.62);backdrop-filter:blur(13px);padding:18px}#elya110ScanModal.open{display:flex}
.elya110-sheet{width:min(520px,100%);border:1px solid rgba(255,255,255,.1);border-radius:26px;padding:18px;background:linear-gradient(180deg,rgba(18,25,36,.98),rgba(8,13,20,.99));box-shadow:0 30px 90px rgba(0,0,0,.55)}
.elya110-sheet-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.elya110-sheet-head h3{margin:0;font-size:21px}.elya110-close{width:40px;height:40px;border-radius:13px}
.elya110-scan-hero{display:grid;grid-template-columns:72px 1fr;gap:14px;align-items:center;margin:16px 0;padding:15px;border:1px solid rgba(255,255,255,.075);border-radius:20px;background:rgba(255,255,255,.035)}
.elya110-orb{width:72px;height:72px;border-radius:22px;display:grid;place-items:center;background:radial-gradient(circle at 35% 30%,rgba(var(--accent-rgb),.28),rgba(var(--accent-rgb),.07) 55%,transparent);border:1px solid rgba(var(--accent-rgb),.22)}.elya110-orb svg{width:31px;height:31px;color:var(--accent)}
#elya110ScanStatus{font-weight:850;font-size:15px}#elya110ScanDetail{margin-top:4px;color:var(--muted);font-size:12px;line-height:1.5}
.elya110-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.elya110-metric{padding:11px;border-radius:16px;background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.065)}.elya110-metric b{display:block;font-size:17px}.elya110-metric span{display:block;margin-top:3px;color:var(--muted);font-size:10px}
.elya110-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px}.elya110-actions button{min-height:46px}.elya110-actions .wide{grid-column:1/-1}
#elya110ScanQuick{position:relative;overflow:hidden}#elya110ScanQuick::after{content:"";position:absolute;inset:auto -18px -26px auto;width:70px;height:70px;border-radius:50%;background:rgba(var(--accent-rgb),.09);filter:blur(2px)}
.elya110-scanning .elya110-orb{animation:elya110pulse 1.1s ease-in-out infinite alternate}@keyframes elya110pulse{to{transform:scale(1.045);box-shadow:0 0 30px rgba(var(--accent-rgb),.14)}}
@media(min-width:700px){#elya110ScanModal{align-items:center}.elya110-sheet{border-radius:28px}}
</style>'''
if 'elya110Style' not in h:
    h=h.replace('</head>',css+'</head>',1)

ui=r'''<div id="elya110Pull" aria-hidden="true"><span class="ring"></span><span id="elya110PullText">Pull to refresh</span></div>
<div id="elya110ScanModal" role="dialog" aria-modal="true" aria-label="Library Scan Center"><div class="elya110-sheet"><div class="elya110-sheet-head"><div><h3>Library Scan Center</h3><small style="color:var(--muted)">Find local music without uploading it</small></div><button class="secondary elya110-close" id="elya110ScanClose" type="button"><svg><use href="#i-close"/></svg></button></div><div class="elya110-scan-hero"><div class="elya110-orb"><svg><use href="#i-folder"/></svg></div><div><div id="elya110ScanStatus">Ready to scan</div><div id="elya110ScanDetail">Elya checks Android music, indexed audio files, then readable Music / Downloads / Podcasts folders.</div></div></div><div class="elya110-metrics"><div class="elya110-metric"><b id="elya110Found">0</b><span>SONGS FOUND</span></div><div class="elya110-metric"><b id="elya110Permission">—</b><span>MUSIC ACCESS</span></div><div class="elya110-metric"><b id="elya110Core">1.1.0</b><span>SCANNER</span></div></div><div class="elya110-actions"><button class="primary wide" id="elya110DeepScan" type="button"><svg><use href="#i-folder"/></svg> Deep Scan Device</button><button class="secondary" id="elya110ChooseFolder" type="button">Choose Folder</button><button class="secondary" id="elya110AppSettings" type="button">App Settings</button></div></div></div>'''
if 'id="elya110Pull"' not in h:
    h=h.replace('</body>',ui+'</body>',1)

script=r'''<script id="elya110Script">(()=>{
  const q=s=>document.querySelector(s);
  const call=(name,...args)=>{try{const a=window.AndroidMusic;if(!a||typeof a[name]!=='function')throw new Error('Native bridge unavailable');return a[name](...args)}catch(e){window.toast?.(e.message||'Android action unavailable')}};

  // ---------- precise page pull-to-refresh ----------
  const pull=q('#elya110Pull'),pullText=q('#elya110PullText'),THRESHOLD=86,MAX=126;
  let startY=0,distance=0,active=false,refreshing=false,scroller=null;
  const blockers=()=>q('.modal.open,#queueDrawer.open,#mobileSearchOverlay.open,#elya110ScanModal.open');
  const currentScroller=(target)=>{
    const np=q('#nowPlaying');
    if(np?.classList.contains('open') && target?.closest?.('#nowPlaying')) return np;
    return q('.main');
  };
  const atRealTop=el=>!!el && Math.max(0,Number(el.scrollTop||0))<=1;
  const paint=()=>{
    if(!pull||!pullText)return;
    const y=Math.max(0,Math.min(MAX,distance));
    pull.classList.toggle('show',y>5);pull.classList.toggle('ready',y>=THRESHOLD);
    pull.style.transform=`translate(-50%,${-76+Math.min(86,y*.76)}px) scale(${.94+Math.min(.06,y/1200)})`;
    const ring=pull.querySelector('.ring');if(ring&&!refreshing)ring.style.transform=`rotate(${Math.min(300,y*2.8)}deg)`;
    pullText.textContent=y>=THRESHOLD?'Release to refresh':'Pull to refresh';
  };
  const reset=()=>{active=false;distance=0;scroller=null;if(!pull)return;pull.classList.remove('show','ready','refreshing');pull.style.transform='translate(-50%,-84px)';if(pullText)pullText.textContent='Pull to refresh'};
  document.addEventListener('touchstart',e=>{
    if(refreshing||blockers()||e.touches.length!==1)return;
    const candidate=currentScroller(e.target);
    // Critical: the gesture can only ARM when the actual current page scroller is at scrollTop 0.
    if(!atRealTop(candidate))return;
    scroller=candidate;startY=e.touches[0].clientY;distance=0;active=true;
  },{passive:true});
  document.addEventListener('touchmove',e=>{
    if(!active||refreshing||e.touches.length!==1)return;
    if(!atRealTop(scroller)&&distance<6){reset();return}
    const dy=e.touches[0].clientY-startY;
    if(dy<=0){distance=0;paint();return}
    distance=Math.min(MAX,dy*.6);
    if(distance>5)e.preventDefault();paint();
  },{passive:false});
  const finishPull=()=>{
    if(!active||refreshing)return;
    active=false;
    if(distance<THRESHOLD){reset();return}
    refreshing=true;pull?.classList.add('show','refreshing');pull?.classList.remove('ready');if(pullText)pullText.textContent='Refreshing this page…';
    try{sessionStorage.setItem('elya110RefreshState',JSON.stringify({view:state?.currentView||null,label:q('#viewTitle')?.textContent||'',nowPlaying:q('#nowPlaying')?.classList.contains('open')||false}))}catch{}
    try{navigator.vibrate?.(18)}catch{}
    setTimeout(()=>location.reload(),240);
  };
  document.addEventListener('touchend',finishPull,{passive:true});
  document.addEventListener('touchcancel',()=>{if(!refreshing)reset()},{passive:true});

  // Restore the exact Elya view after a refresh instead of throwing the user back Home.
  window.addEventListener('load',()=>setTimeout(()=>{
    let saved=null;try{saved=JSON.parse(sessionStorage.getItem('elya110RefreshState')||'null');sessionStorage.removeItem('elya110RefreshState')}catch{}
    if(!saved)return;
    try{if(saved.view?.type) setView(saved.view.type,saved.view.value??null,saved.label||null)}catch{}
    try{const m=q('.main');if(m)m.scrollTop=0}catch{}
    try{if(saved.nowPlaying&&typeof openNowPlaying==='function')openNowPlaying()}catch{}
  },700));

  // ---------- Scan Center ----------
  const modal=q('#elya110ScanModal'),status=q('#elya110ScanStatus'),detail=q('#elya110ScanDetail'),found=q('#elya110Found'),perm=q('#elya110Permission');
  const openScan=()=>modal?.classList.add('open'),closeScan=()=>modal?.classList.remove('open');
  q('#elya110ScanClose')?.addEventListener('click',closeScan);modal?.addEventListener('click',e=>{if(e.target===modal)closeScan()});
  q('#elya110DeepScan')?.addEventListener('click',()=>{modal?.classList.add('elya110-scanning');status.textContent='Scanning device…';detail.textContent='Checking Android media, indexed files, Music, Downloads, Podcasts and readable removable storage.';call(typeof AndroidMusic?.deepScanDeviceMusic==='function'?'deepScanDeviceMusic':'scanAllDeviceMusic')});
  q('#elya110ChooseFolder')?.addEventListener('click',()=>call('chooseMusicFolder'));
  q('#elya110AppSettings')?.addEventListener('click',()=>call('openAppSettings'));

  // Add a premium quick card without replacing the existing Home design.
  const quick=q('#quickRow');
  if(quick&&!q('#elya110ScanQuick')){
    const card=document.createElement('div');card.id='elya110ScanQuick';card.className='quick-card';card.innerHTML='<svg><use href="#i-folder"/></svg><strong>Scan Library</strong><small>Device + folders</small>';card.addEventListener('click',openScan);quick.appendChild(card);
  }

  const oldDiag=window.__elyaNativeDiagnostics;
  window.__elyaNativeDiagnostics=d=>{try{oldDiag?.(d)}catch{};if(!d)return;if(found)found.textContent=String(Number(d.lastScanCount||0));if(perm)perm.textContent=d.musicPermission?'Allowed':'Needed';if(status&&!d.scanRunning)status.textContent=Number(d.lastScanCount||0)>0?'Library ready':'Ready to scan';if(detail){const err=d.lastScanError?` · ${d.lastScanError}`:'';detail.textContent=`${d.scanner||'Elya local scanner'}${err}`}};
  const oldStart=window.__elyaNativeScanStarted;window.__elyaNativeScanStarted=name=>{try{oldStart?.(name)}catch{};modal?.classList.add('elya110-scanning');if(status)status.textContent='Scanning…';if(detail)detail.textContent=`Reading ${name||'device music'} without uploading files.`};
  const oldProgress=window.__elyaNativeScanProgress;window.__elyaNativeScanProgress=n=>{try{oldProgress?.(n)}catch{};if(found)found.textContent=String(Number(n||0));if(status)status.textContent=`Found ${Number(n||0)} audio files…`};
  const oldStatus=window.__elyaNativeScanStatus;window.__elyaNativeScanStatus=o=>{try{oldStatus?.(o)}catch{};if(!o)return;if(Number.isFinite(Number(o.count))&&found)found.textContent=String(Number(o.count));if(status)status.textContent=o.status==='success'?'Library ready':(o.status==='error'?'Scan needs attention':'Scanning…');if(detail&&o.message)detail.textContent=o.message;if(o.status==='success'||o.status==='error')modal?.classList.remove('elya110-scanning')};
  const oldErr=window.__elyaNativeScanError;window.__elyaNativeScanError=m=>{try{oldErr?.(m)}catch{};modal?.classList.remove('elya110-scanning');if(status)status.textContent='Scan needs attention';if(detail)detail.textContent=m||'Could not scan this storage.'};

  // Preserve the user's last library page between normal app restarts too.
  try{
    const oldSetView=setView;
    window.setView=function(type,value=null,label=null){const out=oldSetView(type,value,label);try{localStorage.setItem('elya:lastView',JSON.stringify({type,value,label}))}catch{};return out};
  }catch{}
})();</script>'''
if 'elya110Script' not in h:
    h=h.replace('</body>',script+'</body>',1)

p.write_text(h,encoding='utf-8')
print('Elya 1.1.0 precise refresh + resilient scanner + Scan Center applied')

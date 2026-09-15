from pathlib import Path
import re

r=Path('.')

# ---- Version ----
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+16\b','versionCode 17',s,count=1)
s=re.sub(r"versionName\s+'1\.2\.0'","versionName '1.2.1'",s,count=1)
p.write_text(s,encoding='utf-8')

# ---- Native bridge + LRC sidecar support ----
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_120','// ELYA_NATIVE_CORE_120\n    // ELYA_NATIVE_CORE_121',1)
s=s.replace('return "elya-bridge-1.2.0";','return "elya-bridge-1.2.1";',1)
s=s.replace('o.put("core", "1.2.0");','o.put("core", "1.2.1");',1)

if 'import java.io.ByteArrayOutputStream;' not in s:
    s=s.replace('import java.io.ByteArrayInputStream;','import java.io.ByteArrayInputStream;\nimport java.io.ByteArrayOutputStream;\nimport java.io.FileInputStream;',1)
if 'import java.nio.charset.StandardCharsets;' not in s:
    s=s.replace('import java.util.ArrayList;','import java.nio.charset.StandardCharsets;\nimport java.util.ArrayList;',1)

old='''                String rootId = DocumentsContract.getTreeDocumentId(treeUri);\n                scanDocumentChildren(treeUri, rootId, "", items);'''
new='''                String rootId = DocumentsContract.getTreeDocumentId(treeUri);\n                Map<String, String> sidecarLyrics = new HashMap<>();\n                scanLrcDocumentChildren(treeUri, rootId, "", sidecarLyrics);\n                scanDocumentChildren(treeUri, rootId, "", items, sidecarLyrics);'''
if old not in s: raise SystemExit('scanTree root anchor missing')
s=s.replace(old,new,1)

old='''    private void scanDocumentChildren(Uri treeUri, String parentDocumentId, String relPath,\n                                      ArrayList<JSONObject> out) {'''
new='''    private void scanDocumentChildren(Uri treeUri, String parentDocumentId, String relPath,\n                                      ArrayList<JSONObject> out, Map<String, String> sidecarLyrics) {'''
if old not in s: raise SystemExit('scanDocumentChildren signature missing')
s=s.replace(old,new,1)

old='''                    scanDocumentChildren(treeUri, docId, relPath + name + "/", out);'''
new='''                    scanDocumentChildren(treeUri, docId, relPath + name + "/", out, sidecarLyrics);'''
if old not in s: raise SystemExit('recursive scanDocumentChildren anchor missing')
s=s.replace(old,new,1)

old='''                JSONObject item = describeAudio(docUri, relPath + name, name, mime, size);\n                if (item != null) {\n                    out.add(item);'''
new='''                JSONObject item = describeAudio(docUri, relPath + name, name, mime, size);\n                if (item != null) {\n                    String sidecar = sidecarLyrics == null ? "" : sidecarLyrics.get(sidecarKey(relPath + name));\n                    if (sidecar != null && !sidecar.trim().isEmpty()) {\n                        try { item.put("lyrics", sidecar); item.put("_lyricsSource", "LRC"); } catch (Exception ignored) {}\n                    }\n                    out.add(item);'''
if old not in s: raise SystemExit('tree audio item anchor missing')
s=s.replace(old,new,1)

old='''                String fp = scanFingerprint(f.getName(), f.length());\n                if (!fingerprints.add(fp)) continue;\n                Uri uri = Uri.fromFile(f);\n                JSONObject item = describeAudio(uri, "public/" + f.getAbsolutePath(), f.getName(), null, f.length());\n                if (item == null) continue;\n                item.put("_scanFingerprint", fp);\n                item.put("_scanSource", "PublicFolders");\n                out.add(item);'''
new='''                String fp = scanFingerprint(f.getName(), f.length());\n                String lrc = readSiblingLrc(f);\n                if (!fingerprints.add(fp)) {\n                    if (!lrc.isEmpty()) attachLyricsByFingerprint(out, fp, lrc);\n                    continue;\n                }\n                Uri uri = Uri.fromFile(f);\n                JSONObject item = describeAudio(uri, "public/" + f.getAbsolutePath(), f.getName(), null, f.length());\n                if (item == null) continue;\n                item.put("_scanFingerprint", fp);\n                item.put("_scanSource", "PublicFolders");\n                if (!lrc.isEmpty()) { item.put("lyrics", lrc); item.put("_lyricsSource", "LRC"); }\n                out.add(item);'''
if old not in s: raise SystemExit('public scan item anchor missing')
s=s.replace(old,new,1)

marker='''    private void scanTree(Uri treeUri, boolean userInitiated) {'''
helpers=r'''
    private static String sidecarKey(String path) {
        String p = path == null ? "" : path.replace('\\', '/').trim().toLowerCase(Locale.US);
        int slash = p.lastIndexOf('/');
        String dir = slash >= 0 ? p.substring(0, slash + 1) : "";
        String name = slash >= 0 ? p.substring(slash + 1) : p;
        int dot = name.lastIndexOf('.');
        if (dot > 0) name = name.substring(0, dot);
        return dir + name;
    }

    private String readSmallText(InputStream in) {
        if (in == null) return "";
        try (InputStream src = in; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[8192];
            int n; int total = 0; final int LIMIT = 1024 * 1024;
            while ((n = src.read(buf)) > 0 && total < LIMIT) {
                int take = Math.min(n, LIMIT - total);
                out.write(buf, 0, take); total += take;
            }
            String text = new String(out.toByteArray(), StandardCharsets.UTF_8);
            if (!text.isEmpty() && text.charAt(0) == '\ufeff') text = text.substring(1);
            return text.trim();
        } catch (Exception e) { return ""; }
    }

    private String readSmallText(Uri uri) {
        try { return readSmallText(getContentResolver().openInputStream(uri)); }
        catch (Exception e) { return ""; }
    }

    private String readSmallTextFile(File file) {
        try { return file != null && file.exists() && file.isFile() ? readSmallText(new FileInputStream(file)) : ""; }
        catch (Exception e) { return ""; }
    }

    private String readSiblingLrc(File audio) {
        if (audio == null || audio.getParentFile() == null) return "";
        String name = audio.getName();
        int dot = name.lastIndexOf('.');
        String base = dot > 0 ? name.substring(0, dot) : name;
        File lower = new File(audio.getParentFile(), base + ".lrc");
        String text = readSmallTextFile(lower);
        if (!text.isEmpty()) return text;
        return readSmallTextFile(new File(audio.getParentFile(), base + ".LRC"));
    }

    private void attachLyricsByFingerprint(ArrayList<JSONObject> out, String fp, String lyrics) {
        if (out == null || fp == null || lyrics == null || lyrics.trim().isEmpty()) return;
        for (JSONObject o : out) {
            if (fp.equals(o.optString("_scanFingerprint", ""))) {
                try { o.put("lyrics", lyrics); o.put("_lyricsSource", "LRC"); } catch (Exception ignored) {}
                return;
            }
        }
    }

    private void scanLrcDocumentChildren(Uri treeUri, String parentDocumentId, String relPath,
                                         Map<String, String> sidecars) {
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentDocumentId);
        String[] projection = new String[]{
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE
        };
        try (Cursor c = getContentResolver().query(children, projection, null, null, null)) {
            if (c == null) return;
            int idCol = c.getColumnIndex(DocumentsContract.Document.COLUMN_DOCUMENT_ID);
            int nameCol = c.getColumnIndex(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            int mimeCol = c.getColumnIndex(DocumentsContract.Document.COLUMN_MIME_TYPE);
            while (c.moveToNext()) {
                String docId = idCol >= 0 ? c.getString(idCol) : null;
                String name = nameCol >= 0 ? c.getString(nameCol) : "";
                String mime = mimeCol >= 0 ? c.getString(mimeCol) : "";
                if (docId == null) continue;
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                    scanLrcDocumentChildren(treeUri, docId, relPath + name + "/", sidecars);
                    continue;
                }
                if (name == null || !name.toLowerCase(Locale.US).endsWith(".lrc")) continue;
                Uri docUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, docId);
                String text = readSmallText(docUri);
                if (!text.isEmpty()) sidecars.put(sidecarKey(relPath + name), text);
            }
        } catch (Exception ignored) {}
    }

'''
if marker not in s: raise SystemExit('scanTree marker missing for LRC helpers')
s=s.replace(marker,helpers+marker,1)
p.write_text(s,encoding='utf-8')

# ---- HTML runtime recovery + native cover/LRC sync ----
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')

old="if(ping==='elya-bridge-1.0.7'){"
new="if(typeof ping==='string'&&ping.startsWith('elya-bridge-')){"
if old not in h: raise SystemExit('stale bridge ping guard missing')
h=h.replace(old,new,1)

old='''        if(item.cover) s.cover = item.cover;\n        if(!s.defaultCover) s.defaultCover = s.cover || cover;\n        s.lastSeenAt = Date.now();'''
new='''        if(item.cover){ s.cover = item.cover; s.defaultCover = item.cover; s.nativeCover = true; }\n        if(item.lyrics && String(item.lyrics).trim() && !String(s.lyrics||'').trim()){ s.lyrics = item.lyrics; s.nativeLyrics = true; }\n        if(!s.defaultCover) s.defaultCover = s.cover || cover;\n        s.lastSeenAt = Date.now();'''
if old not in h: raise SystemExit('native existing cover anchor missing')
h=h.replace(old,new,1)

old='''          url: item.url,\n          fromMusicFolder: true,'''
new='''          url: item.url,\n          lyrics: item.lyrics || '',\n          nativeCover: !!item.cover,\n          nativeLyrics: !!(item.lyrics && String(item.lyrics).trim()),\n          fromMusicFolder: true,'''
if old not in h: raise SystemExit('native new song url anchor missing')
h=h.replace(old,new,1)

safety=r'''<script id="elya121RuntimeRecovery">(()=>{
  window.__elyaStabilityVersion='1.2.1';
  const releaseNativeGate=()=>{
    if(!window.AndroidMusic)return;
    const gate=document.getElementById('folderGate');
    gate?.classList.remove('open');
    if(gate){gate.style.pointerEvents='none';gate.setAttribute('aria-hidden','true')}
    const boot=document.getElementById('elyaBoot');
    if(boot?.classList.contains('done'))boot.style.pointerEvents='none';
    document.querySelector('.app')?.style.setProperty('pointer-events','auto');
  };
  const run=()=>{releaseNativeGate();setTimeout(releaseNativeGate,700);setTimeout(releaseNativeGate,2200)};
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
})();</script>'''
if 'id="elya121RuntimeRecovery"' not in h:
    h=h.replace('</body>',safety+'</body>',1)

cover_script=r'''<script id="elya121CoverSafety">(()=>{
  document.addEventListener('error',e=>{
    const img=e.target;
    if(!(img instanceof HTMLImageElement))return;
    const row=img.closest?.('[data-id]');
    const id=row?.dataset?.id;
    const song=id&&window.state?.songs?.find?.(s=>s.id===id);
    if(song && song.cover && song.defaultCover && song.cover!==song.defaultCover){
      song.cover=song.defaultCover;
      img.src=song.defaultCover;
    }
  },true);
})();</script>'''
if 'id="elya121CoverSafety"' not in h:
    h=h.replace('</body>',cover_script+'</body>',1)

p.write_text(h,encoding='utf-8')
print('Elya 1.2.1 interaction + native cover + LRC sidecar fix applied')

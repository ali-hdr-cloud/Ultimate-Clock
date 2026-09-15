from pathlib import Path
import re

r=Path('.')

# Version
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+8\b','versionCode 9',s,count=1)
s=re.sub(r"versionName\s+'1\.0\.7'","versionName '1.0.8'",s,count=1)
p.write_text(s,encoding='utf-8')

# Native core enhancements
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_107','// ELYA_NATIVE_CORE_107\n    // ELYA_NATIVE_CORE_108',1)
s=s.replace('return "elya-bridge-1.0.7";','return "elya-bridge-1.0.8";',1)
s=s.replace('o.put("core", "1.0.7");','o.put("core", "1.0.8");',1)

# Disable WebView edge overscroll / accidental pull refresh behavior.
anchor='''        s.setDisplayZoomControls(false);\n        s.setSupportZoom(false);'''
replacement='''        s.setDisplayZoomControls(false);\n        s.setSupportZoom(false);\n        webView.setOverScrollMode(WebView.OVER_SCROLL_NEVER);'''
if anchor not in s:
    raise SystemExit('WebView settings anchor missing')
s=s.replace(anchor,replacement,1)

# Dedupe MediaStore.Audio and MediaStore.Files rows by volume + row id rather than collection URI.
old='''                Uri uri = ContentUris.withAppendedId(collection, id);\n                String key = uri.toString();\n                if (!seenUris.add(key)) continue;\n\n                String fileName = stringAt(c, nameCol);'''
new='''                Uri uri = ContentUris.withAppendedId(collection, id);\n                String key = uri.toString();\n                String dedupeKey = volumeName + ":" + id;\n                if (!seenUris.add(dedupeKey)) continue;\n\n                String fileName = stringAt(c, nameCol);'''
if old not in s:
    raise SystemExit('MediaStore audio dedupe anchor missing')
s=s.replace(old,new,1)

# Add a second pass through MediaStore.Files. This catches audio that Android has indexed as a generic file.
old='''                if (Build.VERSION.SDK_INT >= 29) {\n                    Set<String> volumes = new HashSet<>(MediaStore.getExternalVolumeNames(this));\n                    if (volumes.isEmpty()) volumes.add(MediaStore.VOLUME_EXTERNAL_PRIMARY);\n                    for (String volume : volumes) {\n                        Uri collection = MediaStore.Audio.Media.getContentUri(volume);\n                        if (scanMediaCollection(collection, volume, items, seen)) successfulVolumes++;\n                    }\n                } else {\n                    if (scanMediaCollection(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,\n                            "external", items, seen)) successfulVolumes++;\n                }'''
new='''                if (Build.VERSION.SDK_INT >= 29) {\n                    Set<String> volumes = new HashSet<>(MediaStore.getExternalVolumeNames(this));\n                    if (volumes.isEmpty()) volumes.add(MediaStore.VOLUME_EXTERNAL_PRIMARY);\n                    for (String volume : volumes) {\n                        boolean okAudio = scanMediaCollection(MediaStore.Audio.Media.getContentUri(volume), volume, items, seen);\n                        boolean okFiles = scanMediaFilesCollection(MediaStore.Files.getContentUri(volume), volume, items, seen);\n                        if (okAudio || okFiles) successfulVolumes++;\n                    }\n                } else {\n                    boolean okAudio = scanMediaCollection(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,\n                            "external", items, seen);\n                    boolean okFiles = scanMediaFilesCollection(MediaStore.Files.getContentUri("external"),\n                            "external", items, seen);\n                    if (okAudio || okFiles) successfulVolumes++;\n                }'''
if old not in s:
    raise SystemExit('device volume scan anchor missing')
s=s.replace(old,new,1)

s=s.replace('emitScanStatus("success", items.size() + " audio files found.");',
            'emitScanStatus("success", items.size() + " audio files found (music + extension scan).");',1)

files_method=r'''
    private boolean scanMediaFilesCollection(Uri collection, String volumeName,
                                             ArrayList<JSONObject> out, Set<String> seenIds) {
        String[] projection = new String[]{
                MediaStore.Files.FileColumns._ID,
                MediaStore.Files.FileColumns.DISPLAY_NAME,
                MediaStore.Files.FileColumns.MIME_TYPE,
                MediaStore.Files.FileColumns.SIZE
        };
        String n = MediaStore.Files.FileColumns.DISPLAY_NAME;
        String m = MediaStore.Files.FileColumns.MIME_TYPE;
        String selection = "(" + m + " LIKE 'audio/%' OR " +
                "lower(" + n + ") LIKE '%.mp3' OR lower(" + n + ") LIKE '%.m4a' OR " +
                "lower(" + n + ") LIKE '%.aac' OR lower(" + n + ") LIKE '%.wav' OR " +
                "lower(" + n + ") LIKE '%.flac' OR lower(" + n + ") LIKE '%.ogg' OR " +
                "lower(" + n + ") LIKE '%.oga' OR lower(" + n + ") LIKE '%.opus' OR " +
                "lower(" + n + ") LIKE '%.aif' OR lower(" + n + ") LIKE '%.aiff' OR " +
                "lower(" + n + ") LIKE '%.mka')";
        try (Cursor c = getContentResolver().query(collection, projection, selection, null,
                MediaStore.Files.FileColumns.DATE_ADDED + " DESC")) {
            if (c == null) return false;
            int idCol = c.getColumnIndex(MediaStore.Files.FileColumns._ID);
            int nameCol = c.getColumnIndex(MediaStore.Files.FileColumns.DISPLAY_NAME);
            int mimeCol = c.getColumnIndex(MediaStore.Files.FileColumns.MIME_TYPE);
            int sizeCol = c.getColumnIndex(MediaStore.Files.FileColumns.SIZE);
            while (c.moveToNext()) {
                if (idCol < 0) continue;
                long id = c.getLong(idCol);
                String dedupeKey = volumeName + ":" + id;
                if (!seenIds.add(dedupeKey)) continue;
                String fileName = stringAt(c, nameCol);
                String mime = stringAt(c, mimeCol);
                if (!isAudio(fileName, mime)) continue;
                long size = longAt(c, sizeCol);
                Uri uri = ContentUris.withAppendedId(collection, id);
                JSONObject item = describeAudio(uri, "mediastore-files/" + id, fileName, mime, size);
                if (item != null) {
                    out.add(item);
                    int found = out.size();
                    if (found == 1 || found % 25 == 0) {
                        js("window.__elyaNativeScanProgress&&window.__elyaNativeScanProgress(" + found + ");");
                    }
                }
            }
            return true;
        } catch (SecurityException e) {
            lastScanError = "Permission denied reading indexed files on " + volumeName;
            return false;
        } catch (Exception e) {
            lastScanError = e.getClass().getSimpleName() + " reading indexed files on " + volumeName + ": " + clean(e.getMessage());
            return false;
        }
    }

'''
marker='''    private void scanTree(Uri treeUri, boolean userInitiated) {'''
if marker not in s:
    raise SystemExit('scanTree marker missing')
s=s.replace(marker,files_method+marker,1)

p.write_text(s,encoding='utf-8')

# UI: no edge reload, sign-out confirmation, clearer scan fallback.
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')

css=r'''<style id="elya108Style">
html,body{overscroll-behavior:none!important;overscroll-behavior-y:none!important}
.elya108-confirm{position:fixed;inset:0;z-index:100000;display:none;align-items:center;justify-content:center;padding:22px;background:rgba(0,0,0,.64);backdrop-filter:blur(14px)}
.elya108-confirm.show{display:flex}.elya108-card{width:min(420px,100%);padding:20px;border:1px solid var(--line);border-radius:22px;background:var(--panel,#0d1118);box-shadow:0 24px 80px rgba(0,0,0,.5)}
.elya108-card h3{margin:0 0 8px;font-size:20px}.elya108-card p{margin:0;color:var(--muted);line-height:1.55}.elya108-actions{display:flex;gap:9px;margin-top:18px}.elya108-actions button{flex:1}
.elya108-scan-note{font-size:11px;color:var(--muted);margin-top:7px;line-height:1.45}
</style>'''
if 'elya108Style' not in h:
    h=h.replace('</head>',css+'</head>',1)

modal=r'''<div class="elya108-confirm" id="elya108SignOutConfirm" role="dialog" aria-modal="true" aria-label="Sign out confirmation"><div class="elya108-card"><h3>Sign out of Elya?</h3><p>Your music files stay on this device. Your Elya account will be disconnected until you sign in again.</p><div class="elya108-actions"><button class="secondary" id="elya108CancelSignOut" type="button">Cancel</button><button class="danger-btn" id="elya108ConfirmSignOut" type="button">Sign Out</button></div></div></div>'''
if 'elya108SignOutConfirm' not in h:
    h=h.replace('</body>',modal+'</body>',1)

script=r'''<script id="elya108Script">(()=>{
  const q=s=>document.querySelector(s);
  const call=(name,...args)=>{try{const b=window.AndroidMusic;if(!b||typeof b[name]!=='function')throw new Error('Native bridge unavailable');return b[name](...args)}catch(e){window.toast?.(e.message||'Native bridge error')}};
  const clone=id=>{const old=q('#'+id);if(!old)return null;const n=old.cloneNode(true);old.replaceWith(n);return n};
  const signOut=clone('elyaSignOut'),box=q('#elya108SignOutConfirm'),cancel=q('#elya108CancelSignOut'),yes=q('#elya108ConfirmSignOut');
  if(signOut){signOut.type='button';signOut.onclick=()=>box?.classList.add('show')}
  cancel?.addEventListener('click',()=>box?.classList.remove('show'));
  box?.addEventListener('click',e=>{if(e.target===box)box.classList.remove('show')});
  yes?.addEventListener('click',()=>{box?.classList.remove('show');call('firebaseSignOut')});

  const oldDiag=window.__elyaNativeDiagnostics;
  window.__elyaNativeDiagnostics=d=>{try{oldDiag?.(d)}catch{};if(!d)return;const s=q('#elyaScanDiag');if(s&&+d.lastScanCount===0&&d.musicPermission){s.textContent='Android media access: allowed · 0 indexed audio files found. Elya also checked file extensions. If the MP3 is still missing, move it into Music/Downloads or use Choose Music Folder.'}};

  // Extra protection against edge pull / bounce reload behavior.
  document.documentElement.style.overscrollBehavior='none';
  if(document.body)document.body.style.overscrollBehavior='none';
})();</script>'''
if 'elya108Script' not in h:
    h=h.replace('</body>',script+'</body>',1)

p.write_text(h,encoding='utf-8')
print('Elya 1.0.8 UI + extended MP3 scan applied')

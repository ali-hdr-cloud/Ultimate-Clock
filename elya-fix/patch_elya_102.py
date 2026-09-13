from pathlib import Path
import re

root = Path('.')
java = root/'app/src/main/java/com/elya/music/MainActivity.java'
s = java.read_text(encoding='utf-8')

imports = {
    'import android.Manifest;': ('import android.app.Activity;', 'import android.app.Activity;\nimport android.Manifest;'),
    'import android.content.ContentUris;': ('import android.content.ContentResolver;', 'import android.content.ContentResolver;\nimport android.content.ContentUris;'),
    'import android.content.pm.PackageManager;': ('import android.content.Context;', 'import android.content.Context;\nimport android.content.pm.PackageManager;'),
    'import android.provider.MediaStore;': ('import android.provider.OpenableColumns;', 'import android.provider.OpenableColumns;\nimport android.provider.MediaStore;'),
    'import java.util.Set;': ('import java.util.Map;', 'import java.util.Map;\nimport java.util.Set;\nimport java.util.HashSet;')
}
for needle, (anchor, replacement) in imports.items():
    if needle not in s:
        if anchor not in s:
            raise SystemExit(f'import anchor missing: {anchor}')
        s = s.replace(anchor, replacement, 1)

if 'REQ_AUDIO_PERMISSION' not in s:
    s = s.replace(
        'private static final int REQ_FILE = 4102;',
        'private static final int REQ_FILE = 4102;\n    private static final int REQ_AUDIO_PERMISSION = 4103;',
        1
    )

old_bridge = '''        @JavascriptInterface
        public void restoreMusicFolder() {
            String value = getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_TREE, null);
            if (value != null) {
                scanTree(Uri.parse(value), false);
            }
        }

        @JavascriptInterface
        public void rescanMusicFolder() {
            String value = getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_TREE, null);
            if (value != null) {
                scanTree(Uri.parse(value), false);
            } else {
                chooseMusicFolder();
            }
        }'''
new_bridge = '''        @JavascriptInterface
        public void restoreMusicFolder() {
            main.post(() -> ensureAudioPermissionAndScan());
        }

        @JavascriptInterface
        public void rescanMusicFolder() {
            main.post(() -> ensureAudioPermissionAndScan());
        }

        @JavascriptInterface
        public void scanAllDeviceMusic() {
            main.post(() -> ensureAudioPermissionAndScan());
        }'''
if old_bridge not in s:
    raise SystemExit('bridge target missing')
s = s.replace(old_bridge, new_bridge, 1)

old_page = '''            if (APP_URL.equals(url)) {
                String saved = getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_TREE, null);
                if (saved != null) {
                    main.postDelayed(() -> scanTree(Uri.parse(saved), false), 350);
                }
            }'''
new_page = '''            if (APP_URL.equals(url)) {
                main.postDelayed(() -> ensureAudioPermissionAndScan(), 350);
            }'''
if old_page not in s:
    raise SystemExit('page startup target missing')
s = s.replace(old_page, new_page, 1)

media_methods = r'''
    private boolean hasAudioPermission() {
        if (Build.VERSION.SDK_INT >= 33) {
            return checkSelfPermission(Manifest.permission.READ_MEDIA_AUDIO) == PackageManager.PERMISSION_GRANTED;
        }
        if (Build.VERSION.SDK_INT >= 23) {
            return checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED;
        }
        return true;
    }

    private void ensureAudioPermissionAndScan() {
        if (hasAudioPermission()) {
            scanAllDeviceMusic();
            return;
        }
        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(new String[]{Manifest.permission.READ_MEDIA_AUDIO}, REQ_AUDIO_PERMISSION);
        } else if (Build.VERSION.SDK_INT >= 23) {
            requestPermissions(new String[]{Manifest.permission.READ_EXTERNAL_STORAGE}, REQ_AUDIO_PERMISSION);
        } else {
            scanAllDeviceMusic();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_AUDIO_PERMISSION) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            scanAllDeviceMusic();
        } else {
            fallbackToFolderPickerPermission();
        }
    }

    private void fallbackToFolderPickerPermission() {
        String saved = getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_TREE, null);
        if (saved != null) {
            js("window.__elyaNativePermissionFallback && window.__elyaNativePermissionFallback(true);");
            scanTree(Uri.parse(saved), false);
        } else {
            js("window.__elyaNativePermissionFallback && window.__elyaNativePermissionFallback(false);");
        }
    }

    private void scanAllDeviceMusic() {
        io.execute(() -> {
            try {
                js("window.__elyaNativeScanStarted && window.__elyaNativeScanStarted('Device music');");
                ArrayList<JSONObject> items = new ArrayList<>();
                synchronized (mediaMap) { mediaMap.clear(); }

                Set<String> seenUris = new HashSet<>();
                int successfulVolumes = 0;

                if (Build.VERSION.SDK_INT >= 29) {
                    Set<String> volumes = MediaStore.getExternalVolumeNames(this);
                    if (volumes == null || volumes.isEmpty()) {
                        volumes = new HashSet<>();
                        volumes.add(MediaStore.VOLUME_EXTERNAL_PRIMARY);
                    }
                    for (String volume : volumes) {
                        Uri collection = MediaStore.Audio.Media.getContentUri(volume);
                        if (scanMediaCollection(collection, volume, items, seenUris)) {
                            successfulVolumes++;
                        }
                    }
                } else {
                    if (scanMediaCollection(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,
                            "external", items, seenUris)) {
                        successfulVolumes++;
                    }
                }

                if (successfulVolumes == 0) {
                    js("window.__elyaNativeScanError && window.__elyaNativeScanError("
                            + JSONObject.quote("Android could not read the device music library. You can still choose a folder manually.") + ");");
                    return;
                }

                JSONArray arr = new JSONArray();
                for (JSONObject o : items) arr.put(o);
                js("window.__elyaReceiveNativeLibrary && window.__elyaReceiveNativeLibrary("
                        + arr.toString() + "," + JSONObject.quote("Device Music") + ");");
            } catch (Exception e) {
                js("window.__elyaNativeScanError && window.__elyaNativeScanError("
                        + JSONObject.quote("Could not scan device music. You can still choose a folder manually.") + ");");
            }
        });
    }

    private boolean scanMediaCollection(Uri collection, String volumeName,
                                        ArrayList<JSONObject> out, Set<String> seenUris) {
        String[] projection = new String[]{
                MediaStore.Audio.Media._ID,
                MediaStore.Audio.Media.DISPLAY_NAME,
                MediaStore.Audio.Media.TITLE,
                MediaStore.Audio.Media.ARTIST,
                MediaStore.Audio.Media.ALBUM,
                MediaStore.Audio.Media.DURATION,
                MediaStore.Audio.Media.MIME_TYPE,
                MediaStore.Audio.Media.SIZE,
                MediaStore.Audio.Media.YEAR,
                MediaStore.Audio.Media.TRACK
        };

        try (Cursor c = getContentResolver().query(
                collection, projection, null, null,
                MediaStore.Audio.Media.DATE_ADDED + " DESC")) {
            if (c == null) return false;

            int idCol = c.getColumnIndex(MediaStore.Audio.Media._ID);
            int nameCol = c.getColumnIndex(MediaStore.Audio.Media.DISPLAY_NAME);
            int titleCol = c.getColumnIndex(MediaStore.Audio.Media.TITLE);
            int artistCol = c.getColumnIndex(MediaStore.Audio.Media.ARTIST);
            int albumCol = c.getColumnIndex(MediaStore.Audio.Media.ALBUM);
            int durationCol = c.getColumnIndex(MediaStore.Audio.Media.DURATION);
            int mimeCol = c.getColumnIndex(MediaStore.Audio.Media.MIME_TYPE);
            int sizeCol = c.getColumnIndex(MediaStore.Audio.Media.SIZE);
            int yearCol = c.getColumnIndex(MediaStore.Audio.Media.YEAR);
            int trackCol = c.getColumnIndex(MediaStore.Audio.Media.TRACK);

            while (c.moveToNext()) {
                if (idCol < 0) continue;
                long id = c.getLong(idCol);
                Uri uri = ContentUris.withAppendedId(collection, id);
                String key = uri.toString();
                if (!seenUris.add(key)) continue;

                String fileName = stringAt(c, nameCol);
                String title = cleanUnknown(stringAt(c, titleCol));
                String artist = cleanUnknown(stringAt(c, artistCol));
                String album = cleanUnknown(stringAt(c, albumCol));
                String mime = stringAt(c, mimeCol);
                long durationMs = longAt(c, durationCol);
                long size = longAt(c, sizeCol);
                int year = intAt(c, yearCol);
                int track = intAt(c, trackCol);

                if (durationMs > 0 && durationMs <= 60000L) continue;
                if (!isAudio(fileName, mime)) continue;

                String token = Integer.toHexString(key.hashCode()) + "_"
                        + Integer.toHexString((volumeName + ":" + id).hashCode());
                synchronized (mediaMap) {
                    mediaMap.put(token, new MediaEntry(uri, normalizeMime(fileName, mime), size, fileName));
                }

                try {
                    JSONObject o = new JSONObject();
                    o.put("fileKey", key);
                    o.put("fileName", fileName);
                    o.put("title", title.isEmpty() ? stripExt(fileName) : title);
                    o.put("artist", artist);
                    o.put("album", album);
                    o.put("genre", "");
                    o.put("year", year > 0 ? String.valueOf(year) : "");
                    o.put("trackNo", track > 0 ? String.valueOf(track) : "");
                    o.put("albumArtist", "");
                    o.put("discNo", 1);
                    o.put("duration", durationMs > 0 ? durationMs / 1000.0 : 0);
                    o.put("url", "https://" + MEDIA_HOST + "/audio/" + token);
                    out.add(o);

                    int found = out.size();
                    if (found == 1 || found % 25 == 0) {
                        js("window.__elyaNativeScanProgress && window.__elyaNativeScanProgress(" + found + ");");
                    }
                } catch (Exception ignored) {}
            }
            return true;
        } catch (SecurityException denied) {
            return false;
        } catch (Exception providerError) {
            return false;
        }
    }

    private static String stringAt(Cursor c, int col) {
        if (col < 0 || c.isNull(col)) return "";
        String v = c.getString(col);
        return v == null ? "" : v.trim();
    }

    private static long longAt(Cursor c, int col) {
        if (col < 0 || c.isNull(col)) return 0;
        try { return c.getLong(col); } catch (Exception e) { return 0; }
    }

    private static int intAt(Cursor c, int col) {
        if (col < 0 || c.isNull(col)) return 0;
        try { return c.getInt(col); } catch (Exception e) { return 0; }
    }

    private static String cleanUnknown(String value) {
        if (value == null) return "";
        String v = value.trim();
        if ("<unknown>".equalsIgnoreCase(v) || "unknown".equalsIgnoreCase(v)) return "";
        return v;
    }

'''

if 'private boolean hasAudioPermission()' not in s:
    anchor = '\n    private void scanTree(Uri treeUri, boolean userInitiated) {'
    if anchor not in s:
        raise SystemExit('scanTree anchor missing')
    s = s.replace(anchor, '\n' + media_methods + anchor, 1)

java.write_text(s, encoding='utf-8')

manifest = root/'app/src/main/AndroidManifest.xml'
m = manifest.read_text(encoding='utf-8')
if 'android.permission.READ_MEDIA_AUDIO' not in m:
    m = m.replace(
        '<uses-permission android:name="android.permission.INTERNET" />',
        '<uses-permission android:name="android.permission.INTERNET" />\n'
        '    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO" />\n'
        '    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" android:maxSdkVersion="32" />',
        1
    )
manifest.write_text(m, encoding='utf-8')

html = root/'app/src/main/assets/index.html'
h = html.read_text(encoding='utf-8')

if '__elyaNativePermissionFallback' not in h:
    anchor = '''window.__elyaNativeScanError = function(message){
'''
    extra = '''window.__elyaNativePermissionFallback = function(hasSavedFolder){
  folderScanBusy = false;
  setFolderStatus?.('Music permission not granted · folder mode available', 'warn');
  $('#folderGate')?.classList.add('open');
  const card = $('#folderGate')?.querySelector('.folder-gate-card');
  const title = card?.querySelector('h2');
  const desc = card?.querySelector('p');
  if(title) title.textContent = 'Allow music access or choose a folder';
  if(desc) desc.textContent = hasSavedFolder
    ? 'Elya is using your previously selected folder because device-wide music access was not allowed.'
    : 'To scan all music automatically, allow Music & Audio access. You can also choose one folder manually.';
  toast?.('Music access was not allowed. Folder mode is still available.');
};

'''
    if anchor not in h:
        raise SystemExit('HTML permission fallback anchor missing')
    h = h.replace(anchor, extra + anchor, 1)

html.write_text(h, encoding='utf-8')

gradle = root/'app/build.gradle'
g = gradle.read_text(encoding='utf-8')
g = re.sub(r'versionCode\s+2\b', 'versionCode 3', g, count=1)
g = re.sub(r"versionName\s+'1\.0\.1'", "versionName '1.0.2'", g, count=1)
gradle.write_text(g, encoding='utf-8')

print('Elya Android 1.0.2 automatic MediaStore scan applied')

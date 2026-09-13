from pathlib import Path
import re

root=Path('.')
java=root/'app/src/main/java/com/elya/music/MainActivity.java'
s=java.read_text(encoding='utf-8')

if 'import android.media.MediaExtractor;' not in s:
    s=s.replace('import android.media.MediaMetadataRetriever;', 'import android.media.MediaMetadataRetriever;\nimport android.media.MediaExtractor;\nimport android.media.MediaFormat;\nimport android.os.ParcelFileDescriptor;')

helper='''
    private boolean setRetrieverSource(MediaMetadataRetriever mmr, Uri uri) {
        try {
            mmr.setDataSource(this, uri);
            return true;
        } catch (Exception first) {
            try (ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r")) {
                if (pfd == null) return false;
                mmr.setDataSource(pfd.getFileDescriptor());
                return true;
            } catch (Exception second) {
                return false;
            }
        }
    }

    private long extractorDurationMs(Uri uri) {
        MediaExtractor extractor = new MediaExtractor();
        try (ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r")) {
            if (pfd == null) return 0;
            extractor.setDataSource(pfd.getFileDescriptor());
            long bestUs = 0;
            for (int i = 0; i < extractor.getTrackCount(); i++) {
                MediaFormat format = extractor.getTrackFormat(i);
                if (format.containsKey(MediaFormat.KEY_DURATION))
                    bestUs = Math.max(bestUs, format.getLong(MediaFormat.KEY_DURATION));
            }
            return bestUs > 0 ? bestUs / 1000L : 0;
        } catch (Exception ignored) {
            return 0;
        } finally {
            try { extractor.release(); } catch (Exception ignored) {}
        }
    }
'''
if 'private boolean setRetrieverSource' not in s:
    s=s.replace('\n    private JSONObject describeAudio(', helper+'\n    private JSONObject describeAudio(',1)

s=s.replace('''            mmr.setDataSource(this, uri);
            long durationMs = parseLong(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
            if (durationMs <= 60000) return null;''','''            if (!setRetrieverSource(mmr, uri)) return null;
            long durationMs = parseLong(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
            if (durationMs <= 0) durationMs = extractorDurationMs(uri);
            if (durationMs > 0 && durationMs <= 60000) return null;''')

s=s.replace('''                DocumentsContract.Document.COLUMN_MIME_TYPE,
                DocumentsContract.Document.COLUMN_SIZE,
                DocumentsContract.Document.COLUMN_LAST_MODIFIED
''','''                DocumentsContract.Document.COLUMN_MIME_TYPE,
                DocumentsContract.Document.COLUMN_SIZE
''')

if '__elyaNativeScanProgress' not in s:
    s=s.replace('''                if (!isAudio(name, mime)) continue;

                Uri docUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, docId);''','''                if (!isAudio(name, mime)) continue;

                final int found = out.size() + 1;
                if (found == 1 || found % 10 == 0)
                    js("window.__elyaNativeScanProgress && window.__elyaNativeScanProgress(" + found + ");");

                Uri docUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, docId);''')
java.write_text(s,encoding='utf-8')

html=root/'app/src/main/assets/index.html'
h=html.read_text(encoding='utf-8')
h=h.replace("""window.__elyaReceiveNativeLibrary = async function(items, folderName){
  if(!Array.isArray(items)) return;
  const seen = new Set();
  setFolderStatus?.(`Connected · ${folderName || 'Android Music'}`, 'good');
""","""window.__elyaReceiveNativeLibrary = async function(items, folderName){
  if(!Array.isArray(items)) return;
  const seen = new Set();
  const nativeFolderName = folderName || 'Android Music';
  folderScanBusy = true;
  updateFolderUI?.(nativeFolderName);
  setFolderStatus?.(`Syncing ${items.length} songs…`, 'scanning');
""")

old="""  render();
  renderResume?.();
  renderPlaylists?.();
  updateCurrentUI?.();

  if(!items.length) toast?.('No playable audio longer than 1 minute was found.');
  else toast?.(`${items.length} songs synced from ${folderName || 'your folder'}.`);
};

window.__elyaNativeScanStarted = function(folderName){
  setFolderStatus?.(`Scanning · ${folderName || 'Music folder'}`, 'warn');
};

window.__elyaNativeScanError = function(message){
  setFolderStatus?.('Folder permission needed', 'warn');
  toast?.(message || 'Could not read this music folder.');
};
"""
new="""  render();
  renderResume?.();
  renderPlaylists?.();
  updateCurrentUI?.();

  folderScanBusy = false;
  updateFolderUI?.(nativeFolderName);
  $('#folderGate')?.classList.remove('open');
  updateRecoveryFolderState?.();
  if(!items.length){
    setFolderStatus?.('Done · no playable songs found in this folder', 'success');
    toast?.('No playable audio was found in this folder.');
  }else{
    setFolderStatus?.(`Done · ${items.length} songs synced`, 'success');
    toast?.(`${items.length} songs synced from ${nativeFolderName}.`);
  }
};

window.__elyaNativeScanStarted = function(folderName){
  folderScanBusy = true;
  const name = folderName || 'Music folder';
  updateFolderUI?.(name);
  setFolderStatus?.(`Scanning · ${name}`, 'scanning');
};

window.__elyaNativeScanProgress = function(count){
  setFolderStatus?.(`Scanning… found ${count} audio file${count===1?'':'s'}`, 'scanning');
};

window.__elyaNativeScanError = function(message){
  folderScanBusy = false;
  setFolderStatus?.('Folder scan failed · tap Change Folder and try again', 'warn');
  $('#folderGate')?.classList.add('open');
  toast?.(message || 'Could not read this music folder.');
};
"""
if old not in h:
    raise SystemExit('Android bridge target not found')
h=h.replace(old,new,1)
html.write_text(h,encoding='utf-8')

gradle=root/'app/build.gradle'
g=gradle.read_text(encoding='utf-8')
g=re.sub(r'versionCode\s+1\b','versionCode 2',g,count=1)
g=re.sub(r"versionName\s+'1\.0\.0'","versionName '1.0.1'",g,count=1)
gradle.write_text(g,encoding='utf-8')
print('Elya Android 1.0.1 scan fix applied')

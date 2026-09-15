from pathlib import Path
import re

r=Path('.')

# Version
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+11\b','versionCode 12',s,count=1)
s=re.sub(r"versionName\s+'1\.1\.0'","versionName '1.1.1'",s,count=1)
p.write_text(s,encoding='utf-8')

# Native diagnostics version
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_110','// ELYA_NATIVE_CORE_110\n    // ELYA_NATIVE_CORE_111',1)
s=s.replace('return "elya-bridge-1.1.0";','return "elya-bridge-1.1.1";',1)
s=s.replace('o.put("core", "1.1.0");','o.put("core", "1.1.1");',1)
p.write_text(s,encoding='utf-8')

# HTML: repair Android-library receiver. 1.1.0 called songBase(), but that helper did not exist.
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')

helper=r'''function songBase(input={}){
  const title=input.title||((input.fileName||'Unknown Song').replace(/\.[^.]+$/,''))||'Unknown Song';
  const cover=input.cover||makeCover(title);
  const out=Object.assign({
    id:uid(),fileKey:'',fileName:'',folderRelPath:'',blob:null,url:'',
    title,artist:'Unknown Artist',album:'Local Music',genre:'',year:'',trackNo:'',albumArtist:'',discNo:1,
    composer:'',bpm:'',explicit:false,notes:'',tags:[],category:'music',favorite:false,pinned:false,hidden:false,rating:0,
    cover,defaultCover:cover,coverZoom:1,coverX:50,coverY:50,duration:0,addedAt:Date.now(),lastPlayed:0,playCount:0,
    lyrics:'',peaks:[],deletedAt:0,lastPosition:0,discStyle:'',mood:'',energy:50,private:false,introEnd:0,outroStart:0,
    fadeIn:0,fadeOut:0,bookmarks:[],lyricsTranslation:'',lyricsRomanization:'',id3Read:false,completed:false,
    fromMusicFolder:false,nativeAndroid:false,lastSeenAt:Date.now()
  },input||{});
  if(!out.cover)out.cover=cover;
  if(!out.defaultCover)out.defaultCover=out.cover;
  if(String(out.category||'').toLowerCase()==='local')out.category='music';
  return out;
}

'''
marker='/* ===== ELYA ANDROID APK BRIDGE ===== */'
if 'function songBase(input={})' not in h:
    if marker not in h:
        raise SystemExit('Android bridge marker missing')
    h=h.replace(marker,helper+marker,1)

pattern=r'''window\.__elyaReceiveNativeLibrary = async function\(items, folderName\)\{.*?\n\};\n\nwindow\.__elyaNativeScanStarted'''
replacement=r'''window.__elyaReceiveNativeLibrary = async function(items, folderName){
  if(!Array.isArray(items)) return;
  const seen = new Set();
  const nativeFolderName = folderName || 'Android Music';
  let imported = 0, failed = 0;
  folderScanBusy = true;
  updateFolderUI?.(nativeFolderName);
  setFolderStatus?.(`Syncing ${items.length} songs…`, 'scanning');

  for(const item of items){
    if(!item || !item.fileKey || !item.url){ failed++; continue; }
    seen.add(item.fileKey);
    try{
      let s = state.songs.find(x => x.fileKey === item.fileKey || x.folderRelPath === item.fileKey);
      const cover = item.cover || (s && s.cover) || makeCover(item.title || item.fileName || 'Music');

      if(s){
        s.url = item.url;
        s.nativeAndroid = true;
        s.fromMusicFolder = true;
        s.folderRelPath = item.fileKey;
        s.fileKey = item.fileKey;
        s.fileName = item.fileName || s.fileName;
        s.duration = Number(item.duration || s.duration || 0);
        s.category = 'music';
        if(!s.userEditedTitle && item.title) s.title = item.title;
        if(item.artist) s.artist = item.artist;
        if(item.album) s.album = item.album;
        if(item.genre) s.genre = item.genre;
        if(item.year) s.year = item.year;
        if(item.trackNo) s.trackNo = item.trackNo;
        if(item.albumArtist) s.albumArtist = item.albumArtist;
        if(item.discNo) s.discNo = item.discNo;
        if(item.cover) s.cover = item.cover;
        if(!s.defaultCover) s.defaultCover = s.cover || cover;
        s.lastSeenAt = Date.now();
        Promise.resolve(persistSong(s)).catch(()=>{});
      } else {
        s = songBase({
          id: uid(),
          title: item.title || (item.fileName || 'Unknown Song').replace(/\.[^.]+$/,''),
          artist: item.artist || 'Unknown Artist',
          album: item.album || 'Local Music',
          category: 'music',
          genre: item.genre || '',
          year: item.year || '',
          trackNo: item.trackNo || '',
          albumArtist: item.albumArtist || '',
          discNo: item.discNo || 1,
          fileName: item.fileName || '',
          folderRelPath: item.fileKey,
          fileKey: item.fileKey,
          duration: Number(item.duration || 0),
          cover,
          defaultCover: cover,
          blob: null,
          url: item.url,
          fromMusicFolder: true,
          nativeAndroid: true,
          addedAt: Date.now(),
          lastSeenAt: Date.now()
        });
        state.songs.push(s);
        Promise.resolve(persistSong(s)).catch(()=>{});
      }
      imported++;
    }catch(err){
      failed++;
      console.error('Elya native song sync failed', item?.fileName || item?.fileKey, err);
    }
  }

  // Only remove stale native rows after a successful non-empty scan. A transient 0-result scan must not wipe the cached library.
  if(seen.size > 0){
    const stale = state.songs.filter(s => s.nativeAndroid && s.fromMusicFolder && !s.deletedAt && !seen.has(s.fileKey));
    if(stale.some(s => s.id === state.currentId)){
      try{ audio.pause(); audio.removeAttribute('src'); audio.load(); }catch(e){}
      state.currentId = null;
    }
    for(const s of stale){
      state.songs = state.songs.filter(x => x.id !== s.id);
      Promise.resolve(dbDelete(s.id)).catch(()=>{});
    }
  }

  render();
  renderResume?.();
  renderPlaylists?.();
  updateCurrentUI?.();
  if(!state.currentId && activeSongs().length){
    try{ loadSong(activeSongs()[0].id,false); }catch(e){}
  }

  folderScanBusy = false;
  updateFolderUI?.(nativeFolderName);
  $('#folderGate')?.classList.remove('open');
  updateRecoveryFolderState?.();
  const visible = activeSongs().filter(s=>s.nativeAndroid&&!s.deletedAt).length;
  if(!items.length){
    setFolderStatus?.(`Scan returned 0 files · ${visible} cached songs kept`, 'warn');
    toast?.(visible ? `${visible} cached songs kept.` : 'No audio files were returned by Android.');
  }else if(failed){
    setFolderStatus?.(`Done · ${imported} synced · ${failed} skipped`, 'warn');
    toast?.(`${imported} songs synced · ${failed} skipped.`);
  }else{
    setFolderStatus?.(`Done · ${imported} songs visible`, 'success');
    toast?.(`${imported} songs synced from ${nativeFolderName}.`);
  }
};

window.__elyaNativeScanStarted'''
new_h,n=re.subn(pattern,replacement,h,count=1,flags=re.S)
if n!=1:
    raise SystemExit('Native library receiver replacement failed')
h=new_h

# Runtime self-check used by diagnostics and CI inspection.
if 'window.__elyaNativeLibraryReceiverVersion' not in h:
    h=h.replace(marker,"window.__elyaNativeLibraryReceiverVersion='1.1.1';\n"+marker,1)

p.write_text(h,encoding='utf-8')
print('Elya 1.1.1 native library sync runtime fix applied')

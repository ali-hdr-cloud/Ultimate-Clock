from pathlib import Path
import re

r=Path('.')

# Version
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+12\b','versionCode 13',s,count=1)
s=re.sub(r"versionName\s+'1\.1\.1'","versionName '1.1.2'",s,count=1)
p.write_text(s,encoding='utf-8')

# Native core version + stronger media response headers / file-origin compatibility.
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_111','// ELYA_NATIVE_CORE_111\n    // ELYA_NATIVE_CORE_112',1)
s=s.replace('return "elya-bridge-1.1.1";','return "elya-bridge-1.1.2";',1)
s=s.replace('o.put("core", "1.1.1");','o.put("core", "1.1.2");',1)

settings_anchor='''        s.setAllowFileAccess(true);\n        s.setAllowContentAccess(true);'''
settings_repl='''        s.setAllowFileAccess(true);\n        s.setAllowContentAccess(true);\n        // Elya UI is loaded from android_asset while audio is served through the local\n        // https://elya.local bridge. Allow that local asset page to request its media.\n        s.setAllowFileAccessFromFileURLs(true);\n        s.setAllowUniversalAccessFromFileURLs(true);'''
if settings_anchor not in s:
    raise SystemExit('WebSettings anchor missing')
s=s.replace(settings_anchor,settings_repl,1)

cors_anchor='''        h.put("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");\n        return h;'''
cors_repl='''        h.put("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");\n        h.put("Cross-Origin-Resource-Policy", "cross-origin");\n        h.put("Timing-Allow-Origin", "*");\n        return h;'''
if cors_anchor not in s:
    raise SystemExit('CORS headers anchor missing')
s=s.replace(cors_anchor,cors_repl,1)
p.write_text(s,encoding='utf-8')

# HTML audio playback repair.
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')

# crossorigin MUST exist before src is assigned. Without it, createMediaElementSource can
# intentionally output silence for Elya's https://elya.local media bridge.
h=h.replace('<audio id="audio"></audio>', '<audio id="audio" crossorigin="anonymous" preload="metadata" playsinline></audio>', 1)
h=h.replace('<audio id="preloadAudio" preload="auto" hidden></audio>', '<audio id="preloadAudio" crossorigin="anonymous" preload="auto" playsinline hidden></audio>', 1)

# Strengthen initAudioGraph: ensure crossOrigin is set before graph creation, and if any
# later graph node fails, connect the source directly so playback never silently disappears.
old=r'''function initAudioGraph(){
  if(audioCtx)return;
  try{
    audioCtx=new (window.AudioContext||window.webkitAudioContext)();
    sourceNode=audioCtx.createMediaElementSource(audio);
    bassNode=audioCtx.createBiquadFilter();bassNode.type='lowshelf';bassNode.frequency.value=200;
    vocalNode=audioCtx.createBiquadFilter();vocalNode.type='peaking';vocalNode.frequency.value=1200;vocalNode.Q.value=1;
    trebleNode=audioCtx.createBiquadFilter();trebleNode.type='highshelf';trebleNode.frequency.value=3500;
    analyser=audioCtx.createAnalyser();analyser.fftSize=256;
    masterGain=audioCtx.createGain();
    sourceNode.connect(bassNode).connect(vocalNode).connect(trebleNode).connect(analyser).connect(masterGain).connect(audioCtx.destination);
    applyEQ();drawVisualizer();
  }catch(e){}
}'''
new=r'''function initAudioGraph(){
  if(audioCtx)return;
  try{
    audio.crossOrigin='anonymous';
    preloadAudio.crossOrigin='anonymous';
    audioCtx=new (window.AudioContext||window.webkitAudioContext)();
    sourceNode=audioCtx.createMediaElementSource(audio);
    try{
      bassNode=audioCtx.createBiquadFilter();bassNode.type='lowshelf';bassNode.frequency.value=200;
      vocalNode=audioCtx.createBiquadFilter();vocalNode.type='peaking';vocalNode.frequency.value=1200;vocalNode.Q.value=1;
      trebleNode=audioCtx.createBiquadFilter();trebleNode.type='highshelf';trebleNode.frequency.value=3500;
      analyser=audioCtx.createAnalyser();analyser.fftSize=256;
      masterGain=audioCtx.createGain();
      sourceNode.connect(bassNode).connect(vocalNode).connect(trebleNode).connect(analyser).connect(masterGain).connect(audioCtx.destination);
      applyEQ();drawVisualizer();
    }catch(graphErr){
      try{sourceNode.connect(audioCtx.destination)}catch(_){}
      console.error('Elya audio graph fallback',graphErr);
      window.__elyaAudioGraphFallback=true;
    }
  }catch(e){
    console.error('Elya audio graph unavailable',e);
    window.__elyaAudioGraphError=String(e?.message||e||'Audio graph unavailable');
  }
}'''
if old not in h:
    raise SystemExit('initAudioGraph block missing')
h=h.replace(old,new,1)

# Make play failures visible instead of swallowing them.
old="async function playAudio(){initAudioGraph();if(audioCtx?.state==='suspended')await audioCtx.resume();audio.play().catch(()=>{})}"
new="""async function playAudio(){
  initAudioGraph();
  try{
    if(audioCtx?.state==='suspended')await audioCtx.resume();
    audio.muted=false;
    if(!Number.isFinite(audio.volume)||audio.volume<=0)audio.volume=Math.max(.01,Number(settings.volume)||1);
    await audio.play();
  }catch(err){
    console.error('Elya playback failed',err,audio.error);
    const code=audio.error?.code||0;
    const msg=code===4?'This audio format/source could not be opened.':code===3?'This audio file could not be decoded.':code===2?'The audio source could not be loaded.':'Could not start audio playback.';
    toast?.(msg);
  }
}"""
if old not in h:
    raise SystemExit('playAudio anchor missing')
h=h.replace(old,new,1)

# Ensure dynamically loaded Android songs always request with CORS before assigning src.
old="state.currentId=id;audio.src=s.url;audio.playbackRate=Number(settings.defaultSpeed)||1;state.crossfadeBusy=false;updateCurrentUI();renderTracks();drawWaveform();"
new="state.currentId=id;audio.crossOrigin='anonymous';audio.src=s.url;audio.playbackRate=Number(settings.defaultSpeed)||1;state.crossfadeBusy=false;updateCurrentUI();renderTracks();drawWaveform();"
if old not in h:
    raise SystemExit('loadSong src anchor missing')
h=h.replace(old,new,1)

old="smartCrossfadeActive=true;smartCrossfadeNextId=n.id;preloadAudio.src=n.url;"
new="smartCrossfadeActive=true;smartCrossfadeNextId=n.id;preloadAudio.crossOrigin='anonymous';preloadAudio.src=n.url;"
if old in h:
    h=h.replace(old,new,1)

# Playback diagnostics: report media-level failures and successful starts.
marker='/* Audio graph + visualizer */'
diag=r'''/* Elya 1.1.2 Android playback diagnostics */
audio.crossOrigin='anonymous';
preloadAudio.crossOrigin='anonymous';
window.__elyaPlaybackVersion='1.1.2';
audio.addEventListener('error',()=>{
  const code=audio.error?.code||0;
  const labels={1:'Playback aborted',2:'Audio network/source error',3:'Audio decode error',4:'Audio source not supported'};
  console.error('Elya media error',code,audio.error,audio.currentSrc||audio.src);
  toast?.(labels[code]||'Audio playback error');
});
audio.addEventListener('playing',()=>{window.__elyaLastAudioPlayingAt=Date.now()});

'''
if 'window.__elyaPlaybackVersion' not in h:
    if marker not in h:
        raise SystemExit('audio marker missing')
    h=h.replace(marker,diag+marker,1)

p.write_text(h,encoding='utf-8')
print('Elya 1.1.2 Android audio playback / WebAudio CORS fix applied')

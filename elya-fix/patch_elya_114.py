from pathlib import Path
import re

r=Path('.')

# Version
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+14\b','versionCode 15',s,count=1)
s=re.sub(r"versionName\s+'1\.1\.3'","versionName '1.1.4'",s,count=1)
p.write_text(s,encoding='utf-8')

# Native diagnostics version only.
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_113','// ELYA_NATIVE_CORE_113\n    // ELYA_NATIVE_CORE_114',1)
s=s.replace('return "elya-bridge-1.1.3";','return "elya-bridge-1.1.4";',1)
s=s.replace('o.put("core", "1.1.3");','o.put("core", "1.1.4");',1)
p.write_text(s,encoding='utf-8')

# Fix the real startup crash introduced in 1.1.2:
# preloadAudio was referenced before its later const declaration, which throws a TDZ
# ReferenceError and aborts the main UI script before click handlers are registered.
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')

old="const audio=$('#audio');"
new="const audio=$('#audio'),preloadAudio=$('#preloadAudio');"
if old not in h:
    raise SystemExit('audio declaration anchor missing')
h=h.replace(old,new,1)

late="const preloadAudio=$('#preloadAudio');"
if h.count(late)!=1:
    raise SystemExit(f'expected exactly one late preloadAudio declaration, found {h.count(late)}')
h=h.replace(late,'/* preloadAudio is initialized with audio above (Elya 1.1.4 runtime fix). */',1)

h=h.replace("window.__elyaPlaybackVersion='1.1.2';","window.__elyaPlaybackVersion='1.1.4';",1)

# Runtime marker: if this line exists, the main script got past the audio declarations.
marker="const audio=$('#audio'),preloadAudio=$('#preloadAudio');"
h=h.replace(marker,marker+"\nwindow.__elyaMainRuntimeVersion='1.1.4';",1)

# Add an early, non-blocking global error recorder for diagnostics. It must never intercept events.
head_marker='</head>'
error_guard='''<script id="elya114RuntimeGuard">\nwindow.__elyaRuntimeErrors=[];\nwindow.addEventListener('error',function(e){try{window.__elyaRuntimeErrors.push(String(e.message||e.error||'Unknown runtime error'))}catch(_){}},true);\nwindow.addEventListener('unhandledrejection',function(e){try{window.__elyaRuntimeErrors.push(String(e.reason?.message||e.reason||'Unhandled promise rejection'))}catch(_){}},true);\n</script>\n'''
if 'id="elya114RuntimeGuard"' not in h:
    if head_marker not in h:
        raise SystemExit('head marker missing')
    h=h.replace(head_marker,error_guard+head_marker,1)

p.write_text(h,encoding='utf-8')
print('Elya 1.1.4 preloadAudio TDZ/runtime interaction fix applied')

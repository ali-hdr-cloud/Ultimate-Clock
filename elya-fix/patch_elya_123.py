from pathlib import Path
import re

r=Path('.')

# Version 1.2.2
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+17\b','versionCode 18',s,count=1)
s=re.sub(r"versionName\s+'1\.2\.1'","versionName '1.2.2'",s,count=1)
p.write_text(s,encoding='utf-8')

# Native: cover art on normal MediaStore.Audio scan + version markers.
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_121','// ELYA_NATIVE_CORE_121\n    // ELYA_NATIVE_CORE_123',1)
s=s.replace('return "elya-bridge-1.2.1";','return "elya-bridge-1.2.2";',1)
s=s.replace('o.put("core", "1.2.1");','o.put("core", "1.2.2");',1)

old='''                    o.put("_scanSource", "MediaStore.Audio");\n                    o.put("url", "https://" + MEDIA_HOST + "/audio/" + token);\n                    out.add(o);'''
new='''                    o.put("_scanSource", "MediaStore.Audio");\n                    o.put("url", "https://" + MEDIA_HOST + "/audio/" + token);\n                    try {\n                        byte[] embeddedArt = readEmbeddedPicture(uri);\n                        if (embeddedArt != null && embeddedArt.length > 0) o.put("cover", "https://" + MEDIA_HOST + "/cover/" + token);\n                    } catch (Exception ignored) {}\n                    out.add(o);'''
if old not in s: raise SystemExit('MediaStore.Audio embedded cover anchor missing')
s=s.replace(old,new,1)

# Don't label embedded PNG/WebP covers as JPEG.
old='''                return new WebResourceResponse("image/jpeg", null, 200, "OK", corsHeaders(),\n                        new ByteArrayInputStream(art));'''
new='''                String artMime = "image/jpeg";\n                if (art.length >= 12 && (art[0] & 0xff) == 0x89 && art[1] == 'P' && art[2] == 'N' && art[3] == 'G') artMime = "image/png";\n                else if (art.length >= 12 && art[0] == 'R' && art[1] == 'I' && art[2] == 'F' && art[3] == 'F' && art[8] == 'W' && art[9] == 'E' && art[10] == 'B' && art[11] == 'P') artMime = "image/webp";\n                return new WebResourceResponse(artMime, null, 200, "OK", corsHeaders(),\n                        new ByteArrayInputStream(art));'''
if old not in s: raise SystemExit('embedded cover MIME anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# HTML: real 1.2.0 interaction crash fix.
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')
old="const tabs=$('#settingsModal .tabs'),tab=document.createElement('button');tab.className='tab';tab.dataset.settingtab='advanced';tab.textContent='Advanced';tabs.appendChild(tab);"
new="const tabs=$('#settingsModal .elya120-setting-tabs')||$('#settingsModal .tabs');if(!tabs)return;const tab=document.createElement('button');tab.className='tab';tab.dataset.settingtab='advanced';tab.textContent='Advanced';tabs.appendChild(tab);"
if old not in h: raise SystemExit('Advanced Settings null appendChild crash anchor missing')
h=h.replace(old,new,1)

h=h.replace("window.__elyaStabilityVersion='1.2.1';","window.__elyaStabilityVersion='1.2.2';",1)
h=h.replace("window.__elyaSettingsVersion='1.2.0';window.__elyaChatVersion='1.2.0';","window.__elyaSettingsVersion='1.2.2';window.__elyaChatVersion='1.2.2';",1)
h=h.replace("window.__elyaMainRuntimeVersion='1.1.4';","window.__elyaMainRuntimeVersion='1.2.2';",1)
h=h.replace("window.__elyaPlaybackVersion='1.1.4';","window.__elyaPlaybackVersion='1.2.2';",1)
h=h.replace('<strong>Elya 1.2.0</strong>','<strong>Elya 1.2.2</strong>',1)

# Marker used by CI/runtime diagnostics.
marker='/* ===== ELYA ANDROID APK BRIDGE ===== */'
if marker in h and "window.__elyaInteractionVersion='1.2.2';" not in h:
    h=h.replace(marker,"window.__elyaInteractionVersion='1.2.2';\n"+marker,1)

p.write_text(h,encoding='utf-8')
print('Elya 1.2.2 interaction + cover art fix applied')

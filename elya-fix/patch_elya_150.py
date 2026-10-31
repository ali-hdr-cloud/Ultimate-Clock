from pathlib import Path
import re

root = Path('.')
gradle = root / 'app/build.gradle'
g = gradle.read_text(encoding='utf-8')
if "versionName '1.4.0'" not in g or not re.search(r'versionCode\s+21\b', g):
    raise SystemExit('Elya 1.4.0 version anchor missing; refusing unsafe version bump')
g = re.sub(r'versionCode\s+21\b', 'versionCode 22', g, count=1)
g = g.replace("versionName '1.4.0'", "versionName '1.5.0'", 1)
gradle.write_text(g, encoding='utf-8')

html = root / 'app/src/main/assets/index.html'
h = html.read_text(encoding='utf-8')
if 'id="elya150ChatRepair"' in h:
    raise SystemExit('Elya 1.5.0 chat repair already applied')

# Keep the existing native chat bridge and message renderer; restore a guaranteed,
# visible text composer after the existing message list.
style = r"""
<style id="elya150ChatRepairStyle">
#elyaChatsModal #elyaChatThread{min-height:0!important;height:100%!important;display:flex!important;flex-direction:column!important;overflow:hidden!important}
#elyaChatsModal #elyaChatMessages{display:block!important;flex:1 1 auto!important;min-height:0!important;overflow-y:auto!important;overscroll-behavior:contain!important}
#elyaChatsModal .elya120-composer{display:flex!important;flex:0 0 auto!important;align-items:end!important;gap:9px!important;width:100%!important;min-height:62px!important;padding:9px!important;background:var(--panel,#111a28)!important;border-top:1px solid var(--line,rgba(255,255,255,.08))!important;position:relative!important;z-index:8!important;visibility:visible!important;opacity:1!important}
#elyaChatsModal #elyaChatInput{display:block!important;flex:1 1 auto!important;min-width:0!important;width:100%!important;min-height:44px!important;max-height:112px!important;resize:none!important;border:1px solid var(--line,rgba(255,255,255,.12))!important;border-radius:15px!important;padding:12px 14px!important;background:var(--card,rgba(255,255,255,.055))!important;color:var(--text,#fff)!important;font:inherit!important;outline:none!important;box-shadow:none!important}
#elyaChatsModal #elyaChatSend{display:grid!important;flex:0 0 46px!important;width:46px!important;height:46px!important;border-radius:14px!important;place-items:center!important}
#elyaChatsModal #elyaChatInput:focus{border-color:var(--accent,#43c6e8)!important;outline:0!important;box-shadow:0 0 0 2px color-mix(in srgb,var(--accent,#43c6e8) 18%,transparent)!important}
#elyaChatsModal button:focus{outline:none!important;box-shadow:none!important}
#elyaChatsModal button:focus-visible{outline:2px solid color-mix(in srgb,var(--accent,#43c6e8) 55%,transparent)!important;outline-offset:2px!important}
@media(max-width:699px){#elyaChatsModal .elya120-composer{padding:8px 9px max(8px,env(safe-area-inset-bottom))!important}}
</style>
"""
if 'id="elya150ChatRepairStyle"' not in h:
    if '</head>' not in h: raise SystemExit('HTML head close missing')
    h = h.replace('</head>', style + '\n</head>', 1)

script = r"""
<script id="elya150ChatRepair">
(()=>{
  if(window.__elya150ChatRepairLoaded)return;
  window.__elya150ChatRepairLoaded=true;
  const q=s=>document.querySelector(s);
  const ensureComposer=()=>{
    const modal=q('#elyaChatsModal'),thread=q('#elyaChatThread'),messages=q('#elyaChatMessages');
    if(!modal||!thread||!messages)return;
    const composer=thread.querySelector('.elya120-composer');
    if(!composer)return;
    if(composer.previousElementSibling!==messages)messages.insertAdjacentElement('afterend',composer);
    composer.hidden=false;
    composer.style.setProperty('display','flex','important');
    composer.style.setProperty('visibility','visible','important');
    composer.style.setProperty('opacity','1','important');
    const input=q('#elyaChatInput'),send=q('#elyaChatSend');
    if(input){input.disabled=false;input.hidden=false}
    if(send){send.disabled=false;send.hidden=false}
  };
  const oldOpened=window.__elyaChatOpened;
  window.__elyaChatOpened=c=>{try{oldOpened?.(c)}finally{ensureComposer()}};
  const observer=new MutationObserver(()=>{if(q('#elyaChatsModal')?.classList.contains('open'))ensureComposer()});
  const start=()=>{
    const modal=q('#elyaChatsModal');
    if(modal)observer.observe(modal,{childList:true,subtree:true,attributes:true,attributeFilter:['class','style']});
    ensureComposer();
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  window.__elyaChatComposerRepair={ensure:ensureComposer};
})();
</script>
"""
if 'id="elya150ChatRepair"' not in h:
    if '</body>' not in h: raise SystemExit('HTML body close missing')
    h = h.replace('</body>', script + '\n</body>', 1)

# Version markers and in-app diagnostics.
for old, new in [
    ("window.__elyaSocialVersion='1.4.0';", "window.__elyaSocialVersion='1.5.0';"),
    ("window.__elyaChatVersion='1.4.0';", "window.__elyaChatVersion='1.5.0';"),
    ("window.__elyaSettingsVersion='1.4.0';", "window.__elyaSettingsVersion='1.5.0';"),
    ("window.__elyaPlaybackVersion='1.4.0';", "window.__elyaPlaybackVersion='1.5.0';"),
    ("window.__elyaMainRuntimeVersion='1.4.0';", "window.__elyaMainRuntimeVersion='1.5.0';"),
]:
    h = h.replace(old, new, 1)
html.write_text(h, encoding='utf-8')
print('Elya 1.5.0 chat composer repair applied')

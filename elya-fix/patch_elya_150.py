from pathlib import Path
import re

root = Path('.')
gradle = root / 'app/build.gradle'
g = gradle.read_text(encoding='utf-8')
if "versionName '1.4.0'" not in g or not re.search(r'versionCode\\s+21\\b', g):
    raise SystemExit('Elya 1.4.0 version anchor missing; refusing unsafe version bump')
g = re.sub(r'versionCode\\s+21\\b', 'versionCode 22', g, count=1)
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
#elyaChatsModal #elyaChatThread{min-height:0!important;display:flex!important;flex-direction:column!important;overflow:hidden!important}
#elyaChatsModal #elyaChatMessages{flex:1 1 auto!important;min-height:0!important;overflow-y:auto!important;overscroll-behavior:contain!important}
#elyaChatsModal .elya150-composer{display:grid!important;grid-template-columns:minmax(0,1fr) 48px!important;gap:9px!important;align-items:end!important;flex:0 0 auto!important;width:100%!important;padding:10px!important;background:var(--panel,#111a28)!important;border-top:1px solid var(--line,rgba(255,255,255,.08))!important;z-index:8!important}
#elyaChatsModal .elya150-composer textarea{display:block!important;width:100%!important;min-height:44px!important;max-height:112px!important;resize:none!important;border:1px solid var(--line,rgba(255,255,255,.12))!important;border-radius:15px!important;padding:12px 14px!important;background:var(--card,rgba(255,255,255,.055))!important;color:var(--text,#fff)!important;font:inherit!important;outline:none!important;box-shadow:none!important}
#elyaChatsModal .elya150-composer textarea:focus{border-color:var(--accent,#43c6e8)!important;outline:0!important;box-shadow:0 0 0 2px color-mix(in srgb,var(--accent,#43c6e8) 18%,transparent)!important}
#elyaChatsModal .elya150-composer button{width:46px!important;height:46px!important;border-radius:14px!important;display:grid!important;place-items:center!important}
#elyaChatsModal .elya150-composer button:focus,#elyaChatsModal button:focus{outline:none!important}
#elyaChatsModal button:focus-visible{outline:2px solid color-mix(in srgb,var(--accent,#43c6e8) 55%,transparent)!important;outline-offset:2px!important}
@media(max-width:699px){#elyaChatsModal .elya150-composer{padding:8px 9px max(8px,env(safe-area-inset-bottom))!important}}
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
  let activeChatId='', activeUid='', sendLocked=false;
  const native=()=>window.AndroidMusic;
  const ensureComposer=()=>{
    const modal=q('#elyaChatsModal'), thread=q('#elyaChatThread'), messages=q('#elyaChatMessages');
    if(!modal||!thread||!messages)return;
    let composer=q('#elya150ChatComposer');
    if(!composer){
      composer=document.createElement('div');
      composer.id='elya150ChatComposer';
      composer.className='elya150-composer';
      composer.innerHTML='<textarea id="elya150ChatInput" rows="1" maxlength="4000" placeholder="Message" aria-label="Write a message"></textarea><button id="elya150ChatSend" class="primary" type="button" aria-label="Send message" title="Send"><svg><use href="#i-up"></use></svg></button>';
      messages.insertAdjacentElement('afterend',composer);
    }
    composer.hidden=false;
    composer.style.display='grid';
  };
  const setActive=c=>{
    if(!c)return;
    activeChatId=String(c.chatId||'');
    activeUid=String(c.uid||activeUid||'');
    ensureComposer();
  };
  const oldOpened=window.__elyaChatOpened;
  window.__elyaChatOpened=c=>{try{oldOpened?.(c)}catch(e){console.error('Elya chat open callback',e)};setActive(c)};
  const oldAuth=window.__elyaFirebaseAuthState;
  window.__elyaFirebaseAuthState=d=>{try{oldAuth?.(d)}catch(e){console.error('Elya auth callback',e)};activeUid=String(d?.uid||'')};
  const send=()=>{
    const input=q('#elya150ChatInput');
    const value=String(input?.value||'').trim();
    if(!activeChatId||!value||sendLocked)return;
    const bridge=native();
    if(!bridge||typeof bridge.chatSend!=='function'){
      window.toast?.('Chat connection is not ready. Please reopen the chat.');
      return;
    }
    sendLocked=true;
    try{
      bridge.chatSend(activeChatId,value);
      input.value='';
      input.style.height='44px';
      input.focus();
    }catch(e){window.toast?.('Could not send message. Please try again.')}
    finally{setTimeout(()=>{sendLocked=false},450)}
  };
  document.addEventListener('click',e=>{
    if(e.target.closest?.('#elya150ChatSend')){e.preventDefault();send()}
  });
  document.addEventListener('keydown',e=>{
    if(e.target?.id==='elya150ChatInput'&&e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}
  });
  document.addEventListener('input',e=>{
    if(e.target?.id==='elya150ChatInput'){e.target.style.height='44px';e.target.style.height=Math.min(112,e.target.scrollHeight)+'px'}
  });
  const observer=new MutationObserver(()=>{if(q('#elyaChatsModal')?.classList.contains('open'))ensureComposer()});
  const start=()=>{
    const modal=q('#elyaChatsModal');
    if(modal)observer.observe(modal,{childList:true,subtree:true,attributes:true,attributeFilter:['class']});
    ensureComposer();
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
  window.__elyaChatComposerRepair={ensure:ensureComposer,setActive};
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

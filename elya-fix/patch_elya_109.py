from pathlib import Path
import re

r=Path('.')

# Version
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+9\b','versionCode 10',s,count=1)
s=re.sub(r"versionName\s+'1\.0\.8'","versionName '1.0.9'",s,count=1)
p.write_text(s,encoding='utf-8')

# Native core version + allow WebView edge movement again.
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_108','// ELYA_NATIVE_CORE_108\n    // ELYA_NATIVE_CORE_109',1)
s=s.replace('return "elya-bridge-1.0.8";','return "elya-bridge-1.0.9";',1)
s=s.replace('o.put("core", "1.0.8");','o.put("core", "1.0.9");',1)
s=s.replace('        webView.setOverScrollMode(WebView.OVER_SCROLL_NEVER);\n','',1)
p.write_text(s,encoding='utf-8')

# Restore pull-to-refresh with a deliberate gesture at the top of the app.
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')

css=r'''<style id="elya109PullStyle">
html,body{overscroll-behavior-y:auto!important}
#elya109PullRefresh{position:fixed;left:50%;top:8px;z-index:120000;transform:translate(-50%,-76px) scale(.92);opacity:0;pointer-events:none;transition:transform .18s ease,opacity .18s ease;display:flex;align-items:center;gap:9px;padding:10px 14px;border:1px solid var(--line);border-radius:999px;background:rgba(10,14,20,.92);backdrop-filter:blur(14px);box-shadow:0 10px 32px rgba(0,0,0,.32);font-size:12px;color:var(--muted)}
#elya109PullRefresh.show{opacity:1}#elya109PullRefresh.ready{color:var(--text)}
#elya109PullRefresh .elya109-ring{width:18px;height:18px;border-radius:50%;border:2px solid currentColor;border-top-color:transparent;transition:transform .12s linear}
#elya109PullRefresh.refreshing .elya109-ring{animation:elya109spin .65s linear infinite}
@keyframes elya109spin{to{transform:rotate(360deg)}}
</style>'''
if 'elya109PullStyle' not in h:
    h=h.replace('</head>',css+'</head>',1)

indicator=r'''<div id="elya109PullRefresh" aria-hidden="true"><span class="elya109-ring"></span><span id="elya109PullText">Pull to refresh</span></div>'''
if 'id="elya109PullRefresh"' not in h:
    h=h.replace('</body>',indicator+'</body>',1)

script=r'''<script id="elya109PullScript">(()=>{
  const el=document.getElementById('elya109PullRefresh');
  const txt=document.getElementById('elya109PullText');
  if(!el||!txt)return;
  const THRESHOLD=82, MAX=118;
  let startY=0, pull=0, active=false, refreshing=false;
  const top=()=>{
    const root=document.scrollingElement||document.documentElement;
    return Math.max(window.scrollY||0,root?.scrollTop||0)<=1;
  };
  const paint=()=>{
    const y=Math.max(0,Math.min(MAX,pull));
    el.classList.toggle('show',y>5);
    el.classList.toggle('ready',y>=THRESHOLD);
    el.style.transform=`translate(-50%, ${-68+Math.min(74,y*.72)}px) scale(${.92+Math.min(.08,y/1000)})`;
    const ring=el.querySelector('.elya109-ring');
    if(ring&&!refreshing)ring.style.transform=`rotate(${Math.min(260,y*2.6)}deg)`;
    txt.textContent=y>=THRESHOLD?'Release to refresh':'Pull to refresh';
  };
  const reset=()=>{
    active=false;pull=0;
    el.classList.remove('show','ready','refreshing');
    el.style.transform='translate(-50%,-76px) scale(.92)';
    txt.textContent='Pull to refresh';
  };
  document.addEventListener('touchstart',e=>{
    if(refreshing||e.touches.length!==1||!top())return;
    startY=e.touches[0].clientY; pull=0; active=true;
  },{passive:true});
  document.addEventListener('touchmove',e=>{
    if(!active||refreshing||e.touches.length!==1)return;
    const dy=e.touches[0].clientY-startY;
    if(dy<=0){pull=0;paint();return;}
    if(!top()&&pull<5){active=false;return;}
    pull=Math.min(MAX,dy*.58);
    if(pull>5)e.preventDefault();
    paint();
  },{passive:false});
  const finish=()=>{
    if(!active||refreshing)return;
    active=false;
    if(pull>=THRESHOLD){
      refreshing=true;
      el.classList.add('show','refreshing');
      el.classList.remove('ready');
      el.style.transform='translate(-50%,6px) scale(1)';
      txt.textContent='Refreshing…';
      if(navigator.vibrate)try{navigator.vibrate(18)}catch{}
      setTimeout(()=>window.location.reload(),220);
    }else reset();
  };
  document.addEventListener('touchend',finish,{passive:true});
  document.addEventListener('touchcancel',()=>{if(!refreshing)reset()},{passive:true});
})();</script>'''
if 'elya109PullScript' not in h:
    h=h.replace('</body>',script+'</body>',1)

p.write_text(h,encoding='utf-8')
print('Elya 1.0.9 pull-to-refresh restored')

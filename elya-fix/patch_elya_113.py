from pathlib import Path
import re

r=Path('.')

# Version
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+13\b','versionCode 14',s,count=1)
s=re.sub(r"versionName\s+'1\.1\.2'","versionName '1.1.3'",s,count=1)
p.write_text(s,encoding='utf-8')

# Native diagnostics version only; playback/scanner behavior from 1.1.2 remains intact.
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_112','// ELYA_NATIVE_CORE_112\n    // ELYA_NATIVE_CORE_113',1)
s=s.replace('return "elya-bridge-1.1.2";','return "elya-bridge-1.1.3";',1)
s=s.replace('o.put("core", "1.1.2");','o.put("core", "1.1.3");',1)
p.write_text(s,encoding='utf-8')

# Touch-safe pull-to-refresh + boot overlay fail-safe.
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')

old=r'''  // ---------- precise page pull-to-refresh ----------
  const pull=q('#elya110Pull'),pullText=q('#elya110PullText'),THRESHOLD=86,MAX=126;
  let startY=0,distance=0,active=false,refreshing=false,scroller=null;
  const blockers=()=>q('.modal.open,#queueDrawer.open,#mobileSearchOverlay.open,#elya110ScanModal.open');
  const currentScroller=(target)=>{
    const np=q('#nowPlaying');
    if(np?.classList.contains('open') && target?.closest?.('#nowPlaying')) return np;
    return q('.main');
  };
  const atRealTop=el=>!!el && Math.max(0,Number(el.scrollTop||0))<=1;
  const paint=()=>{
    if(!pull||!pullText)return;
    const y=Math.max(0,Math.min(MAX,distance));
    pull.classList.toggle('show',y>5);pull.classList.toggle('ready',y>=THRESHOLD);
    pull.style.transform=`translate(-50%,${-76+Math.min(86,y*.76)}px) scale(${.94+Math.min(.06,y/1200)})`;
    const ring=pull.querySelector('.ring');if(ring&&!refreshing)ring.style.transform=`rotate(${Math.min(300,y*2.8)}deg)`;
    pullText.textContent=y>=THRESHOLD?'Release to refresh':'Pull to refresh';
  };
  const reset=()=>{active=false;distance=0;scroller=null;if(!pull)return;pull.classList.remove('show','ready','refreshing');pull.style.transform='translate(-50%,-84px)';if(pullText)pullText.textContent='Pull to refresh'};
  document.addEventListener('touchstart',e=>{
    if(refreshing||blockers()||e.touches.length!==1)return;
    const candidate=currentScroller(e.target);
    // Critical: the gesture can only ARM when the actual current page scroller is at scrollTop 0.
    if(!atRealTop(candidate))return;
    scroller=candidate;startY=e.touches[0].clientY;distance=0;active=true;
  },{passive:true});
  document.addEventListener('touchmove',e=>{
    if(!active||refreshing||e.touches.length!==1)return;
    if(!atRealTop(scroller)&&distance<6){reset();return}
    const dy=e.touches[0].clientY-startY;
    if(dy<=0){distance=0;paint();return}
    distance=Math.min(MAX,dy*.6);
    if(distance>5)e.preventDefault();paint();
  },{passive:false});
  const finishPull=()=>{
    if(!active||refreshing)return;
    active=false;
    if(distance<THRESHOLD){reset();return}
    refreshing=true;pull?.classList.add('show','refreshing');pull?.classList.remove('ready');if(pullText)pullText.textContent='Refreshing this page…';
    try{sessionStorage.setItem('elya110RefreshState',JSON.stringify({view:state?.currentView||null,label:q('#viewTitle')?.textContent||'',nowPlaying:q('#nowPlaying')?.classList.contains('open')||false}))}catch{}
    try{navigator.vibrate?.(18)}catch{}
    setTimeout(()=>location.reload(),240);
  };
  document.addEventListener('touchend',finishPull,{passive:true});
  document.addEventListener('touchcancel',()=>{if(!refreshing)reset()},{passive:true});
'''

new=r'''  // ---------- Elya 1.1.3 touch-safe page pull-to-refresh ----------
  // Never steal taps from controls. A refresh only arms at the real top of the current page
  // and only after a deliberate vertical drag clears a dead-zone.
  const pull=q('#elya110Pull'),pullText=q('#elya110PullText'),THRESHOLD=72,MAX=126,DRAG_DEADZONE=24;
  let startY=0,startX=0,distance=0,active=false,refreshing=false,scroller=null;
  const blockers=()=>q('.modal.open,#queueDrawer.open,#mobileSearchOverlay.open,#elya110ScanModal.open');
  const interactiveTarget=t=>!!t?.closest?.('button,a,input,textarea,select,label,[role="button"],[contenteditable="true"],input[type="range"],.track-row,.queue-row,.playlist-card,.mini-player,.bottom-nav,.context-menu');
  const currentScroller=(target)=>{
    const np=q('#nowPlaying');
    if(np?.classList.contains('open') && target?.closest?.('#nowPlaying')) return np;
    return q('.main');
  };
  const atRealTop=el=>!!el && Math.max(0,Number(el.scrollTop||0))<=1;
  const paint=()=>{
    if(!pull||!pullText)return;
    const y=Math.max(0,Math.min(MAX,distance));
    pull.classList.toggle('show',y>4);pull.classList.toggle('ready',y>=THRESHOLD);
    pull.style.transform=`translate(-50%,${-76+Math.min(86,y*.76)}px) scale(${.94+Math.min(.06,y/1200)})`;
    const ring=pull.querySelector('.ring');if(ring&&!refreshing)ring.style.transform=`rotate(${Math.min(300,y*2.8)}deg)`;
    pullText.textContent=y>=THRESHOLD?'Release to refresh':'Pull to refresh';
  };
  const reset=()=>{active=false;distance=0;scroller=null;if(!pull)return;pull.classList.remove('show','ready','refreshing');pull.style.transform='translate(-50%,-84px)';if(pullText)pullText.textContent='Pull to refresh'};
  document.addEventListener('touchstart',e=>{
    if(refreshing||blockers()||e.touches.length!==1||interactiveTarget(e.target))return;
    const candidate=currentScroller(e.target);
    if(!atRealTop(candidate))return;
    scroller=candidate;startY=e.touches[0].clientY;startX=e.touches[0].clientX;distance=0;active=true;
  },{passive:true});
  document.addEventListener('touchmove',e=>{
    if(!active||refreshing||e.touches.length!==1)return;
    if(!atRealTop(scroller)&&distance<4){reset();return}
    const dy=e.touches[0].clientY-startY,dx=e.touches[0].clientX-startX;
    if(dy<=0||Math.abs(dx)>Math.max(14,dy*.72)){distance=0;if(dy<=0)reset();return}
    if(dy<DRAG_DEADZONE){distance=0;return}
    distance=Math.min(MAX,(dy-DRAG_DEADZONE)*.72);
    // Only a clearly intentional pull may cancel native scrolling/click synthesis.
    if(dy>DRAG_DEADZONE+8 && dy>Math.abs(dx)*1.2)e.preventDefault();
    paint();
  },{passive:false});
  const finishPull=()=>{
    if(!active||refreshing)return;
    active=false;
    if(distance<THRESHOLD){reset();return}
    refreshing=true;pull?.classList.add('show','refreshing');pull?.classList.remove('ready');if(pullText)pullText.textContent='Refreshing this page…';
    try{sessionStorage.setItem('elya110RefreshState',JSON.stringify({view:state?.currentView||null,label:q('#viewTitle')?.textContent||'',nowPlaying:q('#nowPlaying')?.classList.contains('open')||false}))}catch{}
    try{navigator.vibrate?.(18)}catch{}
    setTimeout(()=>location.reload(),240);
  };
  document.addEventListener('touchend',finishPull,{passive:true});
  document.addEventListener('touchcancel',()=>{if(!refreshing)reset()},{passive:true});
'''

if old not in h:
    raise SystemExit('1.1.0 pull-to-refresh block not found')
h=h.replace(old,new,1)

# Independent fail-safe: the premium startup layer can never remain as an invisible touch shield.
# This script is intentionally standalone and late in the document.
safety=r'''<script id="elya113TouchSafety">(()=>{
  window.__elyaTouchVersion='1.1.3';
  const releaseBoot=()=>{
    const b=document.getElementById('elyaBoot');
    if(!b)return;
    b.style.pointerEvents='none';
    b.classList.add('done');
    setTimeout(()=>{try{b.remove()}catch{}},700);
  };
  // Normal boot code dismisses sooner; this is only a hard safety ceiling.
  setTimeout(releaseBoot,5200);
  window.addEventListener('pageshow',()=>setTimeout(()=>{
    const b=document.getElementById('elyaBoot');
    if(b?.classList.contains('done'))b.style.pointerEvents='none';
  },100));
})();</script>'''
if 'id="elya113TouchSafety"' not in h:
    h=h.replace('</body>',safety+'</body>',1)

p.write_text(h,encoding='utf-8')
print('Elya 1.1.3 touch-safe interaction fix applied')

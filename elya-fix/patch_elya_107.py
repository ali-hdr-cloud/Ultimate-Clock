from pathlib import Path
import re, shutil

r=Path('.')

# Replace the accumulated Android bridge with the clean 1.0.7 native core.
src=Path('../elya-fix/MainActivity107.java')
dst=r/'app/src/main/java/com/elya/music/MainActivity.java'
if not src.exists():
    raise SystemExit('MainActivity107.java missing')
shutil.copy2(src,dst)

# Version
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+7\b','versionCode 8',s,count=1)
s=re.sub(r"versionName\s+'1\.0\.6'","versionName '1.0.7'",s,count=1)
p.write_text(s,encoding='utf-8')

# HTML bridge wiring / diagnostics. Clone controls so old patched listeners cannot double-fire.
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')
script=r'''<script id="elya107BridgeScript">(()=>{
  const q=s=>document.querySelector(s);
  const status=t=>{const e=q('#elyaAuthStatus')||q('#elyaCloudStatus');if(e)e.textContent=t||''};
  const scanStatus=t=>{const e=q('#folderScanStatus');if(e){e.textContent=t||'';e.className='folder-scan-status '+(/error|denied|failed/i.test(t)?'warn':'scanning')}};
  const call=(name,...args)=>{
    try{
      const b=window.AndroidMusic;
      if(!b||typeof b[name]!=='function')throw new Error(`Android bridge method missing: ${name}`);
      return b[name](...args);
    }catch(e){
      const m=`Native bridge error: ${e?.message||e}`;status(m);scanStatus(m);return null;
    }
  };
  const clone=id=>{
    const old=q('#'+id);if(!old)return null;
    const n=old.cloneNode(true);old.replaceWith(n);return n;
  };
  const renderDiag=d=>{
    if(!d)return;
    let a=q('#elyaNativeDiag');
    if(!a&&q('#elyaAuthStatus')){a=document.createElement('div');a.id='elyaNativeDiag';a.className='elya-auth-status';a.style.marginTop='6px';q('#elyaAuthStatus').after(a)}
    if(a)a.textContent=`Native ${d.bridge==='ok'?'OK':'?'} · Firebase ${d.firebaseReady?'OK':'ERROR'} · Music ${d.musicPermission?'allowed':'permission needed'}${Number.isFinite(+d.lastScanCount)?` · ${d.lastScanCount} files`:''}`;
    let s=q('#elyaScanDiag');
    if(!s&&q('#folderScanStatus')){s=document.createElement('div');s.id='elyaScanDiag';s.className='install-note';s.style.marginTop='7px';q('#folderScanStatus').after(s)}
    if(s)s.textContent=d.musicPermission?`Android media access: allowed${d.lastScanError?` · ${d.lastScanError}`:''}`:`Android media access: not allowed${d.lastScanError?` · ${d.lastScanError}`:''}`;
    let settings=q('#elyaOpenAndroidSettings');
    if(!d.musicPermission){
      if(!settings&&s){settings=document.createElement('button');settings.id='elyaOpenAndroidSettings';settings.type='button';settings.className='secondary';settings.style.marginTop='8px';settings.textContent='Open Android App Settings';s.after(settings);settings.onclick=()=>call('openAppSettings')}
    }else settings?.remove();
  };
  const oldDiag=window.__elyaNativeDiagnostics;
  window.__elyaNativeDiagnostics=d=>{try{oldDiag?.(d)}catch{}renderDiag(d)};
  const oldAuth=window.__elyaNativeAuthEvent;
  window.__elyaNativeAuthEvent=e=>{try{oldAuth?.(e)}catch{};if(e?.message)status(e.message)};
  const oldScanStatus=window.__elyaNativeScanStatus;
  window.__elyaNativeScanStatus=e=>{try{oldScanStatus?.(e)}catch{};if(e?.message)scanStatus(e.message)};

  function init(){
    const signIn=clone('elyaSignIn'),create=clone('elyaCreate'),google=clone('elyaGoogleSignIn');
    const phoneToggle=clone('elyaPhoneToggle'),send=clone('elyaPhoneSend'),verify=clone('elyaPhoneVerify');
    if(signIn){signIn.type='button';signIn.onclick=()=>{status('Signing in...');call('firebaseEmailSignIn',q('#elyaAuthEmail')?.value||'',q('#elyaAuthPassword')?.value||'')}}
    if(create){create.type='button';create.onclick=()=>{status('Creating account...');call('firebaseEmailSignUp',q('#elyaAuthEmail')?.value||'',q('#elyaAuthPassword')?.value||'')}}
    if(google){google.type='button';google.onclick=()=>{status('Opening Google Sign-In...');call('firebaseGoogleSignIn')}}
    if(phoneToggle){phoneToggle.type='button';phoneToggle.onclick=()=>{q('#elyaPhoneBox')?.classList.toggle('show');q('#elyaPhoneNumber')?.focus()}}
    if(send){send.type='button';send.onclick=()=>{status('Requesting SMS from Firebase...');call('firebasePhoneSendCode',q('#elyaPhoneNumber')?.value||'')}}
    if(verify){verify.type='button';verify.onclick=()=>{status('Verifying SMS code...');call('firebasePhoneVerifyCode',q('#elyaPhoneCode')?.value||'')}}

    for(const id of ['rescanFolderBtn','folderAdd']){
      const b=clone(id);if(b){b.type='button';b.onclick=()=>{scanStatus('Starting Android media scan...');call('scanAllDeviceMusic')}}
    }
    for(const id of ['grantFolderBtn','changeFolderBtn','heroAdd','addMusicBtn']){
      const b=clone(id);if(b){b.type='button';b.onclick=()=>call('chooseMusicFolder')}
    }

    const ping=call('ping');
    if(ping==='elya-bridge-1.0.7'){
      status('Native bridge connected.');
      try{const d=JSON.parse(call('diagnostics')||'{}');renderDiag(d)}catch{}
      setTimeout(()=>call('nativeReady'),80);
    }
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});else init();
})();</script>'''
if 'elya107BridgeScript' not in h:
    h=h.replace('</body>',script+'</body>',1)

p.write_text(h,encoding='utf-8')
print('Elya 1.0.7 clean native bridge applied')

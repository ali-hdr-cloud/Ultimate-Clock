from pathlib import Path
import re

r = Path('.')

# ---------- Version ----------
p = r/'app/build.gradle'
s = p.read_text(encoding='utf-8')
s = re.sub(r'versionCode\s+6\b', 'versionCode 7', s, count=1)
s = re.sub(r"versionName\s+'1\.0\.5'", "versionName '1.0.6'", s, count=1)
p.write_text(s, encoding='utf-8')

# ---------- Firebase auth responsiveness ----------
p = r/'app/src/main/java/com/elya/music/MainActivity.java'
s = p.read_text(encoding='utf-8')

pat = re.compile(r'''        @JavascriptInterface public void firebaseEmailSignUp\(String email,String password\)\{.*?\}\s*(?=        @JavascriptInterface public void firebaseEmailSignIn)''', re.S)
new = '''        @JavascriptInterface public void firebaseEmailSignUp(String email,String password){
            String e=email==null?"":email.trim(),pw=password==null?"":password;
            if(e.isEmpty()||pw.length()<6){emitFirebaseError("Use a valid email and a password with at least 6 characters.");return;}
            emitFirebaseMessage("Creating Elya account...");
            firebaseAuth.createUserWithEmailAndPassword(e,pw)
                    .addOnSuccessListener(x->{
                        FirebaseUser u=x.getUser();
                        if(u==null){emitFirebaseError("Account was created but no user session was returned.");return;}
                        emitFirebaseState(u,null);
                        emitFirebaseMessage("Elya account created.");
                        Map<String,Object>d=new HashMap<>();
                        d.put("email",clean(u.getEmail()));d.put("displayName","Elya Listener");d.put("bio","");d.put("favoriteArtist","");
                        d.put("createdAt",FieldValue.serverTimestamp());d.put("updatedAt",FieldValue.serverTimestamp());
                        firestore.collection("users").document(u.getUid()).set(d,SetOptions.merge())
                                .addOnSuccessListener(v->loadFirebaseProfile(u))
                                .addOnFailureListener(err->emitFirebaseMessage("Signed in. Cloud profile sync will retry later."));
                    })
                    .addOnFailureListener(err->emitFirebaseError(firebaseFriendlyError(err)));
        }

'''
s, n = pat.subn(new, s, count=1)
if n != 1:
    raise SystemExit('firebaseEmailSignUp replacement failed')

p.write_text(s, encoding='utf-8')

# ---------- Web UI / scan responsiveness ----------
p = r/'app/src/main/assets/index.html'
h = p.read_text(encoding='utf-8')

start = h.find('window.__elyaReceiveNativeLibrary = async function(items, folderName){')
end = h.find('window.__elyaNativeScanStarted = function(folderName){', start)
if start < 0 or end < 0:
    raise SystemExit('native receive handler block missing')
block = h[start:end]
block2 = block.replace('      await persistSong(s);', '      Promise.resolve(persistSong(s)).catch(()=>{});')
block2 = block2.replace('    await dbDelete(s.id);', '    Promise.resolve(dbDelete(s.id)).catch(()=>{});')
if block2 == block:
    raise SystemExit('native receive persistence anchors missing')
h = h[:start] + block2 + h[end:]

old = '''window.__elyaReceiveNativeLibrary=async function(items,folderName){
  const n=Array.isArray(items)?items.length:0;
  elya103Boot('Library ready',`${n} song${n===1?'':'s'} synced`);
  await __elya103Receive?.(items,folderName);
  elya103Scanning=false;elya103LastScanCount=n;document.body.classList.remove('elya-scanning');
  elya103UpdateHome();elya103DismissBoot(420);
};'''
new = '''window.__elyaReceiveNativeLibrary=function(items,folderName){
  const n=Array.isArray(items)?items.length:0;
  elya103Boot('Library ready',`${n} song${n===1?'':'s'} found`);
  elya103Scanning=false;elya103LastScanCount=n;document.body.classList.remove('elya-scanning');
  elya103UpdateHome();elya103DismissBoot(180);
  try{Promise.resolve(__elya103Receive?.(items,folderName)).catch(err=>console.warn('Elya library sync',err));}catch(err){console.warn('Elya library sync',err)}
};'''
if old not in h:
    raise SystemExit('Elya 1.0.3 receive wrapper anchor missing')
h = h.replace(old, new, 1)

watchdog = r'''<script id="elya106StabilityScript">(()=>{
  const q=s=>document.querySelector(s);
  let authTimer=0;
  const setStatus=t=>{const e=q('#elyaAuthStatus')||q('#elyaCloudStatus');if(e)e.textContent=t||''};
  const finishBoot=()=>{
    const b=q('#elyaBoot');if(!b||b.classList.contains('done'))return;
    const s=q('#elyaBootStatus'),d=q('#elyaBootCount');
    if(s)s.textContent='Elya is ready';if(d)d.textContent='Music scan is continuing in the background';
    b.classList.add('done');setTimeout(()=>b.remove(),650);
  };
  setTimeout(finishBoot,4200);

  const arm=()=>{clearTimeout(authTimer);authTimer=setTimeout(()=>{setStatus('Firebase did not answer yet. Check internet, then try again.');try{window.AndroidMusic?.firebaseCurrentUser?.()}catch(e){}},15000)};
  ['#elyaSignIn','#elyaCreate','#elyaPhoneSend','#elyaPhoneVerify','#elyaGoogleSignIn'].forEach(sel=>q(sel)?.addEventListener('click',arm));
  const oldState=window.__elyaFirebaseAuthState;window.__elyaFirebaseAuthState=d=>{clearTimeout(authTimer);oldState?.(d)};
  const oldErr=window.__elyaFirebaseError;window.__elyaFirebaseError=m=>{clearTimeout(authTimer);setStatus(m);oldErr?.(m)};
  const oldMsg=window.__elyaFirebaseMessage;window.__elyaFirebaseMessage=m=>{if(/signed in|created|code sent|verification/i.test(String(m)))clearTimeout(authTimer);setStatus(m);oldMsg?.(m)};
})();</script>'''
if 'elya106StabilityScript' not in h:
    h = h.replace('</body>', watchdog + '</body>', 1)

for bid in ['elyaSignIn','elyaCreate','elyaPhoneSend','elyaPhoneVerify','elyaGoogleSignIn']:
    h = h.replace(f'id="{bid}">', f'id="{bid}" type="button">', 1)

p.write_text(h, encoding='utf-8')
print('Elya 1.0.6 stability fixes applied')

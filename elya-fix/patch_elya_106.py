from pathlib import Path
import re

r = Path('.')

# ---------- Version ----------
p = r/'app/build.gradle'
s = p.read_text(encoding='utf-8')
s = re.sub(r'versionCode\s+6\b', 'versionCode 7', s, count=1)
s = re.sub(r"versionName\s+'1\.0\.5'", "versionName '1.0.6'", s, count=1)
p.write_text(s, encoding='utf-8')

# ---------- Native Android fixes ----------
p = r/'app/src/main/java/com/elya/music/MainActivity.java'
s = p.read_text(encoding='utf-8')

if 'import com.google.firebase.auth.FirebaseAuthException;' not in s:
    s = s.replace('import com.google.firebase.auth.FirebaseAuth;',
                  'import com.google.firebase.auth.FirebaseAuth;\nimport com.google.firebase.auth.FirebaseAuthException;', 1)

if 'private volatile boolean deviceScanRunning' not in s:
    anchor = '    private PhoneAuthProvider.ForceResendingToken phoneResendToken;'
    if anchor not in s:
        raise SystemExit('phoneResendToken field anchor missing')
    s = s.replace(anchor, anchor + '\n    private volatile boolean deviceScanRunning = false;\n    private volatile long lastDeviceScanFinishedAt = 0L;', 1)

old_scan_start = '''    private void scanAllDeviceMusic() {\n        io.execute(() -> {\n            try {'''
new_scan_start = '''    private void scanAllDeviceMusic() {\n        if (deviceScanRunning) {\n            js("window.__elyaNativeScanAlreadyRunning && window.__elyaNativeScanAlreadyRunning();");\n            return;\n        }\n        deviceScanRunning = true;\n        io.execute(() -> {\n            try {'''
if old_scan_start not in s:
    raise SystemExit('scanAllDeviceMusic start anchor missing')
s = s.replace(old_scan_start, new_scan_start, 1)

old_scan_end = '''            } catch (Exception e) {\n                js("window.__elyaNativeScanError && window.__elyaNativeScanError("\n                        + JSONObject.quote("Could not scan device music. You can still choose a folder manually.") + ");");\n            }\n        });\n    }\n\n    private boolean scanMediaCollection'''
new_scan_end = '''            } catch (Exception e) {\n                js("window.__elyaNativeScanError && window.__elyaNativeScanError("\n                        + JSONObject.quote("Could not scan device music. You can still choose a folder manually.") + ");");\n            } finally {\n                deviceScanRunning = false;\n                lastDeviceScanFinishedAt = System.currentTimeMillis();\n                js("window.__elyaNativeScanFinished && window.__elyaNativeScanFinished();");\n            }\n        });\n    }\n\n    private boolean scanMediaCollection'''
if old_scan_end not in s:
    raise SystemExit('scanAllDeviceMusic end anchor missing')
s = s.replace(old_scan_end, new_scan_end, 1)

email_signup_pattern = re.compile(r'''        @JavascriptInterface public void firebaseEmailSignUp\(String email,String password\)\{.*?\}\n(?=        @JavascriptInterface public void firebaseEmailSignIn)''', re.S)
email_signup_new = '''        @JavascriptInterface public void firebaseEmailSignUp(String email,String password){\n            String e=email==null?"":email.trim(),pw=password==null?"":password;\n            if(e.isEmpty()||pw.length()<6){emitFirebaseError("Use a valid email and a password with at least 6 characters.");return;}\n            emitFirebaseMessage("Creating Elya account...");\n            firebaseAuth.createUserWithEmailAndPassword(e,pw)\n                    .addOnSuccessListener(x->{\n                        FirebaseUser u=x.getUser();\n                        if(u==null){emitFirebaseError("Account was created but no user session was returned.");return;}\n                        emitFirebaseState(u,null);\n                        emitFirebaseMessage("Elya account created.");\n                        Map<String,Object>d=new HashMap<>();\n                        d.put("email",clean(u.getEmail()));d.put("displayName","Elya Listener");d.put("bio","");d.put("favoriteArtist","");\n                        d.put("createdAt",FieldValue.serverTimestamp());d.put("updatedAt",FieldValue.serverTimestamp());\n                        firestore.collection("users").document(u.getUid()).set(d,SetOptions.merge())\n                                .addOnSuccessListener(v->loadFirebaseProfile(u))\n                                .addOnFailureListener(err->emitFirebaseMessage("Signed in. Cloud profile sync will retry later."));\n                    })\n                    .addOnFailureListener(err->emitFirebaseError(firebaseFriendlyError(err)));\n        }\n'''
s, count = email_signup_pattern.subn(email_signup_new, s, count=1)
if count != 1:
    raise SystemExit('firebaseEmailSignUp replacement failed')

email_signin_pattern = re.compile(r'''        @JavascriptInterface public void firebaseEmailSignIn\(String email,String password\)\{.*?\}\n(?=        @JavascriptInterface public void firebaseGoogleSignIn)''', re.S)
email_signin_new = '''        @JavascriptInterface public void firebaseEmailSignIn(String email,String password){\n            String e=email==null?"":email.trim(),pw=password==null?"":password;\n            if(e.isEmpty()||pw.isEmpty()){emitFirebaseError("Enter your email and password.");return;}\n            emitFirebaseMessage("Signing in...");\n            firebaseAuth.signInWithEmailAndPassword(e,pw)\n                    .addOnSuccessListener(x->{\n                        FirebaseUser u=x.getUser();\n                        if(u==null){emitFirebaseError("Signed in but no user session was returned.");return;}\n                        emitFirebaseState(u,null);\n                        emitFirebaseMessage("Signed in to Elya.");\n                        loadFirebaseProfile(u);\n                    })\n                    .addOnFailureListener(err->emitFirebaseError(firebaseFriendlyError(err)));\n        }\n'''
s, count = email_signin_pattern.subn(email_signin_new, s, count=1)
if count != 1:
    raise SystemExit('firebaseEmailSignIn replacement failed')

finish_pattern = re.compile(r'''    private void finishSocialSignIn\(FirebaseUser user,String provider\)\{.*?\n    \}\n\n(?=    private void emitFirebaseState\()''', re.S)
finish_new = '''    private void finishSocialSignIn(FirebaseUser user,String provider){\n        if(user==null){emitFirebaseError("Sign-In completed but no user session was returned.");return;}\n        String display=clean(user.getDisplayName());\n        if(display.isEmpty()){\n            String phone=clean(user.getPhoneNumber());\n            display=phone.isEmpty()?"Elya Listener":"Elya "+phone.substring(Math.max(0,phone.length()-4));\n        }\n        final String displayName=display;\n        emitFirebaseState(user,null);\n        emitFirebaseMessage("Signed in to Elya with "+("google".equals(provider)?"Google.":"your phone."));\n\n        Map<String,Object> data=new HashMap<>();\n        data.put("email",clean(user.getEmail()));data.put("phoneNumber",clean(user.getPhoneNumber()));\n        data.put("displayName",displayName);data.put("provider",provider);data.put("updatedAt",FieldValue.serverTimestamp());\n        firestore.collection("users").document(user.getUid()).get()\n                .addOnSuccessListener(doc->{\n                    if(!doc.exists()){data.put("bio","");data.put("favoriteArtist","");data.put("createdAt",FieldValue.serverTimestamp());}\n                    firestore.collection("users").document(user.getUid()).set(data,SetOptions.merge())\n                            .addOnSuccessListener(v->loadFirebaseProfile(user))\n                            .addOnFailureListener(err->emitFirebaseMessage("Signed in. Cloud profile sync will retry later."));\n                })\n                .addOnFailureListener(err->emitFirebaseMessage("Signed in. Cloud profile sync will retry later."));\n    }\n\n'''
s, count = finish_pattern.subn(finish_new, s, count=1)
if count != 1:
    raise SystemExit('finishSocialSignIn replacement failed')

friendly_pattern = re.compile(r'''private static String firebaseFriendlyError\(Exception e\)\{.*?\}''', re.S)
friendly_new = '''private static String firebaseFriendlyError(Exception e){\n        if(e==null)return "Could not complete the account action.";\n        if(e instanceof FirebaseAuthException){\n            String code=((FirebaseAuthException)e).getErrorCode();\n            if(code!=null){\n                switch(code){\n                    case "ERROR_INVALID_EMAIL": return "That email address is not valid.";\n                    case "ERROR_EMAIL_ALREADY_IN_USE": return "That email already has an Elya account. Tap Sign In instead.";\n                    case "ERROR_WEAK_PASSWORD": return "Use a stronger password with at least 6 characters.";\n                    case "ERROR_USER_NOT_FOUND": return "No Elya account was found for that email. Tap Create Account first.";\n                    case "ERROR_WRONG_PASSWORD":\n                    case "ERROR_INVALID_CREDENTIAL": return "Email or password is incorrect.";\n                    case "ERROR_OPERATION_NOT_ALLOWED": return "This sign-in method is not enabled in Firebase.";\n                    case "ERROR_TOO_MANY_REQUESTS": return "Too many attempts. Wait a little and try again.";\n                    case "ERROR_APP_NOT_AUTHORIZED": return "Firebase does not recognize this Elya app signature.";\n                    case "ERROR_INVALID_VERIFICATION_CODE": return "That SMS code is incorrect or expired.";\n                    case "ERROR_SESSION_EXPIRED": return "That SMS session expired. Send a new code.";\n                }\n            }\n        }\n        String m=e.getMessage()==null?"Could not complete the account action.":e.getMessage();\n        String l=m.toLowerCase(Locale.US);\n        if(l.contains("network"))return "Check your internet connection and try again.";\n        if(l.contains("quota")||l.contains("too many requests"))return "Firebase SMS limit was reached. Try again later.";\n        if(l.contains("recaptcha")||l.contains("play integrity"))return "Phone verification could not verify this app. Check Google Play Services and try again.";\n        if(l.contains("invalid-verification-code"))return "That SMS code is incorrect or expired.";\n        return m.length()>220?m.substring(0,220):m;\n    }'''
s, count = friendly_pattern.subn(friendly_new, s, count=1)
if count != 1:
    raise SystemExit('firebaseFriendlyError replacement failed')

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

old_wrapper = '''window.__elyaReceiveNativeLibrary=async function(items,folderName){\n  const n=Array.isArray(items)?items.length:0;\n  elya103Boot('Library ready',`${n} song${n===1?'':'s'} synced`);\n  await __elya103Receive?.(items,folderName);\n  elya103Scanning=false;elya103LastScanCount=n;document.body.classList.remove('elya-scanning');\n  elya103UpdateHome();elya103DismissBoot(420);\n};'''
new_wrapper = '''window.__elyaReceiveNativeLibrary=function(items,folderName){\n  const n=Array.isArray(items)?items.length:0;\n  elya103Boot('Library ready',`${n} song${n===1?'':'s'} found`);\n  elya103Scanning=false;elya103LastScanCount=n;document.body.classList.remove('elya-scanning');\n  elya103UpdateHome();elya103DismissBoot(180);\n  try{Promise.resolve(__elya103Receive?.(items,folderName)).catch(err=>console.warn('Elya library sync',err));}catch(err){console.warn('Elya library sync',err)}\n};'''
if old_wrapper not in h:
    raise SystemExit('Elya 1.0.3 receive wrapper anchor missing')
h = h.replace(old_wrapper, new_wrapper, 1)

watchdog = r'''<script id="elya106StabilityScript">(()=>{
  const q=s=>document.querySelector(s);
  let authTimer=0;
  const setStatus=t=>{const e=q('#elyaAuthStatus')||q('#elyaCloudStatus');if(e)e.textContent=t||''};
  const finishBoot=(detail='Scanning can continue in the background')=>{
    const b=q('#elyaBoot');
    if(!b||b.classList.contains('done'))return;
    const s=q('#elyaBootStatus'),d=q('#elyaBootCount');
    if(s)s.textContent='Elya is ready'; if(d)d.textContent=detail;
    b.classList.add('done'); setTimeout(()=>b.remove(),650);
  };
  window.__elyaNativeScanAlreadyRunning=()=>{};
  window.__elyaNativeScanFinished=()=>{if(document.body)document.body.classList.remove('elya-scanning')};
  setTimeout(()=>finishBoot('Music scan is continuing in the background'),4200);

  const armAuthTimeout=()=>{clearTimeout(authTimer);authTimer=setTimeout(()=>{setStatus('Firebase did not answer yet. Check internet, then try again.');window.AndroidMusic?.firebaseCurrentUser?.()},15000)};
  ['#elyaSignIn','#elyaCreate','#elyaPhoneSend','#elyaPhoneVerify','#elyaGoogleSignIn'].forEach(sel=>q(sel)?.addEventListener('click',armAuthTimeout));
  const oldState=window.__elyaFirebaseAuthState;window.__elyaFirebaseAuthState=d=>{clearTimeout(authTimer);oldState?.(d)};
  const oldErr=window.__elyaFirebaseError;window.__elyaFirebaseError=m=>{clearTimeout(authTimer);setStatus(m);oldErr?.(m)};
  const oldMsg=window.__elyaFirebaseMessage;window.__elyaFirebaseMessage=m=>{if(/signed in|created|code sent|verification/i.test(String(m)))clearTimeout(authTimer);setStatus(m);oldMsg?.(m)};
})();</script>'''
if 'elya106StabilityScript' not in h:
    h = h.replace('</body>', watchdog + '</body>', 1)

h = h.replace('id="elyaSignIn">', 'id="elyaSignIn" type="button">', 1)
h = h.replace('id="elyaCreate">', 'id="elyaCreate" type="button">', 1)
h = h.replace('id="elyaPhoneSend">', 'id="elyaPhoneSend" type="button">', 1)
h = h.replace('id="elyaPhoneVerify">', 'id="elyaPhoneVerify" type="button">', 1)
h = h.replace('id="elyaGoogleSignIn">', 'id="elyaGoogleSignIn" type="button">', 1)

p.write_text(h, encoding='utf-8')
print('Elya 1.0.6 stability fixes applied')

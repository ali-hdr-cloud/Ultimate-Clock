from pathlib import Path
import re

r=Path('.')

# ---------- Gradle ----------
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+5\b','versionCode 6',s,count=1)
s=re.sub(r"versionName\s+'1\.0\.4'","versionName '1.0.5'",s,count=1)
if 'com.google.android.libraries.identity.googleid:googleid' not in s:
    s=s.replace("    implementation 'com.google.firebase:firebase-firestore'",
                "    implementation 'com.google.firebase:firebase-firestore'\n"
                "    implementation 'androidx.credentials:credentials:1.3.0'\n"
                "    implementation 'androidx.credentials:credentials-play-services-auth:1.3.0'\n"
                "    implementation 'com.google.android.libraries.identity.googleid:googleid:1.1.1'",1)
p.write_text(s,encoding='utf-8')

# ---------- Java ----------
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')

if 'import androidx.credentials.CredentialManager;' not in s:
    add='''import android.os.CancellationSignal;\n\nimport androidx.annotation.NonNull;\nimport androidx.credentials.Credential;\nimport androidx.credentials.CredentialManager;\nimport androidx.credentials.CredentialManagerCallback;\nimport androidx.credentials.CustomCredential;\nimport androidx.credentials.GetCredentialRequest;\nimport androidx.credentials.GetCredentialResponse;\nimport androidx.credentials.exceptions.GetCredentialException;\n\nimport com.google.android.libraries.identity.googleid.GetGoogleIdOption;\nimport com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;\nimport com.google.firebase.FirebaseException;\nimport com.google.firebase.auth.AuthCredential;\nimport com.google.firebase.auth.GoogleAuthProvider;\nimport com.google.firebase.auth.PhoneAuthCredential;\nimport com.google.firebase.auth.PhoneAuthOptions;\nimport com.google.firebase.auth.PhoneAuthProvider;\n'''
    s=s.replace('import com.google.firebase.auth.FirebaseAuth;',add+'\nimport com.google.firebase.auth.FirebaseAuth;',1)
if 'import java.util.concurrent.TimeUnit;' not in s:
    s=s.replace('import java.util.concurrent.Executors;','import java.util.concurrent.Executors;\nimport java.util.concurrent.TimeUnit;',1)

if 'private CredentialManager credentialManager;' not in s:
    s=s.replace('private FirebaseFirestore firestore;',
                'private FirebaseFirestore firestore;\n    private CredentialManager credentialManager;\n    private String phoneVerificationId;\n    private PhoneAuthProvider.ForceResendingToken phoneResendToken;',1)
if 'credentialManager = CredentialManager.create' not in s:
    s=s.replace('firestore = FirebaseFirestore.getInstance();',
                'firestore = FirebaseFirestore.getInstance();\n        credentialManager = CredentialManager.create(getBaseContext());\n        firebaseAuth.useAppLanguage();',1)

bridge=r'''
        @JavascriptInterface public void firebaseGoogleSignIn(){main.post(()->launchGoogleSignIn());}
        @JavascriptInterface public void firebasePhoneSendCode(String phoneNumber){main.post(()->startPhoneVerification(phoneNumber));}
        @JavascriptInterface public void firebasePhoneVerifyCode(String code){main.post(()->verifyPhoneCode(code));}
'''
if 'firebaseGoogleSignIn' not in s:
    marker='        @JavascriptInterface public void firebaseSignOut()'
    if marker not in s: raise SystemExit('firebaseSignOut anchor missing')
    s=s.replace(marker,bridge+marker,1)

helpers=r'''
    private void launchGoogleSignIn(){
        if(credentialManager==null){emitFirebaseError("Google Sign-In is unavailable on this device.");return;}
        try{
            GetGoogleIdOption option=new GetGoogleIdOption.Builder()
                    .setFilterByAuthorizedAccounts(false)
                    .setServerClientId(getString(R.string.default_web_client_id))
                    .setAutoSelectEnabled(false)
                    .build();
            GetCredentialRequest request=new GetCredentialRequest.Builder().addCredentialOption(option).build();
            credentialManager.getCredentialAsync(
                    MainActivity.this,request,new CancellationSignal(),Executors.newSingleThreadExecutor(),
                    new CredentialManagerCallback<GetCredentialResponse,GetCredentialException>(){
                        @Override public void onResult(GetCredentialResponse result){handleGoogleCredential(result.getCredential());}
                        @Override public void onError(GetCredentialException e){emitFirebaseError("Google Sign-In was cancelled or no Google account is available.");}
                    });
        }catch(Exception e){emitFirebaseError("Could not open Google Sign-In: "+firebaseFriendlyError(e));}
    }

    private void handleGoogleCredential(Credential credential){
        try{
            if(!(credential instanceof CustomCredential)){emitFirebaseError("Google returned an unsupported credential.");return;}
            CustomCredential custom=(CustomCredential)credential;
            if(!GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL.equals(custom.getType())){emitFirebaseError("Google returned an unsupported credential type.");return;}
            GoogleIdTokenCredential google=GoogleIdTokenCredential.createFrom(custom.getData());
            AuthCredential firebaseCredential=GoogleAuthProvider.getCredential(google.getIdToken(),null);
            firebaseAuth.signInWithCredential(firebaseCredential)
                    .addOnSuccessListener(x->finishSocialSignIn(x.getUser(),"google"))
                    .addOnFailureListener(e->emitFirebaseError(firebaseFriendlyError(e)));
        }catch(Exception e){emitFirebaseError("Could not finish Google Sign-In: "+firebaseFriendlyError(e));}
    }

    private void startPhoneVerification(String raw){
        String phone=raw==null?"":raw.trim().replaceAll("[\\s()\\-]","");
        if(!phone.matches("^\\+[1-9][0-9]{7,14}$")){emitFirebaseError("Enter the full phone number with country code, for example +961...");return;}
        emitFirebaseMessage("Sending verification code...");
        PhoneAuthOptions options=PhoneAuthOptions.newBuilder(firebaseAuth)
                .setPhoneNumber(phone).setTimeout(60L,TimeUnit.SECONDS).setActivity(this)
                .setCallbacks(new PhoneAuthProvider.OnVerificationStateChangedCallbacks(){
                    @Override public void onVerificationCompleted(@NonNull PhoneAuthCredential credential){signInWithPhoneCredential(credential);}
                    @Override public void onVerificationFailed(@NonNull FirebaseException e){emitFirebaseError(firebaseFriendlyError(e));}
                    @Override public void onCodeSent(@NonNull String verificationId,@NonNull PhoneAuthProvider.ForceResendingToken token){
                        phoneVerificationId=verificationId;phoneResendToken=token;
                        js("window.__elyaPhoneCodeSent&&window.__elyaPhoneCodeSent("+JSONObject.quote(phone)+");");
                        emitFirebaseMessage("Verification code sent.");
                    }
                }).build();
        PhoneAuthProvider.verifyPhoneNumber(options);
    }

    private void verifyPhoneCode(String raw){
        String code=raw==null?"":raw.trim().replaceAll("[^0-9]","");
        if(phoneVerificationId==null||phoneVerificationId.isEmpty()){emitFirebaseError("Send a verification code first.");return;}
        if(code.length()!=6){emitFirebaseError("Enter the 6-digit verification code.");return;}
        try{signInWithPhoneCredential(PhoneAuthProvider.getCredential(phoneVerificationId,code));}
        catch(Exception e){emitFirebaseError(firebaseFriendlyError(e));}
    }

    private void signInWithPhoneCredential(PhoneAuthCredential credential){
        firebaseAuth.signInWithCredential(credential)
                .addOnSuccessListener(x->{phoneVerificationId=null;phoneResendToken=null;finishSocialSignIn(x.getUser(),"phone");js("window.__elyaPhoneVerified&&window.__elyaPhoneVerified();");})
                .addOnFailureListener(e->emitFirebaseError(firebaseFriendlyError(e)));
    }

    private void finishSocialSignIn(FirebaseUser user,String provider){
        if(user==null){emitFirebaseError("Sign-In completed but no user session was returned.");return;}
        String display=clean(user.getDisplayName());
        if(display.isEmpty()){
            String phone=clean(user.getPhoneNumber());
            display=phone.isEmpty()?"Elya Listener":"Elya "+phone.substring(Math.max(0,phone.length()-4));
        }
        final String displayName=display;
        Map<String,Object> data=new HashMap<>();
        data.put("email",clean(user.getEmail()));data.put("phoneNumber",clean(user.getPhoneNumber()));
        data.put("displayName",displayName);data.put("provider",provider);data.put("updatedAt",FieldValue.serverTimestamp());
        firestore.collection("users").document(user.getUid()).get().addOnSuccessListener(doc->{
            if(!doc.exists()){data.put("bio","");data.put("favoriteArtist","");data.put("createdAt",FieldValue.serverTimestamp());}
            firestore.collection("users").document(user.getUid()).set(data,SetOptions.merge()).addOnCompleteListener(t->{
                emitFirebaseState(user,null);loadFirebaseProfile(user);
                emitFirebaseMessage("Signed in to Elya with "+("google".equals(provider)?"Google.":"your phone."));
            });
        }).addOnFailureListener(e->{emitFirebaseState(user,null);emitFirebaseMessage("Signed in to Elya.");});
    }

'''
if 'private void launchGoogleSignIn()' not in s:
    marker='    private void emitFirebaseState('
    i=s.find(marker)
    if i<0: raise SystemExit('emitFirebaseState anchor missing')
    s=s[:i]+helpers+s[i:]

if 'phoneNumber' not in s[s.find('private void emitFirebaseState('):s.find('private void loadFirebaseProfile(')]:
    compact='o.put("displayName",clean(u.getDisplayName()));'
    expanded='out.put("displayName", clean(user.getDisplayName()));'
    if compact in s:s=s.replace(compact,compact+'o.put("phoneNumber",clean(u.getPhoneNumber()));',1)
    elif expanded in s:s=s.replace(expanded,expanded+'\n                out.put("phoneNumber", clean(user.getPhoneNumber()));',1)

old='private static String firebaseFriendlyError(Exception e){String m=e==null||e.getMessage()==null?"Could not complete the account action.":e.getMessage();return m.length()>180?m.substring(0,180):m;}'
new='''private static String firebaseFriendlyError(Exception e){String m=e==null||e.getMessage()==null?"Could not complete the account action.":e.getMessage();String l=m.toLowerCase(Locale.US);if(l.contains("invalid-verification-code"))return "That verification code is incorrect or expired.";if(l.contains("too many requests")||l.contains("quota"))return "Too many verification attempts. Try again later.";if(l.contains("network"))return "Check your internet connection and try again.";return m.length()>180?m.substring(0,180):m;}'''
if old in s:s=s.replace(old,new,1)

p.write_text(s,encoding='utf-8')

# ---------- HTML / UI ----------
p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')
css='''<style id="elyaFirebase105Style">#elyaGoogleSignIn{font-weight:700}.elya-phone-box{display:none;margin-top:10px;padding:12px;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.025)}.elya-phone-box.show{display:block}.elya-phone-row{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end}.elya-phone-code{display:none;margin-top:9px}.elya-phone-code.show{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end}.elya-phone-note{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.45}.elya-auth-provider-note{font-size:10px;color:var(--muted);text-align:center;margin-top:7px}@media(max-width:700px){.elya-phone-row,.elya-phone-code.show{grid-template-columns:1fr}.elya-phone-row button,.elya-phone-code button{width:100%}}</style>'''
if 'elyaFirebase105Style' not in h:h=h.replace('</head>',css+'</head>',1)

provider_old='<div class="elya-auth-actions"><button class="secondary" disabled>Google · setup pending</button><button class="secondary" disabled>Phone · setup pending</button></div>'
provider_new='''<div class="elya-auth-actions"><button class="secondary" id="elyaGoogleSignIn">Continue with Google</button><button class="secondary" id="elyaPhoneToggle">Continue with Phone</button></div><div class="elya-phone-box" id="elyaPhoneBox"><div class="elya-phone-row"><div class="field" style="margin:0"><label>Phone number</label><input id="elyaPhoneNumber" type="tel" autocomplete="tel" inputmode="tel" placeholder="+961... or +1..."></div><button class="primary" id="elyaPhoneSend">Send Code</button></div><div class="elya-phone-code" id="elyaPhoneCodeBox"><div class="field" style="margin:0"><label>6-digit code</label><input id="elyaPhoneCode" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="123456"></div><button class="primary" id="elyaPhoneVerify">Verify</button></div><div class="elya-phone-note">Use the full international number with country code. Firebase may send an SMS and standard carrier rates may apply.</div></div><div class="elya-auth-provider-note">Account features are optional. Your music library stays on this device.</div>'''
if 'id="elyaGoogleSignIn"' not in h:
    if provider_old not in h: raise SystemExit('Google/Phone provider UI anchor missing')
    h=h.replace(provider_old,provider_new,1)

js=r'''<script id="elyaFirebase105Script">(()=>{const q=s=>document.querySelector(s),B=()=>window.AndroidMusic,S=t=>{const e=q('#elyaAuthStatus')||q('#elyaAccountStatus');if(e)e.textContent=t||''},G=q('#elyaGoogleSignIn'),T=q('#elyaPhoneToggle'),P=q('#elyaPhoneBox'),Send=q('#elyaPhoneSend'),V=q('#elyaPhoneVerify'),C=q('#elyaPhoneCodeBox');G?.addEventListener('click',()=>{G.disabled=true;S('Opening Google Sign-In…');B()?.firebaseGoogleSignIn?.();setTimeout(()=>{if(G)G.disabled=false},5000)});T?.addEventListener('click',()=>{P?.classList.toggle('show');if(P?.classList.contains('show'))q('#elyaPhoneNumber')?.focus()});Send?.addEventListener('click',()=>{const p=q('#elyaPhoneNumber')?.value?.trim()||'';Send.disabled=true;S('Sending verification code…');B()?.firebasePhoneSendCode?.(p);setTimeout(()=>{if(Send)Send.disabled=false},3500)});V?.addEventListener('click',()=>{const c=(q('#elyaPhoneCode')?.value||'').replace(/\D/g,'').slice(0,6);V.disabled=true;S('Verifying code…');B()?.firebasePhoneVerifyCode?.(c);setTimeout(()=>{if(V)V.disabled=false},3500)});q('#elyaPhoneCode')?.addEventListener('input',e=>{e.target.value=e.target.value.replace(/\D/g,'').slice(0,6)});window.__elyaPhoneCodeSent=p=>{C?.classList.add('show');S(`Code sent to ${p}. Enter the 6-digit code.`);q('#elyaPhoneCode')?.focus();if(Send)Send.disabled=false};window.__elyaPhoneVerified=()=>{S('Phone verified. Signed in to Elya.');if(V)V.disabled=false;P?.classList.remove('show')};const E=window.__elyaFirebaseError;window.__elyaFirebaseError=m=>{if(G)G.disabled=false;if(Send)Send.disabled=false;if(V)V.disabled=false;E?.(m)};const A=window.__elyaFirebaseAuthState;window.__elyaFirebaseAuthState=d=>{if(G)G.disabled=false;if(Send)Send.disabled=false;if(V)V.disabled=false;if(d?.signedIn)P?.classList.remove('show');A?.(d)}})();</script>'''
if 'elyaFirebase105Script' not in h:h=h.replace('</body>',js+'</body>',1)
p.write_text(h,encoding='utf-8')
print('Elya 1.0.5 Google + Phone auth patch applied')

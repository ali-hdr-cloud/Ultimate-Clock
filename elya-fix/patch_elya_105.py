from pathlib import Path
import re

root=Path('.')

# Gradle
p=root/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+5\b','versionCode 6',s,1)
s=re.sub(r"versionName\s+'1\.0\.4'","versionName '1.0.5'",s,1)
add_deps="""    implementation 'androidx.credentials:credentials:1.3.0'\n    implementation 'androidx.credentials:credentials-play-services-auth:1.3.0'\n    implementation 'com.google.android.libraries.identity.googleid:googleid:1.1.1'\n"""
if "com.google.android.libraries.identity.googleid:googleid" not in s:
    s=s.replace("    implementation 'com.google.firebase:firebase-firestore'", "    implementation 'com.google.firebase:firebase-firestore'\n"+add_deps.rstrip(),1)
p.write_text(s,encoding='utf-8')

# Java
p=root/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')

imports='''import android.os.CancellationSignal;\n\nimport androidx.annotation.NonNull;\nimport androidx.credentials.Credential;\nimport androidx.credentials.CredentialManager;\nimport androidx.credentials.CredentialManagerCallback;\nimport androidx.credentials.CustomCredential;\nimport androidx.credentials.GetCredentialRequest;\nimport androidx.credentials.GetCredentialResponse;\nimport androidx.credentials.exceptions.GetCredentialException;\n\nimport com.google.android.libraries.identity.googleid.GetGoogleIdOption;\nimport com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;\nimport com.google.firebase.FirebaseException;\nimport com.google.firebase.auth.AuthCredential;\nimport com.google.firebase.auth.GoogleAuthProvider;\nimport com.google.firebase.auth.PhoneAuthCredential;\nimport com.google.firebase.auth.PhoneAuthOptions;\nimport com.google.firebase.auth.PhoneAuthProvider;\n'''
if 'import androidx.credentials.CredentialManager;' not in s:
    s=s.replace('import com.google.firebase.auth.FirebaseAuth;',''+imports+'\nimport com.google.firebase.auth.FirebaseAuth;',1)
if 'import java.util.concurrent.TimeUnit;' not in s:
    s=s.replace('import java.util.concurrent.Executors;','import java.util.concurrent.Executors;\nimport java.util.concurrent.TimeUnit;',1)

if 'private CredentialManager credentialManager;' not in s:
    s=s.replace('private FirebaseFirestore firestore;', 'private FirebaseFirestore firestore;\n    private CredentialManager credentialManager;\n    private String phoneVerificationId;\n    private PhoneAuthProvider.ForceResendingToken phoneResendToken;',1)

if 'credentialManager = CredentialManager.create' not in s:
    s=s.replace('firestore = FirebaseFirestore.getInstance();', 'firestore = FirebaseFirestore.getInstance();\n        credentialManager = CredentialManager.create(getBaseContext());\n        firebaseAuth.useAppLanguage();',1)

bridge_methods=r'''
        @JavascriptInterface
        public void firebaseGoogleSignIn() {
            main.post(() -> launchGoogleSignIn());
        }

        @JavascriptInterface
        public void firebasePhoneSendCode(String phoneNumber) {
            main.post(() -> startPhoneVerification(phoneNumber));
        }

        @JavascriptInterface
        public void firebasePhoneVerifyCode(String code) {
            main.post(() -> verifyPhoneCode(code));
        }

'''
if 'public void firebaseGoogleSignIn()' not in s:
    s=s.replace('        @JavascriptInterface\n        public void firebaseSignOut() {', bridge_methods+'        @JavascriptInterface\n        public void firebaseSignOut() {',1)

helpers=r'''
    private void launchGoogleSignIn() {
        if (credentialManager == null) {
            emitFirebaseError("Google Sign-In is unavailable on this device.");
            return;
        }
        try {
            GetGoogleIdOption googleIdOption = new GetGoogleIdOption.Builder()
                    .setFilterByAuthorizedAccounts(false)
                    .setServerClientId(getString(R.string.default_web_client_id))
                    .setAutoSelectEnabled(false)
                    .build();
            GetCredentialRequest request = new GetCredentialRequest.Builder()
                    .addCredentialOption(googleIdOption)
                    .build();
            credentialManager.getCredentialAsync(
                    MainActivity.this,
                    request,
                    new CancellationSignal(),
                    Executors.newSingleThreadExecutor(),
                    new CredentialManagerCallback<GetCredentialResponse, GetCredentialException>() {
                        @Override
                        public void onResult(GetCredentialResponse result) {
                            handleGoogleCredential(result.getCredential());
                        }
                        @Override
                        public void onError(GetCredentialException e) {
                            emitFirebaseError("Google Sign-In was cancelled or no Google account is available.");
                        }
                    }
            );
        } catch (Exception e) {
            emitFirebaseError("Could not open Google Sign-In: " + firebaseFriendlyError(e));
        }
    }

    private void handleGoogleCredential(Credential credential) {
        try {
            if (!(credential instanceof CustomCredential)) {
                emitFirebaseError("Google returned an unsupported credential.");
                return;
            }
            CustomCredential custom = (CustomCredential) credential;
            if (!GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL.equals(custom.getType())) {
                emitFirebaseError("Google returned an unsupported credential type.");
                return;
            }
            GoogleIdTokenCredential google = GoogleIdTokenCredential.createFrom(custom.getData());
            AuthCredential firebaseCredential = GoogleAuthProvider.getCredential(google.getIdToken(), null);
            firebaseAuth.signInWithCredential(firebaseCredential)
                    .addOnSuccessListener(result -> finishSocialSignIn(result.getUser(), "google"))
                    .addOnFailureListener(err -> emitFirebaseError(firebaseFriendlyError(err)));
        } catch (Exception e) {
            emitFirebaseError("Could not finish Google Sign-In: " + firebaseFriendlyError(e));
        }
    }

    private void startPhoneVerification(String rawPhone) {
        String phone = rawPhone == null ? "" : rawPhone.trim().replaceAll("[\\s()\\-]", "");
        if (!phone.matches("^\\+[1-9][0-9]{7,14}$")) {
            emitFirebaseError("Enter the full phone number with country code, for example +961...");
            return;
        }
        emitFirebaseMessage("Sending verification code...");
        PhoneAuthOptions options = PhoneAuthOptions.newBuilder(firebaseAuth)
                .setPhoneNumber(phone)
                .setTimeout(60L, TimeUnit.SECONDS)
                .setActivity(this)
                .setCallbacks(new PhoneAuthProvider.OnVerificationStateChangedCallbacks() {
                    @Override
                    public void onVerificationCompleted(@NonNull PhoneAuthCredential credential) {
                        signInWithPhoneCredential(credential);
                    }

                    @Override
                    public void onVerificationFailed(@NonNull FirebaseException e) {
                        emitFirebaseError(firebaseFriendlyError(e));
                    }

                    @Override
                    public void onCodeSent(@NonNull String verificationId,
                                           @NonNull PhoneAuthProvider.ForceResendingToken token) {
                        phoneVerificationId = verificationId;
                        phoneResendToken = token;
                        js("window.__elyaPhoneCodeSent && window.__elyaPhoneCodeSent(" + JSONObject.quote(phone) + ");");
                        emitFirebaseMessage("Verification code sent.");
                    }
                })
                .build();
        PhoneAuthProvider.verifyPhoneNumber(options);
    }

    private void verifyPhoneCode(String rawCode) {
        String code = rawCode == null ? "" : rawCode.trim().replaceAll("[^0-9]", "");
        if (phoneVerificationId == null || phoneVerificationId.isEmpty()) {
            emitFirebaseError("Send a verification code first.");
            return;
        }
        if (code.length() != 6) {
            emitFirebaseError("Enter the 6-digit verification code.");
            return;
        }
        try {
            PhoneAuthCredential credential = PhoneAuthProvider.getCredential(phoneVerificationId, code);
            signInWithPhoneCredential(credential);
        } catch (Exception e) {
            emitFirebaseError(firebaseFriendlyError(e));
        }
    }

    private void signInWithPhoneCredential(PhoneAuthCredential credential) {
        firebaseAuth.signInWithCredential(credential)
                .addOnSuccessListener(result -> {
                    phoneVerificationId = null;
                    phoneResendToken = null;
                    finishSocialSignIn(result.getUser(), "phone");
                    js("window.__elyaPhoneVerified && window.__elyaPhoneVerified();");
                })
                .addOnFailureListener(err -> emitFirebaseError(firebaseFriendlyError(err)));
    }

    private void finishSocialSignIn(FirebaseUser user, String provider) {
        if (user == null) {
            emitFirebaseError("Sign-In completed but no user session was returned.");
            return;
        }
        String display = clean(user.getDisplayName());
        if (display.isEmpty()) {
            String phone = clean(user.getPhoneNumber());
            display = phone.isEmpty() ? "Elya Listener" : "Elya " + phone.substring(Math.max(0, phone.length() - 4));
        }
        final String displayName = display;
        Map<String, Object> data = new HashMap<>();
        data.put("email", clean(user.getEmail()));
        data.put("phoneNumber", clean(user.getPhoneNumber()));
        data.put("displayName", displayName);
        data.put("provider", provider);
        data.put("updatedAt", FieldValue.serverTimestamp());
        firestore.collection("users").document(user.getUid()).get()
                .addOnSuccessListener(doc -> {
                    if (!doc.exists()) {
                        data.put("bio", "");
                        data.put("favoriteArtist", "");
                        data.put("createdAt", FieldValue.serverTimestamp());
                    }
                    firestore.collection("users").document(user.getUid()).set(data, SetOptions.merge())
                            .addOnCompleteListener(task -> {
                                emitFirebaseState(user, null);
                                loadFirebaseProfile(user);
                                emitFirebaseMessage("Signed in to Elya with " + ("google".equals(provider) ? "Google." : "your phone."));
                            });
                })
                .addOnFailureListener(err -> {
                    emitFirebaseState(user, null);
                    emitFirebaseMessage("Signed in to Elya.");
                });
    }

'''
if 'private void launchGoogleSignIn()' not in s:
    s=s.replace('    private void emitFirebaseState(FirebaseUser user, JSONObject profile) {',helpers+'    private void emitFirebaseState(FirebaseUser user, JSONObject profile) {',1)

if 'out.put("phoneNumber"' not in s:
    s=s.replace('out.put("displayName", clean(user.getDisplayName()));', 'out.put("displayName", clean(user.getDisplayName()));\n                out.put("phoneNumber", clean(user.getPhoneNumber()));',1)

if 'invalid-verification-code' not in s:
    s=s.replace('if (m.contains("CONFIGURATION_NOT_FOUND")) return "Firebase Authentication is not enabled for this sign-in method yet.";', 'if (m.contains("CONFIGURATION_NOT_FOUND")) return "Firebase Authentication is not enabled for this sign-in method yet.";\n        if (m.toLowerCase(Locale.US).contains("invalid-verification-code")) return "That verification code is incorrect or expired.";\n        if (m.toLowerCase(Locale.US).contains("too many requests") || m.toLowerCase(Locale.US).contains("quota")) return "Too many verification attempts. Try again later.";',1)

p.write_text(s,encoding='utf-8')

# HTML/CSS/UI
p=root/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')

css='''<style id="elyaFirebase105Style">\n.elya-auth-alt #elyaGoogleSignIn{font-weight:700}.elya-phone-box{display:none;margin-top:10px;padding:12px;border:1px solid var(--line);border-radius:14px;background:rgba(255,255,255,.025)}.elya-phone-box.show{display:block}.elya-phone-row{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end}.elya-phone-code{display:none;margin-top:9px}.elya-phone-code.show{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:end}.elya-phone-note{font-size:11px;color:var(--muted);margin-top:8px;line-height:1.45}.elya-auth-provider-note{font-size:10px;color:var(--muted);text-align:center;margin-top:7px}@media(max-width:700px){.elya-phone-row,.elya-phone-code.show{grid-template-columns:1fr}.elya-phone-row button,.elya-phone-code button{width:100%}}\n</style>'''
if 'elyaFirebase105Style' not in h:
    h=h.replace('</head>',css+'\n</head>',1)

old='''      <div class="elya-auth-alt">\n        <button class="secondary" id="elyaGooglePending" disabled>Google · setup pending</button>\n        <button class="secondary" id="elyaPhonePending" disabled>Phone · setup pending</button>\n      </div>\n      <div class="elya-account-status" id="elyaAccountStatus">Sign in only if you want cloud profile features.</div>'''
new='''      <div class="elya-auth-alt">\n        <button class="secondary" id="elyaGoogleSignIn">Continue with Google</button>\n        <button class="secondary" id="elyaPhoneToggle">Continue with Phone</button>\n      </div>\n      <div class="elya-phone-box" id="elyaPhoneBox">\n        <div class="elya-phone-row">\n          <div class="field" style="margin:0"><label>Phone number</label><input id="elyaPhoneNumber" type="tel" autocomplete="tel" inputmode="tel" placeholder="+961... or +1..."></div>\n          <button class="primary" id="elyaPhoneSend">Send Code</button>\n        </div>\n        <div class="elya-phone-code" id="elyaPhoneCodeBox">\n          <div class="field" style="margin:0"><label>6-digit code</label><input id="elyaPhoneCode" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="123456"></div>\n          <button class="primary" id="elyaPhoneVerify">Verify</button>\n        </div>\n        <div class="elya-phone-note">Use the full international number with country code. Firebase may send an SMS and standard carrier rates may apply.</div>\n      </div>\n      <div class="elya-auth-provider-note">Account features are optional. Your music library stays on this device.</div>\n      <div class="elya-account-status" id="elyaAccountStatus">Sign in only if you want cloud profile features.</div>'''
if 'id="elyaGooglePending"' in h:
    h=h.replace(old,new,1)

js=r'''<script id="elyaFirebase105Script">
/* ===== ELYA 1.0.5 GOOGLE + PHONE AUTH ===== */
(()=>{
  const q=s=>document.querySelector(s), bridge=()=>window.AndroidMusic;
  const status=t=>{const el=q('#elyaAccountStatus');if(el)el.textContent=t||''};
  const google=q('#elyaGoogleSignIn'),phoneToggle=q('#elyaPhoneToggle'),phoneBox=q('#elyaPhoneBox');
  const phoneSend=q('#elyaPhoneSend'),phoneVerify=q('#elyaPhoneVerify'),codeBox=q('#elyaPhoneCodeBox');

  google?.addEventListener('click',()=>{
    google.disabled=true;status('Opening Google Sign-In…');
    bridge()?.firebaseGoogleSignIn?.();
    setTimeout(()=>{if(google)google.disabled=false},5000);
  });
  phoneToggle?.addEventListener('click',()=>{
    phoneBox?.classList.toggle('show');
    if(phoneBox?.classList.contains('show')) q('#elyaPhoneNumber')?.focus();
  });
  phoneSend?.addEventListener('click',()=>{
    const phone=q('#elyaPhoneNumber')?.value?.trim()||'';
    phoneSend.disabled=true;status('Sending verification code…');
    bridge()?.firebasePhoneSendCode?.(phone);
    setTimeout(()=>{if(phoneSend)phoneSend.disabled=false},3500);
  });
  phoneVerify?.addEventListener('click',()=>{
    const code=(q('#elyaPhoneCode')?.value||'').replace(/\D/g,'').slice(0,6);
    phoneVerify.disabled=true;status('Verifying code…');
    bridge()?.firebasePhoneVerifyCode?.(code);
    setTimeout(()=>{if(phoneVerify)phoneVerify.disabled=false},3500);
  });
  q('#elyaPhoneCode')?.addEventListener('input',e=>{e.target.value=e.target.value.replace(/\D/g,'').slice(0,6)});

  window.__elyaPhoneCodeSent=phone=>{
    codeBox?.classList.add('show');
    status(`Code sent to ${phone}. Enter the 6-digit code.`);
    q('#elyaPhoneCode')?.focus();
    if(phoneSend)phoneSend.disabled=false;
  };
  window.__elyaPhoneVerified=()=>{
    status('Phone verified. Signed in to Elya.');
    if(phoneVerify)phoneVerify.disabled=false;
    phoneBox?.classList.remove('show');
  };

  const oldErr=window.__elyaFirebaseError;
  window.__elyaFirebaseError=message=>{
    if(google)google.disabled=false;if(phoneSend)phoneSend.disabled=false;if(phoneVerify)phoneVerify.disabled=false;
    oldErr?.(message);
  };
  const oldState=window.__elyaFirebaseAuthState;
  window.__elyaFirebaseAuthState=data=>{
    if(google)google.disabled=false;if(phoneSend)phoneSend.disabled=false;if(phoneVerify)phoneVerify.disabled=false;
    if(data?.signedIn)phoneBox?.classList.remove('show');
    oldState?.(data);
  };
})();
</script>'''
if 'elyaFirebase105Script' not in h:
    h=h.replace('</body>',js+'\n</body>',1)

p.write_text(h,encoding='utf-8')
print('Elya 1.0.5 Google + Phone auth patch applied')

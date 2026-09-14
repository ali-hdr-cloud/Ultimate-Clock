package com.elya.music;

import android.Manifest;
import android.app.Activity;
import android.os.Bundle;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.CancellationSignal;
import android.os.ParcelFileDescriptor;
import android.content.Intent;
import android.content.ContentResolver;
import android.content.ContentUris;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.graphics.Color;
import android.media.MediaMetadataRetriever;
import android.net.Uri;
import android.provider.DocumentsContract;
import android.provider.MediaStore;
import android.provider.OpenableColumns;
import android.provider.Settings;
import android.webkit.JavascriptInterface;
import android.webkit.MimeTypeMap;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import androidx.annotation.NonNull;
import androidx.credentials.Credential;
import androidx.credentials.CredentialManager;
import androidx.credentials.CredentialManagerCallback;
import androidx.credentials.CustomCredential;
import androidx.credentials.GetCredentialRequest;
import androidx.credentials.GetCredentialResponse;
import androidx.credentials.exceptions.GetCredentialException;

import com.google.android.libraries.identity.googleid.GetGoogleIdOption;
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential;
import com.google.firebase.FirebaseApp;
import com.google.firebase.FirebaseException;
import com.google.firebase.auth.AuthCredential;
import com.google.firebase.auth.FirebaseAuth;
import com.google.firebase.auth.FirebaseAuthException;
import com.google.firebase.auth.FirebaseUser;
import com.google.firebase.auth.GoogleAuthProvider;
import com.google.firebase.auth.PhoneAuthCredential;
import com.google.firebase.auth.PhoneAuthOptions;
import com.google.firebase.auth.PhoneAuthProvider;
import com.google.firebase.auth.UserProfileChangeRequest;
import com.google.firebase.firestore.FieldValue;
import com.google.firebase.firestore.FirebaseFirestore;
import com.google.firebase.firestore.SetOptions;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public class MainActivity extends Activity {
    // ELYA_NATIVE_CORE_107
    private static final int REQ_TREE = 4101;
    private static final int REQ_FILE = 4102;
    private static final int REQ_AUDIO_PERMISSION = 4103;
    private static final String PREFS = "elya_android";
    private static final String PREF_TREE = "music_tree_uri";
    private static final String APP_URL = "file:///android_asset/index.html";
    private static final String MEDIA_HOST = "elya.local";

    private WebView webView;
    private ValueCallback<Uri[]> fileCallback;
    private final ExecutorService io = Executors.newSingleThreadExecutor();
    private final Handler main = new Handler(Looper.getMainLooper());
    private final Map<String, MediaEntry> mediaMap = new HashMap<>();
    private final AtomicBoolean deviceScanRunning = new AtomicBoolean(false);
    private volatile long lastScanCount = 0;
    private volatile String lastScanError = "";
    private volatile boolean pageReady = false;
    private volatile JSONArray pendingLibrary = null;
    private volatile String pendingLibraryName = null;

    private FirebaseAuth firebaseAuth;
    private FirebaseFirestore firestore;
    private CredentialManager credentialManager;
    private String firebaseInitError = "";
    private String phoneVerificationId;
    private PhoneAuthProvider.ForceResendingToken phoneResendToken;

    static final class MediaEntry {
        final Uri uri;
        final String mime;
        final long size;
        final String name;
        MediaEntry(Uri uri, String mime, long size, String name) {
            this.uri = uri;
            this.mime = mime == null ? "audio/*" : mime;
            this.size = size;
            this.name = name == null ? "" : name;
        }
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(5, 8, 13));
        getWindow().setNavigationBarColor(Color.rgb(5, 8, 13));

        try {
            FirebaseApp app = FirebaseApp.initializeApp(this);
            if (app == null && FirebaseApp.getApps(this).isEmpty()) {
                firebaseInitError = "FirebaseApp did not initialize.";
            }
            firebaseAuth = FirebaseAuth.getInstance();
            firestore = FirebaseFirestore.getInstance();
            credentialManager = CredentialManager.create(this);
            firebaseAuth.useAppLanguage();
        } catch (Exception e) {
            firebaseInitError = e.getClass().getSimpleName() + ": " + clean(e.getMessage());
        }

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(5, 8, 13));
        setContentView(webView);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setLoadsImagesAutomatically(true);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setSupportZoom(false);
        if (Build.VERSION.SDK_INT >= 26) s.setSafeBrowsingEnabled(true);

        webView.addJavascriptInterface(new AndroidMusicBridge(), "AndroidMusic");
        webView.setWebChromeClient(new ElyaChromeClient());
        webView.setWebViewClient(new ElyaWebViewClient());
        webView.loadUrl(APP_URL);
    }

    private class AndroidMusicBridge {
        @JavascriptInterface public String ping() {
            return "elya-bridge-1.0.7";
        }

        @JavascriptInterface public String diagnostics() {
            return buildDiagnostics().toString();
        }

        @JavascriptInterface public void nativeReady() {
            pageReady = true;
            main.post(() -> {
                flushPendingLibrary();
                emitDiagnostics();
                ensureAudioPermissionAndScan();
            });
        }

        @JavascriptInterface public void chooseMusicFolder() {
            main.post(MainActivity.this::chooseMusicFolderNative);
        }

        @JavascriptInterface public void restoreMusicFolder() {
            main.post(() -> ensureAudioPermissionAndScan());
        }

        @JavascriptInterface public void rescanMusicFolder() {
            main.post(() -> ensureAudioPermissionAndScan());
        }

        @JavascriptInterface public void scanAllDeviceMusic() {
            main.post(() -> ensureAudioPermissionAndScan());
        }

        @JavascriptInterface public void openAppSettings() {
            main.post(() -> {
                Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:" + getPackageName()));
                startActivity(i);
            });
        }

        @JavascriptInterface public void firebaseCurrentUser() {
            main.post(() -> {
                if (!firebaseReady()) {
                    emitFirebaseError(firebaseInitProblem());
                    return;
                }
                FirebaseUser user = firebaseAuth.getCurrentUser();
                emitFirebaseState(user, null);
                if (user != null) loadFirebaseProfile(user);
                emitDiagnostics();
            });
        }

        @JavascriptInterface public void firebaseEmailSignUp(String email, String password) {
            main.post(() -> emailSignUpNative(email, password));
        }

        @JavascriptInterface public void firebaseEmailSignIn(String email, String password) {
            main.post(() -> emailSignInNative(email, password));
        }

        @JavascriptInterface public void firebaseGoogleSignIn() {
            main.post(() -> launchGoogleSignIn());
        }

        @JavascriptInterface public void firebasePhoneSendCode(String phoneNumber) {
            main.post(() -> startPhoneVerification(phoneNumber));
        }

        @JavascriptInterface public void firebasePhoneVerifyCode(String code) {
            main.post(() -> verifyPhoneCode(code));
        }

        @JavascriptInterface public void firebaseSignOut() {
            main.post(() -> {
                if (!firebaseReady()) {
                    emitFirebaseError(firebaseInitProblem());
                    return;
                }
                firebaseAuth.signOut();
                emitFirebaseState(null, null);
                emitFirebaseMessage("Signed out.");
                emitDiagnostics();
            });
        }

        @JavascriptInterface public void firebaseSaveProfile(String displayName, String bio, String favoriteArtist) {
            main.post(() -> saveProfileNative(displayName, bio, favoriteArtist));
        }
    }

    private class ElyaChromeClient extends WebChromeClient {
        @Override
        public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                         FileChooserParams params) {
            if (fileCallback != null) fileCallback.onReceiveValue(null);
            fileCallback = callback;
            Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            intent.setType("*/*");
            String[] accepts = params.getAcceptTypes();
            if (accepts != null && accepts.length > 0) {
                ArrayList<String> clean = new ArrayList<>();
                for (String a : accepts) if (a != null && !a.trim().isEmpty()) clean.add(a);
                if (clean.size() == 1) intent.setType(clean.get(0));
                else if (!clean.isEmpty()) intent.putExtra(Intent.EXTRA_MIME_TYPES, clean.toArray(new String[0]));
            }
            if (params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE) {
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
            }
            startActivityForResult(intent, REQ_FILE);
            return true;
        }
    }

    private class ElyaWebViewClient extends WebViewClient {
        @Override
        public void onPageFinished(WebView view, String url) {
            super.onPageFinished(view, url);
            if (APP_URL.equals(url)) {
                pageReady = true;
                flushPendingLibrary();
                emitDiagnostics();
                // HTML also calls restoreMusicFolder; the AtomicBoolean prevents duplicate scans.
            }
        }

        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            Uri u = request.getUrl();
            if (!"https".equals(u.getScheme()) || !MEDIA_HOST.equals(u.getHost())) return null;
            String path = u.getPath();
            if (path == null) return null;
            if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
                Map<String, String> headers = corsHeaders();
                return new WebResourceResponse("text/plain", "UTF-8", 204, "No Content", headers,
                        new ByteArrayInputStream(new byte[0]));
            }
            if (path.startsWith("/audio/")) {
                String token = path.substring("/audio/".length());
                MediaEntry entry;
                synchronized (mediaMap) { entry = mediaMap.get(token); }
                if (entry == null) return null;
                try {
                    return openAudioResponse(entry, request.getRequestHeaders().get("Range"));
                } catch (Exception e) {
                    return null;
                }
            }
            if (path.startsWith("/cover/")) {
                String token = path.substring("/cover/".length());
                MediaEntry entry;
                synchronized (mediaMap) { entry = mediaMap.get(token); }
                if (entry == null) return null;
                byte[] art = readEmbeddedPicture(entry.uri);
                if (art == null) return null;
                return new WebResourceResponse("image/jpeg", null, 200, "OK", corsHeaders(),
                        new ByteArrayInputStream(art));
            }
            return null;
        }
    }

    private boolean firebaseReady() {
        return firebaseAuth != null && firebaseInitError.isEmpty();
    }

    private String firebaseInitProblem() {
        return firebaseInitError.isEmpty() ? "Firebase is not ready in this Elya build." :
                "Firebase startup failed: " + firebaseInitError;
    }

    private void emailSignUpNative(String email, String password) {
        if (!firebaseReady()) {
            emitFirebaseError(firebaseInitProblem());
            return;
        }
        String e = email == null ? "" : email.trim();
        String pw = password == null ? "" : password;
        if (e.isEmpty() || !e.contains("@")) {
            emitFirebaseError("Enter a valid email address.");
            return;
        }
        if (pw.length() < 6) {
            emitFirebaseError("Password must be at least 6 characters.");
            return;
        }
        emitAuthEvent("email_signup", "started", "Creating account...");
        firebaseAuth.createUserWithEmailAndPassword(e, pw)
                .addOnSuccessListener(result -> {
                    FirebaseUser user = result.getUser();
                    if (user == null) {
                        emitFirebaseError("Firebase created no user session.");
                        return;
                    }
                    emitFirebaseState(user, null);
                    emitAuthEvent("email_signup", "success", "Account created.");
                    emitFirebaseMessage("Elya account created.");
                    syncProfileAsync(user, "email");
                    emitDiagnostics();
                })
                .addOnFailureListener(err -> {
                    String msg = firebaseFriendlyError(err);
                    emitAuthEvent("email_signup", "error", msg);
                    emitFirebaseError(msg);
                });
    }

    private void emailSignInNative(String email, String password) {
        if (!firebaseReady()) {
            emitFirebaseError(firebaseInitProblem());
            return;
        }
        String e = email == null ? "" : email.trim();
        String pw = password == null ? "" : password;
        if (e.isEmpty() || pw.isEmpty()) {
            emitFirebaseError("Enter your email and password.");
            return;
        }
        emitAuthEvent("email_signin", "started", "Signing in...");
        firebaseAuth.signInWithEmailAndPassword(e, pw)
                .addOnSuccessListener(result -> {
                    FirebaseUser user = result.getUser();
                    if (user == null) {
                        emitFirebaseError("Firebase returned no user session.");
                        return;
                    }
                    emitFirebaseState(user, null);
                    emitAuthEvent("email_signin", "success", "Signed in.");
                    emitFirebaseMessage("Signed in to Elya.");
                    loadFirebaseProfile(user);
                    emitDiagnostics();
                })
                .addOnFailureListener(err -> {
                    String msg = firebaseFriendlyError(err);
                    emitAuthEvent("email_signin", "error", msg);
                    emitFirebaseError(msg);
                });
    }

    private void launchGoogleSignIn() {
        if (!firebaseReady()) {
            emitFirebaseError(firebaseInitProblem());
            return;
        }
        if (credentialManager == null) {
            emitFirebaseError("Google Sign-In is unavailable on this device.");
            return;
        }
        try {
            emitAuthEvent("google", "started", "Opening Google Sign-In...");
            GetGoogleIdOption option = new GetGoogleIdOption.Builder()
                    .setFilterByAuthorizedAccounts(false)
                    .setServerClientId(getString(R.string.default_web_client_id))
                    .setAutoSelectEnabled(false)
                    .build();
            GetCredentialRequest request = new GetCredentialRequest.Builder()
                    .addCredentialOption(option)
                    .build();
            credentialManager.getCredentialAsync(
                    MainActivity.this,
                    request,
                    new CancellationSignal(),
                    command -> main.post(command),
                    new CredentialManagerCallback<GetCredentialResponse, GetCredentialException>() {
                        @Override public void onResult(GetCredentialResponse result) {
                            handleGoogleCredential(result.getCredential());
                        }
                        @Override public void onError(GetCredentialException e) {
                            String msg = "Google Sign-In was cancelled or no Google account is available.";
                            emitAuthEvent("google", "error", msg);
                            emitFirebaseError(msg);
                        }
                    }
            );
        } catch (Exception e) {
            String msg = "Could not open Google Sign-In: " + firebaseFriendlyError(e);
            emitAuthEvent("google", "error", msg);
            emitFirebaseError(msg);
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
                    .addOnFailureListener(err -> {
                        String msg = firebaseFriendlyError(err);
                        emitAuthEvent("google", "error", msg);
                        emitFirebaseError(msg);
                    });
        } catch (Exception e) {
            String msg = "Could not finish Google Sign-In: " + firebaseFriendlyError(e);
            emitAuthEvent("google", "error", msg);
            emitFirebaseError(msg);
        }
    }

    private void startPhoneVerification(String rawPhone) {
        if (!firebaseReady()) {
            emitFirebaseError(firebaseInitProblem());
            return;
        }
        String phone = rawPhone == null ? "" : rawPhone.trim().replaceAll("[\\s()\\-]", "");
        if (!phone.matches("^\\+[1-9][0-9]{7,14}$")) {
            emitFirebaseError("Use the full phone number with country code, for example +961...");
            return;
        }
        emitAuthEvent("phone_send", "started", "Requesting SMS from Firebase...");
        PhoneAuthOptions options = PhoneAuthOptions.newBuilder(firebaseAuth)
                .setPhoneNumber(phone)
                .setTimeout(60L, TimeUnit.SECONDS)
                .setActivity(this)
                .setCallbacks(new PhoneAuthProvider.OnVerificationStateChangedCallbacks() {
                    @Override public void onVerificationCompleted(@NonNull PhoneAuthCredential credential) {
                        emitAuthEvent("phone_send", "auto_verified", "Phone automatically verified.");
                        signInWithPhoneCredential(credential);
                    }

                    @Override public void onVerificationFailed(@NonNull FirebaseException e) {
                        String msg = firebaseFriendlyError(e);
                        emitAuthEvent("phone_send", "error", msg);
                        emitFirebaseError(msg);
                    }

                    @Override public void onCodeSent(@NonNull String verificationId,
                                                     @NonNull PhoneAuthProvider.ForceResendingToken token) {
                        phoneVerificationId = verificationId;
                        phoneResendToken = token;
                        emitAuthEvent("phone_send", "success", "Verification code sent.");
                        js("window.__elyaPhoneCodeSent&&window.__elyaPhoneCodeSent(" + JSONObject.quote(phone) + ");");
                        emitFirebaseMessage("Verification code sent.");
                    }
                })
                .build();
        PhoneAuthProvider.verifyPhoneNumber(options);
    }

    private void verifyPhoneCode(String rawCode) {
        if (!firebaseReady()) {
            emitFirebaseError(firebaseInitProblem());
            return;
        }
        String code = rawCode == null ? "" : rawCode.replaceAll("[^0-9]", "");
        if (phoneVerificationId == null || phoneVerificationId.isEmpty()) {
            emitFirebaseError("Send a verification code first.");
            return;
        }
        if (code.length() != 6) {
            emitFirebaseError("Enter the 6-digit verification code.");
            return;
        }
        emitAuthEvent("phone_verify", "started", "Verifying code...");
        try {
            signInWithPhoneCredential(PhoneAuthProvider.getCredential(phoneVerificationId, code));
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
                    emitAuthEvent("phone_verify", "success", "Phone verified.");
                    js("window.__elyaPhoneVerified&&window.__elyaPhoneVerified();");
                })
                .addOnFailureListener(err -> {
                    String msg = firebaseFriendlyError(err);
                    emitAuthEvent("phone_verify", "error", msg);
                    emitFirebaseError(msg);
                });
    }

    private void finishSocialSignIn(FirebaseUser user, String provider) {
        if (user == null) {
            emitFirebaseError("Sign-In completed but no user session was returned.");
            return;
        }
        emitFirebaseState(user, null);
        emitAuthEvent(provider, "success", "Signed in.");
        emitFirebaseMessage("Signed in to Elya with " + ("google".equals(provider) ? "Google." : "your phone."));
        syncProfileAsync(user, provider);
        emitDiagnostics();
    }

    private void syncProfileAsync(FirebaseUser user, String provider) {
        if (user == null || firestore == null) return;
        String display = clean(user.getDisplayName());
        if (display.isEmpty()) {
            String phone = clean(user.getPhoneNumber());
            display = phone.isEmpty() ? "Elya Listener" : "Elya " + phone.substring(Math.max(0, phone.length() - 4));
        }
        Map<String, Object> data = new HashMap<>();
        data.put("email", clean(user.getEmail()));
        data.put("phoneNumber", clean(user.getPhoneNumber()));
        data.put("displayName", display);
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
                            .addOnSuccessListener(v -> loadFirebaseProfile(user))
                            .addOnFailureListener(err -> emitFirebaseMessage("Signed in. Cloud profile sync will retry later."));
                })
                .addOnFailureListener(err -> emitFirebaseMessage("Signed in. Cloud profile sync will retry later."));
    }

    private void saveProfileNative(String displayName, String bio, String favoriteArtist) {
        if (!firebaseReady()) {
            emitFirebaseError(firebaseInitProblem());
            return;
        }
        FirebaseUser user = firebaseAuth.getCurrentUser();
        if (user == null) {
            emitFirebaseError("Sign in to sync your profile.");
            return;
        }
        String n = displayName == null || displayName.trim().isEmpty() ? "Elya Listener" : displayName.trim();
        String b = bio == null ? "" : bio.trim();
        String f = favoriteArtist == null ? "" : favoriteArtist.trim();
        user.updateProfile(new UserProfileChangeRequest.Builder().setDisplayName(n).build());
        if (firestore == null) {
            emitFirebaseMessage("Profile updated on this account. Cloud profile storage is unavailable.");
            emitFirebaseState(user, null);
            return;
        }
        Map<String, Object> data = new HashMap<>();
        data.put("email", clean(user.getEmail()));
        data.put("phoneNumber", clean(user.getPhoneNumber()));
        data.put("displayName", n);
        data.put("bio", b);
        data.put("favoriteArtist", f);
        data.put("updatedAt", FieldValue.serverTimestamp());
        firestore.collection("users").document(user.getUid()).set(data, SetOptions.merge())
                .addOnSuccessListener(v -> {
                    emitFirebaseMessage("Profile synced to Elya Cloud.");
                    loadFirebaseProfile(user);
                })
                .addOnFailureListener(err -> emitFirebaseError(firebaseFriendlyError(err)));
    }

    private void emitFirebaseState(FirebaseUser user, JSONObject profile) {
        try {
            JSONObject out = new JSONObject();
            out.put("signedIn", user != null);
            if (user != null) {
                out.put("uid", user.getUid());
                out.put("email", clean(user.getEmail()));
                out.put("displayName", clean(user.getDisplayName()));
                out.put("phoneNumber", clean(user.getPhoneNumber()));
            }
            if (profile != null) out.put("profile", profile);
            js("window.__elyaFirebaseAuthState&&window.__elyaFirebaseAuthState(" + out.toString() + ");");
        } catch (Exception ignored) {}
    }

    private void loadFirebaseProfile(FirebaseUser user) {
        if (user == null || firestore == null) {
            emitFirebaseState(user, null);
            return;
        }
        firestore.collection("users").document(user.getUid()).get()
                .addOnSuccessListener(doc -> {
                    try {
                        JSONObject p = new JSONObject();
                        p.put("displayName", clean(doc.getString("displayName")));
                        p.put("bio", clean(doc.getString("bio")));
                        p.put("favoriteArtist", clean(doc.getString("favoriteArtist")));
                        emitFirebaseState(user, p);
                    } catch (Exception e) {
                        emitFirebaseState(user, null);
                    }
                })
                .addOnFailureListener(err -> emitFirebaseState(user, null));
    }

    private void emitAuthEvent(String action, String status, String message) {
        try {
            JSONObject o = new JSONObject();
            o.put("action", action);
            o.put("status", status);
            o.put("message", message == null ? "" : message);
            js("window.__elyaNativeAuthEvent&&window.__elyaNativeAuthEvent(" + o.toString() + ");");
        } catch (Exception ignored) {}
    }

    private void emitFirebaseError(String message) {
        js("window.__elyaFirebaseError&&window.__elyaFirebaseError(" + JSONObject.quote(message == null ? "Firebase error" : message) + ");");
    }

    private void emitFirebaseMessage(String message) {
        js("window.__elyaFirebaseMessage&&window.__elyaFirebaseMessage(" + JSONObject.quote(message == null ? "Done" : message) + ");");
    }

    private static String firebaseFriendlyError(Exception e) {
        if (e == null) return "Could not complete the account action.";
        if (e instanceof FirebaseAuthException) {
            String code = ((FirebaseAuthException) e).getErrorCode();
            if (code != null) {
                switch (code) {
                    case "ERROR_INVALID_EMAIL": return "That email address is not valid.";
                    case "ERROR_EMAIL_ALREADY_IN_USE": return "That email already has an Elya account. Tap Sign In instead.";
                    case "ERROR_WEAK_PASSWORD": return "Password is too weak. Use at least 6 characters.";
                    case "ERROR_USER_NOT_FOUND": return "No Elya account was found for that email.";
                    case "ERROR_WRONG_PASSWORD":
                    case "ERROR_INVALID_CREDENTIAL":
                    case "ERROR_INVALID_LOGIN_CREDENTIALS": return "Email or password is incorrect.";
                    case "ERROR_OPERATION_NOT_ALLOWED": return "This sign-in method is not enabled in Firebase.";
                    case "ERROR_TOO_MANY_REQUESTS": return "Too many attempts. Wait a little and try again.";
                    case "ERROR_APP_NOT_AUTHORIZED": return "Firebase does not recognize this Elya app signature.";
                    case "ERROR_INVALID_VERIFICATION_CODE": return "That SMS code is incorrect or expired.";
                    case "ERROR_SESSION_EXPIRED": return "That SMS session expired. Send a new code.";
                }
            }
        }
        String m = e.getMessage() == null ? "Could not complete the account action." : e.getMessage();
        String l = m.toLowerCase(Locale.US);
        if ((l.contains("sms") && l.contains("region")) || l.contains("blocked for this region")) {
            return "Firebase is blocking SMS to this country. In Firebase: Authentication > Settings > SMS region policy, allow this country.";
        }
        if (l.contains("quota") || l.contains("too many requests")) {
            return "Firebase SMS limit was reached. Try again later or check the SMS quota.";
        }
        if (l.contains("network")) return "Check your internet connection and try again.";
        if (l.contains("recaptcha") || l.contains("play integrity")) {
            return "Phone verification could not verify this app. Check Google Play Services and Firebase SHA fingerprints.";
        }
        return m.length() > 260 ? m.substring(0, 260) : m;
    }

    private void chooseMusicFolderNative() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION
                | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
                | Intent.FLAG_GRANT_PREFIX_URI_PERMISSION);
        startActivityForResult(intent, REQ_TREE);
    }

    private boolean hasAudioPermission() {
        if (Build.VERSION.SDK_INT >= 33) {
            return checkSelfPermission(Manifest.permission.READ_MEDIA_AUDIO) == PackageManager.PERMISSION_GRANTED;
        }
        if (Build.VERSION.SDK_INT >= 23) {
            return checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED;
        }
        return true;
    }

    private String audioPermissionName() {
        return Build.VERSION.SDK_INT >= 33 ? Manifest.permission.READ_MEDIA_AUDIO : Manifest.permission.READ_EXTERNAL_STORAGE;
    }

    private void ensureAudioPermissionAndScan() {
        if (deviceScanRunning.get()) {
            emitDiagnostics();
            return;
        }
        if (hasAudioPermission()) {
            scanAllDeviceMusicNative();
            return;
        }
        if (Build.VERSION.SDK_INT >= 23) {
            emitScanStatus("permission", "Music permission is required for automatic scanning.");
            requestPermissions(new String[]{audioPermissionName()}, REQ_AUDIO_PERMISSION);
        } else {
            scanAllDeviceMusicNative();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_AUDIO_PERMISSION) return;
        if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            emitScanStatus("permission", "Music access allowed.");
            scanAllDeviceMusicNative();
        } else {
            lastScanError = "Music permission denied";
            String saved = getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_TREE, null);
            if (saved != null) {
                emitScanStatus("fallback", "Music permission denied. Using your saved folder instead.");
                scanTree(Uri.parse(saved), false);
            } else {
                emitScanStatus("permission_denied", "Music permission denied. Allow Music & Audio in Android settings, or choose a folder.");
                js("window.__elyaNativePermissionFallback&&window.__elyaNativePermissionFallback(false);");
            }
            emitDiagnostics();
        }
    }

    private void scanAllDeviceMusicNative() {
        if (!deviceScanRunning.compareAndSet(false, true)) return;
        io.execute(() -> {
            ArrayList<JSONObject> items = new ArrayList<>();
            int successfulVolumes = 0;
            try {
                lastScanError = "";
                js("window.__elyaNativeScanStarted&&window.__elyaNativeScanStarted('Device music');");
                emitScanStatus("started", "Scanning device music...");
                synchronized (mediaMap) { mediaMap.clear(); }
                Set<String> seen = new HashSet<>();

                if (Build.VERSION.SDK_INT >= 29) {
                    Set<String> volumes = new HashSet<>(MediaStore.getExternalVolumeNames(this));
                    if (volumes.isEmpty()) volumes.add(MediaStore.VOLUME_EXTERNAL_PRIMARY);
                    for (String volume : volumes) {
                        Uri collection = MediaStore.Audio.Media.getContentUri(volume);
                        if (scanMediaCollection(collection, volume, items, seen)) successfulVolumes++;
                    }
                } else {
                    if (scanMediaCollection(MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,
                            "external", items, seen)) successfulVolumes++;
                }

                if (successfulVolumes == 0) {
                    lastScanError = "Android MediaStore returned no readable volumes.";
                    emitScanError(lastScanError + " Check Music & Audio permission.");
                    return;
                }

                lastScanCount = items.size();
                deliverLibrary(items, "Device Music");
                emitScanStatus("success", items.size() + " audio files found.");
            } catch (Exception e) {
                lastScanError = e.getClass().getSimpleName() + ": " + clean(e.getMessage());
                emitScanError("Device scan failed: " + lastScanError);
            } finally {
                deviceScanRunning.set(false);
                js("window.__elyaNativeScanFinished&&window.__elyaNativeScanFinished();");
                emitDiagnostics();
            }
        });
    }

    private boolean scanMediaCollection(Uri collection, String volumeName,
                                        ArrayList<JSONObject> out, Set<String> seenUris) {
        String[] projection = new String[]{
                MediaStore.Audio.Media._ID,
                MediaStore.Audio.Media.DISPLAY_NAME,
                MediaStore.Audio.Media.TITLE,
                MediaStore.Audio.Media.ARTIST,
                MediaStore.Audio.Media.ALBUM,
                MediaStore.Audio.Media.DURATION,
                MediaStore.Audio.Media.MIME_TYPE,
                MediaStore.Audio.Media.SIZE,
                MediaStore.Audio.Media.YEAR,
                MediaStore.Audio.Media.TRACK
        };
        try (Cursor c = getContentResolver().query(collection, projection, null, null,
                MediaStore.Audio.Media.DATE_ADDED + " DESC")) {
            if (c == null) return false;
            int idCol = c.getColumnIndex(MediaStore.Audio.Media._ID);
            int nameCol = c.getColumnIndex(MediaStore.Audio.Media.DISPLAY_NAME);
            int titleCol = c.getColumnIndex(MediaStore.Audio.Media.TITLE);
            int artistCol = c.getColumnIndex(MediaStore.Audio.Media.ARTIST);
            int albumCol = c.getColumnIndex(MediaStore.Audio.Media.ALBUM);
            int durationCol = c.getColumnIndex(MediaStore.Audio.Media.DURATION);
            int mimeCol = c.getColumnIndex(MediaStore.Audio.Media.MIME_TYPE);
            int sizeCol = c.getColumnIndex(MediaStore.Audio.Media.SIZE);
            int yearCol = c.getColumnIndex(MediaStore.Audio.Media.YEAR);
            int trackCol = c.getColumnIndex(MediaStore.Audio.Media.TRACK);

            while (c.moveToNext()) {
                if (idCol < 0) continue;
                long id = c.getLong(idCol);
                Uri uri = ContentUris.withAppendedId(collection, id);
                String key = uri.toString();
                if (!seenUris.add(key)) continue;

                String fileName = stringAt(c, nameCol);
                String mime = stringAt(c, mimeCol);
                if (!isAudio(fileName, mime)) continue;

                String title = cleanUnknown(stringAt(c, titleCol));
                String artist = cleanUnknown(stringAt(c, artistCol));
                String album = cleanUnknown(stringAt(c, albumCol));
                long durationMs = longAt(c, durationCol);
                long size = longAt(c, sizeCol);
                int year = intAt(c, yearCol);
                int track = intAt(c, trackCol);

                String token = Integer.toHexString(key.hashCode()) + "_" +
                        Integer.toHexString((volumeName + ":" + id).hashCode());
                synchronized (mediaMap) {
                    mediaMap.put(token, new MediaEntry(uri, normalizeMime(fileName, mime), size, fileName));
                }

                try {
                    JSONObject o = new JSONObject();
                    o.put("fileKey", key);
                    o.put("fileName", fileName);
                    o.put("title", title.isEmpty() ? stripExt(fileName) : title);
                    o.put("artist", artist);
                    o.put("album", album);
                    o.put("genre", "");
                    o.put("year", year > 0 ? String.valueOf(year) : "");
                    o.put("trackNo", track > 0 ? String.valueOf(track) : "");
                    o.put("albumArtist", "");
                    o.put("discNo", 1);
                    o.put("duration", durationMs > 0 ? durationMs / 1000.0 : 0);
                    o.put("url", "https://" + MEDIA_HOST + "/audio/" + token);
                    out.add(o);
                    int found = out.size();
                    if (found == 1 || found % 25 == 0) {
                        js("window.__elyaNativeScanProgress&&window.__elyaNativeScanProgress(" + found + ");");
                    }
                } catch (Exception ignored) {}
            }
            return true;
        } catch (SecurityException e) {
            lastScanError = "Permission denied reading " + volumeName;
            return false;
        } catch (Exception e) {
            lastScanError = e.getClass().getSimpleName() + " reading " + volumeName + ": " + clean(e.getMessage());
            return false;
        }
    }

    private void scanTree(Uri treeUri, boolean userInitiated) {
        if (!deviceScanRunning.compareAndSet(false, true)) return;
        io.execute(() -> {
            ArrayList<JSONObject> items = new ArrayList<>();
            try {
                String folderName = queryName(treeUri);
                if (folderName == null || folderName.isEmpty()) folderName = "Music folder";
                final String fn = folderName;
                js("window.__elyaNativeScanStarted&&window.__elyaNativeScanStarted(" + JSONObject.quote(fn) + ");");
                synchronized (mediaMap) { mediaMap.clear(); }
                String rootId = DocumentsContract.getTreeDocumentId(treeUri);
                scanDocumentChildren(treeUri, rootId, "", items);
                lastScanCount = items.size();
                lastScanError = "";
                deliverLibrary(items, fn);
                emitScanStatus("success", items.size() + " audio files found in " + fn + ".");
            } catch (Exception e) {
                lastScanError = e.getClass().getSimpleName() + ": " + clean(e.getMessage());
                emitScanError("Could not read this folder: " + lastScanError);
            } finally {
                deviceScanRunning.set(false);
                js("window.__elyaNativeScanFinished&&window.__elyaNativeScanFinished();");
                emitDiagnostics();
            }
        });
    }

    private void scanDocumentChildren(Uri treeUri, String parentDocumentId, String relPath,
                                      ArrayList<JSONObject> out) {
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, parentDocumentId);
        String[] projection = new String[]{
                DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE,
                DocumentsContract.Document.COLUMN_SIZE
        };
        try (Cursor c = getContentResolver().query(children, projection, null, null, null)) {
            if (c == null) return;
            int idCol = c.getColumnIndex(DocumentsContract.Document.COLUMN_DOCUMENT_ID);
            int nameCol = c.getColumnIndex(DocumentsContract.Document.COLUMN_DISPLAY_NAME);
            int mimeCol = c.getColumnIndex(DocumentsContract.Document.COLUMN_MIME_TYPE);
            int sizeCol = c.getColumnIndex(DocumentsContract.Document.COLUMN_SIZE);
            while (c.moveToNext()) {
                String docId = idCol >= 0 ? c.getString(idCol) : null;
                String name = nameCol >= 0 ? c.getString(nameCol) : "";
                String mime = mimeCol >= 0 ? c.getString(mimeCol) : "";
                long size = sizeCol >= 0 && !c.isNull(sizeCol) ? c.getLong(sizeCol) : -1;
                if (docId == null) continue;
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                    scanDocumentChildren(treeUri, docId, relPath + name + "/", out);
                    continue;
                }
                if (!isAudio(name, mime)) continue;
                Uri docUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, docId);
                JSONObject item = describeAudio(docUri, relPath + name, name, mime, size);
                if (item != null) {
                    out.add(item);
                    int found = out.size();
                    if (found == 1 || found % 10 == 0) {
                        js("window.__elyaNativeScanProgress&&window.__elyaNativeScanProgress(" + found + ");");
                    }
                }
            }
        } catch (Exception ignored) {}
    }

    private JSONObject describeAudio(Uri uri, String relPath, String fileName, String mime, long size) {
        MediaMetadataRetriever mmr = new MediaMetadataRetriever();
        try {
            if (!setRetrieverSource(mmr, uri)) return null;
            long durationMs = parseLong(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION));
            String title = clean(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE));
            String artist = clean(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST));
            String album = clean(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM));
            String genre = clean(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_GENRE));
            String year = clean(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_YEAR));
            String track = clean(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_CD_TRACK_NUMBER));
            String albumArtist = clean(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUMARTIST));
            String discNo = Build.VERSION.SDK_INT >= 23 ?
                    clean(mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DISC_NUMBER)) : "";
            String key = uri.toString();
            String token = Integer.toHexString(key.hashCode()) + "_" + Integer.toHexString(relPath.hashCode());
            synchronized (mediaMap) {
                mediaMap.put(token, new MediaEntry(uri, normalizeMime(fileName, mime), size, fileName));
            }
            JSONObject o = new JSONObject();
            o.put("fileKey", key);
            o.put("fileName", fileName);
            o.put("title", title.isEmpty() ? stripExt(fileName) : title);
            o.put("artist", artist);
            o.put("album", album);
            o.put("genre", genre);
            o.put("year", year);
            o.put("trackNo", track);
            o.put("albumArtist", albumArtist);
            o.put("discNo", discNo);
            o.put("duration", durationMs > 0 ? durationMs / 1000.0 : 0);
            o.put("url", "https://" + MEDIA_HOST + "/audio/" + token);
            byte[] art = mmr.getEmbeddedPicture();
            if (art != null && art.length > 0) o.put("cover", "https://" + MEDIA_HOST + "/cover/" + token);
            return o;
        } catch (Exception e) {
            return null;
        } finally {
            try { mmr.release(); } catch (Exception ignored) {}
        }
    }

    private boolean setRetrieverSource(MediaMetadataRetriever mmr, Uri uri) {
        try {
            mmr.setDataSource(this, uri);
            return true;
        } catch (Exception first) {
            try (ParcelFileDescriptor pfd = getContentResolver().openFileDescriptor(uri, "r")) {
                if (pfd == null) return false;
                mmr.setDataSource(pfd.getFileDescriptor());
                return true;
            } catch (Exception second) {
                return false;
            }
        }
    }

    private void deliverLibrary(ArrayList<JSONObject> items, String name) {
        JSONArray arr = new JSONArray();
        for (JSONObject o : items) arr.put(o);
        if (!pageReady || webView == null) {
            pendingLibrary = arr;
            pendingLibraryName = name;
            return;
        }
        js("window.__elyaReceiveNativeLibrary&&window.__elyaReceiveNativeLibrary(" +
                arr.toString() + "," + JSONObject.quote(name) + ");");
    }

    private void flushPendingLibrary() {
        JSONArray arr = pendingLibrary;
        String name = pendingLibraryName;
        if (arr == null || webView == null) return;
        pendingLibrary = null;
        pendingLibraryName = null;
        js("window.__elyaReceiveNativeLibrary&&window.__elyaReceiveNativeLibrary(" +
                arr.toString() + "," + JSONObject.quote(name == null ? "Device Music" : name) + ");");
    }

    private void emitScanStatus(String status, String message) {
        try {
            JSONObject o = new JSONObject();
            o.put("status", status);
            o.put("message", message == null ? "" : message);
            o.put("count", lastScanCount);
            js("window.__elyaNativeScanStatus&&window.__elyaNativeScanStatus(" + o.toString() + ");");
        } catch (Exception ignored) {}
    }

    private void emitScanError(String message) {
        js("window.__elyaNativeScanError&&window.__elyaNativeScanError(" + JSONObject.quote(message) + ");");
        emitScanStatus("error", message);
    }

    private JSONObject buildDiagnostics() {
        JSONObject o = new JSONObject();
        try {
            o.put("bridge", "ok");
            o.put("core", "1.0.7");
            o.put("sdk", Build.VERSION.SDK_INT);
            o.put("package", getPackageName());
            o.put("musicPermission", hasAudioPermission());
            o.put("scanRunning", deviceScanRunning.get());
            o.put("lastScanCount", lastScanCount);
            o.put("lastScanError", lastScanError);
            o.put("savedFolder", getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_TREE, "") != null &&
                    !getSharedPreferences(PREFS, MODE_PRIVATE).getString(PREF_TREE, "").isEmpty());
            o.put("firebaseReady", firebaseReady());
            o.put("firebaseInitError", firebaseInitError);
            try {
                FirebaseApp app = FirebaseApp.getInstance();
                o.put("firebaseProjectId", clean(app.getOptions().getProjectId()));
                o.put("firebaseAppId", clean(app.getOptions().getApplicationId()));
            } catch (Exception ignored) {}
            FirebaseUser user = firebaseAuth == null ? null : firebaseAuth.getCurrentUser();
            o.put("signedIn", user != null);
            if (user != null) {
                o.put("uid", user.getUid());
                o.put("email", clean(user.getEmail()));
                o.put("phone", clean(user.getPhoneNumber()));
            }
        } catch (Exception ignored) {}
        return o;
    }

    private void emitDiagnostics() {
        JSONObject o = buildDiagnostics();
        js("window.__elyaNativeDiagnostics&&window.__elyaNativeDiagnostics(" + o.toString() + ");");
    }

    private WebResourceResponse openAudioResponse(MediaEntry entry, String range) throws Exception {
        ContentResolver cr = getContentResolver();
        long total = entry.size;
        long start = 0;
        long end = total > 0 ? total - 1 : -1;
        boolean partial = false;
        if (range != null && range.startsWith("bytes=") && total > 0) {
            String spec = range.substring(6).split(",")[0].trim();
            String[] parts = spec.split("-", 2);
            if (!parts[0].isEmpty()) start = Long.parseLong(parts[0]);
            if (parts.length > 1 && !parts[1].isEmpty()) end = Math.min(total - 1, Long.parseLong(parts[1]));
            if (end < start) end = total - 1;
            partial = true;
        }
        InputStream base = cr.openInputStream(entry.uri);
        if (base == null) return null;
        long skipped = 0;
        while (skipped < start) {
            long n = base.skip(start - skipped);
            if (n <= 0) break;
            skipped += n;
        }
        InputStream body = base;
        long contentLength = total > 0 ? (partial ? end - start + 1 : total) : -1;
        if (contentLength >= 0) body = new LimitedInputStream(base, contentLength);
        Map<String, String> headers = corsHeaders();
        headers.put("Accept-Ranges", "bytes");
        headers.put("Cache-Control", "no-store");
        if (contentLength >= 0) headers.put("Content-Length", String.valueOf(contentLength));
        if (partial && total > 0) {
            headers.put("Content-Range", "bytes " + start + "-" + end + "/" + total);
            return new WebResourceResponse(entry.mime, null, 206, "Partial Content", headers, body);
        }
        return new WebResourceResponse(entry.mime, null, 200, "OK", headers, body);
    }

    private Map<String, String> corsHeaders() {
        Map<String, String> h = new HashMap<>();
        h.put("Access-Control-Allow-Origin", "*");
        h.put("Access-Control-Allow-Headers", "Range, Content-Type");
        h.put("Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length");
        h.put("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
        return h;
    }

    private static class LimitedInputStream extends FilterInputStream {
        private long remaining;
        LimitedInputStream(InputStream in, long remaining) {
            super(in);
            this.remaining = remaining;
        }
        @Override public int read() throws IOException {
            if (remaining <= 0) return -1;
            int v = super.read();
            if (v >= 0) remaining--;
            return v;
        }
        @Override public int read(byte[] b, int off, int len) throws IOException {
            if (remaining <= 0) return -1;
            len = (int) Math.min(len, remaining);
            int n = super.read(b, off, len);
            if (n > 0) remaining -= n;
            return n;
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_TREE) {
            if (resultCode == RESULT_OK && data != null && data.getData() != null) {
                Uri tree = data.getData();
                int flags = data.getFlags() & Intent.FLAG_GRANT_READ_URI_PERMISSION;
                try { getContentResolver().takePersistableUriPermission(tree, flags); } catch (Exception ignored) {}
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(PREF_TREE, tree.toString()).apply();
                scanTree(tree, true);
            }
            return;
        }
        if (requestCode == REQ_FILE) {
            if (fileCallback == null) return;
            Uri[] result = null;
            if (resultCode == RESULT_OK && data != null) {
                if (data.getClipData() != null) {
                    int n = data.getClipData().getItemCount();
                    result = new Uri[n];
                    for (int i = 0; i < n; i++) result[i] = data.getClipData().getItemAt(i).getUri();
                } else if (data.getData() != null) {
                    result = new Uri[]{data.getData()};
                }
            }
            fileCallback.onReceiveValue(result);
            fileCallback = null;
        }
    }

    private byte[] readEmbeddedPicture(Uri uri) {
        MediaMetadataRetriever mmr = new MediaMetadataRetriever();
        try {
            if (!setRetrieverSource(mmr, uri)) return null;
            return mmr.getEmbeddedPicture();
        } catch (Exception e) {
            return null;
        } finally {
            try { mmr.release(); } catch (Exception ignored) {}
        }
    }

    private String queryName(Uri uri) {
        try (Cursor c = getContentResolver().query(uri,
                new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst()) return c.getString(0);
        } catch (Exception ignored) {}
        return null;
    }

    private static boolean isAudio(String name, String mime) {
        if (mime != null && mime.toLowerCase(Locale.US).startsWith("audio/")) return true;
        String ext = "";
        int dot = name == null ? -1 : name.lastIndexOf('.');
        if (dot >= 0) ext = name.substring(dot + 1).toLowerCase(Locale.US);
        return ext.matches("mp3|m4a|aac|wav|ogg|oga|opus|flac|webm|mp4|aif|aiff|mka");
    }

    private static String normalizeMime(String name, String mime) {
        if (mime != null && mime.startsWith("audio/")) return mime;
        String ext = MimeTypeMap.getFileExtensionFromUrl(name == null ? "" : name);
        String guessed = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext == null ? "" : ext.toLowerCase(Locale.US));
        return guessed != null ? guessed : "audio/*";
    }

    private static String stringAt(Cursor c, int col) {
        if (col < 0 || c.isNull(col)) return "";
        String v = c.getString(col);
        return v == null ? "" : v.trim();
    }

    private static long longAt(Cursor c, int col) {
        if (col < 0 || c.isNull(col)) return 0;
        try { return c.getLong(col); } catch (Exception e) { return 0; }
    }

    private static int intAt(Cursor c, int col) {
        if (col < 0 || c.isNull(col)) return 0;
        try { return c.getInt(col); } catch (Exception e) { return 0; }
    }

    private static String cleanUnknown(String value) {
        if (value == null) return "";
        String v = value.trim();
        if ("<unknown>".equalsIgnoreCase(v) || "unknown".equalsIgnoreCase(v)) return "";
        return v;
    }

    private static String clean(String s) { return s == null ? "" : s.trim(); }

    private static long parseLong(String s) {
        try { return Long.parseLong(s == null ? "0" : s); } catch (Exception e) { return 0; }
    }

    private static String stripExt(String name) {
        if (name == null || name.trim().isEmpty()) return "Unknown Song";
        int dot = name.lastIndexOf('.');
        return dot > 0 ? name.substring(0, dot) : name;
    }

    private void js(String code) {
        main.post(() -> {
            if (webView != null) webView.evaluateJavascript(code, null);
        });
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) webView.goBack();
        else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        io.shutdownNow();
        if (webView != null) {
            webView.loadUrl("about:blank");
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}

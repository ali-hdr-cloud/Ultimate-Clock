from pathlib import Path
import re

r=Path('.')

# ---- Version ----
p=r/'app/build.gradle'
s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+15\b','versionCode 16',s,count=1)
s=re.sub(r"versionName\s+'1\.1\.4'","versionName '1.2.0'",s,count=1)
p.write_text(s,encoding='utf-8')

# ---- Native chat bridge ----
p=r/'app/src/main/java/com/elya/music/MainActivity.java'
s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_114','// ELYA_NATIVE_CORE_114\n    // ELYA_NATIVE_CORE_120',1)
s=s.replace('return "elya-bridge-1.1.4";','return "elya-bridge-1.2.0";',1)
s=s.replace('o.put("core", "1.1.4");','o.put("core", "1.2.0");',1)

imp='import com.google.firebase.firestore.SetOptions;'
repl='''import com.google.firebase.firestore.SetOptions;\nimport com.google.firebase.firestore.DocumentReference;\nimport com.google.firebase.firestore.DocumentSnapshot;\nimport com.google.firebase.firestore.ListenerRegistration;\nimport com.google.firebase.firestore.Query;'''
if imp not in s: raise SystemExit('firestore import anchor missing')
s=s.replace(imp,repl,1)

imp='import java.util.ArrayList;'
repl='''import java.util.ArrayList;\nimport java.util.Collections;\nimport java.util.Comparator;\nimport java.util.List;'''
if imp not in s: raise SystemExit('util import anchor missing')
s=s.replace(imp,repl,1)

field_anchor='''    private PhoneAuthProvider.ForceResendingToken phoneResendToken;'''
field_repl='''    private PhoneAuthProvider.ForceResendingToken phoneResendToken;\n\n    private ListenerRegistration chatListRegistration;\n    private ListenerRegistration chatMessageRegistration;\n    private volatile String activeChatId = "";'''
if field_anchor not in s: raise SystemExit('chat field anchor missing')
s=s.replace(field_anchor,field_repl,1)

bridge_anchor='''        @JavascriptInterface public void firebaseSaveProfile(String displayName, String bio, String favoriteArtist) {\n            main.post(() -> saveProfileNative(displayName, bio, favoriteArtist));\n        }'''
bridge_repl=bridge_anchor+'''\n\n        @JavascriptInterface public void chatMyProfile() {\n            main.post(MainActivity.this::chatMyProfileNative);\n        }\n\n        @JavascriptInterface public void chatSetUsername(String username) {\n            main.post(() -> chatSetUsernameNative(username));\n        }\n\n        @JavascriptInterface public void chatFindUsername(String username) {\n            main.post(() -> chatFindUsernameNative(username));\n        }\n\n        @JavascriptInterface public void chatListenConversations() {\n            main.post(MainActivity.this::chatListenConversationsNative);\n        }\n\n        @JavascriptInterface public void chatOpenWithUser(String uid, String displayName, String username) {\n            main.post(() -> chatOpenWithUserNative(uid, displayName, username));\n        }\n\n        @JavascriptInterface public void chatListenMessages(String chatId) {\n            main.post(() -> chatListenMessagesNative(chatId));\n        }\n\n        @JavascriptInterface public void chatSend(String chatId, String text) {\n            main.post(() -> chatSendNative(chatId, text));\n        }\n\n        @JavascriptInterface public void chatMarkSeen(String chatId) {\n            main.post(() -> chatMarkSeenNative(chatId));\n        }\n\n        @JavascriptInterface public void chatSetBlocked(String uid, boolean blocked) {\n            main.post(() -> chatSetBlockedNative(uid, blocked));\n        }\n\n        @JavascriptInterface public void chatCheckBlocked(String uid) {\n            main.post(() -> chatCheckBlockedNative(uid));\n        }\n\n        @JavascriptInterface public void chatStopListeners() {\n            main.post(MainActivity.this::chatStopListenersNative);\n        }'''
if bridge_anchor not in s: raise SystemExit('bridge anchor missing')
s=s.replace(bridge_anchor,bridge_repl,1)

methods=r'''
    // ---------------- Elya Chat 1.2.0 ----------------
    private FirebaseUser chatUserOrError() {
        if (!firebaseReady()) {
            emitChatError(firebaseInitProblem());
            return null;
        }
        FirebaseUser u = firebaseAuth.getCurrentUser();
        if (u == null) emitChatError("Sign in to your Elya account to use Chats.");
        return u;
    }

    private static String normalizeChatUsername(String raw) {
        String n = raw == null ? "" : raw.trim().toLowerCase(Locale.US);
        while (n.startsWith("@")) n = n.substring(1);
        return n.replaceAll("[^a-z0-9._]", "");
    }

    private static boolean validChatUsername(String n) {
        return n != null && n.matches("[a-z0-9][a-z0-9._]{2,23}") && !n.endsWith(".") && !n.endsWith("_");
    }

    private void chatMyProfileNative() {
        FirebaseUser u = chatUserOrError();
        if (u == null) return;
        firestore.collection("profiles").document(u.getUid()).get()
                .addOnSuccessListener(doc -> {
                    JSONObject o = publicProfileJson(u.getUid(), doc.exists() ? doc.getData() : null);
                    try {
                        if (o.optString("displayName").isEmpty()) o.put("displayName", clean(u.getDisplayName()).isEmpty() ? "Elya Listener" : clean(u.getDisplayName()));
                    } catch (Exception ignored) {}
                    emitChat("__elyaChatProfile", o);
                })
                .addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));
    }

    private void chatSetUsernameNative(String raw) {
        FirebaseUser u = chatUserOrError();
        if (u == null) return;
        final String username = normalizeChatUsername(raw);
        if (!validChatUsername(username)) {
            emitChatError("Username must be 3–24 characters using letters, numbers, . or _.");
            return;
        }
        final String uid = u.getUid();
        final DocumentReference userRef = firestore.collection("users").document(uid);
        final DocumentReference profileRef = firestore.collection("profiles").document(uid);
        final DocumentReference nameRef = firestore.collection("usernames").document(username);

        firestore.runTransaction(tx -> {
            DocumentSnapshot own = tx.get(userRef);
            String old = own.exists() ? clean(own.getString("usernameLower")) : "";
            DocumentSnapshot wanted = tx.get(nameRef);
            if (wanted.exists() && !uid.equals(clean(wanted.getString("uid")))) {
                throw new IllegalStateException("That username is already taken.");
            }
            DocumentReference oldRef = null;
            DocumentSnapshot oldSnap = null;
            if (!old.isEmpty() && !old.equals(username)) {
                oldRef = firestore.collection("usernames").document(old);
                oldSnap = tx.get(oldRef);
            }

            Map<String,Object> privateData = new HashMap<>();
            privateData.put("username", username);
            privateData.put("usernameLower", username);
            privateData.put("updatedAt", FieldValue.serverTimestamp());
            tx.set(userRef, privateData, SetOptions.merge());

            Map<String,Object> pub = new HashMap<>();
            String display = clean(u.getDisplayName());
            pub.put("displayName", display.isEmpty() ? "Elya Listener" : display);
            pub.put("username", username);
            pub.put("usernameLower", username);
            pub.put("updatedAt", FieldValue.serverTimestamp());
            tx.set(profileRef, pub, SetOptions.merge());

            Map<String,Object> reservation = new HashMap<>();
            reservation.put("uid", uid);
            reservation.put("username", username);
            reservation.put("updatedAt", FieldValue.serverTimestamp());
            tx.set(nameRef, reservation, SetOptions.merge());

            if (oldRef != null && oldSnap != null && oldSnap.exists() && uid.equals(clean(oldSnap.getString("uid")))) tx.delete(oldRef);
            return null;
        }).addOnSuccessListener(v -> {
            emitChatStatus("Username saved as @" + username + ".");
            chatMyProfileNative();
        }).addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));
    }

    private void chatFindUsernameNative(String raw) {
        FirebaseUser u = chatUserOrError();
        if (u == null) return;
        String username = normalizeChatUsername(raw);
        if (!validChatUsername(username)) {
            emitChatError("Enter a valid Elya username.");
            return;
        }
        firestore.collection("usernames").document(username).get()
                .addOnSuccessListener(nameDoc -> {
                    String uid = nameDoc.exists() ? clean(nameDoc.getString("uid")) : "";
                    if (uid.isEmpty()) {
                        emitChat("__elyaChatSearchResult", new JSONObject());
                        emitChatStatus("No user found with @" + username + ".");
                        return;
                    }
                    if (uid.equals(u.getUid())) {
                        emitChatError("That is your own username.");
                        return;
                    }
                    firestore.collection("profiles").document(uid).get()
                            .addOnSuccessListener(p -> emitChat("__elyaChatSearchResult", publicProfileJson(uid, p.getData())))
                            .addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));
                })
                .addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));
    }

    private String deterministicChatId(String a, String b) {
        return a.compareTo(b) < 0 ? a + "__" + b : b + "__" + a;
    }

    private void chatOpenWithUserNative(String otherUid, String otherName, String otherUsername) {
        FirebaseUser me = chatUserOrError();
        if (me == null) return;
        otherUid = clean(otherUid);
        if (otherUid.isEmpty() || otherUid.equals(me.getUid())) {
            emitChatError("Could not open that chat.");
            return;
        }
        final String chatId = deterministicChatId(me.getUid(), otherUid);
        final String otherUidFinal = otherUid;
        final DocumentReference chatRef = firestore.collection("chats").document(chatId);
        chatRef.get().addOnSuccessListener(existing -> {
            Map<String,Object> data = new HashMap<>();
            ArrayList<String> participants = new ArrayList<>();
            participants.add(me.getUid()); participants.add(otherUidFinal);
            data.put("participants", participants);
            Map<String,Object> info = new HashMap<>();
            Map<String,Object> mine = new HashMap<>();
            String meName = clean(me.getDisplayName());
            mine.put("displayName", meName.isEmpty() ? "Elya Listener" : meName);
            Map<String,Object> theirs = new HashMap<>();
            theirs.put("displayName", clean(otherName).isEmpty() ? "Elya Listener" : clean(otherName));
            theirs.put("username", normalizeChatUsername(otherUsername));
            info.put(me.getUid(), mine); info.put(otherUidFinal, theirs);
            data.put("participantInfo", info);
            if (!existing.exists()) {
                data.put("createdAt", FieldValue.serverTimestamp());
                data.put("updatedAt", FieldValue.serverTimestamp());
                data.put("lastMessage", "");
                data.put("lastSenderId", "");
                data.put("seenBy", participants);
            }
            chatRef.set(data, SetOptions.merge()).addOnSuccessListener(v -> {
                JSONObject opened = new JSONObject();
                try {
                    opened.put("chatId", chatId); opened.put("otherUid", otherUidFinal);
                    opened.put("displayName", clean(otherName).isEmpty() ? "Elya Listener" : clean(otherName));
                    opened.put("username", normalizeChatUsername(otherUsername));
                } catch (Exception ignored) {}
                emitChat("__elyaChatOpened", opened);
                chatListenMessagesNative(chatId);
                chatMarkSeenNative(chatId);
            }).addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));
        }).addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));
    }

    private void chatListenConversationsNative() {
        FirebaseUser me = chatUserOrError();
        if (me == null) return;
        if (chatListRegistration != null) chatListRegistration.remove();
        final String uid = me.getUid();
        chatListRegistration = firestore.collection("chats")
                .whereArrayContains("participants", uid).limit(100)
                .addSnapshotListener((snap, err) -> {
                    if (err != null) { emitChatError(chatFriendlyError(err)); return; }
                    JSONArray arr = new JSONArray();
                    if (snap != null) for (DocumentSnapshot d : snap.getDocuments()) {
                        try {
                            List<String> participants = (List<String>) d.get("participants");
                            String other = "";
                            if (participants != null) for (String p : participants) if (!uid.equals(p)) { other = p; break; }
                            Map<String,Object> info = d.get("participantInfo") instanceof Map ? (Map<String,Object>)d.get("participantInfo") : null;
                            Map<String,Object> otherInfo = info != null && info.get(other) instanceof Map ? (Map<String,Object>)info.get(other) : null;
                            JSONObject o = new JSONObject();
                            o.put("chatId", d.getId()); o.put("otherUid", other);
                            o.put("displayName", otherInfo == null ? "Elya Listener" : clean(String.valueOf(otherInfo.get("displayName"))));
                            o.put("username", otherInfo == null || otherInfo.get("username") == null ? "" : clean(String.valueOf(otherInfo.get("username"))));
                            o.put("lastMessage", clean(d.getString("lastMessage")));
                            o.put("lastSenderId", clean(d.getString("lastSenderId")));
                            Object t = d.get("updatedAt");
                            long ms = t instanceof com.google.firebase.Timestamp ? ((com.google.firebase.Timestamp)t).toDate().getTime() : 0;
                            o.put("updatedAt", ms);
                            List<String> seen = d.get("seenBy") instanceof List ? (List<String>)d.get("seenBy") : new ArrayList<>();
                            o.put("unread", !uid.equals(o.optString("lastSenderId")) && !seen.contains(uid));
                            o.put("seenByOther", seen.contains(other));
                            arr.put(o);
                        } catch (Exception ignored) {}
                    }
                    emitChat("__elyaChatConversations", arr);
                });
    }

    private void chatListenMessagesNative(String chatId) {
        FirebaseUser me = chatUserOrError();
        if (me == null) return;
        chatId = clean(chatId);
        if (chatId.isEmpty()) return;
        if (chatMessageRegistration != null) chatMessageRegistration.remove();
        activeChatId = chatId;
        final String cid = chatId;
        chatMessageRegistration = firestore.collection("chats").document(cid).collection("messages")
                .orderBy("createdAt", Query.Direction.ASCENDING).limitToLast(200)
                .addSnapshotListener((snap, err) -> {
                    if (err != null) { emitChatError(chatFriendlyError(err)); return; }
                    JSONArray arr = new JSONArray();
                    if (snap != null) for (DocumentSnapshot d : snap.getDocuments()) {
                        try {
                            JSONObject o = new JSONObject();
                            o.put("id", d.getId()); o.put("senderId", clean(d.getString("senderId")));
                            o.put("text", clean(d.getString("text")));
                            Object t = d.get("createdAt");
                            long ms = t instanceof com.google.firebase.Timestamp ? ((com.google.firebase.Timestamp)t).toDate().getTime() : 0;
                            o.put("createdAt", ms);
                            arr.put(o);
                        } catch (Exception ignored) {}
                    }
                    emitChat("__elyaChatMessages", arr);
                    chatMarkSeenNative(cid);
                });
    }

    private void chatSendNative(String chatId, String rawText) {
        FirebaseUser me = chatUserOrError();
        if (me == null) return;
        final String cid = clean(chatId);
        final String text = rawText == null ? "" : rawText.trim();
        if (cid.isEmpty() || text.isEmpty()) return;
        if (text.length() > 4000) { emitChatError("Messages can be up to 4000 characters."); return; }
        final DocumentReference chatRef = firestore.collection("chats").document(cid);
        chatRef.get().addOnSuccessListener(chatDoc -> {
            if (!chatDoc.exists()) { emitChatError("This chat no longer exists."); return; }
            List<String> parts = chatDoc.get("participants") instanceof List ? (List<String>)chatDoc.get("participants") : new ArrayList<>();
            if (!parts.contains(me.getUid())) { emitChatError("You do not have access to this chat."); return; }
            String other = ""; for (String p : parts) if (!me.getUid().equals(p)) { other=p; break; }
            final String otherUid = other;
            firestore.collection("users").document(me.getUid()).collection("blocks").document(otherUid).get()
                    .addOnSuccessListener(block -> {
                        if (block.exists()) { emitChatError("Unblock this person before sending a message."); return; }
                        DocumentReference msgRef = chatRef.collection("messages").document();
                        com.google.firebase.firestore.WriteBatch batch = firestore.batch();
                        Map<String,Object> msg = new HashMap<>();
                        msg.put("senderId", me.getUid()); msg.put("text", text); msg.put("createdAt", FieldValue.serverTimestamp());
                        batch.set(msgRef, msg);
                        Map<String,Object> meta = new HashMap<>();
                        meta.put("lastMessage", text); meta.put("lastSenderId", me.getUid()); meta.put("updatedAt", FieldValue.serverTimestamp());
                        meta.put("seenBy", Collections.singletonList(me.getUid()));
                        batch.set(chatRef, meta, SetOptions.merge());
                        batch.commit().addOnSuccessListener(v -> emitChatStatus("Sent"))
                                .addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));
                    }).addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));
        }).addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));
    }

    private void chatMarkSeenNative(String chatId) {
        FirebaseUser me = firebaseAuth == null ? null : firebaseAuth.getCurrentUser();
        if (me == null || chatId == null || chatId.trim().isEmpty()) return;
        Map<String,Object> u = new HashMap<>(); u.put("seenBy", FieldValue.arrayUnion(me.getUid()));
        firestore.collection("chats").document(chatId.trim()).set(u, SetOptions.merge());
    }

    private void chatSetBlockedNative(String otherUid, boolean blocked) {
        FirebaseUser me = chatUserOrError();
        if (me == null) return;
        otherUid = clean(otherUid); if (otherUid.isEmpty()) return;
        DocumentReference ref = firestore.collection("users").document(me.getUid()).collection("blocks").document(otherUid);
        final String ou = otherUid;
        if (blocked) {
            Map<String,Object> d = new HashMap<>(); d.put("uid", otherUid); d.put("createdAt", FieldValue.serverTimestamp());
            ref.set(d).addOnSuccessListener(v -> emitChatBlock(ou, true)).addOnFailureListener(e -> emitChatError(chatFriendlyError(e)));
        } else ref.delete().addOnSuccessListener(v -> emitChatBlock(ou, false)).addOnFailureListener(e -> emitChatError(chatFriendlyError(e)));
    }

    private void chatCheckBlockedNative(String otherUid) {
        FirebaseUser me = chatUserOrError(); if (me == null) return;
        otherUid = clean(otherUid); if (otherUid.isEmpty()) return;
        final String ou = otherUid;
        firestore.collection("users").document(me.getUid()).collection("blocks").document(otherUid).get()
                .addOnSuccessListener(d -> emitChatBlock(ou, d.exists()))
                .addOnFailureListener(e -> emitChatError(chatFriendlyError(e)));
    }

    private void chatStopListenersNative() {
        if (chatListRegistration != null) { chatListRegistration.remove(); chatListRegistration = null; }
        if (chatMessageRegistration != null) { chatMessageRegistration.remove(); chatMessageRegistration = null; }
        activeChatId = "";
    }

    private JSONObject publicProfileJson(String uid, Map<String,Object> data) {
        JSONObject o = new JSONObject();
        try {
            o.put("uid", uid == null ? "" : uid);
            o.put("displayName", data == null || data.get("displayName") == null ? "Elya Listener" : clean(String.valueOf(data.get("displayName"))));
            o.put("username", data == null || data.get("username") == null ? "" : clean(String.valueOf(data.get("username"))));
        } catch (Exception ignored) {}
        return o;
    }

    private void emitChat(String callback, Object payload) {
        String body = payload == null ? "null" : payload.toString();
        js("window." + callback + "&&window." + callback + "(" + body + ");");
    }

    private void emitChatStatus(String message) {
        js("window.__elyaChatStatus&&window.__elyaChatStatus(" + JSONObject.quote(message == null ? "" : message) + ");");
    }

    private void emitChatError(String message) {
        js("window.__elyaChatError&&window.__elyaChatError(" + JSONObject.quote(message == null ? "Chat error" : message) + ");");
    }

    private void emitChatBlock(String uid, boolean blocked) {
        js("window.__elyaChatBlockState&&window.__elyaChatBlockState(" + JSONObject.quote(uid) + "," + (blocked ? "true" : "false") + ");");
    }

    private String chatFriendlyError(Exception e) {
        if (e == null) return "Could not complete the chat action.";
        String m = e.getMessage() == null ? "Could not complete the chat action." : e.getMessage();
        String l = m.toLowerCase(Locale.US);
        if (l.contains("already taken")) return "That username is already taken.";
        if (l.contains("permission") || l.contains("permission_denied")) return "Elya Chat cloud rules are not enabled yet. Update Firestore Rules, then try again.";
        if (l.contains("network")) return "Check your internet connection and try again.";
        return m.length() > 260 ? m.substring(0,260) : m;
    }

'''
marker='''    private class ElyaChromeClient extends WebChromeClient {'''
if marker not in s: raise SystemExit('chat method insertion marker missing')
s=s.replace(marker,methods+marker,1)

destroy_anchor='''    @Override\n    protected void onDestroy() {\n        io.shutdownNow();'''
destroy_repl='''    @Override\n    protected void onDestroy() {\n        chatStopListenersNative();\n        io.shutdownNow();'''
if destroy_anchor not in s: raise SystemExit('onDestroy anchor missing')
s=s.replace(destroy_anchor,destroy_repl,1)
p.write_text(s,encoding='utf-8')

p=r/'app/src/main/assets/index.html'
h=p.read_text(encoding='utf-8')
svg_anchor='<symbol id="i-lyrics" viewBox="0 0 24 24"><path d="M5 5h14v11H9l-4 4V5Zm3 4h8M8 12h6" fill="none" stroke="currentColor" stroke-width="1.7"/></symbol>'
chat_symbol=svg_anchor+'<symbol id="i-chat" viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-5 4v-4.7A2.5 2.5 0 0 1 4 13.5v-8Z" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M8 8h8M8 12h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></symbol>'
if svg_anchor not in h: raise SystemExit('svg chat anchor missing')
h=h.replace(svg_anchor,chat_symbol,1)

settings_new=r'''<div class="modal" id="settingsModal"><div class="dialog wide elya120-settings">
  <button id="settingsAdvancedToggle" type="button" hidden>Advanced</button>
  <div class="dialog-head"><div><h3>Settings</h3><small class="install-note">Everything in one place.</small></div><button class="close" data-close="settingsModal"><svg><use href="#i-close"/></svg></button></div>
  <div class="elya120-setting-tabs"><button class="tab active" data-settingtab="account">Account</button><button class="tab" data-settingtab="appearance">Appearance</button><button class="tab" data-settingtab="playback">Playback</button><button class="tab" data-settingtab="audio">Audio</button><button class="tab" data-settingtab="library">Library & Storage</button><button class="tab" data-settingtab="privacy">Privacy</button><button class="tab" data-settingtab="data">Data & Backup</button><button class="tab" data-settingtab="about">About</button></div>
  <div data-settingpanel="account"><div class="settings-grid"><div class="setting-card elya120-account-card"><strong>Elya Account</strong><p id="elya120AccountText">Sign in only if you want cloud features and Chats. Your music stays local.</p><div class="choice-row"><button class="primary" id="elya120OpenAccount" type="button"><svg><use href="#i-user"/></svg>Account & Profile</button><button class="secondary" id="elya120OpenChats" type="button"><svg><use href="#i-chat"/></svg>Open Chats</button></div></div><div class="setting-card"><strong>Chat Username</strong><p>Your username is how people find you in Elya Chats.</p><div class="elya120-inline"><span class="elya120-at">@</span><input class="search" id="elya120SettingsUsername" maxlength="24" placeholder="yourname"><button class="secondary" id="elya120SaveUsername" type="button">Save</button></div><small class="install-note" id="elya120UsernameStatus">3–24 letters, numbers, . or _</small></div></div></div>
  <div data-settingpanel="appearance" class="hidden"><div class="settings-grid"><div class="setting-card"><strong>Theme</strong><p>Choose the overall look.</p><select id="themeSelect" class="search"><option value="dark">Dark</option><option value="light">Light</option><option value="amoled">AMOLED Black</option><option value="ocean">Ocean</option><option value="purple">Purple</option><option value="red">Red</option></select></div><div class="setting-card"><strong>Accent Color</strong><p>Set your own accent.</p><input id="accentPicker" type="color" value="#67dcff" style="width:100%;height:44px;border:0;border-radius:10px;background:transparent"></div><div class="setting-card"><strong>CD Style</strong><p>Change the disc material.</p><select id="cdStyleSelect" class="search"><option value="black">Black Vinyl</option><option value="silver">Silver CD</option><option value="transparent">Transparent</option><option value="neon">Neon</option></select></div><div class="setting-card"><strong>Motion</strong><p>Animations and CD speed.</p><label class="checkbox-row"><input type="checkbox" id="animationsToggle" checked> Enable animations</label><label class="checkbox-row"><input type="checkbox" id="reduceMotionToggle"> Reduce motion</label><div class="field"><label>CD Speed</label><input id="cdSpeed" type="range" min="4" max="20" step="1" value="9"></div></div></div></div>
  <div data-settingpanel="playback" class="hidden"><div class="settings-grid"><div class="setting-card"><strong>Crossfade</strong><p>Smoothly fade between songs.</p><div class="field"><label>Seconds <span id="crossfadeLabel">0s</span></label><input id="crossfadeRange" type="range" min="0" max="10" step="1" value="0"></div></div><div class="setting-card"><strong>Playback Speed</strong><p>Default playback speed.</p><select id="defaultSpeed" class="search"><option>.5</option><option>.75</option><option selected>1</option><option>1.25</option><option>1.5</option><option>1.75</option><option>2</option></select></div><div class="setting-card"><strong>Sleep Timer</strong><p>Stop playback automatically.</p><div class="choice-row"><button class="chip sleepOpt" data-min="10">10 min</button><button class="chip sleepOpt" data-min="20">20 min</button><button class="chip sleepOpt" data-min="30">30 min</button><button class="chip sleepOpt" data-min="60">60 min</button><button class="chip" id="sleepEndSong">End of song</button></div><small id="sleepStatus" class="install-note"></small></div><div class="setting-card"><strong>Visualizer</strong><p>Choose the visualizer style.</p><select id="visualizerStyle" class="search"><option value="bars">Bars</option><option value="circle">Circle</option><option value="wave">Wave</option><option value="off">Off</option></select></div></div></div>
  <div data-settingpanel="audio" class="hidden"><div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:15px"><button class="chip eqPreset" data-preset="flat">Flat</button><button class="chip eqPreset" data-preset="bass">Bass Boost</button><button class="chip eqPreset" data-preset="pop">Pop</button><button class="chip eqPreset" data-preset="rock">Rock</button><button class="chip eqPreset" data-preset="classical">Classical</button><button class="chip eqPreset" data-preset="night">Night</button></div><div class="eq-grid"><div class="eq-band"><input id="eqBass" type="range" min="-12" max="12" value="0"><strong>Bass</strong></div><div class="eq-band"><input id="eqVocal" type="range" min="-12" max="12" value="0"><strong>Vocal</strong></div><div class="eq-band"><input id="eqTreble" type="range" min="-12" max="12" value="0"><strong>Treble</strong></div></div><h4 style="margin-top:22px">10-Band Equalizer</h4><div class="audio-panel-scroll"><div class="ten-eq" id="eq10Host"></div></div><div class="setting-card" style="margin-top:14px"><strong>Stereo Balance</strong><p>Move audio between left and right channels.</p><div class="balance-row"><span>Left</span><input id="balanceRange" type="range" min="-1" max="1" step=".01" value="0"><span>Right</span></div></div><div class="setting-card" style="margin-top:10px"><strong>Playback Intelligence</strong><p>Preload and skip saved intro/outro markers.</p><label class="checkbox-row"><input id="preloadToggle" type="checkbox" checked> Preload next track</label><label class="checkbox-row"><input id="skipIntroToggle" type="checkbox"> Auto-skip intros</label><label class="checkbox-row"><input id="skipOutroToggle" type="checkbox"> Auto-skip outros</label></div></div>
  <div data-settingpanel="library" class="hidden"><div class="settings-grid"><div class="setting-card"><strong>Music Library</strong><p>Scan your device or choose a specific music folder.</p><div class="choice-row"><button class="primary" id="elya120DeepScan" type="button"><svg><use href="#i-search"/></svg>Deep Scan</button><button class="secondary" id="changeFolderBtn"><svg><use href="#i-folder"/></svg>Choose Folder</button><button class="secondary" id="rescanFolderBtn"><svg><use href="#i-search"/></svg>Rescan</button></div><div class="install-note" id="folderSettingsStatus" style="margin-top:9px">Checking library…</div></div><div class="setting-card"><strong>Android Permissions</strong><p>Manage Music & Audio access from Android.</p><button class="secondary" id="elya120AndroidSettings" type="button">Open App Settings</button></div></div></div>
  <div data-settingpanel="privacy" class="hidden"><div class="settings-grid"><div class="setting-card"><strong>Private Library</strong><p>Private songs are protected by your local Elya PIN.</p><button class="secondary" id="elya120Privacy" type="button"><svg><use href="#i-pin"/></svg>Privacy & PIN</button></div><div class="setting-card"><strong>Chats & Cloud</strong><p>Chat messages use Firebase. Music files are never uploaded by Elya Chats.</p><small class="install-note">You can block a user from inside a conversation.</small></div></div></div>
  <div data-settingpanel="data" class="hidden"><div class="settings-grid"><div class="setting-card"><strong>Backup</strong><p>Exports settings, playlists, lyrics and metadata. Audio files are not included.</p><button class="secondary" id="exportBackup"><svg><use href="#i-download"/></svg>Export Backup</button></div><div class="setting-card"><strong>Restore Backup</strong><p>Import a previous Elya backup.</p><button class="secondary" id="importBackupBtn"><svg><use href="#i-upload"/></svg>Import Backup</button></div><div class="setting-card"><strong>Install App</strong><p class="install-note">Install support depends on the current platform.</p><button class="secondary" id="installBtn">Install Elya</button></div><div class="setting-card"><strong>Reset App</strong><p>Resets Elya settings. Your original music files stay untouched.</p><button class="danger-btn" id="resetSettings">Reset Settings</button></div></div></div>
  <div data-settingpanel="about" class="hidden"><div class="settings-grid"><div class="setting-card"><strong>Elya 1.2.0</strong><p>Local-first music player with optional Elya Account and private 1-to-1 Chats.</p><small class="install-note">Music stays on your device unless you explicitly share something in a future sharing feature.</small></div><div class="setting-card"><strong>Runtime</strong><p id="elya120Runtime">Android bridge · checking…</p><button class="secondary" id="elya120Diagnostics" type="button">Refresh Diagnostics</button></div></div></div>
</div></div>

'''
pattern=r'<div class="modal" id="settingsModal">.*?</div></div>\s*(?=<div class="modal" id="profileModal">)'
new_h,n=re.subn(pattern,settings_new,h,count=1,flags=re.S)
if n!=1: raise SystemExit('settings modal replacement failed')
h=new_h

anchor='<div class="label">Tools</div>'
if anchor not in h: raise SystemExit('sidebar tools anchor missing')
h=h.replace(anchor,anchor+'\n  <button class="nav" id="elyaChatsBtn"><svg><use href="#i-chat"/></svg><span>Chats</span><span class="badge" id="elyaChatBadge" style="display:none">0</span></button>',1)
anchor='<div class="tool-grid">'
if anchor not in h: raise SystemExit('more tool grid anchor missing')
h=h.replace(anchor,anchor+'\n    <button class="tool-tile" data-more="chats"><svg><use href="#i-chat"/></svg><strong>Chats</strong><small>Private 1-to-1 conversations with Elya users.</small></button>',1)

chat_ui=r'''<div class="modal" id="elyaChatsModal"><div class="dialog wide elya120-chat-dialog"><div class="dialog-head"><div><h3>Chats</h3><small class="install-note" id="elyaChatStatus">Elya account required.</small></div><button class="close" data-close="elyaChatsModal"><svg><use href="#i-close"/></svg></button></div><div class="elya120-chat-gate" id="elyaChatGate"><svg><use href="#i-user"/></svg><strong>Sign in to use Chats</strong><p>Your local music library stays separate from your Elya account.</p><button class="primary" id="elyaChatOpenAccount" type="button">Open Account</button></div><div class="elya120-chat-app" id="elyaChatApp"><aside class="elya120-chat-sidebar"><div class="elya120-chat-profile"><div class="elya120-avatar" id="elyaChatMeAvatar">E</div><div><strong id="elyaChatMeName">Elya Listener</strong><span id="elyaChatMeUser">Set a username</span></div><button class="icon-btn" id="elyaChatNew" type="button" title="New chat"><svg><use href="#i-plus"/></svg></button></div><div class="elya120-chat-find" id="elyaChatFindBox"><div class="search-wrap"><svg><use href="#i-search"/></svg><input class="search" id="elyaChatFindInput" maxlength="24" placeholder="Find @username"></div><button class="primary" id="elyaChatFindBtn" type="button">Find</button></div><div id="elyaChatSearchResult"></div><div class="elya120-chat-section-title">Messages</div><div class="elya120-conversations" id="elyaChatList"><div class="empty"><strong>No chats yet</strong>Find someone by username.</div></div></aside><section class="elya120-conversation" id="elyaConversation"><div class="elya120-chat-empty" id="elyaChatEmpty"><svg><use href="#i-chat"/></svg><strong>Your Elya Chats</strong><span>Select a conversation or find a username.</span></div><div class="elya120-thread" id="elyaChatThread"><div class="elya120-thread-head"><button class="icon-btn elya120-chat-back" id="elyaChatBack" type="button"><svg><use href="#i-back"/></svg></button><div class="elya120-avatar" id="elyaChatOtherAvatar">E</div><div class="elya120-thread-person"><strong id="elyaChatOtherName">Elya Listener</strong><span id="elyaChatOtherUser">@user</span></div><button class="secondary elya120-block" id="elyaChatBlock" type="button">Block</button></div><div class="elya120-messages" id="elyaChatMessages"></div><div class="elya120-composer"><textarea id="elyaChatInput" rows="1" maxlength="4000" placeholder="Message"></textarea><button class="primary" id="elyaChatSend" type="button"><svg><use href="#i-up"/></svg></button></div></div></section></div></div></div>'''
if 'id="elyaChatsModal"' not in h: h=h.replace('<div class="toast" id="toast"></div>',chat_ui+'\n<div class="toast" id="toast"></div>',1)

css='''<style id="elya120Style">.elya120-settings{max-width:920px}.elya120-settings .rare-setting{display:block!important}.elya120-setting-tabs{display:flex;gap:7px;overflow:auto;padding:2px 0 13px;scrollbar-width:none}.elya120-setting-tabs::-webkit-scrollbar{display:none}.elya120-setting-tabs .tab{white-space:nowrap}.elya120-inline{display:grid;grid-template-columns:auto 1fr auto;gap:7px;align-items:center}.elya120-at{font-weight:900;color:var(--muted)}.elya120-chat-dialog{max-width:1040px;height:min(760px,84vh);overflow:hidden;display:flex;flex-direction:column}.elya120-chat-gate{margin:auto;max-width:380px;text-align:center;display:none}.elya120-chat-gate.show{display:grid;justify-items:center;gap:10px}.elya120-chat-gate>svg{width:46px;height:46px;color:var(--accent)}.elya120-chat-gate p{color:var(--muted);margin:0 0 6px}.elya120-chat-app{display:none;grid-template-columns:330px 1fr;min-height:0;flex:1;border:1px solid var(--line);border-radius:20px;overflow:hidden;background:rgba(255,255,255,.018)}.elya120-chat-app.show{display:grid}.elya120-chat-sidebar{min-width:0;border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:0}.elya120-chat-profile{display:grid;grid-template-columns:42px 1fr auto;align-items:center;gap:10px;padding:13px;border-bottom:1px solid var(--line)}.elya120-chat-profile span,.elya120-thread-person span{display:block;color:var(--muted);font-size:11px;margin-top:2px}.elya120-avatar{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;font-weight:900;background:linear-gradient(145deg,rgba(var(--accent-rgb),.3),rgba(var(--accent-rgb),.08));border:1px solid rgba(var(--accent-rgb),.25);color:var(--accent)}.elya120-chat-find{display:grid;grid-template-columns:1fr auto;gap:7px;padding:10px}.elya120-chat-find .search-wrap{min-width:0}.elya120-chat-section-title{padding:8px 13px 5px;color:var(--muted);font-size:10px;font-weight:900;letter-spacing:.12em;text-transform:uppercase}.elya120-conversations{overflow:auto;min-height:0;padding:4px 7px 10px}.elya120-conv{display:grid;grid-template-columns:44px 1fr auto;gap:10px;align-items:center;padding:9px;border-radius:14px;cursor:pointer}.elya120-conv:hover,.elya120-conv.active{background:rgba(255,255,255,.055)}.elya120-conv .meta{min-width:0}.elya120-conv strong,.elya120-conv span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.elya120-conv span{display:block;color:var(--muted);font-size:11px;margin-top:3px}.elya120-conv time{font-size:9px;color:var(--muted)}.elya120-unread{width:8px;height:8px;border-radius:50%;background:var(--accent);margin:6px 0 0 auto}.elya120-search-person{margin:0 9px 8px;padding:10px;border:1px solid var(--line);border-radius:14px;display:grid;grid-template-columns:40px 1fr auto;gap:9px;align-items:center}.elya120-conversation{min-width:0;min-height:0;position:relative}.elya120-chat-empty{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;color:var(--muted);text-align:center}.elya120-chat-empty svg{width:46px;height:46px;color:var(--accent)}.elya120-chat-empty strong{color:var(--text);font-size:18px}.elya120-thread{height:100%;display:none;grid-template-rows:auto 1fr auto}.elya120-thread.open{display:grid}.elya120-thread-head{display:grid;grid-template-columns:auto 42px 1fr auto;align-items:center;gap:10px;padding:10px 12px;border-bottom:1px solid var(--line)}.elya120-chat-back{display:none}.elya120-messages{overflow:auto;padding:18px;display:flex;flex-direction:column;gap:7px;min-height:0;background:radial-gradient(circle at 50% -20%,rgba(var(--accent-rgb),.07),transparent 50%)}.elya120-msg{max-width:min(76%,560px);padding:9px 12px;border-radius:16px 16px 16px 5px;background:rgba(255,255,255,.075);border:1px solid rgba(255,255,255,.05);line-height:1.38;white-space:pre-wrap;overflow-wrap:anywhere}.elya120-msg.mine{align-self:flex-end;border-radius:16px 16px 5px 16px;background:rgba(var(--accent-rgb),.16);border-color:rgba(var(--accent-rgb),.18)}.elya120-msg small{display:block;text-align:right;color:var(--muted);font-size:9px;margin-top:4px}.elya120-composer{display:grid;grid-template-columns:1fr auto;gap:8px;padding:10px;border-top:1px solid var(--line)}.elya120-composer textarea{resize:none;max-height:120px;min-height:44px;border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.05);color:var(--text);padding:11px 13px;font:inherit;outline:none}.elya120-composer textarea:focus{border-color:rgba(var(--accent-rgb),.45)}.elya120-composer button{width:46px;height:46px;padding:0;justify-content:center;border-radius:15px}.elya120-block.blocked{border-color:rgba(255,90,90,.4);color:#ff8b8b}@media(max-width:699px){.elya120-chat-dialog{height:calc(100dvh - 26px);max-height:none}.elya120-chat-app{grid-template-columns:1fr}.elya120-chat-sidebar{border-right:0}.elya120-conversation{display:none;position:absolute;inset:64px 0 0;background:var(--panel);z-index:2}.elya120-conversation.mobile-open{display:block}.elya120-thread{height:100%}.elya120-chat-back{display:grid}.elya120-thread-head{grid-template-columns:40px 38px 1fr auto}.elya120-thread-head .elya120-avatar{width:38px;height:38px}.elya120-block{padding:8px 10px}.elya120-msg{max-width:84%}.elya120-settings{height:calc(100dvh - 24px);overflow:auto}.elya120-setting-tabs{position:sticky;top:0;z-index:4;background:var(--panel);padding-top:6px}}</style>'''
if 'id="elya120Style"' not in h: h=h.replace('</head>',css+'</head>',1)

script='''<script id="elya120Script">(()=>{const q=s=>document.querySelector(s),qa=s=>[...document.querySelectorAll(s)],B=()=>window.AndroidMusic;const call=(name,...args)=>{try{const b=B();if(!b||typeof b[name]!==\'function\')throw new Error(\'Native method unavailable: \'+name);return b[name](...args)}catch(e){window.toast?.(e.message||\'Chat unavailable\')}};window.__elyaSettingsVersion=\'1.2.0\';window.__elyaChatVersion=\'1.2.0\';let auth={signedIn:false,uid:\'\'},me=null,current=null,conversations=[],blocked=false;const initials=n=>(String(n||\'E\').trim().split(/\\s+/).slice(0,2).map(x=>x[0]||\'\').join(\'\').toUpperCase()||\'E\'),time=t=>{if(!t)return\'\';const d=new Date(+t),now=new Date();return d.toDateString()===now.toDateString()?d.toLocaleTimeString([],{hour:\'2-digit\',minute:\'2-digit\'}):d.toLocaleDateString([],{month:\'short\',day:\'numeric\'})},chatStatus=t=>{const e=q(\'#elyaChatStatus\');if(e)e.textContent=t||\'\'};const showAuth=()=>{const on=!!auth.signedIn;q(\'#elyaChatGate\')?.classList.toggle(\'show\',!on);q(\'#elyaChatApp\')?.classList.toggle(\'show\',on);const a=q(\'#elya120AccountText\');if(a)a.textContent=on?\'Connected to Elya Cloud. Chats are available.\':\'Sign in only if you want cloud features and Chats. Your music stays local.\';if(on){call(\'chatMyProfile\');call(\'chatListenConversations\')}};const openChats=()=>{openModal(\'elyaChatsModal\');showAuth();if(!auth.signedIn)call(\'firebaseCurrentUser\');else{call(\'chatMyProfile\');call(\'chatListenConversations\')}};window.openElyaChats=openChats;q(\'#elyaChatsBtn\')?.addEventListener(\'click\',openChats);q(\'[data-more="chats"]\')?.addEventListener(\'click\',e=>{e.stopPropagation();closeModal(\'moreModal\');openChats()});q(\'#elya120OpenChats\')?.addEventListener(\'click\',()=>{closeModal(\'settingsModal\');openChats()});q(\'#elya120OpenAccount\')?.addEventListener(\'click\',()=>{closeModal(\'settingsModal\');q(\'#profileBtn\')?.click()});q(\'#elyaChatOpenAccount\')?.addEventListener(\'click\',()=>{closeModal(\'elyaChatsModal\');q(\'#profileBtn\')?.click()});q(\'#elya120DeepScan\')?.addEventListener(\'click\',()=>call(typeof B()?.deepScanDeviceMusic===\'function\'?\'deepScanDeviceMusic\':\'scanAllDeviceMusic\'));q(\'#elya120AndroidSettings\')?.addEventListener(\'click\',()=>call(\'openAppSettings\'));q(\'#elya120Privacy\')?.addEventListener(\'click\',()=>q(\'#privacyBtn\')?.click());q(\'#elya120Diagnostics\')?.addEventListener(\'click\',()=>{try{const d=JSON.parse(call(\'diagnostics\')||\'{}\');q(\'#elya120Runtime\').textContent=`Android ${d.core||\'?\'} · Firebase ${d.firebaseReady?\'connected\':\'error\'} · ${d.lastScanCount||0} audio files last scan`}catch{}});const oldAuth=window.__elyaFirebaseAuthState;window.__elyaFirebaseAuthState=d=>{try{oldAuth?.(d)}catch{};auth=d||{signedIn:false};showAuth();if(!auth.signedIn){me=null;current=null;conversations=[];renderList();closeThread()}};q(\'#elya120SaveUsername\')?.addEventListener(\'click\',()=>call(\'chatSetUsername\',q(\'#elya120SettingsUsername\')?.value||\'\'));window.__elyaChatProfile=p=>{me=p||{};q(\'#elyaChatMeName\').textContent=me.displayName||\'Elya Listener\';q(\'#elyaChatMeUser\').textContent=me.username?\'@\'+me.username:\'Set a username in Settings\';q(\'#elyaChatMeAvatar\').textContent=initials(me.displayName);const u=q(\'#elya120SettingsUsername\');if(u&&me.username)u.value=me.username;q(\'#elya120UsernameStatus\').textContent=me.username?\'Your Elya username is @\'+me.username:\'Choose a username to let people find you.\'};window.__elyaChatStatus=m=>{chatStatus(m);if(m)window.toast?.(m)};window.__elyaChatError=m=>{chatStatus(m);window.toast?.(m)};window.__elyaChatSearchResult=p=>{const box=q(\'#elyaChatSearchResult\');if(!box)return;if(!p||!p.uid){box.innerHTML=\'\';return}box.innerHTML=`<div class="elya120-search-person"><div class="elya120-avatar">${esc(initials(p.displayName))}</div><div><strong>${esc(p.displayName||\'Elya Listener\')}</strong><span class="install-note">@${esc(p.username||\'user\')}</span></div><button class="primary" id="elya120StartFound" type="button">Chat</button></div>`;q(\'#elya120StartFound\').onclick=()=>call(\'chatOpenWithUser\',p.uid,p.displayName||\'Elya Listener\',p.username||\'\')};q(\'#elyaChatFindBtn\')?.addEventListener(\'click\',()=>call(\'chatFindUsername\',q(\'#elyaChatFindInput\')?.value||\'\'));q(\'#elyaChatFindInput\')?.addEventListener(\'keydown\',e=>{if(e.key===\'Enter\'){e.preventDefault();q(\'#elyaChatFindBtn\')?.click()}});q(\'#elyaChatNew\')?.addEventListener(\'click\',()=>q(\'#elyaChatFindInput\')?.focus());function renderList(){const box=q(\'#elyaChatList\');if(!box)return;const list=[...conversations].sort((a,b)=>(b.updatedAt||0)-(a.updatedAt||0)),unread=list.filter(x=>x.unread).length,badge=q(\'#elyaChatBadge\');if(badge){badge.textContent=unread;badge.style.display=unread?\'\':\'none\'};if(!list.length){box.innerHTML=\'<div class="empty"><strong>No chats yet</strong>Find someone by username.</div>\';return}box.innerHTML=list.map(c=>`<div class="elya120-conv ${current?.chatId===c.chatId?\'active\':\'\'}" data-chat="${esc(c.chatId)}"><div class="elya120-avatar">${esc(initials(c.displayName))}</div><div class="meta"><strong>${esc(c.displayName||\'Elya Listener\')}</strong><span>${esc(c.lastMessage||(\'@\'+(c.username||\'user\')))}</span></div><div><time>${esc(time(c.updatedAt))}</time>${c.unread?\'<i class="elya120-unread"></i>\':\'\'}</div></div>`).join(\'\');qa(\'.elya120-conv\').forEach(row=>row.onclick=()=>{const c=conversations.find(x=>x.chatId===row.dataset.chat);if(c)openThread(c)})}window.__elyaChatConversations=a=>{conversations=Array.isArray(a)?a:[];renderList();if(current){const fresh=conversations.find(x=>x.chatId===current.chatId);if(fresh)current={...current,...fresh}}};function openThread(c){current=c;blocked=false;q(\'#elyaChatEmpty\')?.style.setProperty(\'display\',\'none\');q(\'#elyaChatThread\')?.classList.add(\'open\');q(\'#elyaConversation\')?.classList.add(\'mobile-open\');q(\'#elyaChatOtherName\').textContent=c.displayName||\'Elya Listener\';q(\'#elyaChatOtherUser\').textContent=c.username?\'@\'+c.username:\'\';q(\'#elyaChatOtherAvatar\').textContent=initials(c.displayName);q(\'#elyaChatBlock\').textContent=\'Block\';q(\'#elyaChatBlock\').classList.remove(\'blocked\');renderList();call(\'chatListenMessages\',c.chatId);call(\'chatCheckBlocked\',c.otherUid);call(\'chatMarkSeen\',c.chatId)}window.__elyaChatOpened=c=>{if(!c)return;const old=conversations.find(x=>x.chatId===c.chatId)||{};openThread({...old,...c})};function closeThread(){current=null;q(\'#elyaChatThread\')?.classList.remove(\'open\');q(\'#elyaConversation\')?.classList.remove(\'mobile-open\');const e=q(\'#elyaChatEmpty\');if(e)e.style.display=\'flex\';renderList()}q(\'#elyaChatBack\')?.addEventListener(\'click\',closeThread);window.__elyaChatMessages=a=>{const box=q(\'#elyaChatMessages\');if(!box)return;const arr=Array.isArray(a)?a:[];box.innerHTML=arr.map(m=>`<div class="elya120-msg ${m.senderId===auth.uid?\'mine\':\'\'}">${esc(m.text||\'\')}<small>${esc(time(m.createdAt))}</small></div>`).join(\'\');requestAnimationFrame(()=>box.scrollTop=box.scrollHeight)};const send=()=>{if(!current||blocked)return;const inp=q(\'#elyaChatInput\'),text=inp?.value?.trim()||\'\';if(!text)return;call(\'chatSend\',current.chatId,text);inp.value=\'\';inp.style.height=\'\'};q(\'#elyaChatSend\')?.addEventListener(\'click\',send);q(\'#elyaChatInput\')?.addEventListener(\'keydown\',e=>{if(e.key===\'Enter\'&&!e.shiftKey){e.preventDefault();send()}});q(\'#elyaChatInput\')?.addEventListener(\'input\',e=>{e.target.style.height=\'auto\';e.target.style.height=Math.min(120,e.target.scrollHeight)+\'px\'});q(\'#elyaChatBlock\')?.addEventListener(\'click\',()=>{if(!current)return;call(\'chatSetBlocked\',current.otherUid,!blocked)});window.__elyaChatBlockState=(uid,b)=>{if(!current||current.otherUid!==uid)return;blocked=!!b;const btn=q(\'#elyaChatBlock\');btn.textContent=blocked?\'Unblock\':\'Block\';btn.classList.toggle(\'blocked\',blocked);q(\'#elyaChatInput\').disabled=blocked;q(\'#elyaChatSend\').disabled=blocked;chatStatus(blocked?\'You blocked this user.\':\'Chat ready.\')};const originalClose=window.closeModal;window.closeModal=function(id){originalClose(id);if(id===\'elyaChatsModal\')call(\'chatStopListeners\')};q(\'#settingsModal .dialog\')?.classList.remove(\'settings-simple\',\'show-advanced\');qa(\'#settingsModal .rare-setting\').forEach(x=>x.classList.remove(\'rare-setting\'));setTimeout(()=>call(\'firebaseCurrentUser\'),400)})();</script>'''
if 'id="elya120Script"' not in h: h=h.replace('</body>',script+'</body>',1)
h=h.replace("window.__elyaMainRuntimeVersion='1.1.4';","window.__elyaMainRuntimeVersion='1.2.0';",1)
p.write_text(h,encoding='utf-8')
print('Elya 1.2.0 organized Settings + Chats patch applied')

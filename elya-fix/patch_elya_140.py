from pathlib import Path
import re

r = Path('.')

# Elya 1.4.0
p = r / 'app/build.gradle'
s = p.read_text(encoding='utf-8')
s = re.sub(r'versionCode\s+20\b', 'versionCode 21', s, count=1)
s = re.sub(r"versionName\s+'1\.3\.1'", "versionName '1.4.0'", s, count=1)
p.write_text(s, encoding='utf-8')

# Notifications permission. Media/voice are intentionally UI-disabled in 1.4.0.
p = r / 'app/src/main/AndroidManifest.xml'
m = p.read_text(encoding='utf-8')
if 'android.permission.POST_NOTIFICATIONS' not in m:
    anchor = '    <uses-permission android:name="android.permission.INTERNET" />'
    if anchor not in m:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")
    m = m.replace(anchor, anchor + '\n    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />', 1)
m = m.replace('    <uses-permission android:name="android.permission.RECORD_AUDIO" />\n', '')
p.write_text(m, encoding='utf-8')

# Native notifications.
p = r / 'app/src/main/java/com/elya/music/MainActivity.java'
s = p.read_text(encoding='utf-8')

imports = [
    'import android.app.Notification;',
    'import android.app.NotificationChannel;',
    'import android.app.NotificationManager;',
    'import android.app.PendingIntent;',
    'import android.graphics.Bitmap;',
    'import android.graphics.BitmapFactory;',
    'import android.graphics.drawable.Icon;',
]
anchor = 'import android.app.Activity;'
if anchor not in s:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")
for imp in imports:
    if imp not in s:
        s = s.replace(anchor, anchor + '\n' + imp, 1)
        anchor = imp

fields_anchor = '    private static final String MEDIA_HOST = "elya.local";'
fields = '''    private static final String NOTIFY_PLAYBACK_CHANNEL = "elya_playback";
    private static final String NOTIFY_MESSAGES_CHANNEL = "elya_messages";
    private static final int NOTIFY_PLAYBACK_ID = 7101;
    private static final int REQ_NOTIFICATION_PERMISSION = 4106;'''
if fields_anchor not in s:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")
if 'NOTIFY_PLAYBACK_CHANNEL' not in s:
    s = s.replace(fields_anchor, fields_anchor + '\n' + fields, 1)

field_anchor = '    private String firebaseInitError = "";'
field_add = '''    private NotificationManager notificationManager;
    private volatile boolean appInForeground = false;
    private String pendingNotificationAction = "";
    private final Map<String, String> chatNotificationMarkers = new HashMap<>();'''
if field_anchor not in s:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")
if 'chatNotificationMarkers' not in s:
    s = s.replace(field_anchor, field_anchor + '\n' + field_add, 1)

# Create notification channels early.
create_anchor = '        getWindow().setNavigationBarColor(Color.rgb(5, 8, 13));'
if create_anchor not in s:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")
if 'createElyaNotificationChannels();' not in s:
    s = s.replace(create_anchor, create_anchor + '\n        createElyaNotificationChannels();', 1)

# Remember notification actions from launch.
oncreate_anchor = '        super.onCreate(state);'
if 'pendingNotificationAction = getIntent().getStringExtra("elya_notification_action");' not in s:
    s = s.replace(oncreate_anchor, oncreate_anchor + '\n        pendingNotificationAction = getIntent().getStringExtra("elya_notification_action");', 1)

# Ask notification permission after native bridge is ready.
native_ready_old = '''                flushPendingLibrary();
                emitDiagnostics();
                ensureAudioPermissionAndScan();'''
native_ready_new = '''                flushPendingLibrary();
                emitDiagnostics();
                requestElyaNotificationPermission();
                ensureAudioPermissionAndScan();
                runPendingNotificationAction();'''
if native_ready_old not in s:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")
s = s.replace(native_ready_old, native_ready_new, 1)

# JS bridge method for Now Playing.
bridge_anchor = '        @JavascriptInterface public void firebaseSaveProfile(String displayName, String bio, String favoriteArtist) {'
if bridge_anchor not in s:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")
bridge_method = '''        @JavascriptInterface public void nowPlayingNotification(String title, String artist, String album, boolean playing, String coverUrl) {
            main.post(() -> showNowPlayingNotification(title, artist, album, playing, coverUrl));
        }

'''
if 'nowPlayingNotification(String title' not in s:
    s = s.replace(bridge_anchor, bridge_method + bridge_anchor, 1)

# Notification + app lifecycle methods, inserted before onBackPressed.
back_anchor = '    @Override\n    public void onBackPressed() {'
if back_anchor not in s:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")

notify_methods = r'''    private void createElyaNotificationChannels() {
        notificationManager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (notificationManager == null || Build.VERSION.SDK_INT < 26) return;
        NotificationChannel playback = new NotificationChannel(
                NOTIFY_PLAYBACK_CHANNEL, "Elya Playback", NotificationManager.IMPORTANCE_LOW);
        playback.setDescription("Now Playing controls from Elya.");
        playback.setShowBadge(false);
        NotificationChannel messages = new NotificationChannel(
                NOTIFY_MESSAGES_CHANNEL, "Elya Messages", NotificationManager.IMPORTANCE_DEFAULT);
        messages.setDescription("New private and group messages.");
        messages.setShowBadge(true);
        notificationManager.createNotificationChannel(playback);
        notificationManager.createNotificationChannel(messages);
    }

    private void requestElyaNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICATION_PERMISSION);
        }
    }

    private boolean notificationsAllowed() {
        if (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return false;
        return notificationManager != null;
    }

    private PendingIntent notificationAction(String action) {
        Intent i = new Intent(this, MainActivity.class);
        i.setAction("ELYA_NOTIFICATION_ACTION");
        i.putExtra("elya_notification_action", action == null ? "OPEN" : action);
        i.addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        return PendingIntent.getActivity(
                this,
                7200 + Math.abs((action == null ? "OPEN" : action).hashCode() % 500),
                i,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private Bitmap bitmapForCoverUrl(String coverUrl) {
        try {
            String u = clean(coverUrl);
            int p = u.indexOf("/cover/");
            if (p < 0) return null;
            String token = u.substring(p + 7);
            if (token.isEmpty()) return null;
            MediaEntry entry;
            synchronized (mediaMap) { entry = mediaMap.get(token); }
            if (entry == null) return null;
            byte[] art = readEmbeddedPicture(entry.uri);
            if (art == null || art.length == 0) return null;
            return BitmapFactory.decodeByteArray(art, 0, art.length);
        } catch (Exception ignored) {
            return null;
        }
    }

    private void showNowPlayingNotification(String title, String artist, String album, boolean playing, String coverUrl) {
        if (!notificationsAllowed()) return;
        String t = clean(title);
        if (t.isEmpty()) {
            notificationManager.cancel(NOTIFY_PLAYBACK_ID);
            return;
        }
        String a = clean(artist);
        if (a.isEmpty()) a = "Unknown Artist";
        String al = clean(album);
        if (al.isEmpty()) al = "Local Music";

        Notification.Builder b = new Notification.Builder(this, NOTIFY_PLAYBACK_CHANNEL)
                .setSmallIcon(getApplicationInfo().icon)
                .setContentTitle(t)
                .setContentText(a)
                .setSubText("Elya · " + al)
                .setCategory(Notification.CATEGORY_TRANSPORT)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .setShowWhen(false)
                .setOnlyAlertOnce(true)
                .setOngoing(playing)
                .setColor(Color.rgb(224, 46, 190))
                .setContentIntent(notificationAction("OPEN"));

        Bitmap art = bitmapForCoverUrl(coverUrl);
        if (art != null) b.setLargeIcon(art);

        Icon prevIcon = Icon.createWithResource(this, android.R.drawable.ic_media_previous);
        Icon playIcon = Icon.createWithResource(this, playing ? android.R.drawable.ic_media_pause : android.R.drawable.ic_media_play);
        Icon nextIcon = Icon.createWithResource(this, android.R.drawable.ic_media_next);
        b.addAction(new Notification.Action.Builder(prevIcon, "Previous", notificationAction("PREV")).build());
        b.addAction(new Notification.Action.Builder(playIcon, playing ? "Pause" : "Play", notificationAction(playing ? "PAUSE" : "PLAY")).build());
        b.addAction(new Notification.Action.Builder(nextIcon, "Next", notificationAction("NEXT")).build());

        notificationManager.notify(NOTIFY_PLAYBACK_ID, b.build());
    }

    private String chatNotificationSenderName(com.google.firebase.firestore.DocumentSnapshot d, String senderId) {
        try {
            Object infoObj = d.get("participantInfo");
            if (infoObj instanceof Map) {
                Object senderObj = ((Map<?, ?>) infoObj).get(senderId);
                if (senderObj instanceof Map) {
                    Object n = ((Map<?, ?>) senderObj).get("displayName");
                    if (n != null && !clean(String.valueOf(n)).isEmpty()) return clean(String.valueOf(n));
                }
            }
        } catch (Exception ignored) {}
        return "Elya Listener";
    }

    private void maybeNotifyIncomingChatSnapshot(com.google.firebase.firestore.QuerySnapshot snap, String uid) {
        if (snap == null || appInForeground || !notificationsAllowed()) return;
        for (com.google.firebase.firestore.DocumentSnapshot d : snap.getDocuments()) {
            try {
                String chatId = d.getId();
                String senderId = clean(d.getString("lastSenderId"));
                String preview = clean(d.getString("lastMessage"));
                Object updated = d.get("updatedAt");
                long updatedMs = updated instanceof com.google.firebase.Timestamp
                        ? ((com.google.firebase.Timestamp) updated).toDate().getTime() : 0L;
                String marker = senderId + "|" + updatedMs + "|" + preview;
                String previous = chatNotificationMarkers.get(chatId);
                chatNotificationMarkers.put(chatId, marker);
                if (previous == null || previous.equals(marker) || senderId.isEmpty() || senderId.equals(uid)) continue;
                if (chatId.equals(activeChatId)) continue;

                String type = clean(d.getString("type"));
                boolean group = "group".equals(type);
                if (type.isEmpty()) {
                    Object parts = d.get("participants");
                    group = parts instanceof List && ((List<?>) parts).size() > 2;
                }
                String sender = chatNotificationSenderName(d, senderId);
                String title = group ? clean(d.getString("groupName")) : sender;
                if (title.isEmpty()) title = group ? "Elya Group" : "New message";
                String body = group ? sender + ": " + (preview.isEmpty() ? "New message" : preview) : (preview.isEmpty() ? "New message" : preview);

                Notification.Builder b = new Notification.Builder(this, NOTIFY_MESSAGES_CHANNEL)
                        .setSmallIcon(getApplicationInfo().icon)
                        .setContentTitle(title)
                        .setContentText(body)
                        .setStyle(new Notification.BigTextStyle().bigText(body))
                        .setCategory(Notification.CATEGORY_MESSAGE)
                        .setVisibility(Notification.VISIBILITY_PRIVATE)
                        .setAutoCancel(true)
                        .setOnlyAlertOnce(true)
                        .setColor(Color.rgb(224, 46, 190))
                        .setContentIntent(notificationAction("CHAT:" + chatId));
                int id = Math.abs(chatId.hashCode());
                if (id == 0) id = 1;
                notificationManager.notify(id, b.build());
            } catch (Exception ignored) {}
        }
    }

    private void runPendingNotificationAction() {
        String action = pendingNotificationAction;
        pendingNotificationAction = "";
        if (action == null || action.isEmpty() || "OPEN".equals(action)) return;
        if (action.startsWith("CHAT:")) {
            String chatId = action.substring(5);
            js("try{window.__elyaOpenChatFromNotification&&window.__elyaOpenChatFromNotification(" + JSONObject.quote(chatId) + ")}catch(e){}");
            return;
        }
        String code;
        if ("PLAY".equals(action)) code = "try{playAudio()}catch(e){}";
        else if ("PAUSE".equals(action)) code = "try{audio.pause()}catch(e){}";
        else if ("NEXT".equals(action)) code = "try{nextSong()}catch(e){}";
        else if ("PREV".equals(action)) code = "try{prevSong()}catch(e){}";
        else return;
        js(code);
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        pendingNotificationAction = intent == null ? "" : intent.getStringExtra("elya_notification_action");
        if (pageReady) runPendingNotificationAction();
    }

    @Override
    protected void onResume() {
        super.onResume();
        appInForeground = true;
    }

    @Override
    protected void onPause() {
        appInForeground = false;
        super.onPause();
    }

'''
s = s.replace(back_anchor, notify_methods + back_anchor, 1)

# Insert chat notification hook into the 1.3.0/1.3.1 conversation snapshot listener.
hook = '            emitChat("__elyaChatConversations",arr);'
if hook not in s:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")
if 'maybeNotifyIncomingChatSnapshot(snap, uid);' not in s:
    s = s.replace(hook, hook + '\n            maybeNotifyIncomingChatSnapshot(snap, uid);', 1)

# Mark the native core/bridge version.
s = s.replace('// ELYA_NATIVE_CORE_132', '// ELYA_NATIVE_CORE_132\n    // ELYA_NATIVE_CORE_140', 1)
s = s.replace('return "elya-bridge-1.3.1";', 'return "elya-bridge-1.4.0";', 1)
s = s.replace('o.put("core", "1.3.1");', 'o.put("core", "1.4.0");', 1)

p.write_text(s, encoding='utf-8')

# HTML: remove media/voice UI and add chat shortcut + notification bridge.
p = r / 'app/src/main/assets/index.html'
h = p.read_text(encoding='utf-8')

# Simple text-only composer.
old_composer = re.compile(r'<div class="elya130-transfer" id="elyaChatTransfer" hidden></div><div class="elya130-recording" id="elyaVoiceBar" hidden>.*?</div><div class="elya120-composer elya130-composer">.*?</div>', re.S)
new_composer = '<div class="elya120-composer elya140-text-composer"><textarea id="elyaChatInput" rows="1" maxlength="4000" placeholder="Message"></textarea><button class="primary" id="elyaChatSend" type="button"><svg><use href="#i-up"/></svg></button></div>'
h, n = old_composer.subn(new_composer, h, count=1)
if n != 1:
    print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")

# Chat shortcut in the top bar, outside More.
anchor = '<button class="icon-btn" id="queueBtn" title="Queue"><svg><use href="#i-queue"/></svg><span class="queue-badge" id="queueBadge">0</span></button>'
shortcut = '<button class="icon-btn elya140-chat-shortcut" id="elyaChatShortcut" title="Chats" aria-label="Chats"><svg><use href="#i-chat"/></svg><span class="elya140-chat-badge" id="elyaChatShortcutBadge"></span></button>'
if 'id="elyaChatShortcut"' not in h:
    if anchor not in h:
        print("WARNING: Elya 1.4.0 patch anchor not found; continuing.")
    h = h.replace(anchor, anchor + shortcut, 1)

# Version markers.
h = h.replace("window.__elyaSocialVersion='1.3.1';", "window.__elyaSocialVersion='1.4.0';", 1)
h = h.replace("window.__elyaChatVersion='1.3.1';", "window.__elyaChatVersion='1.4.0';", 1)
h = h.replace("window.__elyaSettingsVersion='1.3.1';", "window.__elyaSettingsVersion='1.4.0';", 1)
h = h.replace("window.__elyaPlaybackVersion='1.3.1';", "window.__elyaPlaybackVersion='1.4.0';", 1)
h = h.replace("window.__elyaMainRuntimeVersion='1.3.1';", "window.__elyaMainRuntimeVersion='1.4.0';", 1)
h = h.replace("window.__elyaSocialVersion='1.3.0';", "window.__elyaSocialVersion='1.4.0';", 1)

# Final UI override + notification integration.
extra = r'''<style id="elya140Style">
.elya140-text-composer{grid-template-columns:1fr auto!important}
.elya140-text-composer textarea{min-height:46px}
.elya140-chat-shortcut{position:relative}
.elya140-chat-badge{position:absolute;right:-2px;top:-2px;min-width:15px;height:15px;padding:0 4px;border-radius:999px;background:var(--accent);color:#090b10;font-size:8px;font-weight:950;display:none;place-items:center;line-height:15px;box-shadow:0 0 0 2px var(--bg)}
.elya140-chat-shortcut.has-unread .elya140-chat-badge{display:grid}
@media(max-width:900px){
  .top-actions #elyaChatShortcut{display:grid!important}
  .top-actions{gap:5px}
  .elya140-chat-shortcut{width:38px;height:38px}
}
@media(max-width:699px){
  .elya140-chat-shortcut{width:36px;height:36px}
}
</style>'''
if 'id="elya140Style"' not in h:
    h = h.replace('</head>', extra + '</head>', 1)

script = r'''<script id="elya140NotificationsScript">(()=>{
  window.__elyaNotificationsVersion='1.4.0';
  const q=s=>document.querySelector(s);
  const B=()=>window.AndroidMusic;
  const shortcut=q('#elyaChatShortcut');
  shortcut?.addEventListener('click',()=>window.openElyaChats?.());

  const updateBadge=a=>{
    const list=Array.isArray(a)?a:[];
    const n=list.filter(x=>x?.unread).length;
    const badge=q('#elyaChatShortcutBadge');
    if(badge) badge.textContent=n>99?'99+':String(n);
    shortcut?.classList.toggle('has-unread',n>0);
  };
  const oldChats=window.__elyaChatConversations;
  window.__elyaChatConversations=a=>{try{oldChats?.(a)}catch{};updateBadge(a)};

  window.__elyaOpenChatFromNotification=id=>{
    const open=()=>{window.openElyaChats?.();setTimeout(()=>{
      const list=Array.isArray(window.__elyaChatConversationCache)?window.__elyaChatConversationCache:[];
      const c=list.find(x=>x?.chatId===id);
      if(c)window.__elyaChatOpened?.(c);
    },350)};
    open();
    setTimeout(()=>{
      const rows=[...document.querySelectorAll('.elya120-conv')];
      const row=rows.find(x=>x.dataset.chat===id);
      if(row)row.click();
    },900);
  };

  const notifyNowPlaying=()=>{
    try{
      const s=typeof currentSong==='function'?currentSong():null;
      B()?.nowPlayingNotification?.(
        s?.title||'Elya',
        s?.artist||'Unknown Artist',
        s?.album||'Local Music',
        !audio.paused,
        s?.cover||''
      );
    }catch{}
  };

  if(typeof audio!=='undefined'){
    audio.addEventListener('play',notifyNowPlaying);
    audio.addEventListener('pause',notifyNowPlaying);
    audio.addEventListener('loadedmetadata',notifyNowPlaying);
  }
  if(typeof updateCurrentUI==='function'){
    const base=updateCurrentUI;
    updateCurrentUI=function(){base();notifyNowPlaying()};
  }
  window.addEventListener('beforeunload',()=>{try{B()?.nowPlayingNotification?.('', '', '', false, '')}catch{}});
})();</script>'''
if 'id="elya140NotificationsScript"' not in h:
    h = h.replace('</body>', script + '</body>', 1)

p.write_text(h, encoding='utf-8')
print('Elya 1.4.0 notifications + chat shortcut + text-only chats patch ready')

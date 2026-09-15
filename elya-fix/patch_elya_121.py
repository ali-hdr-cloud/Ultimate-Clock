from pathlib import Path

p=Path('app/src/main/java/com/elya/music/MainActivity.java')
s=p.read_text(encoding='utf-8')
old='''        final DocumentReference chatRef = firestore.collection("chats").document(chatId);
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
        }).addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));'''
new='''        final DocumentReference chatRef = firestore.collection("chats").document(chatId);
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
        // Merge directly so a brand-new chat can be created without probing a non-existent
        // chat document first. Security rules still protect existing chats by membership.
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
        }).addOnFailureListener(err -> emitChatError(chatFriendlyError(err)));'''
if old not in s:
    raise SystemExit('1.2.0 chat-create anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('Elya 1.2.0 chat create security fix applied')

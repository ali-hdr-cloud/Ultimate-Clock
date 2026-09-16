from pathlib import Path
import re
r=Path('.')

# version + storage SDK
p=r/'app/build.gradle'; s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+18\b','versionCode 19',s,count=1)
s=re.sub(r"versionName\s+'1\.2\.2'","versionName '1.3.0'",s,count=1)
if 'firebase-storage' not in s:
    a="    implementation 'com.google.firebase:firebase-firestore'"
    if a not in s: raise SystemExit('firestore dependency anchor missing')
    s=s.replace(a,a+"\n    implementation 'com.google.firebase:firebase-storage'",1)
p.write_text(s,encoding='utf-8')

# microphone permission
p=r/'app/src/main/AndroidManifest.xml'; m=p.read_text(encoding='utf-8')
if 'android.permission.RECORD_AUDIO' not in m:
    a='    <uses-permission android:name="android.permission.INTERNET" />'
    if a not in m: raise SystemExit('manifest anchor missing')
    m=m.replace(a,a+'\n    <uses-permission android:name="android.permission.RECORD_AUDIO" />',1)
p.write_text(m,encoding='utf-8')

p=r/'app/src/main/java/com/elya/music/MainActivity.java'; s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_123','// ELYA_NATIVE_CORE_123\n    // ELYA_NATIVE_CORE_130',1)
s=s.replace('return "elya-bridge-1.2.2";','return "elya-bridge-1.3.0";',1)
s=s.replace('o.put("core", "1.2.2");','o.put("core", "1.3.0");',1)
if 'import android.media.MediaRecorder;' not in s:s=s.replace('import android.media.MediaMetadataRetriever;','import android.media.MediaMetadataRetriever;\nimport android.media.MediaRecorder;',1)
if 'import java.io.File;' not in s:s=s.replace('import java.io.FilterInputStream;','import java.io.FilterInputStream;\nimport java.io.File;',1)
if 'import com.google.firebase.storage.FirebaseStorage;' not in s:s=s.replace('import com.google.firebase.firestore.Query;','import com.google.firebase.firestore.Query;\nimport com.google.firebase.storage.FirebaseStorage;\nimport com.google.firebase.storage.StorageReference;',1)

a='    private static final int REQ_AUDIO_PERMISSION = 4103;'
if a not in s: raise SystemExit('request code anchor missing')
s=s.replace(a,a+'\n    private static final int REQ_CHAT_MEDIA = 4104;\n    private static final int REQ_RECORD_AUDIO = 4105;',1)
a='    private FirebaseFirestore firestore;'
if a not in s: raise SystemExit('firebase field anchor missing')
s=s.replace(a,a+'\n    private FirebaseStorage firebaseStorage;',1)
a='    private volatile String activeChatId = "";'
if a not in s: raise SystemExit('chat field anchor missing')
s=s.replace(a,a+'\n    private String pendingChatMediaId = "";\n    private String pendingChatMediaKind = "";\n    private MediaRecorder voiceRecorder;\n    private File voiceFile;\n    private String voiceChatId = "";\n    private long voiceStartedAt = 0L;\n    private String pendingVoiceChatId = "";',1)
a='            firestore = FirebaseFirestore.getInstance();\n            credentialManager = CredentialManager.create(this);'
if a not in s: raise SystemExit('firebase init anchor missing')
s=s.replace(a,'            firestore = FirebaseFirestore.getInstance();\n            firebaseStorage = FirebaseStorage.getInstance();\n            credentialManager = CredentialManager.create(this);',1)

# direct chats are explicit, while old chats remain backward compatible
old='        data.put("participants", participants);\n        Map<String,Object> info = new HashMap<>();'
if old not in s: raise SystemExit('direct chat type anchor missing')
s=s.replace(old,'        data.put("participants", participants);\n        data.put("type", "direct");\n        Map<String,Object> info = new HashMap<>();',1)

# JS bridge additions
a='''        @JavascriptInterface public void chatStopListeners() {\n            main.post(MainActivity.this::chatStopListenersNative);\n        }'''
if a not in s: raise SystemExit('chat bridge anchor missing')
s=s.replace(a,a+'''\n\n        @JavascriptInterface public void chatReact(String chatId, String messageId, String reaction) { main.post(() -> chatReactNative(chatId, messageId, reaction)); }\n        @JavascriptInterface public void chatCreateGroup(String groupName, String membersJson) { main.post(() -> chatCreateGroupNative(groupName, membersJson)); }\n        @JavascriptInterface public void chatPickMedia(String chatId, String kind) { main.post(() -> chatPickMediaNative(chatId, kind)); }\n        @JavascriptInterface public void chatStartVoice(String chatId) { main.post(() -> chatStartVoiceNative(chatId)); }\n        @JavascriptInterface public void chatStopVoice(boolean send) { main.post(() -> chatStopVoiceNative(send)); }''',1)

# group-aware conversation list
pat=r'''    private void chatListenConversationsNative\(\) \{.*?\n    \}\n\n    private void chatListenMessagesNative'''
rep=r'''    private void chatListenConversationsNative() {
        FirebaseUser me=chatUserOrError(); if(me==null)return;
        if(chatListRegistration!=null)chatListRegistration.remove(); final String uid=me.getUid();
        chatListRegistration=firestore.collection("chats").whereArrayContains("participants",uid).limit(100).addSnapshotListener((snap,err)->{
            if(err!=null){emitChatError(chatFriendlyError(err));return;} JSONArray arr=new JSONArray();
            if(snap!=null)for(DocumentSnapshot d:snap.getDocuments())try{
                List<String> parts=d.get("participants") instanceof List?(List<String>)d.get("participants"):new ArrayList<>();
                String type=clean(d.getString("type")); if(type.isEmpty())type=parts.size()>2?"group":"direct";
                Map<String,Object> info=d.get("participantInfo") instanceof Map?(Map<String,Object>)d.get("participantInfo"):new HashMap<>();
                JSONObject o=new JSONObject(); o.put("chatId",d.getId());o.put("type",type);o.put("memberCount",parts.size());o.put("participants",new JSONArray(parts));o.put("participantInfo",new JSONObject(info));
                List<String> admins=d.get("admins") instanceof List?(List<String>)d.get("admins"):new ArrayList<>();o.put("admins",new JSONArray(admins));
                if("group".equals(type)){String n=clean(d.getString("groupName"));o.put("displayName",n.isEmpty()?"Elya Group":n);o.put("username",parts.size()+" members");o.put("otherUid","");}
                else{String other="";for(String x:parts)if(!uid.equals(x)){other=x;break;}Map<String,Object> oi=info.get(other) instanceof Map?(Map<String,Object>)info.get(other):null;o.put("otherUid",other);o.put("displayName",oi==null?"Elya Listener":clean(String.valueOf(oi.get("displayName"))));o.put("username",oi==null||oi.get("username")==null?"":clean(String.valueOf(oi.get("username"))));}
                o.put("lastMessage",clean(d.getString("lastMessage")));o.put("lastSenderId",clean(d.getString("lastSenderId")));Object t=d.get("updatedAt");o.put("updatedAt",t instanceof com.google.firebase.Timestamp?((com.google.firebase.Timestamp)t).toDate().getTime():0);
                List<String> seen=d.get("seenBy") instanceof List?(List<String>)d.get("seenBy"):new ArrayList<>();o.put("unread",!uid.equals(o.optString("lastSenderId"))&&!seen.contains(uid));o.put("seenByOther","direct".equals(type)&&seen.size()>1);arr.put(o);
            }catch(Exception ignored){} emitChat("__elyaChatConversations",arr);
        });
    }

    private void chatListenMessagesNative'''
s,n=re.subn(pat,rep,s,count=1,flags=re.S)
if n!=1: raise SystemExit('conversation listener replace failed')

# rich message listener
pat=r'''    private void chatListenMessagesNative\(String chatId\) \{.*?\n    \}\n\n    private void chatSendNative'''
rep=r'''    private void chatListenMessagesNative(String chatId) {
        FirebaseUser me=chatUserOrError();if(me==null)return;chatId=clean(chatId);if(chatId.isEmpty())return;
        if(chatMessageRegistration!=null)chatMessageRegistration.remove();activeChatId=chatId;final String cid=chatId;
        chatMessageRegistration=firestore.collection("chats").document(cid).collection("messages").orderBy("createdAt",Query.Direction.ASCENDING).limitToLast(250).addSnapshotListener((snap,err)->{
            if(err!=null){emitChatError(chatFriendlyError(err));return;}JSONArray arr=new JSONArray();
            if(snap!=null)for(DocumentSnapshot d:snap.getDocuments())try{JSONObject o=new JSONObject();o.put("id",d.getId());o.put("senderId",clean(d.getString("senderId")));o.put("senderName",clean(d.getString("senderName")));o.put("text",clean(d.getString("text")));String k=clean(d.getString("kind"));o.put("kind",k.isEmpty()?"text":k);o.put("mediaUrl",clean(d.getString("mediaUrl")));o.put("fileName",clean(d.getString("fileName")));o.put("mimeType",clean(d.getString("mimeType")));Long fs=d.getLong("fileSize"),du=d.getLong("durationMs");o.put("fileSize",fs==null?0:fs);o.put("durationMs",du==null?0:du);Map<String,Object> rx=d.get("reactions") instanceof Map?(Map<String,Object>)d.get("reactions"):new HashMap<>();o.put("reactions",new JSONObject(rx));Object t=d.get("createdAt");o.put("createdAt",t instanceof com.google.firebase.Timestamp?((com.google.firebase.Timestamp)t).toDate().getTime():0);arr.put(o);}catch(Exception ignored){}
            emitChat("__elyaChatMessages",arr);chatMarkSeenNative(cid);
        });
    }

    private void chatSendNative'''
s,n=re.subn(pat,rep,s,count=1,flags=re.S)
if n!=1: raise SystemExit('message listener replace failed')

# generic send pipeline (text/media/voice)
pat=r'''    private void chatSendNative\(String chatId, String rawText\) \{.*?\n    \}\n\n    private void chatMarkSeenNative'''
rep=r'''    private void chatSendNative(String chatId,String rawText){String text=rawText==null?"":rawText.trim();if(text.isEmpty())return;if(text.length()>4000){emitChatError("Messages can be up to 4000 characters.");return;}chatWriteMessageNative(clean(chatId),text,"text","","","",0L,0L);}

    private void chatWriteMessageNative(String chatId,String text,String kind,String mediaUrl,String fileName,String mimeType,long fileSize,long durationMs){
        FirebaseUser me=chatUserOrError();if(me==null)return;final String cid=clean(chatId),k=clean(kind).isEmpty()?"text":clean(kind);if(cid.isEmpty())return;final DocumentReference chatRef=firestore.collection("chats").document(cid);
        chatRef.get().addOnSuccessListener(doc->{if(!doc.exists()){emitChatError("This chat no longer exists.");return;}List<String> parts=doc.get("participants") instanceof List?(List<String>)doc.get("participants"):new ArrayList<>();if(!parts.contains(me.getUid())){emitChatError("You do not have access to this chat.");return;}String type=clean(doc.getString("type"));if(type.isEmpty())type=parts.size()>2?"group":"direct";
            Runnable write=()->{DocumentReference mr=chatRef.collection("messages").document();com.google.firebase.firestore.WriteBatch b=firestore.batch();Map<String,Object> msg=new HashMap<>();msg.put("senderId",me.getUid());String sn=clean(me.getDisplayName());msg.put("senderName",sn.isEmpty()?"Elya Listener":sn);msg.put("text",text==null?"":text);msg.put("kind",k);msg.put("createdAt",FieldValue.serverTimestamp());msg.put("reactions",new HashMap<String,Object>());if(!"text".equals(k)){msg.put("mediaUrl",mediaUrl==null?"":mediaUrl);msg.put("fileName",fileName==null?"":fileName);msg.put("mimeType",mimeType==null?"":mimeType);msg.put("fileSize",Math.max(0L,fileSize));msg.put("durationMs",Math.max(0L,durationMs));}b.set(mr,msg);String preview="image".equals(k)?"Photo":"video".equals(k)?"Video":"voice".equals(k)?"Voice message":"file".equals(k)?(fileName==null||fileName.isEmpty()?"File":fileName):text;Map<String,Object> meta=new HashMap<>();meta.put("lastMessage",preview);meta.put("lastSenderId",me.getUid());meta.put("updatedAt",FieldValue.serverTimestamp());meta.put("seenBy",Collections.singletonList(me.getUid()));b.set(chatRef,meta,SetOptions.merge());b.commit().addOnSuccessListener(v->emitChatStatus("Sent")).addOnFailureListener(e->emitChatError(chatFriendlyError(e)));};
            if("group".equals(type)){write.run();return;}String other="";for(String x:parts)if(!me.getUid().equals(x)){other=x;break;}if(other.isEmpty()){write.run();return;}firestore.collection("users").document(me.getUid()).collection("blocks").document(other).get().addOnSuccessListener(bl->{if(bl.exists()){emitChatError("Unblock this person before sending a message.");return;}write.run();}).addOnFailureListener(e->emitChatError(chatFriendlyError(e)));
        }).addOnFailureListener(e->emitChatError(chatFriendlyError(e)));
    }

    private void chatMarkSeenNative'''
s,n=re.subn(pat,rep,s,count=1,flags=re.S)
if n!=1: raise SystemExit('send pipeline replace failed')

# social helpers
anchor='    private void chatStopListenersNative() {'
if anchor not in s: raise SystemExit('chatStop anchor missing')
methods=r'''    private void chatReactNative(String chatId,String messageId,String raw){FirebaseUser me=chatUserOrError();if(me==null)return;String cid=clean(chatId),mid=clean(messageId),reaction=clean(raw).toLowerCase(Locale.US);if(cid.isEmpty()||mid.isEmpty())return;if(!reaction.isEmpty()&&!reaction.matches("heart|like|laugh|fire")){emitChatError("Unsupported reaction.");return;}DocumentReference ref=firestore.collection("chats").document(cid).collection("messages").document(mid);firestore.runTransaction(tx->{DocumentSnapshot d=tx.get(ref);if(!d.exists())throw new IllegalStateException("Message not found.");Map<String,Object> rx=d.get("reactions") instanceof Map?new HashMap<>((Map<String,Object>)d.get("reactions")):new HashMap<>();if(reaction.isEmpty())rx.remove(me.getUid());else rx.put(me.getUid(),reaction);tx.update(ref,"reactions",rx);return null;}).addOnFailureListener(e->emitChatError(chatFriendlyError(e)));}

    private void chatCreateGroupNative(String rawName,String membersJson){FirebaseUser me=chatUserOrError();if(me==null)return;String name=rawName==null?"":rawName.trim();if(name.length()<2||name.length()>60){emitChatError("Group name must be 2–60 characters.");return;}try{JSONArray a=new JSONArray(membersJson==null?"[]":membersJson);ArrayList<String> parts=new ArrayList<>();parts.add(me.getUid());Map<String,Object> info=new HashMap<>();Map<String,Object> mine=new HashMap<>();String mn=clean(me.getDisplayName());mine.put("displayName",mn.isEmpty()?"Elya Listener":mn);info.put(me.getUid(),mine);for(int i=0;i<a.length()&&parts.size()<50;i++){JSONObject u=a.optJSONObject(i);if(u==null)continue;String uid=clean(u.optString("uid"));if(uid.isEmpty()||uid.equals(me.getUid())||parts.contains(uid))continue;parts.add(uid);Map<String,Object> one=new HashMap<>();String dn=clean(u.optString("displayName"));one.put("displayName",dn.isEmpty()?"Elya Listener":dn);one.put("username",normalizeChatUsername(u.optString("username")));info.put(uid,one);}if(parts.size()<3){emitChatError("Add at least 2 other people to make a group.");return;}DocumentReference ref=firestore.collection("chats").document();Map<String,Object>d=new HashMap<>();d.put("type","group");d.put("groupName",name);d.put("participants",parts);d.put("participantInfo",info);d.put("admins",Collections.singletonList(me.getUid()));d.put("createdAt",FieldValue.serverTimestamp());d.put("updatedAt",FieldValue.serverTimestamp());d.put("lastMessage","Group created");d.put("lastSenderId",me.getUid());d.put("seenBy",Collections.singletonList(me.getUid()));ref.set(d).addOnSuccessListener(v->{JSONObject o=new JSONObject();try{o.put("chatId",ref.getId());o.put("type","group");o.put("displayName",name);o.put("username",parts.size()+" members");o.put("memberCount",parts.size());o.put("participants",new JSONArray(parts));o.put("participantInfo",new JSONObject(info));o.put("admins",new JSONArray(Collections.singletonList(me.getUid())));}catch(Exception ignored){}emitChat("__elyaChatGroupCreated",o);chatListenConversationsNative();chatListenMessagesNative(ref.getId());}).addOnFailureListener(e->emitChatError(chatFriendlyError(e)));}catch(Exception e){emitChatError("Could not create this group.");}}

    private void chatPickMediaNative(String chatId,String rawKind){FirebaseUser me=chatUserOrError();if(me==null)return;String cid=clean(chatId),kind=clean(rawKind).toLowerCase(Locale.US);if(cid.isEmpty())return;if(!kind.matches("image|video|file"))kind="file";pendingChatMediaId=cid;pendingChatMediaKind=kind;Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.addCategory(Intent.CATEGORY_OPENABLE);i.setType("image".equals(kind)?"image/*":"video".equals(kind)?"video/*":"*/*");startActivityForResult(i,REQ_CHAT_MEDIA);}

    private void uploadChatUri(String chatId,String kind,Uri uri,String forcedName,long durationMs){FirebaseUser me=chatUserOrError();if(me==null||firebaseStorage==null||uri==null){emitChatError("Chat media storage is unavailable.");return;}String name=clean(forcedName);if(name.isEmpty())name=clean(queryName(uri));if(name.isEmpty())name="attachment";String mime=clean(getContentResolver().getType(uri));if(mime.isEmpty())mime="application/octet-stream";long size=querySize(uri);if(size>25L*1024L*1024L){emitChatError("Attachments can be up to 25 MB.");return;}String safe=name.replaceAll("[^A-Za-z0-9._-]","_");if(safe.length()>80)safe=safe.substring(safe.length()-80);StorageReference ref=firebaseStorage.getReference().child("chat-media/"+chatId+"/"+me.getUid()+"/"+System.currentTimeMillis()+"_"+safe);final String fn=name,mt=mime,k=kind;emitChatUpload("started",0,fn);ref.putFile(uri).addOnProgressListener(x->{long total=x.getTotalByteCount();int pct=total>0?(int)Math.min(100,(x.getBytesTransferred()*100L)/total):0;emitChatUpload("progress",pct,fn);}).addOnSuccessListener(x->ref.getDownloadUrl().addOnSuccessListener(url->{emitChatUpload("uploaded",100,fn);chatWriteMessageNative(chatId,"",k,url.toString(),fn,mt,size,durationMs);}).addOnFailureListener(e->emitChatError(chatFriendlyError(e)))).addOnFailureListener(e->emitChatError(chatFriendlyError(e)));}

    private long querySize(Uri uri){try(Cursor c=getContentResolver().query(uri,new String[]{OpenableColumns.SIZE},null,null,null)){if(c!=null&&c.moveToFirst()&&!c.isNull(0))return c.getLong(0);}catch(Exception ignored){}try(ParcelFileDescriptor pfd=getContentResolver().openFileDescriptor(uri,"r")){return pfd==null?0L:Math.max(0L,pfd.getStatSize());}catch(Exception ignored){return 0L;}}

    private void chatStartVoiceNative(String chatId){FirebaseUser me=chatUserOrError();if(me==null)return;String cid=clean(chatId);if(cid.isEmpty())return;if(voiceRecorder!=null){emitChatError("A voice message is already recording.");return;}if(Build.VERSION.SDK_INT>=23&&checkSelfPermission(Manifest.permission.RECORD_AUDIO)!=PackageManager.PERMISSION_GRANTED){pendingVoiceChatId=cid;requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},REQ_RECORD_AUDIO);return;}startVoiceRecorder(cid);}
    private void startVoiceRecorder(String cid){try{voiceFile=new File(getCacheDir(),"elya_voice_"+System.currentTimeMillis()+".m4a");voiceRecorder=new MediaRecorder();voiceRecorder.setAudioSource(MediaRecorder.AudioSource.MIC);voiceRecorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);voiceRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);voiceRecorder.setAudioEncodingBitRate(96000);voiceRecorder.setAudioSamplingRate(44100);voiceRecorder.setOutputFile(voiceFile.getAbsolutePath());voiceRecorder.prepare();voiceRecorder.start();voiceChatId=cid;voiceStartedAt=System.currentTimeMillis();emitChatVoice("recording",0L);}catch(Exception e){releaseVoiceRecorder();emitChatError("Could not start voice recording: "+clean(e.getMessage()));}}
    private void chatStopVoiceNative(boolean send){if(voiceRecorder==null)return;long dur=Math.max(0L,System.currentTimeMillis()-voiceStartedAt);File f=voiceFile;String cid=voiceChatId;boolean ok=true;try{voiceRecorder.stop();}catch(Exception e){ok=false;}releaseVoiceRecorder();if(!send||!ok||f==null||!f.exists()){if(f!=null)try{f.delete();}catch(Exception ignored){}emitChatVoice("idle",0L);if(send&&!ok)emitChatError("Voice recording was too short. Hold it a little longer.");return;}emitChatVoice("uploading",dur);uploadChatUri(cid,"voice",Uri.fromFile(f),"Voice message.m4a",dur);}
    private void releaseVoiceRecorder(){if(voiceRecorder!=null)try{voiceRecorder.release();}catch(Exception ignored){}voiceRecorder=null;voiceChatId="";voiceStartedAt=0L;voiceFile=null;}
    private void emitChatUpload(String state,int percent,String name){js("window.__elyaChatUpload&&window.__elyaChatUpload("+JSONObject.quote(state)+","+percent+","+JSONObject.quote(name==null?"":name)+");");}
    private void emitChatVoice(String state,long durationMs){js("window.__elyaChatVoice&&window.__elyaChatVoice("+JSONObject.quote(state)+","+durationMs+");");}

'''
s=s.replace(anchor,methods+anchor,1)

# microphone permission result
old='        if (requestCode != REQ_AUDIO_PERMISSION) return;'
if old not in s: raise SystemExit('permission result anchor missing')
s=s.replace(old,'        if (requestCode == REQ_RECORD_AUDIO) { if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) { String cid=pendingVoiceChatId; pendingVoiceChatId=""; if(!cid.isEmpty()) startVoiceRecorder(cid); } else { pendingVoiceChatId=""; emitChatError("Microphone permission is required for voice messages."); } return; }\n        if (requestCode != REQ_AUDIO_PERMISSION) return;',1)

# media picker result
old='        if (requestCode == REQ_FILE) {'
if old not in s: raise SystemExit('activity result anchor missing')
s=s.replace(old,'        if (requestCode == REQ_CHAT_MEDIA) { String cid=pendingChatMediaId,kind=pendingChatMediaKind;pendingChatMediaId="";pendingChatMediaKind="";if(resultCode==RESULT_OK&&data!=null&&data.getData()!=null&&!cid.isEmpty())uploadChatUri(cid,kind,data.getData(),"",0L);return; }\n'+old,1)

# recorder cleanup
old='        chatStopListenersNative();\n        io.shutdownNow();'
if old not in s: raise SystemExit('destroy anchor missing')
s=s.replace(old,'        chatStopListenersNative();\n        if(voiceRecorder!=null){try{voiceRecorder.stop();}catch(Exception ignored){}releaseVoiceRecorder();}\n        io.shutdownNow();',1)
p.write_text(s,encoding='utf-8')
print('Elya 1.3.0 social backend applied')

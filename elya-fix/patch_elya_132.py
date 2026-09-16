from pathlib import Path
import re
r=Path('.')

# Version 1.3.1
p=r/'app/build.gradle'; s=p.read_text(encoding='utf-8')
s=re.sub(r'versionCode\s+19\b','versionCode 20',s,count=1)
s=re.sub(r"versionName\s+'1\.3\.0'","versionName '1.3.1'",s,count=1)
p.write_text(s,encoding='utf-8')

# Native upload reliability + actionable Storage errors.
p=r/'app/src/main/java/com/elya/music/MainActivity.java'; s=p.read_text(encoding='utf-8')
s=s.replace('// ELYA_NATIVE_CORE_130','// ELYA_NATIVE_CORE_130\n    // ELYA_NATIVE_CORE_132',1)
s=s.replace('return "elya-bridge-1.3.0";','return "elya-bridge-1.3.1";',1)
s=s.replace('o.put("core", "1.3.0");','o.put("core", "1.3.1");',1)

old='''    private void uploadChatUri(String chatId,String kind,Uri uri,String forcedName,long durationMs){FirebaseUser me=chatUserOrError();if(me==null||firebaseStorage==null||uri==null){emitChatError("Chat media storage is unavailable.");return;}String name=clean(forcedName);if(name.isEmpty())name=clean(queryName(uri));if(name.isEmpty())name="attachment";String mime=clean(getContentResolver().getType(uri));if(mime.isEmpty())mime="application/octet-stream";long size=querySize(uri);if(size>25L*1024L*1024L){emitChatError("Attachments can be up to 25 MB.");return;}String safe=name.replaceAll("[^A-Za-z0-9._-]","_");if(safe.length()>80)safe=safe.substring(safe.length()-80);StorageReference ref=firebaseStorage.getReference().child("chat-media/"+chatId+"/"+me.getUid()+"/"+System.currentTimeMillis()+"_"+safe);final String fn=name,mt=mime,k=kind;emitChatUpload("started",0,fn);ref.putFile(uri).addOnProgressListener(x->{long total=x.getTotalByteCount();int pct=total>0?(int)Math.min(100,(x.getBytesTransferred()*100L)/total):0;emitChatUpload("progress",pct,fn);}).addOnSuccessListener(x->ref.getDownloadUrl().addOnSuccessListener(url->{emitChatUpload("uploaded",100,fn);chatWriteMessageNative(chatId,"",k,url.toString(),fn,mt,size,durationMs);}).addOnFailureListener(e->emitChatError(chatFriendlyError(e)))).addOnFailureListener(e->emitChatError(chatFriendlyError(e)));}'''
new=r'''    private void uploadChatUri(String chatId,String kind,Uri uri,String forcedName,long durationMs){
        FirebaseUser me=chatUserOrError();
        if(me==null||firebaseStorage==null||uri==null){emitChatUpload("error",0,"attachment");emitChatError("Chat media storage is unavailable.");return;}
        String name=clean(forcedName);if(name.isEmpty())name=clean(queryName(uri));if(name.isEmpty())name="attachment";
        String mime="";try{mime=clean(getContentResolver().getType(uri));}catch(Exception ignored){}if(mime.isEmpty())mime="application/octet-stream";
        long size=querySize(uri);if(size>25L*1024L*1024L){emitChatUpload("error",0,name);emitChatError("Attachments can be up to 25 MB.");return;}
        String safe=name.replaceAll("[^A-Za-z0-9._-]","_");if(safe.length()>80)safe=safe.substring(safe.length()-80);
        StorageReference ref=firebaseStorage.getReference().child("chat-media/"+chatId+"/"+me.getUid()+"/"+System.currentTimeMillis()+"_"+safe);
        final String fn=name,mt=mime,k=kind;final long fileSize=size;
        java.io.InputStream input=null;
        try{
            if("file".equalsIgnoreCase(uri.getScheme())&&uri.getPath()!=null) input=new FileInputStream(new File(uri.getPath()));
            else input=getContentResolver().openInputStream(uri);
        }catch(Exception e){emitChatUpload("error",0,fn);emitChatError("Elya cannot read this attachment: "+clean(e.getMessage()));return;}
        if(input==null){emitChatUpload("error",0,fn);emitChatError("Elya cannot open this attachment.");return;}
        final java.io.InputStream uploadStream=input;
        emitChatUpload("started",1,fn);
        com.google.firebase.storage.UploadTask task=ref.putStream(uploadStream);
        task.addOnProgressListener(x->{long total=x.getTotalByteCount();int pct=total>0?(int)Math.max(1,Math.min(99,(x.getBytesTransferred()*100L)/total)):1;emitChatUpload("progress",pct,fn);})
            .addOnSuccessListener(x->{try{uploadStream.close();}catch(Exception ignored){}ref.getDownloadUrl().addOnSuccessListener(url->{emitChatUpload("uploaded",100,fn);chatWriteMessageNative(chatId,"",k,url.toString(),fn,mt,fileSize,durationMs);}).addOnFailureListener(e->{emitChatUpload("error",0,fn);emitChatError(chatStorageFriendlyError(e));});})
            .addOnFailureListener(e->{try{uploadStream.close();}catch(Exception ignored){}emitChatUpload("error",0,fn);emitChatError(chatStorageFriendlyError(e));});
    }

    private String chatStorageFriendlyError(Exception e){
        String m=e==null||e.getMessage()==null?"Cloud media upload failed.":e.getMessage();
        String l=m.toLowerCase(Locale.US);
        if(l.contains("402")||l.contains("quota")||l.contains("billing")||l.contains("blaze")) return "Cloud media needs Firebase Blaze. Your project is on Spark, so Firebase Storage blocks photo, video, file and voice uploads.";
        if(l.contains("403")||l.contains("unauthorized")||l.contains("permission")||l.contains("not authorized")) return "Firebase Storage blocked this upload. If the project is still on Spark, upgrade to Blaze; otherwise publish the Elya Storage Rules and try again.";
        if(l.contains("bucket")&&l.contains("not")) return "Firebase Storage bucket is not available. Open Firebase > Storage and finish Storage setup.";
        if(l.contains("network")||l.contains("timeout")) return "Media upload could not reach Firebase Storage. Check your connection and try again.";
        return m.length()>260?m.substring(0,260):m;
    }'''
if old not in s: raise SystemExit('1.3.0 uploadChatUri anchor missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# HTML fullscreen chats + clearer upload state.
p=r/'app/src/main/assets/index.html'; h=p.read_text(encoding='utf-8')
h=h.replace("window.__elyaSocialVersion='1.3.0';","window.__elyaSocialVersion='1.3.1';",1)
h=h.replace("window.__elyaChatVersion='1.3.0';","window.__elyaChatVersion='1.3.1';",1)
h=h.replace("window.__elyaSettingsVersion='1.3.0';","window.__elyaSettingsVersion='1.3.1';",1)
h=h.replace("window.__elyaPlaybackVersion='1.3.0';","window.__elyaPlaybackVersion='1.3.1';",1)
h=h.replace("window.__elyaMainRuntimeVersion='1.2.2';","window.__elyaMainRuntimeVersion='1.3.1';",1)
h=h.replace('<strong>Elya 1.2.2</strong>','<strong>Elya 1.3.1</strong>',1)

css=r'''<style id="elya131FullscreenChatStyle">
#elyaChatsModal{padding:0!important;align-items:stretch!important;justify-content:stretch!important;background:var(--bg)!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important}
#elyaChatsModal>.dialog,.elya120-chat-dialog{width:100vw!important;max-width:none!important;height:100dvh!important;max-height:none!important;margin:0!important;border:0!important;border-radius:0!important;box-shadow:none!important;background:var(--bg)!important;padding:max(10px,env(safe-area-inset-top)) max(10px,env(safe-area-inset-right)) max(10px,env(safe-area-inset-bottom)) max(10px,env(safe-area-inset-left))!important}
#elyaChatsModal .dialog-head{flex:0 0 auto;padding:4px 4px 10px!important}
#elyaChatsModal .elya120-chat-app{flex:1!important;border-radius:18px!important;min-height:0!important}
#elyaChatsModal .elya120-conversation{height:100%!important}
#elyaChatsModal .elya120-messages{overscroll-behavior:contain}
#elyaChatsModal.open{display:flex!important}
.elya131-chat-fullscreen-open{overflow:hidden!important}
.elya131-chat-fullscreen-open .mini-player,.elya131-chat-fullscreen-open .mobile-nav{visibility:hidden!important}
.elya131-upload-error{color:#ff8b8b!important;background:rgba(255,82,95,.07)!important}
@media(max-width:699px){#elyaChatsModal>.dialog,.elya120-chat-dialog{padding:max(6px,env(safe-area-inset-top)) 0 max(4px,env(safe-area-inset-bottom))!important}.elya120-chat-app{border:0!important;border-radius:0!important}.elya120-conversation{inset:58px 0 0!important}.elya120-thread-head{padding-left:8px!important;padding-right:8px!important}.elya120-messages{padding:12px!important}.elya130-composer{padding:7px!important}}
</style>'''
if 'id="elya131FullscreenChatStyle"' not in h:h=h.replace('</head>',css+'</head>',1)

script=r'''<script id="elya131FullscreenChatScript">(()=>{
 window.__elyaFullscreenChatVersion='1.3.1';
 const q=s=>document.querySelector(s),modal=q('#elyaChatsModal');
 const sync=()=>document.documentElement.classList.toggle('elya131-chat-fullscreen-open',!!modal?.classList.contains('open'));
 if(modal){new MutationObserver(sync).observe(modal,{attributes:true,attributeFilter:['class']});sync()}
 const prev=window.__elyaChatUpload;
 window.__elyaChatUpload=(st,pct,n)=>{try{prev?.(st,pct,n)}catch{};const b=q('#elyaChatTransfer');if(!b)return;if(st==='error'){b.hidden=false;b.classList.add('elya131-upload-error');b.textContent='Upload failed · '+(n||'media');setTimeout(()=>{b.hidden=true;b.classList.remove('elya131-upload-error')},5000)}else{b.classList.remove('elya131-upload-error')}};
 const oldErr=window.__elyaChatError;
 window.__elyaChatError=m=>{try{oldErr?.(m)}catch{};const text=String(m||'');if(/Blaze|Storage|upload/i.test(text)){const b=q('#elyaChatTransfer');if(b){b.hidden=false;b.classList.add('elya131-upload-error');b.textContent=text;setTimeout(()=>{b.hidden=true;b.classList.remove('elya131-upload-error')},8000)}}};
})();</script>'''
if 'id="elya131FullscreenChatScript"' not in h:h=h.replace('</body>',script+'</body>',1)
p.write_text(h,encoding='utf-8')
print('Elya 1.3.1 fullscreen chat + media upload diagnostics applied')

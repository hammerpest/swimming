/* ===== Swim Opt 2.0: Supabase store. Same calls as the stores in store-local.js, plus the PIN calls.
   Used when js/config.js has the project URL and key. Add ?mode=local to the address for one-device test mode.
   Extra calls: role (the job the server has for this device), claimRole(hash), releaseRole(), setYear(y), checkPin(job,hash) =====
   Each browser tab signs in anonymously on its own (sessionStorage), so each tab is its own device, like test mode. */
const SB_TABLES=["config","roster","extras","heats","times","finish","slips","records","counter","years"];
async function supabaseStore(onQueue){
  const C=window.SWIM_CONFIG||{};
  if(!C.url||!C.key)return null;
  if(new URLSearchParams(location.search).get("mode")==="local")return null;
  /* the Supabase library loads only when it is used, so test mode runs exactly as before */
  if(!window.supabase)await new Promise((ok,no)=>{const s=document.createElement("script");s.src="js/vendor/supabase.js";s.onload=ok;s.onerror=no;document.head.appendChild(s)});
  /* the key is per tab: with one shared key, the library passes a new sign-in to every open tab */
  const sb=window.supabase.createClient(C.url,C.key,{auth:{storage:window.sessionStorage,storageKey:"swim_auth_"+DEV,persistSession:true,autoRefreshToken:true}});
  const split=p=>{const i=p.indexOf("/");return [p.slice(0,i),p.slice(i+1)]};
  /* a refused write (no job, locked, bad data) is dropped; a network failure waits in the queue */
  const err=e=>{const c=String((e&&(e.code||e.statusCode))||"");const net=!c||c==="PGRST301"||c==="401"||/fetch|network/i.test((e&&e.message)||"");return {code:net?"offline":"invalid_argument",message:e&&e.message}};
  const merge=(a,b)=>{const o=Object.assign({},a||{});for(const k in b){if(b[k]&&typeof b[k]==="object"&&!Array.isArray(b[k])&&o[k]&&typeof o[k]==="object")o[k]=merge(o[k],b[k]);else o[k]=b[k]}return o};

  /* sign in once per tab; keep trying if there is no signal */
  let authed=null;
  function signIn(){
    if(!authed)authed=(async()=>{
      for(;;){
        try{const {data}=await sb.auth.getSession();if(data&&data.session)return true;
          const r=await sb.auth.signInAnonymously();if(!r.error)return true}catch(e){}
        await sleep(5000);
      }
    })();
    return authed;
  }

  /* photos live in the private Storage bucket "slips", one file per race */
  const toBlob=url=>fetch(url).then(r=>r.blob());
  const toUrl=blob=>new Promise((ok,no)=>{const f=new FileReader();f.onload=()=>ok(f.result);f.onerror=no;f.readAsDataURL(blob)});
  async function photoWrite(w,id){
    const B=sb.storage.from("slips");let r;
    if(w.op==="del")r=await B.remove([id+".jpg"]);
    else{const blob=await toBlob(w.data.img);r=await B.upload(id+".jpg",blob,{upsert:true,contentType:blob.type||"image/jpeg"})}
    if(r.error)throw err(r.error);
    return {ok:true};
  }
  async function write(w){
    await signIn();
    const [t,id]=split(w.path);
    if(t==="photos")return photoWrite(w,id);
    let r,doc=w.data;
    /* Swim Opt 2.30 (problem 27): a slip or multitimer send is merged with the server's copy as it goes, not
       with the copy the phone had when Send was pressed (it may be minutes old after no signal), so a time
       the Recorder typed in the meantime stays and the slip time shows beside it ("Slip differs").
       The server does the same again (times_slip_merge in supabase/01-setup.sql). */
    if(w.op==="set"&&w.raw&&t==="times"&&typeof lateSlip==="function"){
      const c=await sb.from(t).select("doc").eq("id",id).maybeSingle();
      if(c.error)throw err(c.error);
      doc=lateSlip(c.data?c.data.doc:null,w.raw);
    }
    if(w.op==="set")r=await sb.from(t).upsert({id,doc,updated_at:new Date().toISOString()});
    else if(w.op==="update")r=await sb.rpc("doc_update",{tbl:t,doc_id:id,patch:w.data});
    else r=await sb.from(t).delete().eq("id",id);
    if(r.error)throw err(r.error);
    return {ok:true};
  }
  const queue=makeQueue(write,onQueue,()=>{try{return !!role}catch(e){return false}});

  /* local copy of each table, kept live by Realtime; writes show straight away, even offline */
  const cache=new Map(),docSubs=new Map(),colSubs=new Map();
  const pendingFor=path=>lsGet("swim_queue",[]).filter(w=>w.path===path);
  const applyOp=(m,id,w)=>{if(w.op==="del")m.delete(id);else if(w.op==="set")m.set(id,w.data);else m.set(id,merge(m.get(id),w.data))};
  const colDocs=t=>{const m=cache.get(t)||new Map();return [...m.keys()].sort().map(id=>Object.assign({_id:id},m.get(id)))};
  function fire(t,id){
    const m=cache.get(t)||new Map();
    (docSubs.get(t+"/"+id)||[]).forEach(cb=>cb(m.has(id)?m.get(id):null));
    (colSubs.get(t)||[]).forEach(cb=>cb(colDocs(t)));
  }
  function fireAll(t){
    for(const [p,cbs] of docSubs)if(split(p)[0]===t){const m=cache.get(t)||new Map();const id=split(p)[1];cbs.forEach(cb=>cb(m.has(id)?m.get(id):null))}
    (colSubs.get(t)||[]).forEach(cb=>cb(colDocs(t)));
  }
  const watched=()=>{const s=new Set(colSubs.keys());for(const p of docSubs.keys())s.add(split(p)[0]);return [...s].filter(t=>SB_TABLES.includes(t))};
  /* while this device's own save of a record is on its way, its echoes (which can arrive out of order)
     are ignored; once the last save lands, the record is read again */
  const inflight=new Map();
  async function load(t){
    const {data,error}=await sb.from(t).select("id,doc");
    if(error)return;
    const old=cache.get(t)||new Map();
    const m=new Map(data.map(r=>[r.id,r.doc]));
    for(const w of lsGet("swim_queue",[])){const [wt,id]=split(w.path);if(wt===t)applyOp(m,id,w)}
    for(const [p,n] of inflight){const [wt,id]=split(p);if(wt===t&&n>0){if(old.has(id))m.set(id,old.get(id));else m.delete(id)}}
    cache.set(t,m);fireAll(t);
  }
  const loadAll=()=>Promise.all(watched().map(load));
  async function reread(path){
    const [t,id]=split(path);const m=cache.get(t);if(!m||t==="photos")return;
    const r=await sb.from(t).select("doc").eq("id",id).maybeSingle();
    if(r.error||(inflight.get(path)||0)>0)return;
    if(r.data)m.set(id,r.data.doc);else m.delete(id);
    for(const w of pendingFor(path))applyOp(m,id,w);
    fire(t,id);
  }
  /* Swim Opt 2.30 (problem 6): saves of one record go one after another, in the order they were made.
     Before, four fast Place Judge taps were four saves on the road at once, and a slower earlier one
     (3 places) could land after the last one (4 places) and wipe the 4th place. */
  const chains=new Map();
  function send(w){
    local(w);inflight.set(w.path,(inflight.get(w.path)||0)+1);
    const prev=chains.get(w.path)||Promise.resolve();
    const p=prev.catch(()=>{}).then(()=>queue.run(w)).finally(()=>{
      if(chains.get(w.path)===p)chains.delete(w.path);
      const n=inflight.get(w.path)-1;if(n>0)inflight.set(w.path,n);else{inflight.delete(w.path);reread(w.path).catch(()=>{})}});
    chains.set(w.path,p);
    return p;
  }
  function local(w){
    const [t,id]=split(w.path);if(t==="photos")return;
    const m=cache.get(t)||cache.set(t,new Map()).get(t);
    applyOp(m,id,JSON.parse(JSON.stringify(w)));fire(t,id);
  }
  function onChange(p){
    const t=p.table;const m=cache.get(t);if(!m)return;
    const id=p.eventType==="DELETE"?(p.old&&p.old.id):(p.new&&p.new.id);if(id==null)return;
    if((inflight.get(t+"/"+id)||0)>0)return;
    if(p.eventType==="DELETE")m.delete(id);else m.set(id,p.new.doc);
    for(const w of pendingFor(t+"/"+id))applyOp(m,id,w);
    fire(t,id);
  }

  /* one private channel, "carnival": row changes plus presence. Only a device with a job can join. */
  let ch=null,myPres={},peersCb=[],role=null;
  const emitPeers=list=>peersCb.forEach(cb=>cb(list));
  /* Swim Opt 2.30 (problem 26): Supabase closes the channel of a device that sends more than 5 presence
     updates in 30 seconds ("Client presence rate limit exceeded"). The Recorder sent one for every race it
     opened, so its channel was closed about every second race and live updates stopped.
     Now: an update that changes nothing is not sent, at most 4 go in any 30 seconds (a later one waits and
     only the newest is sent), and a closed channel is joined again by itself, then every table is read again
     so nothing missed while it was closed is lost. "up" says whether live updates are on. */
  const PRES_MAX=4,PRES_WIN=30000;let presAt=[],presSent="",presTimer=null,up=false;
  function track(){
    if(!ch||!up)return;
    const body=Object.assign({dev:DEV},myPres),key=JSON.stringify(body);
    if(key===presSent)return;
    const now=Date.now();presAt=presAt.filter(t=>now-t<PRES_WIN);
    if(presAt.length>=PRES_MAX){if(!presTimer)presTimer=setTimeout(()=>{presTimer=null;track()},PRES_WIN-(now-presAt[0])+50);return}
    presAt.push(now);presSent=key;ch.track(body).catch(()=>{presSent=""});
  }
  let rejoinT=null,tries=0;
  const setUp=v=>{if(up!==v){up=v;try{onQueue&&onQueue()}catch(e){}}};
  function rejoinSoon(){
    if(rejoinT||!role)return;
    const wait=Math.min(30000,1000*Math.pow(2,tries++));
    rejoinT=setTimeout(()=>{rejoinT=null;join()},wait);
  }
  async function join(){
    clearTimeout(rejoinT);rejoinT=null;
    const old=ch;ch=null;setUp(false);
    if(old){try{await sb.removeChannel(old)}catch(e){}}
    /* the library hands back a channel of the same name if one is still listed, so none may be left */
    for(const c of sb.getChannels())if(c.topic==="realtime:carnival"){try{await sb.removeChannel(c)}catch(e){}try{c.teardown();sb.realtime._remove(c)}catch(e){}}
    if(!role){emitPeers([]);return}
    if(ch)return; /* another join started while this one waited */
    try{await sb.realtime.setAuth()}catch(e){}
    if(ch)return;
    const me=sb.channel("carnival",{config:{private:true,presence:{key:DEV}}});ch=me;
    for(const t of SB_TABLES)me.on("postgres_changes",{event:"*",schema:"public",table:t},onChange);
    me.on("presence",{event:"sync"},()=>{const st=me.presenceState();emitPeers(Object.values(st).flat().map(p=>{const o=Object.assign({},p);delete o.presence_ref;return o}))});
    try{me.subscribe(st=>{
      if(me!==ch)return;
      if(st==="SUBSCRIBED"){tries=0;setUp(true);presSent="";track();loadAll()}
      else if(st==="CLOSED"||st==="CHANNEL_ERROR"||st==="TIMED_OUT"){setUp(false);rejoinSoon()}
    })}catch(e){rejoinSoon()}
  }
  /* back from no signal, or the page shown again: join at once if live updates are off */
  const wake=()=>{if(role&&!up){tries=0;clearTimeout(rejoinT);rejoinT=null;join()}};
  window.addEventListener("online",wake);
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)wake()});

  await signIn();
  try{const r=await sb.rpc("my_role");role=r.error?null:r.data||null}catch(e){}
  if(role){join();queue.flush()}

  return {
    mode:"supabase",
    get role(){return role},
    onDoc(path,cb){(docSubs.get(path)||docSubs.set(path,[]).get(path)).push(cb);const [t,id]=split(path);
      if(cache.has(t)){const m=cache.get(t);setTimeout(()=>cb(m.has(id)?m.get(id):null))}else if(role)load(t);else setTimeout(()=>cb(null));return()=>{}},
    onCol(col,cb){(colSubs.get(col)||colSubs.set(col,[]).get(col)).push(cb);
      if(cache.has(col))setTimeout(()=>cb(colDocs(col)));else if(role)load(col);else setTimeout(()=>cb([]));return()=>{}},
    async get(path){
      await signIn();const [t,id]=split(path);
      if(t==="photos"){const r=await sb.storage.from("slips").download(id+".jpg");if(r.error){if(String(r.error.statusCode||"")==="404"||/not.?found/i.test(r.error.message||""))return null;throw err(r.error)}return {img:await toUrl(r.data)}}
      const r=await sb.from(t).select("doc").eq("id",id).maybeSingle();
      if(r.error)throw err(r.error);
      return r.data?r.data.doc:null;
    },
    /* opt.raw: the slip's own times, merged with the server's copy when the save goes (see write) */
    set(path,data,opt){const w={op:"set",path,data};if(opt&&opt.raw)w.raw=opt.raw;return send(w)},
    update(path,data){return send({op:"update",path,data})},
    del(path){return send({op:"del",path})},
    async nextRace(){
      await signIn();
      let r;try{r=await withTimeout(sb.rpc("next_race",{dev:DEV}),6000)}catch(e){throw {code:"offline"}}
      if(r.error)throw err(r.error).code==="offline"?{code:"offline"}:{code:"busy"};
      return r.data;
    },
    presence(obj){myPres=Object.assign(myPres,obj);track()},
    /* Swim Opt 2.30: false while the live channel is closed and being joined again */
    get live(){return !role||up},
    onPeers(cb){peersCb.push(cb)},
    hasRoom:true,
    pending:()=>queue.size(),queued:pre=>queue.count(pre),flush:()=>queue.flush(),
    /* PINs are checked on the server; the page never sees the PIN table */
    async claimRole(hash){
      await signIn();const r=await sb.rpc("claim_role",{pin_hash:hash});
      if(r.error)throw err(r.error);
      role=r.data||null;
      if(role){await join();await loadAll();queue.flush()}
      return role;
    },
    async releaseRole(){role=null;await join();try{await sb.rpc("release_role")}catch(e){}},
    /* Swim Opt 2.30 (problem 28): Clear practice data in one server call, then this carnival's slip photos
       (r0001.jpg and so on; a kept year's photos, y2027-..., stay). Photos left by a page closed too soon are
       found and removed by the next clear, as the whole folder is listed, not this device's copy. */
    async clearPractice(runId){
      await signIn();
      const r=await sb.rpc("clear_practice",{run_id:String(runId||"")});
      /* the 2.30 01-setup.sql not run yet: the page clears record by record, as before */
      if(r.error&&String(r.error.code||"")==="PGRST202")return null;
      if(r.error)throw err(r.error);
      const B=sb.storage.from("slips");const names=[];
      for(let off=0;off<20000;off+=1000){const l=await B.list("",{limit:1000,offset:off});if(l.error||!l.data)break;
        for(const f of l.data)if(/^r\d+\.jpg$/.test(f.name))names.push(f.name);if(l.data.length<1000)break}
      for(let i=0;i<names.length;i+=100){const d=await B.remove(names.slice(i,i+100));if(d.error)break}
      return r.data;
    },
    async setYear(y){const r=await sb.rpc("set_year",{y:String(y||"current")});if(r.error)throw err(r.error)},
    async checkPin(job,hash){const r=await sb.rpc("check_pin",{job,pin_hash:hash});if(r.error)throw err(r.error);return !!r.data}
  };
}

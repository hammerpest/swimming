/* ===== Swim Opt 2.31 (decisions 197 to 199, design S1.49 version 3): two carnivals in one year =====
   A year can hold two carnivals, for example 2027 Secondary and 2027 Primary, each with its own students,
   program, races, results and house points. The first carnival's records keep their ids (config/main,
   heats/r0001); the second carnival's start with "b_" (config/b_main, heats/b_r0001, photo b_r0001.jpg).
   carnStore() wraps the store so every screen keeps using plain paths and sees only the carnival open on
   this device. Kept years (years, archive) and the running carnival (config/running) are shared.
   Only one carnival runs at a time. Every job PIN opens the running one; only the Carnival Organiser
   switches it (the morning question, or the button in 1. Carnival details). It never switches by itself. */
const CARN_KEYS=["","b_"];
const CARN_SHARED=["years","archive"];
function carnKey(k){return k==="b_"?"b_":""}
function carnPath(key,path){
  if(!key)return path;
  const i=path.indexOf("/");const t=path.slice(0,i);
  if(CARN_SHARED.includes(t)||path==="config/running")return path;
  return t+"/"+key+path.slice(i+1);
}
function carnOwns(key,id){return key?String(id).startsWith(key):!String(id).startsWith("b_")}
function carnStore(base,key){
  const P=p=>carnPath(key,p);
  const strip=d=>key?Object.assign({},d,{_id:String(d._id).slice(key.length)}):d;
  const w={
    key,raw:base,
    get mode(){return base.mode},get role(){return base.role},get live(){return base.live},get hasRoom(){return base.hasRoom},
    onDoc:(p,cb)=>base.onDoc(P(p),cb),
    onCol:(c,cb)=>base.onCol(c,l=>cb(CARN_SHARED.includes(c)?l:l.filter(d=>carnOwns(key,d._id)).map(strip))),
    get:p=>base.get(P(p)),
    set:(p,d,o)=>base.set(P(p),d,o),
    update:(p,d)=>base.update(P(p),d),
    del:p=>base.del(P(p)),
    nextRace:()=>base.nextRace(key),
    /* "Already selected" and the Recorder lock only count devices on the same carnival */
    presence:o=>base.presence(Object.assign({carn:key},o)),
    onPeers:cb=>base.onPeers(l=>cb(l.filter(p=>carnKey(p&&p.carn)===key))),
    pending:()=>base.pending(),
    queued:pre=>base.queued?base.queued(P(pre)):0,
    flush:()=>base.flush()
  };
  for(const k of ["claimRole","releaseRole","setYear","checkPin","carnivalsReady"])if(base[k])w[k]=(...a)=>base[k](...a);
  if(base.clearPractice)w.clearPractice=runId=>base.clearPractice(runId,key);
  return w;
}

/* ---------- the carnivals on this project ---------- */
/* the first carnival always exists (a new project may not have saved its settings yet) */
function carnCfg(k){return (A.carns&&A.carns[k])||(k===""?(A.carn===""?A.L.cfg||A.cfg:Object.assign({},DEFAULT_CONFIG)):null)}
function twoCarnivals(){return !!(carnCfg("")&&carnCfg("b_"))}
function otherKey(k){return k==="b_"?"":"b_"}
function carnYear(k){const c=carnCfg(k)||{};const m=carnCfg("")||{};return String(c.date||m.date||A.cfg.date||"2027").slice(0,4)}
/* "Change carnival" only when a year has two carnivals; with one, the header keeps "Change year" (and its line breaks) */
function chgLabel(){return twoCarnivals()?"Change carnival":"Change year"}
function levelName(c){return LEVELS[carnLevel(c)].name}
function carnLabel(k){return carnYear(k)+" "+levelName(carnCfg(k)||A.cfg)}
function todayIso(){const d=new Date();return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0")}
function shortDate(iso){const d=new Date(String(iso||"")+"T12:00:00");if(!iso||isNaN(d))return "";return d.toLocaleDateString("en-AU",{weekday:"short",day:"numeric",month:"short"}).replace(",","")}
/* the header title: the open carnival, or the kept year being looked at */
function hdrTitle(){
  if(A.past){const e=pastEntry();return e.year+(e.level?" "+LEVELS[e.level==="primary"?"primary":"secondary"].name:"")}
  return curYear()+(twoCarnivals()?" "+levelName(A.cfg):"");
}
function pastEntry(){
  const y=A.years.find(y=>(y._id||y.year)===A.past)||{};
  const key=carnKey(y.key);
  return {id:A.past,key,year:String(y.year||String(A.past).replace(/^b_/,"")),level:y.level||null};
}
/* a slip photo: the open carnival's, or a kept year's (y2027-r0001.jpg, b_y2027-r0001.jpg) */
function photoGet(id){
  if(!A.past)return A.store.get("photos/"+id);
  const e=pastEntry();
  return (A.store.raw||A.store).get("photos/"+e.key+"y"+e.year+"-"+id);
}

/* ---------- which carnival this device opens ---------- */
/* A job PIN always works on the running carnival: if it changes, or this tab was left on the other one
   by an organiser, the page loads again on the running one. */
function checkCarn(){
  if(A.reloading||!A.runKnown||!A.role||A.role==="org"||A.carn===A.running)return;
  A.reloading=true;ssSet("swim_carn",null);location.reload();
}
function openCarn(k){
  k=carnKey(k);
  ssSet("swim_carn",k);ssSet("swim_year","current");ssSet("swim_job",null);
  if(k===A.carn){enterYear("current");return}
  A.reloading=true;location.reload();
}
/* the morning question: on the other carnival's date, straight after the organiser PIN, once per sign-in */
function morningCheck(){
  if(A.role!=="org"||A.yearPicked||A.modal||A.morningAsked||!A.runKnown||!twoCarnivals())return;
  const o=otherKey(A.running);const c=carnCfg(o);
  if(c&&c.date===todayIso()){A.morningAsked=true;A.modal={t:"makeRunning",key:o,morning:true}}
}

/* ---------- the Which carnival cards ---------- */
function carnCards(){
  const keys=CARN_KEYS.filter(k=>carnCfg(k));
  const live=keys.map(k=>{
    const c=carnCfg(k)||A.cfg;const run=k===A.running;
    const when=c.date?shortDate(c.date):"date not set";
    return `<button type="button" class="tile wide carn${run?" run":""}" style="min-height:0" data-act="year" data-v="${run?"current":"carn"+(k||"a")}"><span class="row" style="justify-content:space-between;width:100%"><b>${esc(carnLabel(k))}</b><span class="chip${run?" final":""}">${run?"Running now":"Not running"}</span></span><span>${esc(c.name||"")} · ${esc(when)}${run?" · live":""}</span></button>`;
  });
  const liveIds=new Set(keys.map(k=>k+carnYear(k)));
  const past=A.years.filter(y=>!liveIds.has((y._id||y.year))).map(y=>{
    const lv=y.level?" "+LEVELS[y.level==="primary"?"primary":"secondary"].name:"";
    return `<button type="button" class="tile wide" style="min-height:0" data-act="year" data-v="${esc(y._id||y.year)}"><span class="row" style="justify-content:space-between;width:100%"><b>${esc(y.year)}${esc(lv)}</b><span class="chip">Look only</span></span><span>${esc(y.name||"")} · ${y.heats||0} races, ${y.students||0} students</span></button>`;
  });
  return {cards:live.join("")+(past.join("")||`<p class="muted" style="margin:0">No past years kept yet. A year is kept when the organiser presses Start a new carnival.</p>`),
    add:!carnCfg("b_")?`<button type="button" class="linkbtn" data-act="addcarn">Add a carnival for ${esc(carnYear(""))} (Primary or Secondary)</button>`:""};
}

/* ---------- the running carnival box in 1. Carnival details ---------- */
function runningBox(){
  if(!twoCarnivals()||A.past)return "";
  const me=carnLabel(A.carn);
  if(A.carn===A.running)return `<div class="msg ok"><b>${esc(me)} is running now.</b> Every job PIN opens it.</div>`;
  return `<div class="msg warn" style="display:flex;flex-direction:column;gap:10px;align-items:flex-start"><span><b>${esc(me)} is not running.</b> Every job PIN opens ${esc(carnLabel(A.running))}. Make ${esc(levelName(A.cfg))} the running carnival on the morning of its carnival.</span><button type="button" class="btn primary" data-act="mkrunask">Make ${esc(me)} the running carnival</button></div>`;
}

const CARN_MODALS={
  makeRunning:M=>{const lb=carnLabel(M.key),lv=levelName(carnCfg(M.key)||A.cfg),cur=carnLabel(otherKey(M.key));
    return `<h2>${M.morning?"Today is the "+esc(lb)+" carnival":"Make "+esc(lb)+" the running carnival?"}</h2><p style="margin:0">${M.morning?"Make it the running carnival? ":""}Every job PIN will then open ${esc(lb)}.</p><p style="margin:0">${esc(cur)} is kept as it is. You can still open it from Which carnival.</p><div class="acts"><button type="button" class="btn" data-act="closemodal">Not yet</button><button type="button" class="btn go" data-act="mkrun" data-v="${M.key||"a"}">Make ${esc(lv)} running</button></div>`},
  addCarn:M=>{const lb=M.year+" "+LEVELS[M.level].name;
    return `<h2>Add a ${esc(lb)} carnival?</h2><p style="margin:0">It gets its own students, program, races, results and house points. The PINs stay the same.</p><p style="margin:0">Every job PIN keeps opening ${esc(carnLabel(A.running))} until you make ${esc(LEVELS[M.level].name)} the running carnival.</p><div class="acts"><button type="button" class="btn" data-act="closemodal">&lt; Back</button><button type="button" class="btn go" data-act="addcarn1">Add ${esc(lb)}</button></div>`}
};
const CARN_ACT={
  mkrunask:()=>{A.modal={t:"makeRunning",key:A.carn};render()},
  mkrun:async el=>{
    const k=carnKey(el.dataset.v==="a"?"":el.dataset.v);
    try{const r=await A.store.raw.set("config/running",{key:k,at:Date.now(),by:DEV});if(r&&r.queued)toast("Saved on this device. Sends when there is signal.")}
    catch(e){toast("Not saved. Check the connection and try again.");return}
    A.running=k;A.modal=null;toast(carnLabel(k)+" is now the running carnival. Every job PIN opens it.");render();
  },
  addcarn:()=>{const m=carnCfg("")||A.cfg;A.modal={t:"addCarn",year:carnYear(""),level:carnLevel(m)==="primary"?"secondary":"primary"};render()},
  addcarn1:async()=>{
    const M=A.modal;if(!M||M.t!=="addCarn")return;
    if(A.store.carnivalsReady&&!(await A.store.carnivalsReady())){A.modal=null;toast("Run the Swim Opt 2.31 supabase/01-setup.sql on the project first.");render();return}
    const m=carnCfg("")||A.cfg;const lb=M.year+" "+LEVELS[M.level].name;
    const cfg=Object.assign({},DEFAULT_CONFIG,{name:M.level==="primary"?"CCAS Primary Swimming Carnival "+M.year:"CCAS Swimming Carnival "+M.year,
      level:M.level,date:"",dateConfirmed:false,ageDate:m.ageDate,pool:m.pool,poolLen:m.poolLen,lanes:m.lanes,runId:newRunId()});
    delete cfg.pins;
    try{await A.store.raw.set("config/b_main",cfg);await A.store.raw.set("counter/b_race",{next:1,at:Date.now()})}
    catch(e){toast("Not saved. Check the connection and try again.");return}
    A.modal=null;toast(lb+" added. It is not running yet.");render();
  }
};

/* Swim Opt 2.30 (problem 7): which slip times go yellow when the two readings are put together.
   Run: node tests/slipmerge.test.js */
const fs=require('fs'),path=require('path'),vm=require('vm');
const ctx={console,URL,Math,Object,Array,JSON,Number,String,Set,Map,Promise};vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'..','js','slip-reader.js'),'utf8')+';this.slipMerge=slipMerge;',ctx);
const a=(x,m)=>{if(!x){console.log('FAIL',m);process.exitCode=1}else console.log('ok',m)};
/* a reading as parseSlip gives it; start 10:00:00.000, each clock agrees with its time unless bad says not */
function R(lanes,unsure,bad){
  const clocks={};for(const l in lanes)clocks[l]=36000000+lanes[l]*10+((bad||[]).includes(+l)?5000:0);
  return {race:5,raceLow:false,lanes,order:Object.keys(lanes).map(Number),problems:[],unsure:unsure||[],missed:[],far:[],clocks,start:36000000,head:true,twoSlips:false,mixed:false};
}
let m=C=>ctx.slipMerge(C[0],C[1]);
// one reading only, and that reading sure of it (clock agrees): no longer yellow
let r=m([R({1:3412,2:3500}),R({1:3412})]);
a(!r.unsure.includes(2)&&r.lanes[2]===3500,'one reading only, sure in it: not yellow');
// one reading only, unsure in it: still yellow
r=m([R({1:3412,2:3500},[2]),R({1:3412})]);
a(r.unsure.includes(2),'one reading only, unsure in it: yellow');
// one reading only, but the other reading has the same time under another lane (lane number misread): yellow
r=m([R({1:3412,3:3500}),R({1:3412,8:3500})]);
a(r.unsure.includes(3)&&r.unsure.includes(8),'a time under two different lanes: both yellow');
// both readings, same time, both unsure but a clock agrees: not yellow
r=m([R({1:3412},[1]),R({1:3412},[1])]);
a(!r.unsure.includes(1),'both unsure, same time, clock agrees: not yellow');
// both readings, same time, both unsure and no clock agrees: yellow
r=m([R({1:3412},[1],[1]),R({1:3412},[1],[1])]);
a(r.unsure.includes(1),'both unsure, no clock agrees: yellow');
// readings differ: always yellow, even when one is sure (every misread in the half-day run)
r=m([R({1:5702},[1],[1]),R({1:3702})]);
a(r.unsure.includes(1),'readings differ: yellow');
// no start clock read: a one-reading lane cannot be sure (parseSlip marks it unsure)
const ns=R({1:3412,2:3500},[2]);ns.start=null;
r=m([ns,R({1:3412})]);
a(r.unsure.includes(2),'no start clock: yellow');

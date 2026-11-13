const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
function element(tag,text){return {tag,textContent:text||'',children:[],value:'',attributes:{},style:{},append(...items){this.children.push(...items);},setAttribute(k,v){this.attributes[k]=v;},replaceChildren(...items){this.children=items;},replaceWith(item){this.replacement=item;},addEventListener(){},showModal(){},close(){},remove(){}};}
const storage=new Map(),entry=element('nav');
const scope={console,Set,Date,localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},node:element,choiceButton:(title,action)=>Object.assign(element('button',title),{onclick:action}),showToast(){},confirm:()=>true,document:{createElement:element,createTextNode:t=>t,querySelector:()=>entry,body:element('body')},navigator:{clipboard:{writeText:async text=>scope.copied=text}},draftDialog:{close(){}},sendMessage(){}};
vm.createContext(scope);vm.runInContext(fs.readFileSync('server/src/main/resources/static/senior-journey.js','utf8'),scope);
storage.set('a1-travel-preferences','{broken');assert.equal(scope.readTravelPreferences(),null);
storage.set('a1-travel-preferences',JSON.stringify({walkMinutes:999,avoidSteps:true}));assert.equal(scope.readTravelPreferences(),null);
storage.set('a1-travel-preferences',JSON.stringify({walkMinutes:20,avoidSteps:true}));assert.equal(scope.readTravelPreferences().walkMinutes,20);
function all(root){return [root,...root.children.filter(x=>typeof x==='object').flatMap(all)];}
function button(root,title){const result=all(root).find(x=>x.tag==='button'&&x.textContent===title);assert(result,title);return result;}
const day={date:'2026-11-03',places:[{id:'a',name:'已游公园'},{id:'b',name:'下一站'},{id:'c',name:'较远景点'}]};
const key='a1-local-journey:d1:'+day.date;
storage.set(key,JSON.stringify({marks:{a:'visited',removed:'visited'},feedback:'想多休息'}));
let panel=scope.journeyNotesPanel({id:'d1',title:'慢游'},day,0);
button(panel,'我累了，看看怎么减少剩余安排').onclick();
assert.equal(JSON.parse(storage.get(key)).marks.c,undefined,'fatigue advice must not mutate records before confirmation');
button(panel,'确认将后续地点标为本次跳过').onclick();
assert.deepEqual(JSON.parse(storage.get(key)).marks,{a:'visited',c:'skip'},'preserve visited and next stop, remove stale marks');
panel=panel.replacement;
(async()=>{await button(panel,'复制自己记录的游览小结').onclick();assert(scope.copied.includes('已游公园'));assert(scope.copied.includes('较远景点'));assert(scope.copied.includes('未提交平台档案'));button(panel,'删除本日的本机记录').onclick();assert.equal(storage.has(key),false);console.log('PASS: preferences, confirmed fatigue adjustment, record summary and deletion');})().catch(e=>{console.error(e);process.exitCode=1;});

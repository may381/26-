// Exercise the real save handler with a pending HTTP response and minimal DOM doubles.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
class Element {
 constructor(tag='div'){this.tagName=tag;this.children=[];this.textContent='';this.style={};}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=[...items];}
 setAttribute(){}
}
const elements=new Map();
function element(selector){if(!elements.has(selector))elements.set(selector,new Element());return elements.get(selector);}
const context={console,Intl,Date,AbortSignal,URLSearchParams,window:{},document:{querySelector:element,createElement:tag=>new Element(tag)},showToast:()=>{},busy:false};
context.document.querySelector('.topbar-title').firstChild={textContent:''};
vm.createContext(context);
vm.runInContext(fs.readFileSync('server/src/main/resources/static/travel-ui.js','utf8'),context);
let finish,requested,renders=0;
context.fetch=(url,options)=>{requested=JSON.parse(options.body);return new Promise(resolve=>{finish=resolve;});};
context.renderDraftDetail=()=>{renders++;};
vm.runInContext("travelDraft={id:'draft-1',title:'合成草案',version:2,days:[{date:'2026-11-02',places:[{id:'B123456'}]}]}",context);
const root=new Element();context.appendDraftEditing(root,0);
function find(node,label){if(node.textContent===label)return node;for(const child of node.children||[]){const found=find(child,label);if(found)return found;}}
const save=find(root,'保存草案');assert.ok(save);
const pending=save.onclick();
assert.equal(context.canEditDraft(),false,'editing must be gated during save');
assert.equal(requested.expectedVersion,2);
context.window.clearTravelDraft();
finish({ok:true,json:async()=>({code:'OK',data:{id:'draft-1',version:3}})});
pending.then(()=>{
 assert.equal(vm.runInContext('travelDraft',context),null,'late save must not restore a cleared draft');
 assert.equal(renders,0);assert.equal(context.canEditDraft(),true);
 console.log('Pending save edit protection and stale response checks passed');
}).catch(error=>{console.error(error);process.exitCode=1;});

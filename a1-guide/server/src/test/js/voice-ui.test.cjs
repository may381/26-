const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('server/src/main/resources/static/voice-ui.js','utf8');
function element(){return {hidden:false,disabled:false,value:'',textContent:'',classList:{add(){},remove(){}},append(){},before(){},setAttribute(){},removeAttribute(){},addEventListener(){}};}
const player={...element(),paused:true,playCount:0,pause(){this.paused=true;},load(){},play(){this.paused=false;this.playCount++;return Promise.resolve();}};
let completeFetch,fetchCount=0;
const context={console,AbortController,AbortSignal,Event,setTimeout,clearTimeout,setInterval,clearInterval,Map,Date,document:{createElement:element,addEventListener(){}},window:{addEventListener(){}},localStorage:{getItem(){return null;},setItem(){}},speechPlayer:player,voiceState:element(),recordButton:element(),recorder:null,micStream:null,recordTimer:null,voiceProcessing:false,busy:false,showToast(){},navigator:{},input:element(),fetch(){fetchCount++;return new Promise(resolve=>completeFetch=()=>resolve({ok:true,json:async()=>({code:'OK',data:{audioUrl:'/api/speech/audio/test'}})}));}};
vm.createContext(context);vm.runInContext(source,context);
(async()=>{
 const long='先去海边走走，坐下休息。'.repeat(500);const chunks=context.speechChunks(long);assert(chunks.length>1);assert(chunks.every(c=>c.length<=220));assert.equal(chunks.join(''),long);
 const rich=context.speechChunks('**海陵岛** [详情](https://example.com) 🌊。请休息。').join('');assert(rich.includes('海陵岛 详情'));assert(!rich.includes('https'));assert(!rich.includes('**'));assert(rich.includes('请休息。'));
 const emojiChunks=context.speechChunks('游'.repeat(219)+'𠀀'+'玩'.repeat(400));assert(emojiChunks.every(c=>!/[\uD800-\uDBFF]$/.test(c)));
 const button=element();const pending=context.speakAnswer('阳江海陵岛，适合慢慢散步。',button);context.stopReading();completeFetch();await pending;assert.equal(player.playCount,0,'cancelled synthesis must never start playback');assert.equal(button.textContent,'听这段');
 const next=context.speakAnswer('下一段朗读。',element());completeFetch();await next;assert.equal(player.playCount,1);vm.runInContext('voicePause.onclick()',context);assert.equal(player.paused,true);await vm.runInContext('voicePause.onclick()',context);assert.equal(player.paused,false);context.stopReading();
 context.window.voicePreference={id:'neural-66'};let voiceA=context.speakAnswer('音色缓存测试。',element());completeFetch();await voiceA;context.stopReading();let before=fetchCount;
 context.window.voicePreference.id='neural-0';let voiceB=context.speakAnswer('音色缓存测试。',element());assert.equal(fetchCount,before+1,'different voices must never reuse the same audio cache entry');completeFetch();await voiceB;context.stopReading();
 console.log('PASS: long speech splitting, text cleanup, Unicode boundaries, cancellation and pause/resume');
})().catch(error=>{console.error(error);process.exitCode=1;});

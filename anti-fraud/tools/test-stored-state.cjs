const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
function load(path){const output={};new Function('exports',ts.transpileModule(fs.readFileSync(path,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(output);return output;}
const {restoreStored}=load('src/services/storedState.ts');
const defaults={name:'演示用户',role:'老人',age:'70',job:'',gender:'',preference:50,largeFont:false,guardians:[]};
assert.deepEqual(restoreStored('anzhi-settings','null',defaults),defaults);
assert.deepEqual(restoreStored('anzhi-settings','{invalid',defaults),defaults);
const partial=restoreStored('anzhi-settings',JSON.stringify({name:'新名字',guardians:[null,{id:'g',name:'家人',relation:'子女',phone:'123',isDefault:true}],largeFont:'yes',preference:999}),defaults);
assert.equal(partial.name,'新名字');assert.equal(partial.largeFont,false);assert.equal(partial.preference,50);assert.equal(partial.guardians.length,1);assert.equal(defaults.name,'演示用户');
const good={id:'demo',type:'测试',summary:'合成内容',user:'演示',evidence:'依据',modality:'文本',level:'low',time:'2026-11-01T00:00:00Z',handled:false,advice:[],logs:[]};
assert.deepEqual(restoreStored('anzhi-alerts',JSON.stringify([good,null,{...good,logs:'bad'},{...good,time:'invalid'}]),[]),[good]);
assert.deepEqual(restoreStored('anzhi-reports',JSON.stringify([{id:'r',type:'测试',start:'2026-11-01',end:'2026-11-01',created:good.time,events:[null]}]),[]),[]);
assert.equal(restoreStored('anzhi-session','"true"',false),false);
assert.equal(restoreStored('anzhi-session','true',false),true);
const storage=load('src/services/browserStorage.ts');
Object.defineProperty(globalThis,'localStorage',{configurable:true,get(){throw new Error('storage blocked');}});
assert.equal(storage.readBrowser('x'),null);assert.equal(storage.writeBrowser('x','v'),false);assert.equal(storage.removeBrowser('x'),false);
delete globalThis.localStorage;
console.log('Stored state corruption, migration, and unavailable-storage checks passed');

'use strict';
window.voicePreference={id:null};
const timbreDialog=node('dialog',null,'voice-timbre-dialog');timbreDialog.setAttribute('aria-label','选择朗读音色');
const timbreHeader=node('header',null,'import-header');const timbreClose=choiceButton('✕',()=>timbreDialog.close());timbreClose.setAttribute('aria-label','关闭音色设置');timbreHeader.append(node('h2','选一个喜欢的声音'),timbreClose);
const timbreList=node('section',null,'timbre-list'),timbreStatus=node('p','正在读取可用音色…','import-note');timbreStatus.setAttribute('role','status');
const timbreStop=choiceButton('停止试听',()=>{voiceStop.click();timbreStatus.textContent='已停止试听';});
timbreDialog.append(timbreHeader,node('p','每种音色使用同一句话、同样语速试听。选好后会记住，下次朗读继续使用。','import-note'),timbreStatus,timbreList,timbreStop);document.body.append(timbreDialog);
const timbrePreviewButtons=new Set();
async function loadTimbres(){
 try{const response=await fetch('/api/speech/voices',{signal:AbortSignal.timeout(10000)});const result=await response.json();if(!response.ok||result.code!=='OK')throw new Error('音色列表未读取成功');
  const voices=result.data.voices||[];let saved=null;try{saved=localStorage.getItem('a1.voiceTimbre');}catch{}window.voicePreference.id=voices.some(v=>v.id===saved)?saved:result.data.defaultVoice;
  timbreList.replaceChildren();
  const refresh=()=>timbreList.querySelectorAll('.timbre-select').forEach(b=>{b.setAttribute('aria-pressed',String(b.dataset.voice===window.voicePreference.id));b.textContent=b.dataset.voice===window.voicePreference.id?'已选用':'选用';});
  for(const voice of voices){const card=node('article',null,'timbre-card'),body=node('div');body.append(node('strong',voice.label),node('p',voice.engine==='LOCAL_NEURAL'?'中文音色 · 本机合成':'兼容音色','import-note'));const actions=node('div',null,'timbre-actions');
   const select=choiceButton('选用',()=>{stopReading(false);window.voicePreference.id=voice.id;try{localStorage.setItem('a1.voiceTimbre',voice.id);}catch{}refresh();timbreStatus.textContent='已选用'+voice.label;});select.className='timbre-select';select.dataset.voice=voice.id;
   const preview=choiceButton('试听',async()=>{select.click();stopReading(false);voiceRate=1;timbreStatus.textContent='正在试听'+voice.label+'，可点击下方停止。';await speakAnswer('你好，我是小颐。我们慢慢走，看看沿途的风景。累了，就找个地方坐下休息。',preview,1,true);});preview.dataset.voiceOriginalText='试听';timbrePreviewButtons.add(preview);actions.append(preview,select);card.append(body,actions);timbreList.append(card);
  }
  refresh();timbreStatus.textContent=voices.some(v=>v.engine==='LOCAL_NEURAL')?'三种中文音色已就绪，点击试听比较。':'当前可用系统备用音色。';
 }catch(e){timbreStatus.textContent=(e.message||'音色列表读取失败')+'，请稍后重新打开。';}
}
function openTimbres(){stopReading(false);timbreDialog.showModal();loadTimbres();}
document.querySelector('.tool-row').append(choiceButton('音色试听',openTimbres));
document.querySelector('#more-menu').append(choiceButton('选择朗读音色',()=>{closeMore();openTimbres();}));
timbreDialog.addEventListener('close',()=>{if(timbrePreviewButtons.has(voiceButton))stopReading(false);});
loadTimbres();

const timbreProgressObserver=new MutationObserver(()=>{if(timbreDialog.open)timbreStatus.textContent=voiceState.textContent;});timbreProgressObserver.observe(voiceState,{childList:true,characterData:true,subtree:true});

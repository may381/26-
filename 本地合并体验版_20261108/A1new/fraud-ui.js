'use strict';
let fraudProgress=null, fraudPollStarted=0, lastFraudReport=null, fraudEpoch=0, lastFraudInput=null;
function fraudStage(title,description,failed=false){if(!fraudProgress||!fraudProgress.isConnected){fraudProgress=el('section',null,'fraud-progress');$('conversation').append(fraudProgress);}fraudProgress.classList.toggle('failed',failed);fraudProgress.setAttribute('role','status');fraudProgress.replaceChildren(el('strong',title),el('p',description));bottom();}
function fraudReportText(result){return ['防诈核对记录（模型辅助判断）','风险：'+(result.assessment==='needs_review'?'信息不足，待核实':({high:'高风险',medium:'需要警惕',low:'暂未发现明显风险'}[result.level]||'待核实')),'类型：'+result.type,'分析：'+result.evidence,'原文证据：',...(result.evidenceItems||[]).map(x=>x.excerpt||''),'建议：',...(result.advice||[]),'模型：'+(result.model||'未提供'),'低风险不代表安全。未执行报警、通知、冻结或转账。'].join('\n');}
facts=function(bubble,result){
 if(validateFraudResult(result))return;
 lastFraudReport=result;const card=el('section',null,'fraud-report risk-'+result.level);const level=result.assessment==='needs_review'?['?','信息不足，暂不能判断']:{high:['!','高风险，先暂停操作'],medium:['!','需要警惕，先核实来源'],low:['✓','暂未发现明显风险']}[result.level];const hero=el('div',null,'fraud-risk-heading');hero.append(el('span',level[0],'fraud-risk-icon'),el('div'));hero.lastChild.append(el('span','防诈核对结果','fraud-eyebrow'),el('h3',level[1]),el('p',result.type||'类型待核实'));card.append(hero);
 const overview=el('div',null,'fraud-overview');for(const [value,label] of [[(result.evidenceItems||[]).length,'原文证据'],[(result.advice||[]).length,'行动建议'],[(result.sources||[]).length,'参考来源']]){const item=el('div');item.append(el('strong',String(value)),el('span',label));overview.append(item);}card.append(overview);
 if(result.assessment==='needs_review')card.append(el('p','信息不足，需要进一步核实；当前结论不能代替官方认定。','fraud-review'));
 card.append(el('h4','为什么这样判断'),el('p',result.evidence||'未提供有效分析依据。','fraud-explanation'));
 const evidence=el('details',null,'fraud-evidence');evidence.open=true;evidence.append(el('summary','原文证据 · '+(result.evidenceItems||[]).length+'条'));for(const item of result.evidenceItems||[]){const quote=el('blockquote',item.excerpt||'未返回可显示的原文');evidence.append(quote);}if(!result.evidenceItems?.length)evidence.append(el('p','接口未返回原文片段，请结合完整内容核对。'));card.append(evidence);
 card.append(el('h4','现在可以怎么做'));const advice=el('ol',null,'fraud-advice');for(const text of result.advice||[])advice.append(el('li',text));if(!advice.children.length)advice.append(el('li','先暂停相关操作，并通过您独立找到的官方渠道核实。'));card.append(advice);
 if(result.modality==='图片'||result.imageObservedText?.length){const observed=el('details',null,'fraud-evidence');observed.append(el('summary','查看图片识别内容'));for(const text of result.imageObservedText||result.evidenceItems?.map(x=>x.excerpt)||[])observed.append(el('p',text));observed.append(el('p','图片识别可能漏字或误读，请对照原图。','subtle'));card.append(observed);}
 const sources=el('details',null,'fraud-evidence');sources.open=!!result.sources?.length;sources.append(el('summary','参考案例与来源 · '+(result.sources||[]).length));for(const source of result.sources||[]){const block=el('article');block.append(el('strong',source.title||'参考案例'));const url=safeWebUrl(source.source||source.url);if(url){const link=el('a','查看来源 ↗');link.href=url;link.target='_blank';link.rel='noopener noreferrer';block.append(link);}else block.append(el('p','未提供外部来源链接','subtle'));sources.append(block);}if(!result.sources?.length)sources.append(el('p','本次没有引用案例，不能视为已完成官方信息核验。'));card.append(sources);
 const actions=el('div',null,'fraud-report-actions');actions.append(control('复制核对记录',async()=>{try{await navigator.clipboard.writeText(fraudReportText(result));status('记录已复制，可自行发给信任的人核对。');}catch{status('无法复制，请手动选择文本。');}}),control('下载记录',()=>{const url=URL.createObjectURL(new Blob([fraudReportText(result)],{type:'text/plain;charset=utf-8'}));const a=el('a');a.href=url;a.download='防诈核对记录.txt';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}),control('补充信息再分析',()=>{document.querySelector('.topics [data-topic="fraud"]').click();const followup=fraudFollowupText(result);$('question').value=followup.text;$('question').dispatchEvent(new Event('input'));$('question').focus();status(followup.tooLong?'原文较长，未自动截断；请粘贴完整待核对内容后再发送。':'已带入原文，请在末尾补充信息后再发送。图片补充分析请重新上传原图。');}),control('打 96110 / 找家里人',()=>fraudHelpSheet(result)));card.append(actions,el('p','模型：'+(result.model||'接口未返回模型名')+' · '+(result.modality||'文本')+'分析','fraud-model'),el('p','低风险不代表安全。此处未执行报警、通知家属、冻结账户或任何资金操作。','fraud-footer'));bubble.append(card);
};
 function fraudHelpSheet(result){
  const d=el('dialog',null,'place-sheet');const head=el('header');head.append(el('h2','需要人帮忙时'));d.append(head);
  const body=el('section');const num=el('p','96110 反诈专线');num.style.cssText='font-size:34px;font-weight:700;margin:6px 0 4px';
  const tip=el('p','这是官方反诈号码。打过去说三件事：我收到了什么、我做到哪一步、请帮我核实。','subtle');
  const dialogText=fraudReportText(result)+'\n\n我目前：（还没转账 / 已经转了____元）\n请帮我核实，并告诉我下一步该怎么做。';
  const pre=el('pre',dialogText,'subtle');pre.style.cssText='white-space:pre-wrap;font-size:13px;line-height:1.7;max-height:220px;overflow:auto;background:#f6f8fa;padding:10px;border-radius:8px';
  const copy=control('复制要说的内容',async()=>{try{await navigator.clipboard.writeText(dialogText);status('已复制：可以发给家里人，或照着念给 96110。');}catch{status('无法复制，请手动选择文字。');}});
  const call=el('a');call.href='tel:96110';call.textContent='拨打 96110';
  call.style.cssText='display:inline-block;margin:8px 0 0;padding:10px 18px;border-radius:8px;background:#2f6f8f;color:#fff;text-decoration:none';
  const close=control('关闭',()=>d.close());
  body.append(num,tip,pre,copy);body.append(call);body.append(close);
  d.append(body);d.addEventListener('close',()=>d.remove(),{once:true});document.body.append(d);d.showModal();
 }
const plainDisplay=display;
display=function(packet){const domain=packet.domainResult;const task=domain?.status;const result=task==='completed'?domain.result:domain;const isFraud=packet.domain==='fraud'||packet.state==='WAIT_RESULT'||['queued','processing','completed','failed','interrupted'].includes(task)||result?.level||domain?.state==='ACCEPTED';if(!isFraud)return plainDisplay(packet);
 if(packet.state==='WAIT_RESULT'&&!domain){pending=false;fraudPollStarted=0;clearTimeout(pollTimer);fraudStage('结果未通过可信校验','自动查询已停止，原任务引用仍保留；可稍后手动查询，不会重复创建任务。',true);const retry=control('手动查询原任务',async()=>{retry.disabled=true;try{display(await api('status',{}));}catch(error){status(error.message+'；自动查询保持停止。');retry.disabled=false;}});fraudProgress.append(retry);status('结果未通过校验，已停止自动查询。');return;}
 if(task==='failed'||task==='interrupted'){fraudPollStarted=0;pending=false;clearTimeout(pollTimer);fraudStage('本次分析未完成',domain.error||'模型未返回有效结论，请核对学校服务连接后重试。',true);const retry=control('补充内容 / 重新分析',()=>{document.querySelector('.topics [data-topic="fraud"]').click();restoreFraudInput();status('已恢复本次原文与图片，请核对后重新发送。当前没有风险结论。');});fraudProgress.append(retry);status('未获得风险结论。');return;}
 if(packet.state==='WAIT_RESULT'||domain?.state==='ACCEPTED'||['queued','processing'].includes(task)){pending=true;if(!fraudPollStarted)fraudPollStarted=Date.now();fraudStage(task==='queued'?'分析任务已排队':'正在分析可疑内容','请求已受理，等待学校模型返回；这不代表已识别出诈骗。');status('正在等待防诈结果，无需重复提交。');schedulePoll();return;}
 if(result&&['high','medium','low'].includes(result.level)){const invalid=validateFraudResult(result);if(invalid){pending=false;fraudPollStarted=0;clearTimeout(pollTimer);fraudStage('结果需要重新核对',invalid+'。未展示风险结论，请重试分析。',true);status('模型结果不完整，不能视为分析成功。');return;}pending=false;clearTimeout(pollTimer);fraudPollStarted=0;fraudProgress?.remove();fraudProgress=null;const bubble=message('已收到防诈分析，请结合原文核对。');facts(bubble,result);status('分析已返回，可查看依据、建议与来源。');bottom();return;}pending=false;fraudStage('未获得完整分析','接口返回缺少可验证的风险结论，请重新核对。',true);
};
schedulePoll=function(){clearTimeout(pollTimer);const epoch=fraudEpoch;pollTimer=setTimeout(async()=>{if(!pending||epoch!==fraudEpoch)return;if(busy){schedulePoll();return;}if(fraudPollStarted&&Date.now()-fraudPollStarted>180000){status('分析等待较久，可手动查询原任务；没有生成风险结论。');fraudStage('仍在等待分析结果','可以稍后查询原任务，无需重复提交。');fraudProgress.append(control('查询原任务',()=>{fraudPollStarted=Date.now();schedulePoll();}));return;}try{const packet=await api('status',{});if(epoch!==fraudEpoch)return;const task=packet.domainResult?.status;if(['queued','processing'].includes(task)){fraudStage(task==='queued'?'分析任务已排队':'学校模型正在处理','已等待 '+Math.floor((Date.now()-fraudPollStarted)/1000)+' 秒 · 未收到分析结论');schedulePoll();return;}display(packet);}catch(error){if(epoch!==fraudEpoch)return;fraudStage('暂时未取得任务结果',error.message,true);fraudProgress.append(control('查询原任务',()=>{fraudPollStarted=Date.now();schedulePoll();}));status('原任务引用已保留，不会重复创建任务。');}},2200);};
const fraudTopic=document.querySelector('.topics [data-topic="fraud"]');fraudTopic.addEventListener('click',()=>{if(document.querySelector('.fraud-input-guide'))return;const guide=el('section',null,'fraud-input-guide');guide.append(el('strong','拿不准的消息，我们一起核对'),el('p','粘贴完整短信、聊天内容，或上传清晰截图。涉及转账、验证码、陌生链接时，先暂停操作。'));const prompts=el('div');for(const text of ['收到退款或理赔通知','有人推荐高收益投资','亲友突然要求转账'])prompts.append(control(text,()=>{$('question').value=text+'。可疑原文：';$('question').focus();}));guide.append(prompts);$('conversation').append(guide);bottom();});
const oldResetFraud=reset;reset=async function(){await oldResetFraud();if(!history.length){fraudEpoch++;clearTimeout(pollTimer);fraudProgress?.remove();fraudProgress=null;fraudPollStarted=0;lastFraudReport=null;lastFraudInput=null;document.querySelectorAll('.fraud-input-guide').forEach(x=>x.remove());}};
window.fraudSubmissionFailure=function(error){if(!error.submissionUncertain)return;pending=true;fraudStage('提交结果尚未确认','保留了原请求标识，请使用原任务重试，避免重复提交。',true);const button=control('重试原请求',async()=>{button.disabled=true;try{display(await api('message',{topic:'fraud',text:'/retry'}));}catch(e){status(e.message);button.disabled=false;}});fraudProgress.append(button);};
// Keep the same toolbar layout; show actions relevant to the selected domain.
const fraudToolbar=el('nav',null,'travel-tools fraud-tools');fraudToolbar.setAttribute('aria-label','防诈工具');fraudToolbar.hidden=true;
fraudToolbar.append(control('上传截图',()=>{if(busy||pending){status('请先等待当前分析结束。');return;}$('file').click();}),control('核对清单',()=>{const d=el('dialog',null,'place-sheet');d.append(el('h2','发送前，一起核对'),control('关闭 ✕',()=>d.close()),el('p','这是通用核对清单，不是对本条信息的分析结论。','subtle'));for(const text of ['保留完整聊天与短信上下文','确认对方身份时，使用自己找到的官方联系方式','涉及转账、验证码或远程控制，先暂停操作','截图尽量清晰，遮住无关的身份证号、银行卡号等隐私']){const label=el('label',null,'fraud-check-item'),box=el('input');box.type='checkbox';label.append(box,el('span',text));d.append(label);}d.addEventListener('close',()=>d.remove(),{once:true});document.body.append(d);d.showModal();}),control('上次核对结果',()=>{if(!lastFraudReport){status('本页尚无完整分析结果，请先提交文字或截图。');return;}[...document.querySelectorAll('.fraud-report')].at(-1)?.scrollIntoView({behavior:'smooth',block:'start'});}));
const travelToolbar=document.querySelector('nav.travel-tools');travelToolbar.after(fraudToolbar);
for(const button of document.querySelectorAll('[data-topic]'))button.addEventListener('click',()=>{fraudToolbar.hidden=topic!=='fraud';travelToolbar.hidden=topic==='fraud';$('question').placeholder=topic==='fraud'?'粘贴可疑原文，或上传聊天截图…':'输入问题，或上传一张图片…';});

// Capture before the composer clears its inputs. Kept in memory only, cleared on reset.
$('composer').addEventListener('submit',()=>{if(topic==='fraud'&&!busy&&!pending)lastFraudInput={text:$('question').value.trim(),image};},true);
function restoreFraudInput(){
 if(!lastFraudInput){$('question').focus();return;}
 $('question').value=lastFraudInput.text;$('question').dispatchEvent(new Event('input'));
 if(lastFraudInput.image){image=lastFraudInput.image;const preview=el('img');preview.src=image;preview.alt='未完成分析的原图';const remove=control('移除 ✕',clearImage);remove.type='button';$('attachment').replaceChildren(preview,el('span','原图已恢复，请核对后发送'),remove);$('attachment').hidden=false;}
 $('question').focus();
}

const recoverFraudTask=control('恢复后台任务',async()=>{
 if(busy){status('请等待当前请求结束后再查询后台任务。');return;}
 clearTimeout(pollTimer);recoverFraudTask.disabled=true;setBusy(true);
 try{const packet=await api('status',{});fraudPollStarted=Date.now();display(packet);}
 catch(error){status(error.message+'；未创建新的分析任务。');}
 finally{setBusy(false);recoverFraudTask.disabled=false;}
});
fraudToolbar.append(recoverFraudTask);

const fraudIntake=control('分步核对',()=>{
 const d=el('dialog',null,'place-sheet fraud-intake');const head=el('header');head.append(el('h2','一起核对这条消息'),control('关闭',()=>d.close()));d.append(head,el('p','先保留原文，再补充已发生的操作。不要填写验证码、完整卡号或身份证号。','subtle'));
 const original=el('textarea');original.maxLength=1500;original.rows=7;original.placeholder='粘贴完整可疑短信、聊天原文；截图请返回后上传。';original.setAttribute('aria-label','可疑原文');
 const action=select([['尚未操作','尚未转账，也未提供敏感信息'],['已转账','已经转账或付款'],['已提供敏感信息','已经提供验证码或账户等信息'],['已开启远程控制','已经开启屏幕共享或远程控制'],['不确定','不确定发生了什么']]);field(d,'可疑原文',original);field(d,'目前情况',action);const note=el('p','','subtle');d.append(note,control('带入对话，核对后发送',()=>{if(!original.value.trim()){note.textContent='请先提供待分析原文。';original.focus();return;}$('question').value='请分析以下可疑原文。\n'+original.value.trim()+'\n\n用户补充的当前情况：'+action.value;lastFraudInput=null;$('question').dispatchEvent(new Event('input'));d.close();$('question').focus();status('内容已带入，请核对并发送；尚未提交分析。');}));d.addEventListener('close',()=>d.remove(),{once:true});document.body.append(d);d.showModal();
});fraudToolbar.prepend(fraudIntake);

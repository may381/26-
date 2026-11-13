'use strict';
function openImageRecognition(){
 const dialog=node('dialog');dialog.setAttribute('aria-label','识别旅游图片');
 const file=node('input');file.type='file';file.accept='image/png,image/jpeg';file.setAttribute('aria-label','选择旅游图片');
 const question=node('textarea');question.maxLength=1000;question.value='请识别这张图片里的文字、标识和景物，说明看不清或不能确认的部分。';question.setAttribute('aria-label','希望了解图片的什么内容');
 const result=node('p');result.setAttribute('role','status');const preview=node('img');preview.alt='待识别图片预览';preview.style.maxWidth='100%';preview.hidden=true;let image='',working=false;
 file.onchange=async()=>{image='';preview.hidden=true;const picked=file.files[0];if(!picked)return;if(!['image/png','image/jpeg'].includes(picked.type)||picked.size>4*1024*1024){result.textContent='请选择4MB以内PNG或JPEG图片。';return;}try{image=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(picked);});preview.src=image;preview.hidden=false;result.textContent='图片尚未上传。请确认不含不必要的个人信息。';}catch{result.textContent='图片读取失败。';}};
 const submit=choiceButton('发送给学校模型识别',async()=>{if(working||!image||!question.value.trim())return;working=true;submit.disabled=true;file.disabled=true;result.textContent='正在请求学校模型识图…';try{const response=await fetch('/api/a1/images/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image,question:question.value.trim()}),signal:AbortSignal.timeout(180000)});const packet=await response.json();if(!response.ok||packet.code!=='OK')throw new Error(packet.message||'图片识别失败');result.textContent=packet.data.text+'\n图片识别不代表已核实现场位置或营业状态。';}catch(e){result.textContent=e.name==='TimeoutError'?'学校模型识图等待超时，未获得结论。':e.message;}finally{working=false;submit.disabled=false;file.disabled=false;}});
 dialog.append(node('h2','识别旅游图片'),choiceButton('关闭',()=>dialog.close()),node('p','可上传路牌、景点照片或攻略截图。图片会发给学校服务器；本功能不保存原图、不打开图中链接。'),file,preview,question,submit,result);
 dialog.addEventListener('close',()=>{image='';preview.removeAttribute('src');dialog.remove();},{once:true});document.body.append(dialog);dialog.showModal();
}
document.querySelector('.tool-row').append(choiceButton('识别图片',openImageRecognition));

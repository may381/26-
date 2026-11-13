import { useVisionAvailability } from "../hooks/useVisionAvailability";
import { useEffect, useRef, useState } from "react";
import { AudioLines, CheckCircle2, ImagePlus, Layers3, Send, X } from "lucide-react";
import { api } from "../services/api";
import { Alert } from "../types";
import { useApp } from "../context/AppContext";
import { AlertDetail, Badge } from "./UI";
import Loader from "./Loader";
import { notifyHighRisk } from "../services/notifications";
import { signalDigitalHuman } from "../services/digitalHuman";

export default function RealMultimodalAnalysis(){
  const {settings,refreshRealAlerts,setToast}=useApp();
  const vision=useVisionAvailability();
  const imageInput=useRef<HTMLInputElement>(null),audioInput=useRef<HTMLInputElement>(null);
  const [text,setText]=useState(''),[image,setImage]=useState<File|null>(null),[audio,setAudio]=useState<File|null>(null);
  const [imageUrl,setImageUrl]=useState(''),[audioUrl,setAudioUrl]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState<Alert|null>(null),[detail,setDetail]=useState(false);
  useEffect(()=>()=>{if(imageUrl)URL.revokeObjectURL(imageUrl);if(audioUrl)URL.revokeObjectURL(audioUrl)},[imageUrl,audioUrl]);
  const count=(text.trim()?1:0)+(image?1:0)+(audio?1:0);
  function chooseImage(file?:File){if(!file)return;if(!vision.available){setError(vision.notice);return;}if(!['image/png','image/jpeg','image/webp'].includes(file.type)){setError('图片仅支持 PNG、JPEG 或 WebP');return}if(file.size>10*1024*1024){setError('图片不能超过10MB');return}if(imageUrl)URL.revokeObjectURL(imageUrl);setImage(file);setImageUrl(URL.createObjectURL(file));setError('');setResult(null)}
  function chooseAudio(file?:File){if(!file)return;if(file.size>20*1024*1024){setError('音频不能超过20MB');return}if(audioUrl)URL.revokeObjectURL(audioUrl);setAudio(file);setAudioUrl(URL.createObjectURL(file));setError('');setResult(null)}
  async function submit(){if(count<2||busy||(image&&!vision.available))return;setBusy(true);setError('');setResult(null);signalDigitalHuman({state:'analyzing'});try{const value=await api.analyzeMultimodal(text.trim(),image,audio,settings);setResult(value);signalDigitalHuman({state:'result',alert:value});void notifyHighRisk(value);await refreshRealAlerts();setToast('多模态联合分析完成，已写入预警中心')}catch(e){setError((e as Error).message);signalDigitalHuman({state:'error'})}finally{setBusy(false)}}
  return <section className="panel real-analysis">
    <div className="panel-heading"><h2><Layers3 size={20}/>真实多模态联合分析</h2><span className="muted">证据提取 + 案例检索 + 风险分析</span></div>
    <p className="muted">任选至少两种输入。系统先分别提取文字、画面和语音证据，再生成一个统一风险结论。</p>
    <label className="field-label">聊天或事件说明<textarea rows={4} maxLength={10000} value={text} onChange={e=>setText(e.target.value)} placeholder="粘贴聊天记录，或者描述图片、语音出现的背景…"/></label>
    <p className="info-box">{vision.notice} <button className="text-button" onClick={vision.refresh}>重新检查</button></p>
    <div className="real-image-grid">
      <button className="real-image-drop" type="button" disabled={!vision.available} onClick={()=>imageInput.current?.click()}>{imageUrl?<img src={imageUrl} alt="联合分析图片预览"/>:<><ImagePlus size={28}/><strong>添加图片证据</strong><small>PNG / JPEG / WebP</small></>}</button>
      <div className="real-image-fields">
        <button className="real-audio-drop" type="button" onClick={()=>audioInput.current?.click()}><AudioLines size={28}/><strong>{audio?.name||'添加音频证据'}</strong><small>最大20MB</small></button>
        {audioUrl&&<audio className="real-audio-player" controls src={audioUrl}/>} 
        <div className="selected-file"><span>已选择 {count}/3 种模态（至少2种）</span>{(image||audio)&&<button className="icon-button" aria-label="清除附件" onClick={()=>{setImage(null);setAudio(null);setImageUrl('');setAudioUrl('')}}><X size={16}/></button>}</div>
        <button className="button" disabled={count<2||busy||!!image&&!vision.available} onClick={submit}><Send size={16}/>开始联合分析</button>
      </div>
    </div>
    <input hidden ref={imageInput} type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>{chooseImage(e.target.files?.[0]);e.target.value=''}}/>
    <input hidden ref={audioInput} type="file" accept="audio/*,.m4a,.webm" onChange={e=>{chooseAudio(e.target.files?.[0]);e.target.value=''}}/>
    {error&&<p role="alert" className="analysis-error">{error}</p>}
    {busy&&<Loader label="正在提取多模态证据、检索案例并融合判断…"/>}
    {result&&<div className="real-result"><div className="flex items-center gap-3"><Badge level={result.level}/><strong>{result.type}</strong><span className="muted">{result.modality}</span></div><p>{result.evidence}</p><h3>联合证据</h3>{result.evidenceItems?.map(item=><blockquote key={item.id}>「{item.excerpt}」</blockquote>)}<h3>防御建议</h3><ul>{result.advice.map(item=><li key={item}>{item}</li>)}</ul><p className="green"><CheckCircle2 size={16}/>统一结论已保存到预警中心</p><button className="button secondary" onClick={()=>setDetail(true)}>查看完整详情</button></div>}
    {detail&&result&&<AlertDetail alert={result} onClose={()=>setDetail(false)}/>} 
  </section>
}

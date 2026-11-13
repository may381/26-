import { useVisionAvailability } from "../hooks/useVisionAvailability";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Film, Send, X } from "lucide-react";
import { api } from "../services/api";
import { Alert } from "../types";
import { useApp } from "../context/AppContext";
import { AlertDetail, Badge } from "./UI";
import Loader from "./Loader";
import { notifyHighRisk } from "../services/notifications";
import { signalDigitalHuman } from "../services/digitalHuman";

const allowed = new Set(["video/mp4","video/webm","video/quicktime","video/x-matroska"]);

export default function RealVideoAnalysis(){
  const {settings,refreshRealAlerts,setToast}=useApp();
  const vision=useVisionAvailability();
  const input=useRef<HTMLInputElement>(null);
  const [file,setFile]=useState<File|null>(null);
  const [preview,setPreview]=useState("");
  const [note,setNote]=useState("");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [result,setResult]=useState<Alert|null>(null);
  const [detail,setDetail]=useState(false);
  useEffect(()=>()=>{if(preview)URL.revokeObjectURL(preview)},[preview]);
  function choose(next?:File){
    if(!next)return;
    const ext=next.name.split(".").pop()?.toLowerCase();
    if(!allowed.has(next.type)&&!['mp4','webm','mov','mkv'].includes(ext||''))return setError('视频仅支持 MP4、WebM、MOV 或 MKV');
    if(next.size>100*1024*1024)return setError('视频不能超过100MB');
    if(preview)URL.revokeObjectURL(preview);
    setFile(next);setPreview(URL.createObjectURL(next));setResult(null);setError('');
  }
  async function submit(){
    if(!file||busy||!vision.available)return;setBusy(true);setError('');setResult(null);signalDigitalHuman({state:'analyzing'});
    try{const alert=await api.analyzeVideo(file,note.trim(),settings);setResult(alert);signalDigitalHuman({state:'result',alert});void notifyHighRisk(alert);await refreshRealAlerts();setToast('视频关键帧与音轨分析完成，已写入预警中心');}
    catch(e){setError((e as Error).message);signalDigitalHuman({state:'error'})}finally{setBusy(false)}
  }
  return <section className="panel real-analysis real-video-analysis">
    <div className="panel-heading"><h2>真实视频分析</h2><span className="muted">PyAV关键帧 + Whisper音轨 + 学校模型（视觉未验证）</span></div>
    <p className="muted">抽取最多6个代表画面，并在视频包含清晰人声时转写音轨。原视频分析后立即删除，不进行AI深伪鉴定。</p>
    <p className="info-box">{vision.notice} <button className="text-button" onClick={vision.refresh}>重新检查</button></p>
    <div className="real-image-grid">
      <button className="real-image-drop video-drop" type="button" onClick={()=>input.current?.click()} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();choose(e.dataTransfer.files[0])}}>
        {preview?<video src={preview} controls preload="metadata"/>:<><Film size={34}/><strong>点击或拖入视频</strong><small>MP4 / WebM / MOV / MKV，最大100MB，最长10分钟</small></>}
      </button>
      <div className="real-image-fields">
        <label className="field-label">补充说明（可选）<textarea rows={4} maxLength={1000} value={note} onChange={e=>setNote(e.target.value)} placeholder="例如：陌生网友发来的视频投资邀请"/></label>
        {file&&<div className="selected-file"><span>{file.name} · {(file.size/1024/1024).toFixed(2)}MB</span><button className="icon-button" aria-label="移除视频" onClick={()=>{setFile(null);setPreview('');setResult(null)}}><X size={16}/></button></div>}
        <button className="button" disabled={!file||busy||!vision.available} onClick={submit}><Send size={16}/>开始视频分析</button>
      </div>
    </div>
    <input hidden ref={input} type="file" accept="video/mp4,video/webm,video/quicktime,.mkv" onChange={e=>{choose(e.target.files?.[0]);e.target.value=''}}/>
    {error&&<p role="alert" className="analysis-error">{error}</p>}
    {busy&&<Loader label="正在抽取关键帧、转写可用音轨并融合判断，视频分析可能需要数分钟…"/>}
    {result&&<div className="real-result">
      <div className="flex items-center gap-3"><Badge level={result.level}/><strong>{result.type}</strong></div>
      <p>{result.evidence}</p>
      <h3>关键帧</h3><p className="muted">已分析时间点：{result.videoFrameTimes?.map(value=>`${value.toFixed(1)}s`).join('、')||'已提取代表画面'}</p>
      <h3>画面文字与线索</h3>{result.imageObservedText?.length?result.imageObservedText.map((value,index)=><blockquote key={`${value}-${index}`}>「{value}」</blockquote>):<p className="muted">画面中没有提取到清晰文字。</p>}
      <h3>音轨转写</h3><p>{result.transcript||'视频没有可识别的清晰人声，结论来自关键帧。'}</p>
      <h3>防御建议</h3><ul>{result.advice.map(value=><li key={value}>{value}</li>)}</ul>
      <p className="audio-boundary">AI生成痕迹：未鉴定。当前结果只判断诈骗风险，不判断视频或声音是否由AI合成。</p>
      <p className="green"><CheckCircle2 size={16}/> 已保存到预警中心</p>
      <button className="button secondary" onClick={()=>setDetail(true)}>查看预警详情</button>
    </div>}
    {detail&&result&&<AlertDetail alert={result} onClose={()=>setDetail(false)}/>} 
  </section>
}

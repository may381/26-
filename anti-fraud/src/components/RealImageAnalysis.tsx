import { useVisionAvailability } from "../hooks/useVisionAvailability";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ImagePlus, Send, X } from "lucide-react";
import { api } from "../services/api";
import { Alert } from "../types";
import { useApp } from "../context/AppContext";
import { AlertDetail, Badge } from "./UI";
import Loader from "./Loader";
import { notifyHighRisk } from "../services/notifications";
import { signalDigitalHuman } from "../services/digitalHuman";

const allowed = new Set(["image/png", "image/jpeg", "image/webp"]);

export default function RealImageAnalysis() {
  const { settings, refreshRealAlerts, setToast } = useApp();
  const vision=useVisionAvailability();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Alert | null>(null);
  const [detail, setDetail] = useState(false);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  function choose(next?: File) {
    if (!next) return;
    if (!allowed.has(next.type)) return setError("仅支持 PNG、JPEG 或 WebP 图片");
    if (next.size > 10 * 1024 * 1024) return setError("图片不能超过 10MB");
    if (preview) URL.revokeObjectURL(preview);
    setFile(next); setPreview(URL.createObjectURL(next)); setError(""); setResult(null);
  }

  function asDataUrl(value: File) {
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error("读取图片失败"));
      reader.readAsDataURL(value);
    });
  }

  async function submit() {
    if (!file || busy || !vision.available) return;
    setBusy(true); setError(""); setResult(null); signalDigitalHuman({state:"analyzing"});
    try {
      const alert = await api.analyzeImage(await asDataUrl(file), note.trim(), settings);
      setResult(alert); signalDigitalHuman({state:"result",alert}); void notifyHighRisk(alert); await refreshRealAlerts(); setToast("图片分析完成，已写入预警中心");
    } catch (e) { setError((e as Error).message); signalDigitalHuman({state:"error"}); }
    finally { setBusy(false); }
  }

  return <section className="panel real-analysis real-image-analysis">
    <div className="panel-heading"><h2>真实图片分析</h2><span className="muted">本机多模态模型</span></div>
    <p className="muted">上传聊天截图、投资海报或可疑二维码页面。图片发给当前配置的模型分析，不保存原文件。</p>
    <p className="info-box">{vision.notice} <button className="text-button" onClick={vision.refresh}>重新检查</button></p>
    <div className="real-image-grid">
      <button className="real-image-drop" type="button" onClick={() => inputRef.current?.click()}
        onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); choose(e.dataTransfer.files[0]); }}>
        {preview ? <img src={preview} alt="待分析图片预览"/> : <><ImagePlus size={32}/><strong>点击或拖入图片</strong><small>PNG / JPEG / WebP，最大 10MB</small></>}
      </button>
      <div className="real-image-fields">
        <label className="field-label">补充说明（可选）<textarea rows={5} maxLength={2000} value={note} onChange={e=>setNote(e.target.value)} placeholder="例如：陌生人发来的投资群截图"/></label>
        {file && <div className="selected-file"><span>{file.name} · {(file.size/1024/1024).toFixed(2)}MB</span><button className="icon-button" onClick={()=>{setFile(null);setPreview("");}} aria-label="移除图片"><X size={16}/></button></div>}
        <button className="button" disabled={!file || busy || !vision.available} onClick={submit}><Send size={16}/>开始真实图片分析</button>
      </div>
    </div>
    <input hidden ref={inputRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>{choose(e.target.files?.[0]);e.target.value="";}}/>
    {error && <p role="alert" className="analysis-error">{error}</p>}
    {busy && <Loader label="正在读取图片文字并判断诈骗风险…"/>}
    {result && <div className="real-result">
      <div className="flex items-center gap-3"><Badge level={result.level}/><strong>{result.type}</strong></div>
      <p>{result.evidence}</p>
      <h3>图片识别文字</h3>{result.evidenceItems?.length ? result.evidenceItems.map(e=><blockquote key={e.id}>「{e.excerpt}」</blockquote>) : <p className="muted">图片中没有提取到清晰文字。</p>}
      <h3>防御建议</h3><ul>{result.advice.map(a=><li key={a}>{a}</li>)}</ul>
      <p className="green"><CheckCircle2 size={16}/> 已保存到预警中心</p>
      <button className="button secondary" onClick={()=>setDetail(true)}>查看预警详情</button>
    </div>}
    {detail && result && <AlertDetail alert={result} onClose={()=>setDetail(false)}/>} 
  </section>;
}

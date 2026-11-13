import { useEffect, useRef, useState } from "react";
import { AudioLines, CheckCircle2, CircleStop, Mic, Send, X } from "lucide-react";
import { api } from "../services/api";
import { Alert } from "../types";
import { useApp } from "../context/AppContext";
import { AlertDetail, Badge } from "./UI";
import Loader from "./Loader";
import { notifyHighRisk } from "../services/notifications";
import { signalDigitalHuman } from "../services/digitalHuman";

const allowed = new Set(["audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3", "audio/mp4", "audio/x-m4a", "audio/aac", "audio/ogg", "audio/webm", "video/webm"]);

function clock(seconds = 0) {
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2,"0")}:${String(Math.floor(seconds % 60)).padStart(2,"0")}`;
}

export default function RealAudioAnalysis() {
  const { settings, refreshRealAlerts, setToast } = useApp();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Alert | null>(null);
  const [detail, setDetail] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const recordTimer = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
    clearInterval(recordTimer.current);
    stream.current?.getTracks().forEach(track => track.stop());
  }, [preview]);

  async function toggleRecording() {
    if (recording) {
      recorder.current?.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("当前浏览器不支持录音，请改为上传音频文件");
      return;
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({audio:true});
      stream.current = media;
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
      const instance = new MediaRecorder(media,{mimeType:mime});
      const chunks:BlobPart[]=[];
      instance.ondataavailable = event => { if(event.data.size) chunks.push(event.data); };
      instance.onstop = () => {
        const blob = new Blob(chunks,{type:"audio/webm"});
        choose(new File([blob],`浏览器录音-${new Date().toISOString().replace(/[:.]/g,"-")}.webm`,{type:"audio/webm"}));
        media.getTracks().forEach(track=>track.stop());
        stream.current=null; setRecording(false); clearInterval(recordTimer.current);
      };
      instance.start(500); recorder.current=instance; setRecordSeconds(0); setRecording(true); setError("");
      recordTimer.current=setInterval(()=>setRecordSeconds(value=>{
        if(value>=299){instance.stop();return 300;} return value+1;
      }),1000);
    } catch {
      setError("无法使用麦克风，请在浏览器地址栏允许麦克风权限");
    }
  }

  function choose(next?: File) {
    if (!next) return;
    if (!allowed.has(next.type)) return setError("仅支持 WAV、MP3、M4A、AAC、OGG 或 WebM 音频");
    if (next.size > 20 * 1024 * 1024) return setError("音频不能超过 20MB");
    if (preview) URL.revokeObjectURL(preview);
    setFile(next); setPreview(URL.createObjectURL(next)); setError(""); setResult(null);
  }

  async function submit() {
    if (!file || busy) return;
    setBusy(true); setError(""); setResult(null); signalDigitalHuman({state:"analyzing"});
    try {
      const alert = await api.analyzeAudio(file, note.trim(), settings);
      setResult(alert); signalDigitalHuman({state:"result",alert}); void notifyHighRisk(alert); await refreshRealAlerts(); setToast("语音转写与风险分析完成，已写入预警中心");
    } catch (e) { setError((e as Error).message); signalDigitalHuman({state:"error"}); }
    finally { setBusy(false); }
  }

  return <section className="panel real-analysis real-audio-analysis">
    <div className="panel-heading"><h2>真实语音分析</h2><span className="muted">Faster-Whisper + 本地风险模型</span></div>
    <p className="muted">音频在本机转写并分析诈骗话术，原文件分析后立即删除。当前不对声音是否由 AI 合成作确定判断。</p>
    <div className="record-controls">
      <button className={`button secondary ${recording?'recording':''}`} type="button" disabled={busy} onClick={toggleRecording}>
        {recording?<CircleStop size={17}/>:<Mic size={17}/>} {recording?`停止录音 · ${clock(recordSeconds)}`:"使用麦克风录音"}
      </button>
      <small className="muted">最多5分钟；录音只在停止后提交，本页面不会后台监听。</small>
    </div>
    <div className="real-audio-grid">
      <button className="real-audio-drop" type="button" onClick={() => inputRef.current?.click()}
        onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); choose(e.dataTransfer.files[0]); }}>
        <AudioLines size={34}/><strong>{file ? file.name : "点击或拖入音频"}</strong>
        <small>{file ? `${(file.size/1024/1024).toFixed(2)} MB` : "WAV / MP3 / M4A / AAC / OGG / WebM，最大20MB"}</small>
      </button>
      <div className="real-image-fields">
        {preview && <audio className="real-audio-player" controls src={preview}/>} 
        <label className="field-label">补充说明（可选）<textarea rows={3} maxLength={500} value={note} onChange={e=>setNote(e.target.value)} placeholder="例如：陌生号码发来的语音消息"/></label>
        <div className="real-analysis-actions">
          {file && <button className="icon-button" onClick={()=>{setFile(null);setPreview("");setResult(null);}} aria-label="移除音频"><X size={16}/></button>}
          <button className="button" disabled={!file || busy} onClick={submit}><Send size={16}/>转写并分析</button>
        </div>
      </div>
    </div>
    <input hidden ref={inputRef} type="file" accept="audio/wav,audio/mpeg,audio/mp4,audio/aac,audio/ogg,audio/webm,.m4a,.mp3,.wav"
      onChange={e=>{choose(e.target.files?.[0]);e.target.value="";}}/>
    {error && <p role="alert" className="analysis-error">{error}</p>}
    {busy && <Loader label="正在本机转写语音并分析诈骗话术，首次使用需要加载模型…"/>}
    {result && <div className="real-result">
      <div className="flex items-center gap-3"><Badge level={result.level}/><strong>{result.type}</strong><span className="muted">{result.audioDuration?.toFixed(1)} 秒</span></div>
      <p>{result.evidence}</p>
      <h3>语音转写</h3>
      <div className="transcript-list">{result.audioSegments?.map(item=><blockquote key={item.id}><time>{clock(item.start)}–{clock(item.end)}</time>「{item.excerpt}」</blockquote>)}</div>
      <h3>防御建议</h3><ul>{result.advice.map(a=><li key={a}>{a}</li>)}</ul>
      <p className="audio-boundary">声音真伪：未鉴定。当前结论基于语音内容，不代表声音一定为真人或 AI 合成。</p>
      <p className="green"><CheckCircle2 size={16}/> 已保存到预警中心</p>
      <button className="button secondary" onClick={()=>setDetail(true)}>查看预警详情</button>
    </div>}
    {detail && result && <AlertDetail alert={result} onClose={()=>setDetail(false)}/>} 
  </section>;
}

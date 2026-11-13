import { readBrowser, writeBrowser, removeBrowser } from "../services/browserStorage";
import { restoreSubmission, submissionFingerprint, type SubmissionIdentity } from "../services/submissionIdentity";
import { safeSourceUrl } from "../services/sourceUrl";
import { useEffect, useRef, useState } from "react";
import { Send, RefreshCw, CheckCircle2, History } from "lucide-react";
import { api, ApiError } from "../services/api";
import { useApp } from "../context/AppContext";
import { Alert } from "../types";
import { AlertDetail, Badge } from "./UI";
import Loader from "./Loader";
import { notifyHighRisk } from "../services/notifications";
import { signalDigitalHuman } from "../services/digitalHuman";

export default function RealTextAnalysis({template}: {template?:{id:string;text:string}|null}) {
  const {settings, alerts, refreshRealAlerts} = useApp();
  const [text, setText] = useState("");
  const [health, setHealth] = useState<Awaited<ReturnType<typeof api.health>> | null>(null);
  const [error, setError] = useState("");
  const [job, setJob] = useState(() => readBrowser("anzhi-active-text-job") || "");
  const submissionRef = useRef<SubmissionIdentity|null>(restoreSubmission(readBrowser("anzhi-pending-text-submit")));
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState("");
  const [paused, setPaused] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [result, setResult] = useState<Alert|null>(null);
  const [detail, setDetail] = useState(false);
  const seenTemplate = useRef<string>();
  useEffect(() => {
    if (!template || seenTemplate.current === template.id) return;
    seenTemplate.current = template.id;
    if (job || submitting) { setError('当前分析仍在处理，未替换输入。请完成原任务后重新选择案例。'); return; }
    if (text.trim() && text !== template.text && !window.confirm('使用教学案例替换当前输入？案例不会自动提交。')) return;
    setText(template.text); setError('');
  }, [template, job, submitting, text]);
  async function check() {
    try { setHealth(await api.health()); setError(""); }
    catch (e) { setHealth(null); setError((e as Error).message); }
  }
  useEffect(() => { void check(); }, []);
  useEffect(() => {
    if (!job) { setElapsed(0); return; }
    const started=Date.now();
    const timer=setInterval(() => setElapsed(Math.floor((Date.now()-started)/1000)),1000);
    return () => clearInterval(timer);
  }, [job]);
  useEffect(() => {
    if (!job || paused) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const task = await api.task(job);
        if (cancelled) return;
        setError("");
        setStatus(task.status);
        if (!["queued", "processing", "completed", "failed", "interrupted"].includes(task.status)
            || task.status === "completed" && !task.result) {
          setPaused(true); setError("任务响应无效，已暂停查询并保留原任务，请检查后端后恢复查询。"); return;
        }
        if (task.status === "completed" && task.result) {
          setResult(task.result); setJob(""); removeBrowser("anzhi-active-text-job");
          signalDigitalHuman({state:"result", alert:task.result});
          void notifyHighRisk(task.result);
          void refreshRealAlerts().catch(() => setError("分析已完成并保存，但预警列表刷新失败，请刷新页面核对；无需重复提交。"));
        } else if (["failed","interrupted"].includes(task.status)) {
          signalDigitalHuman({state:"error"});
          setError(task.error || "分析未完成"); setJob(""); removeBrowser("anzhi-active-text-job");
        } else timer = setTimeout(poll, 1200);
      } catch (e) {
        if (!cancelled) {
          if (e instanceof ApiError && e.status === 404) {
            setError("原任务不存在，请重新提交文本"); setJob(""); removeBrowser("anzhi-active-text-job");
          } else { setError((e as Error).message + "；保留任务并自动重连"); timer = setTimeout(poll, 4000); }
        }
      }
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [job, paused, refreshRealAlerts]);
  async function submit() {
    if (!text.trim() || submitting || job) return;
    setSubmitting(true); setError(""); setResult(null);
    try {
      const fingerprint = await submissionFingerprint([text.trim(), settings.name, settings.role, settings.age, settings.job, settings.preference]);
      if (submissionRef.current && submissionRef.current.fingerprint !== fingerprint
          && !window.confirm("上次提交的受理结果尚未确认。建议先用原内容重试以找回同一任务。现在改为提交另一份内容吗？这不会取消原任务。")) return;
      if (submissionRef.current?.fingerprint !== fingerprint) submissionRef.current = {fingerprint, key:crypto.randomUUID()};
      writeBrowser("anzhi-pending-text-submit",JSON.stringify(submissionRef.current));
      signalDigitalHuman({state:"analyzing"});
      const r = await api.submit(text.trim(), settings, submissionRef.current!.key);
      if (typeof r.analysis_id !== 'string' || !/^real-[A-Za-z0-9-]{1,120}$/.test(r.analysis_id)) throw new Error("受理响应缺少有效任务标识，请保留相同内容重试。");
      writeBrowser("anzhi-active-text-job", r.analysis_id);
      setStatus("queued"); setPaused(false); setJob(r.analysis_id); submissionRef.current=null;
      removeBrowser("anzhi-pending-text-submit");
    } catch(e) { setError((e as Error).message); signalDigitalHuman({state:"error"}); }
    finally { setSubmitting(false); }
  }
  return <section className="panel real-analysis">
    <div className="panel-heading"><h2>真实文本分析</h2><button className="text-button" onClick={check}><RefreshCw size={16}/>检查连接</button></div>
    <p className="muted">文字将提交给当前配置的模型，结合反诈知识库分析；近期风险记录只作辅助，不是本次判断证据。请勿输入密码、验证码或完整银行卡号。</p>
    <div className="info-box">{health ? (health.model_ready ? "模型服务可访问：" + health.model + "（实际生成结果仍需校验）" : health.model_configured ? health.provider === "school" ? "学校模型当前不可达，请连接校园网络并检查服务器服务" : "本机模型不可用：" + health.model + "；请检查 Ollama 与模型安装" : "后端已连接，但模型配置不完整") : "正在检查本地后端…"}<br/>{health?.embedding_ready?`RAG 已就绪：${health.embedding_model} · ${health.knowledge_chunk_count} 个知识块 · 语义向量与关键词混合检索`:'RAG 向量模型未就绪，当前自动使用关键词检索。'}</div>
    {submissionRef.current && !job && <p className="info-box">有一份提交的受理结果尚未确认。请使用原内容和相同用户设置重试，系统会复用提交标识；不会额外缓存原文。</p>}
    <label className="field-label">待分析内容<textarea value={text} maxLength={10000} disabled={!!job || submitting} onChange={e=>setText(e.target.value)} placeholder="粘贴可疑聊天或短信，例如：保证每天收益，先转入保证金……" rows={6}/></label>
    <div className="real-analysis-actions"><span className="muted">{text.length}/10000</span><button className="button" disabled={!health?.model_ready || !text.trim() || !!job || submitting} onClick={submit}><Send size={16}/>提交真实分析</button></div>
    {error && <p role="alert" className="analysis-error">{error}</p>}
    {(job || submitting) && !paused && <Loader label={status === "queued" ? "任务已保存，等待分析…" : "正在检索案例并调用真实模型…"}/>}
    {job && <div className="info-box"><p>任务：{job} · 本次页面已等待 {elapsed} 秒。{elapsed >= 60 && "模型可能仍在排队或计算，请保留原任务，不要重复提交。"}</p><button className="text-button" onClick={() => setPaused(value => !value)}>{paused ? "恢复查询原任务" : "暂停查询"}</button><small>暂停仅停止页面轮询，后台任务继续；刷新后会恢复查询。</small></div>}
    {result && <div className="real-result">
      <div className="flex items-center gap-3"><Badge level={result.level}/><strong>{result.type}</strong><span>{result.assessment === "needs_review" ? "需要进一步核实" : ""}</span></div>
      <p>{result.evidence}</p>
      <p className="info-box">{result.assessment === 'needs_review' ? '资料或分析仍需核实，请先保留原始记录，避免把当前结论当作定论。' : '这是模型辅助判断，低风险不代表安全，也不代表已经核实收款方身份。'} 未执行转账、报警或家属通知。</p>
      <h3>输入证据</h3>{result.evidenceItems?.map(e=><blockquote key={e.id}>「{e.excerpt}」</blockquote>)}
      <h3>引用案例</h3>{result.sources?.length ? result.sources.map(s=><article key={s.id}>{safeSourceUrl(s.source) ? <a href={safeSourceUrl(s.source)} target="_blank" rel="noreferrer">{s.title} ↗</a> : <strong>{s.title}</strong>}<p className="muted">{s.content}</p></article>) : <p className="muted">未引用相关案例，本结果没有案例检索支撑。</p>}
      <h3>防御建议</h3><ul>{result.advice.map(a=><li key={a}>{a}</li>)}</ul>
      <p className="green"><CheckCircle2 size={16}/> 已保存到后端数据库和预警中心</p>
      <button className="button secondary" onClick={()=>setDetail(true)}>查看预警详情</button>
    </div>}
    {detail && result && <AlertDetail alert={result} onClose={()=>setDetail(false)}/>}
    <div className="analysis-history">
      <div className="panel-heading"><h3><History size={17}/>最近分析</h3><span className="muted">自动保留在本机</span></div>
      {alerts.filter(a=>a.origin==='backend').slice(0,5).map(item=><button key={item.id} onClick={()=>{setResult(item);setDetail(true)}}>
        <span><Badge level={item.level}/><strong>{item.type}</strong></span><small>{new Date(item.time).toLocaleString('zh-CN')} · {item.modality}</small><p>{item.summary}</p>
      </button>)}
      {!alerts.some(a=>a.origin==='backend')&&<p className="muted">完成第一次真实分析后，记录会显示在这里。</p>}
    </div>
  </section>;
}

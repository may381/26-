import { csvCell } from "../services/csv";
import { useEffect, useState } from 'react';
import { Activity, CheckCircle2, Download, FileText, FlaskConical, Play, XCircle } from 'lucide-react';
import { Heading, Badge } from '../components/UI';
import { api, EvaluationCase, EvaluationRun } from '../services/api';
import { useApp } from '../context/AppContext';

const percent = (value:number) => `${(value*100).toFixed(1)}%`;

export default function Evaluation(){
  const {settings,setToast} = useApp();
  const [cases,setCases] = useState<EvaluationCase[]>([]);
  const [health,setHealth] = useState<Awaited<ReturnType<typeof api.health>>|null>(null);
  const [run,setRun] = useState<EvaluationRun|null>(null);
  const [busy,setBusy] = useState(false);
  const [split,setSplit] = useState('all');
  const [ablation,setAblation] = useState('full');
  useEffect(()=>{ void Promise.all([api.evaluationCases(),api.health()]).then(([list,state])=>{setCases(list);setHealth(state)}).catch(e=>setToast((e as Error).message)); },[setToast]);
  useEffect(()=>{
    if(!run || !['running','queued'].includes(run.status)) return;
    const timer=setTimeout(()=>void api.evaluation(run.evaluation_id).then(setRun).catch(e=>setToast((e as Error).message)),1000);
    return()=>clearTimeout(timer);
  },[run,setToast]);
  async function start(mode:'rules'|'model'){
    setBusy(true);
    try { const created=await api.startEvaluation(mode,settings,split,ablation); setRun(await api.evaluation(created.evaluation_id)); }
    catch(e){setToast((e as Error).message)} finally {setBusy(false)}
  }
  function download(){
    if(!run?.result)return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(run.result,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`安知评测结果-${run.mode}.json`;a.click();URL.revokeObjectURL(url);
  }
  function downloadCsv(){
    if(!run?.result)return;
    const quote=csvCell;
    const rows=[['编号','模态','真实标签','诈骗类型','预测标签','预测类型','是否正确','耗时ms','评测范围','转写文本','错误'],...run.result.items.map(item=>[item.id,item.modality,item.label,item.type,item.prediction,item.predicted_type,item.correct?'是':'否',item.latency_ms,item.evaluation_scope,item.transcript,item.error])];
    const url=URL.createObjectURL(new Blob(['\ufeff'+rows.map(row=>row.map(quote).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}));
    const a=document.createElement('a');a.href=url;a.download=`安知逐条评测-${run.mode}.csv`;a.click();URL.revokeObjectURL(url);
  }
  function report(){
    if(!run?.result)return;
    const result=run.result, metrics=result.metrics;
    const esc=(value:unknown)=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]||char));
    const lines=result.items.map(item=>`<tr><td>${esc(item.id)}</td><td>${esc(item.modality)}</td><td>${esc(item.label)}</td><td>${esc(item.prediction)}</td><td>${esc(item.predicted_type)}</td><td>${item.correct?'正确':'错误'}</td><td>${item.latency_ms}</td><td>${esc(item.error)}</td></tr>`).join('');
    const win=window.open('','_blank'); if(!win)return setToast('浏览器阻止了报告窗口，请允许弹窗后重试');
    win.document.write(`<!doctype html><meta charset="utf-8"><title>安知评估报告</title><style>body{font:14px/1.6 Arial,"Microsoft YaHei";max-width:1100px;margin:40px auto;color:#172033}h1{color:#172554}section{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:24px 0}.card{border:1px solid #ccd5e1;border-radius:8px;padding:14px}.card strong{display:block;font-size:22px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{border:1px solid #ccd5e1;padding:7px;text-align:left}th{background:#eff6ff}@media print{button{display:none}}</style><h1>安知多模态反诈智能助手评估报告</h1><p>生成时间：${new Date().toLocaleString()}　模式：${esc(run.mode)}　模型：${esc(result.model)}</p><p>测试集：${result.dataset.total} 例（黑样本 ${result.dataset.fraud}，白样本 ${result.dataset.normal}，诈骗类型 ${result.dataset.fraud_types} 种）</p><section><div class="card">准确率<strong>${percent(metrics.accuracy)}</strong></div><div class="card">Precision<strong>${percent(metrics.precision)}</strong></div><div class="card">Recall<strong>${percent(metrics.recall)}</strong></div><div class="card">F1-score<strong>${percent(metrics.f1)}</strong></div><div class="card">误报率<strong>${percent(metrics.false_positive_rate)}</strong></div><div class="card">平均响应<strong>${metrics.average_latency_ms} ms</strong></div><div class="card">完成<strong>${metrics.completed}/${metrics.total}</strong></div><div class="card">失败<strong>${metrics.failed}</strong></div></section><button onclick="print()">打印 / 导出 PDF</button><h2>逐条结果</h2><table><thead><tr><th>编号</th><th>模态</th><th>真实标签</th><th>预测</th><th>预测类型</th><th>结果</th><th>耗时ms</th><th>错误</th></tr></thead><tbody>${lines}</tbody></table>`); win.document.close();
  }
  function downloadCases(){
    const url=URL.createObjectURL(new Blob([JSON.stringify(cases,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='安知标准测试集-20例.json';a.click();URL.revokeObjectURL(url);
  }
  const m=run?.result?.metrics;
  return <>
    <Heading eyebrow="MODEL EVALUATION" title="测评中心" description="用固定测试集验证识别质量，让每个指标都有原始记录。" action={<span className="model-chip"><FlaskConical size={16}/>{cases.length} 条标准样本</span>}/>
    <section className="panel eval-overview">
      <div><h2>标准多模态测试集</h2><p>黑样本 10 条，覆盖 10 种诈骗类型；白样本 10 条，黑白比例 1:1。包含 12 条文本、4 张图片和 4 段音频。真实模型模式会运行文本模型、图片视觉模型以及 Faster-Whisper 音频转写。</p></div>
      <div className="eval-actions">
        <select aria-label="测试集分层" value={split} onChange={e=>setSplit(e.target.value)}><option value="all">全部 20 例</option><option value="development">开发集 12 例</option><option value="validation">验证集 4 例</option><option value="blind">盲测集 4 例</option></select>
        <select aria-label="消融配置" value={ablation} onChange={e=>setAblation(e.target.value)}><option value="full">完整系统</option><option value="no_rag">关闭 RAG</option><option value="no_profile">关闭画像</option></select>
        <button className="button secondary" onClick={downloadCases}><Download size={16}/>导出测试集</button>
        <button className="button secondary" disabled={busy||run?.status==='running'} onClick={()=>start('rules')}><Play size={16}/>运行规则基线</button>
        <button className="button" disabled={busy||run?.status==='running'||!health?.model_ready} onClick={()=>start('model')}><Activity size={16}/>运行真实模型评测</button>
      </div>
      {!health?.model_ready&&<p className="muted">学校模型当前不可用，请检查校园网络与服务；可以先运行规则基线检查评测流程。</p>}
      {run?.status==='running'&&<div className="eval-progress"><span>正在评测：{run.progress}%</span><div className="progress-track"><span style={{width:`${run.progress}%`}}/></div></div>}
      {run?.status==='failed'&&<p className="analysis-error">{run.error}</p>}
    </section>
    <section className="system-status panel">
      <div><i className="ready"/><span>FastAPI 后端</span><strong>{health?'正常':'未连接'}</strong></div>
      <div><i className={health?.database_ready?'ready':''}/><span>SQLite 数据库</span><strong>{health?.database_ready?`正常 · ${health.alert_count} 条预警`:'不可用'}</strong></div>
      <div><i className={health?.model_ready?'ready':'waiting'}/><span>Ollama 模型</span><strong>{health?.model_ready?`${health.model} 已就绪`:`${health?.model||'模型'} 下载中`}</strong></div>
      <div><i className="ready"/><span>知识库</span><strong>{health?`${health.case_count} 官方 + ${health.knowledge_count} 自建`:'检查中'}</strong></div>
    </section>
    {m&&<>
      <div className="eval-metrics">
        {[['准确率',m.accuracy],['Precision',m.precision],['Recall',m.recall],['F1-score',m.f1],['误报率',m.false_positive_rate],['类型准确率',m.type_accuracy]].map(([name,value])=><article className="panel" key={String(name)}><span>{name}</span><strong>{percent(value as number)}</strong></article>)}
      </div>
      <section className="panel eval-result-head"><div><h2>{run?.result?.model}</h2><p>TP {m.tp} · TN {m.tn} · FP {m.fp} · FN {m.fn} · 完成 {m.completed}/{m.total} · 失败 {m.failed} · 平均响应 {m.average_latency_ms} ms</p></div><div className="eval-actions"><button className="button secondary" onClick={download}><Download size={16}/>JSON</button><button className="button secondary" onClick={downloadCsv}><Download size={16}/>CSV</button><button className="button secondary" onClick={report}><FileText size={16}/>评估报告</button></div></section>
      <section className="panel modality-metrics"><div className="panel-heading"><h2>分模态指标</h2><span className="muted">文本、图片和音频分别统计</span></div><div className="modality-grid">{(['text','image','audio'] as const).map(key=>{const item=run?.result?.modality_metrics[key];if(!item)return null;return <article key={key}><strong>{key==='text'?'文本':key==='image'?'图片':'音频'}</strong><span>准确率 {percent(item.accuracy)}</span><span>F1 {percent(item.f1)}</span><span>平均 {item.average_latency_ms} ms</span><span>失败 {item.failed}</span></article>})}</div></section>
    </>}
    <section className="panel eval-table">
      <div className="panel-heading"><h2>逐条结果</h2><span className="muted">{run?.result?'已完成':'等待运行'}</span></div>
      <div className="eval-row eval-head"><span>样本</span><span>真实标签</span><span>预测</span><span>结果</span></div>
      {cases.map(item=>{const result=run?.result?.items.find(x=>x.id===item.id);return <div className="eval-row" key={item.id}><div className="eval-sample"><strong>{item.id} · {item.type} <em>{item.modality}</em></strong>{item.modality==='image'&&item.asset_url&&<img src={item.asset_url} alt={`${item.id}测评图片`}/>} {item.modality==='audio'&&item.asset_url&&<audio controls preload="none" src={item.asset_url}/>}<p>{item.text}</p>{result?.transcript&&<p>实际转写：{result.transcript}</p>}{result?.error&&<p className="eval-wrong">{result.error}</p>}</div><span>{item.label==='fraud'?<Badge level="high"/>:<Badge level="low"/>}</span><span>{result?(result.prediction==='error'?`失败 · ${result.predicted_type}`:`${result.prediction==='fraud'?'风险':'正常'} · ${result.predicted_type}`):'—'}</span><span className={result?.correct?'green':'eval-wrong'}>{result?(result.correct?<><CheckCircle2 size={16}/>正确</>:<><XCircle size={16}/>{result.prediction==='error'?'失败':'错误'}</>):'—'}</span></div>})}
    </section>
  </>;
}

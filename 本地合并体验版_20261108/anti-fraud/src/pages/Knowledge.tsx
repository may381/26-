import { useRef, useState, useEffect } from "react";
import {
  Database,
  Upload,
  RefreshCw,
  CheckCircle2,
  FileText,
  Search,
  Pencil,
  Trash2,
  TestTube2,
  ArchiveRestore,
  GitBranch,
} from "lucide-react";
import { useApp } from "../context/AppContext";
import { fraudTypes, today } from "../data/mockData";
import { Heading, Modal, Empty } from "../components/UI";
import Loader from "../components/Loader";
import { api, KnowledgeCase, KnowledgeMatch, KnowledgeStats, KnowledgeVersion } from "../services/api";
export default function Knowledge() {
  const { knowledge, setKnowledge, updates, setUpdates, setToast } = useApp();
  const [text, setText] = useState("");
  const [type, setType] = useState(fraudTypes[0]);
  const [progress, setProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const [fileName, setFileName] = useState("");
  const [serverStats, setServerStats] = useState<KnowledgeStats|null>(null);
  const [cases,setCases]=useState<KnowledgeCase[]>([]);
  const [search,setSearch]=useState('');
  const [editing,setEditing]=useState<KnowledgeCase|null>(null);
  const [testQuery,setTestQuery]=useState('');
  const [matches,setMatches]=useState<KnowledgeMatch[]>([]);
  const [retrievalMethod,setRetrievalMethod]=useState('');
  const [indexing,setIndexing]=useState(false);
  const [versions,setVersions]=useState<KnowledgeVersion[]>([]);
  const [versionName,setVersionName]=useState('');
  const file = useRef<HTMLInputElement>(null);
  const timer = useRef<ReturnType<typeof setInterval>>();
  useEffect(() => {
    void refresh();
    return () => clearInterval(timer.current);
  }, []);
  async function refresh(){
    const [stats,list,snapshots]=await Promise.all([api.knowledge(),api.knowledgeCases(search),api.knowledgeVersions()]);
    setServerStats(stats);setCases(list);setVersions(snapshots);
  }
  async function rebuildIndex(){
    setIndexing(true);
    try {
      const result=await api.reindexKnowledge();
      await refresh();
      setToast(`向量索引已完成：${result.documents} 篇文档、${result.chunks} 个知识块`);
    } catch(e) { setToast((e as Error).message); }
    finally { setIndexing(false); }
  }
  async function load(f?: File) {
    if (!f) return;
    if (!/\.(txt|json|csv)$/i.test(f.name) || f.size > 2 * 1024 * 1024) {
      setToast("请上传不超过 2 MB 的 .txt、.json 或 .csv 文件");
      return;
    }
    try {
      const content = await f.text();
      if (f.name.endsWith(".json")) JSON.parse(content);
      setText(content);
      setFileName(f.name);
      setToast("案例文件已读取，请确认内容后入库");
    } catch {
      setToast("文件读取失败或 JSON 格式不正确");
    }
  }
  function ingest() {
    if (!text.trim()) {
      setToast("请先粘贴案例或上传文件");
      return;
    }
    setBusy(true);
    setProgress(0);
    let p = 0;
    timer.current = setInterval(() => {
      p += 20;
      setProgress(p);
      if (p >= 80) {
        clearInterval(timer.current);
        void api.ingestKnowledge(type, text.trim(), fileName || '手动粘贴').then(async (result) => {
          setProgress(100);
          setKnowledge((ks) => ks.map((k) => k.type === type ? { ...k, count: k.count + 1, updated: today } : k));
          setUpdates((ls) => [`${new Date().toLocaleString("zh-CN")} · ${type} · 已清洗并保存 ${result.characters} 字`, ...ls]);
          setServerStats(await api.knowledge());
          setCases(await api.knowledgeCases());
          setText(""); setFileName("");
          setToast("案例正文已清洗并保存到本地知识库");
        }).catch(e => { setProgress(0); setToast((e as Error).message); }).finally(() => setBusy(false));
      }
    }, 350);
  }
  return (
    <>
      <Heading
        eyebrow="CONTINUOUS LEARNING"
        title="知识库进化"
        description="让每一个新案例，成为下一次识别的经验。"
        action={
          <span className="model-chip">
            <Database size={16} />
            {serverStats ? `${serverStats.official_count} 个官方案例 · ${serverStats.user_count} 个自建案例` : `${knowledge.length} 类场景`}
          </span>
        }
      />
      <div className="knowledge-grid">
        <section className="panel knowledge-table">
          <div className="panel-heading">
            <h2>反诈知识库</h2>
            <span className="muted text-xs">SQLite 本地持久化 · 语义向量与关键词混合检索</span>
          </div>
          <div className="knowledge-row knowledge-head">
            <span>诈骗类型 / 关键词</span>
            <span>案例数</span>
            <span>最后更新</span>
          </div>
          {knowledge.map((k) => (
            <div className="knowledge-row" key={k.id}>
              <div>
                <strong>{k.type}</strong>
                <small>{k.keywords}</small>
              </div>
              <span>{serverStats?.groups.find(g=>g.fraud_type===k.type)?.count ?? 0} 个自建</span>
              <time>{serverStats?.groups.find(g=>g.fraud_type===k.type)?.updated?.slice(0,10) || '—'}</time>
            </div>
          ))}
        </section>
        <div className="space-y-5">
          <section className="panel form-panel">
            <h2>
              <Upload size={20} />
              上传新案例
            </h2>
            <p className="muted">支持文本及文件导入，正文会清洗、去重并保存到本机 SQLite。</p>
            <label className="field-label">
              诈骗类型
              <select
                value={type}
                disabled={busy}
                onChange={(e) => setType(e.target.value)}
              >
                {fraudTypes.map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <textarea
              aria-label="案例内容"
              className="case-text"
              disabled={busy}
              placeholder="粘贴案例内容，包含诈骗话术、过程与风险特征…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <button
              disabled={busy}
              className="upload-zone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (!busy) load(e.dataTransfer.files[0]);
              }}
              onClick={() => file.current?.click()}
            >
              <FileText size={24} />
              <strong>{fileName || "点击或拖拽文件到这里"}</strong>
              <small>.txt / .json / .csv · 最大 2 MB</small>
            </button>
            <input
              hidden
              type="file"
              ref={file}
              accept=".txt,.json,.csv"
              onChange={(e) => {
                load(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            {busy && <Loader label="正在清洗案例并写入本地知识库…" />}
            {progress > 0 && (
              <div className="ingest-progress">
                <span>
                  {progress === 100
                    ? "清洗与入库完成"
                    : "正在清洗、去重并持久化…"}{" "}
                  {progress}%
                </span>
                <div className="progress-track">
                  <span style={{ width: `${progress}%` }} />
                </div>
              </div>
            )}
            <button
              className="button w-full justify-center mt-4"
              disabled={busy || !text.trim()}
              onClick={ingest}
            >
              {!busy && <RefreshCw size={16} />}
              {busy ? "正在处理…" : "清洗并入库"}
            </button>
          </section>
          <section className="panel update-panel">
            <h2>更新日志</h2>
            <div className="timeline">
              {updates.slice(0, 6).map((u, i) => (
                <div key={`${u}${i}`}>
                  <CheckCircle2 size={16} />
                  <p>{u}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
      <section className="panel knowledge-manager">
        <div className="panel-heading"><div><h2>自建案例管理</h2><p className="muted">查看、搜索、编辑或删除已经保存的案例正文。</p></div><div className="knowledge-search"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')void refresh()}} placeholder="搜索正文或文件名"/><button onClick={()=>void refresh()}>搜索</button></div></div>
        {cases.length?cases.map(item=><article className="knowledge-case" key={item.id}><div><span>{item.fraud_type} · {item.review_status==='approved'?'已启用':'已停用'}</span><strong>{item.source_name}</strong><small>{new Date(item.created).toLocaleString('zh-CN')}</small><p>{item.content}</p></div><div><button className="icon-button" title={item.review_status==='approved'?'停用并移出检索':'启用并建立索引'} aria-label="切换案例状态" onClick={()=>void api.reviewKnowledge(item.id,item.review_status==='approved'?'disabled':'approved').then(()=>{setToast(item.review_status==='approved'?'案例已停用':'案例已启用');return refresh()}).catch(e=>setToast((e as Error).message))}><CheckCircle2 size={16}/></button><button className="icon-button" aria-label="编辑案例" onClick={()=>setEditing(item)}><Pencil size={16}/></button><button className="icon-button" aria-label="删除案例" onClick={()=>{if(confirm('确定删除这条自建案例吗？'))void api.deleteKnowledge(item.id).then(()=>{setToast('案例已删除');return refresh()}).catch(e=>setToast((e as Error).message))}}><Trash2 size={16}/></button></div></article>):<Empty text="暂无自建案例，可在上方上传第一条案例"/>}
      </section>
      <section className="panel retrieval-test">
        <div className="panel-heading"><div><h2><TestTube2 size={19}/>RAG 检索测试</h2><p className="muted">输入自然语言，验证语义检索是否找到含义相近的案例。</p></div><button className="button secondary" disabled={indexing || !serverStats?.embedding_ready} onClick={()=>void rebuildIndex()}><RefreshCw size={16} className={indexing?'spin':''}/>{indexing?'正在生成向量…':'重建向量索引'}</button></div>
        <div className="ingest-progress"><span>向量模型：{serverStats?.embedding_model || '检测中'} · {serverStats?.embedding_ready?'已就绪':'未就绪'} · {serverStats?.chunk_count || 0} 个知识块 / {serverStats?.indexed_document_count || 0} 篇文档</span></div>
        <div className="retrieval-input"><input value={testQuery} onChange={e=>setTestQuery(e.target.value)} placeholder="例如：先做任务交钱，结束后给奖励"/><button className="button secondary" disabled={!testQuery.trim()} onClick={()=>void api.retrieveKnowledge(testQuery).then(r=>{setMatches(r.items);setRetrievalMethod(r.method)}).catch(e=>setToast((e as Error).message))}>测试检索</button></div>
        {retrievalMethod&&<p className="muted text-xs">本次方式：{retrievalMethod}</p>}
        <div className="retrieval-results">{matches.map(item=><article key={item.id}><strong>{item.title}{item.score!==null&&<small> · 综合相似度 {(item.score*100).toFixed(1)}%</small>}</strong><p>{item.content}</p>{item.source&&<small>来源：{item.source}</small>}</article>)}{testQuery&&matches.length===0&&<p className="muted">尚未运行，或没有匹配案例。</p>}</div>
      </section>
      <section className="panel knowledge-manager">
        <div className="panel-heading"><div><h2><GitBranch size={19}/>知识版本与回滚</h2><p className="muted">为当前自建案例创建完整快照。发布用于标记当前基线；恢复会用快照覆盖现有自建案例并重建索引。</p></div></div>
        <div className="retrieval-input"><input value={versionName} maxLength={80} onChange={e=>setVersionName(e.target.value)} placeholder="版本名称，例如：校园诈骗案例 V2"/><button className="button secondary" disabled={!versionName.trim()} onClick={()=>void api.createKnowledgeVersion(versionName.trim()).then(()=>{setVersionName('');setToast('知识版本快照已创建');return refresh()}).catch(e=>setToast((e as Error).message))}>创建快照</button></div>
        <div className="version-list">{versions.map(item=><article className="knowledge-case" key={item.id}><div><span>{item.status==='active'?'当前版本':item.status==='draft'?'草稿':'历史版本'}</span><strong>{item.name}</strong><small>{item.case_count} 条自建案例 · {new Date(item.created).toLocaleString('zh-CN')}</small></div><div>{item.status!=='active'&&<button className="button secondary" onClick={()=>void api.publishKnowledgeVersion(item.id).then(()=>{setToast('已标记为当前知识版本');return refresh()}).catch(e=>setToast((e as Error).message))}>发布</button>}<button className="button secondary" onClick={()=>{if(confirm('恢复后会覆盖当前自建案例，是否继续？'))void api.restoreKnowledgeVersion(item.id).then(()=>{setToast('知识版本已恢复并重建索引');return refresh()}).catch(e=>setToast((e as Error).message))}}><ArchiveRestore size={15}/>恢复</button></div></article>)}{!versions.length&&<p className="muted">尚未创建知识版本快照。</p>}</div>
      </section>
      {editing&&<Modal title="编辑自建案例" onClose={()=>setEditing(null)}><div className="form-grid"><label>诈骗类型<select value={editing.fraud_type} onChange={e=>setEditing({...editing,fraud_type:e.target.value})}>{fraudTypes.map(x=><option key={x}>{x}</option>)}</select></label><label className="col-span-full">案例正文<textarea rows={10} value={editing.content} onChange={e=>setEditing({...editing,content:e.target.value})}/></label></div><div className="modal-actions"><button className="button secondary" onClick={()=>setEditing(null)}>取消</button><button className="button" onClick={()=>void api.updateKnowledge(editing.id,editing.fraud_type,editing.content).then(()=>{setEditing(null);setToast('案例已更新');return refresh()}).catch(e=>setToast((e as Error).message))}>保存修改</button></div></Modal>}
    </>
  );
}

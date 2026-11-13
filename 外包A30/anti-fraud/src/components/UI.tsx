import { safeSourceUrl } from "../services/sourceUrl";
import { analysisSummary } from "../services/analysisSummary";
import { ReactNode, useEffect, useRef, useState } from "react";
import { X, ShieldCheck, ArrowUpRight } from "lucide-react";
import { Risk, Alert } from "../types";
import { useApp } from "../context/AppContext";
export const riskLabels = { low: "低风险", medium: "中风险", high: "高风险" };
export function Badge({ level }: { level: Risk }) {
  return (
    <span className={`badge ${level}`}>
      <i />
      {riskLabels[level]}
    </span>
  );
}
export function Heading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const old = document.activeElement as HTMLElement;
    ref.current?.focus();
    const fn = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeRef.current();
      if (e.key === "Tab") {
        const els = ref.current?.querySelectorAll<HTMLElement>(
          'button,input,select,textarea,[tabindex="0"]',
        );
        if (!els?.length) return;
        const first = els[0],
          last = els[els.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", fn);
    return () => {
      document.removeEventListener("keydown", fn);
      old?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={ref}
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭" onClick={onClose}>
            <X size={20} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}
export function AlertDetail({
  alert,
  onClose,
}: {
  alert: Alert;
  onClose: () => void;
}) {
  const { notify, handle, disposition } = useApp();
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [copyStatus, setCopyStatus] = useState('');
  return (
    <Modal title="风险事件详情" onClose={onClose}>
      <div className="flex items-center gap-3">
        <Badge level={alert.level} />
        <strong>{alert.type}</strong>
        <span className="muted">
          {new Date(alert.time).toLocaleString("zh-CN")}
        </span>
      </div>
      <h3>对话与输入内容</h3>
      <div className="quote">{alert.summary}</div>
      <h3>多模态分析 · {alert.modality}</h3>
      <p>{alert.evidence}</p>
      <p className="muted">
        {alert.origin === "backend" ? "真实模型分析 · 未提供校准概率" : `模拟置信度 ${alert.confidence}%`} · 用户：{alert.user}
      </p>
      {alert.origin === "backend" && <><h3>引用案例与输入证据</h3>
        {alert.evidenceItems?.map(e => <p className="quote" key={e.id}>{e.excerpt}</p>)}
        {alert.sources?.length ? alert.sources.map(s => <p key={s.id}>{safeSourceUrl(s.source) ? <a href={safeSourceUrl(s.source)} target="_blank" rel="noreferrer">{s.title} ↗</a> : <span>{s.title} · 来源：{s.source || "未登记"}</span>}</p>) : <p className="muted">未引用相关案例</p>}
        <p className="muted">模型：{alert.model} · 检索依据以本次引用为准</p></>}
      <h3>防御建议</h3>
      <button className="button secondary" onClick={() => { setSummaryOpen(value => !value); setCopyStatus(''); }}>核对与复制摘要</button>
      {summaryOpen && <div className="info-box">
        <textarea aria-label="待分享的反诈摘要" rows={10} readOnly value={analysisSummary(alert)} style={{width:'100%'}} />
        <button className="button secondary" onClick={async () => {
          try { await navigator.clipboard.writeText(analysisSummary(alert)); setCopyStatus('已复制，请核对个人信息后自行分享。'); }
          catch { setCopyStatus('浏览器无法复制，请选中上方摘要手动复制。'); }
        }}>复制已核对摘要</button><p role="status">{copyStatus}</p>
      </div>}
      <ul className="advice">
        {alert.advice.map((x) => (
          <li key={x}>
            <ShieldCheck size={17} />
            {x}
          </li>
        ))}
      </ul>
      <h3>监护人联动与处置记录</h3>
      {alert.logs.length ? (
        alert.logs.map((x, i) => (
          <p className="log" key={i}>
            {x}
          </p>
        ))
      ) : (
        <p className="muted">暂无联动或处置记录</p>
      )}
      <h3>监护人处置</h3>
      <div className="guardian-disposition">
        <button className={alert.disposition==='viewed'?'selected':''} onClick={()=>disposition(alert.id,'viewed')}>已查看</button>
        <button className={alert.disposition==='safe'?'selected':''} onClick={()=>disposition(alert.id,'safe')}>确认安全</button>
        <button className={alert.disposition==='help'?'selected danger':''} onClick={()=>disposition(alert.id,'help')}>需要帮助</button>
      </div>
      <div className="modal-actions">
        <button
          className="button secondary"
          disabled={alert.handled}
          onClick={() => handle([alert.id])}
        >
          {alert.handled ? "已处理" : "标记已处理"}
        </button>
        <button className="button" onClick={() => notify(alert.id)}>
          通知监护人
          <ArrowUpRight size={16} />
        </button>
      </div>
    </Modal>
  );
}
export function Empty({ text = "暂无记录" }: { text?: string }) {
  return (
    <div className="empty">
      <ShieldCheck size={34} />
      <p>{text}</p>
    </div>
  );
}

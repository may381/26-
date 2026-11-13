import { useEffect, useState } from "react";
import {
  Plus,
  FileText,
  Download,
  Printer,
  ArrowLeft,
  ArrowUpRight,
  CalendarDays,
} from "lucide-react";
import { useApp } from "../context/AppContext";
import { Heading, Modal, Empty } from "../components/UI";
import { TrendChart, Distribution } from "../components/Charts";
import { today } from "../data/mockData";
import { Report } from "../types";
import { api } from "../services/api";
const weekAgo = () => {
  const d = new Date();
  d.setDate(d.getDate() - 6);
  return d.toISOString().slice(0, 10);
};
export default function Reports({ autoOpen = false }: { autoOpen?: boolean }) {
  const { alerts, reports, setReports, setToast, settings } = useApp();
  const [config, setConfig] = useState(autoOpen);
  const [active, setActive] = useState<Report | null>(null);
  const [start, setStart] = useState(weekAgo());
  const [end, setEnd] = useState(today);
  const [type, setType] = useState("综合安全报告");
  useEffect(()=>{void api.reports().then(items=>{if(items.length)setReports(items)}).catch(()=>{})},[setReports]);
  const inRange = (r: Report) => r.events ??
    alerts.filter(
      (a) => a.time.slice(0, 10) >= r.start && a.time.slice(0, 10) <= r.end,
    );
  async function generate() {
    if (!start || !end || start > end) {
      setToast("请选择有效时间范围，结束时间不能早于开始时间");
      return;
    }
    try {
      const r=await api.createReport(start,end,type,settings.name);
      setReports((rs) => [r, ...rs.filter(item=>item.id!==r.id)]);
      setActive(r); setConfig(false); setToast("安全监测报告已生成并保存到后端");
    } catch(e) { setToast((e as Error).message); }
  }
  const events = active ? inRange(active) : [];
  const dates = Array.from(
    new Set(events.map((a) => a.time.slice(0, 10))),
  ).sort();
  const trend = dates.map((date) => ({
    date: date.slice(5),
    high: events.filter((a) => a.time.startsWith(date) && a.level === "high")
      .length,
    medium: events.filter(
      (a) => a.time.startsWith(date) && a.level === "medium",
    ).length,
  }));
  const types = Array.from(new Set(events.map((a) => a.type))).map((name) => ({
    name,
    value: events.filter((a) => a.type === name).length,
  }));
  function download() {
    if (!active) return;
    const content = JSON.stringify(
      {
        title: active.type,
        user: settings.name,
        period: { start: active.start, end: active.end },
        generated: active.created,
        disclaimer: "本报告包含本地演示与后端模型事件，按事件origin区分；不代表已达到测评指标",
        summary: {
          total: events.length,
          high: events.filter((a) => a.level === "high").length,
        },
        events,
      },
      null,
      2,
    );
    const url = URL.createObjectURL(
      new Blob([content], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `安知安全报告-${active.end}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setToast("报告已导出为 JSON，可使用打印保存为 PDF");
  }
  return (
    <>
      <Heading
        eyebrow="SECURITY INSIGHTS"
        title={active ? "安全监测报告" : "安全报告"}
        description={
          active
            ? `${active.start} 至 ${active.end} · ${settings.name} · ${active.type}`
            : "用清晰的数据，记录每一次安心守护。"
        }
        action={
          <div className="flex gap-2">
            {active ? (
              <>
                <button className="button secondary" onClick={download}>
                  <Download size={16} />
                  导出
                </button>
                <button className="button" onClick={() => window.print()}>
                  <Printer size={16} />
                  打印 / PDF
                </button>
              </>
            ) : (
              <button className="button" onClick={() => setConfig(true)}>
                <Plus size={17} />
                生成新报告
              </button>
            )}
          </div>
        }
      />
      {active ? (
        <>
          <button
            className="text-button mb-5 no-print"
            onClick={() => setActive(null)}
          >
            <ArrowLeft size={16} />
            返回报告列表
          </button>
          <div className="report-summary">
            <FileText size={35} />
            <div>
              <h2>{active.type}</h2>
              <p>
                本期共分析 <strong>{events.length}</strong> 条事件，其中高风险{" "}
                <strong>
                  {events.filter((a) => a.level === "high").length}
                </strong>{" "}
                条，已处理{" "}
                <strong>{events.filter((a) => a.handled).length}</strong> 条。
              </p>
              <small>
                基于当前预警记录生成（可能包含演示数据） ·{" "}
                {new Date(active.created).toLocaleString("zh-CN")}
              </small>
            </div>
          </div>
          <div className="report-grid">
            <section className="panel">
              <h2>风险趋势</h2>
              {events.length ? (
                <TrendChart data={trend} />
              ) : (
                <Empty text="所选时间段暂无事件" />
              )}
            </section>
            <section className="panel">
              <h2>诈骗类型分布</h2>
              {events.length ? <Distribution data={types} /> : <Empty />}
            </section>
            <section className="panel">
              <h2>风险等级分布</h2>
              <Distribution
                bar
                data={(["high", "medium", "low"] as const).map((l, i) => ({
                  name: ["高风险", "中风险", "低风险"][i],
                  value: events.filter((a) => a.level === l).length,
                }))}
              />
            </section>
            <section className="panel report-advice">
              <h2>
                {active.type === "监护人摘要"
                  ? "监护人联动摘要"
                  : "风险说明与防御建议"}
              </h2>
              <p>
                {active.type === "监护人摘要"
                  ? `本期 ${events.filter((a) => a.logs.length).length} 条事件包含联动或处置记录（不等于通知送达），仍有 ${events.filter((a) => !a.handled).length} 条事件待处理。`
                  : events.length
                    ? "风险信号主要来自资金诱导、身份核验不足和紧急行动要求。请优先核实高风险事件，避免在压力下做出转账决定。"
                    : "所选时间段没有风险事件。保持良好的信息核验习惯。"}
              </p>
              <ul className="advice">
                {Array.from(new Set(events.flatMap((a) => a.advice)))
                  .slice(0, 4)
                  .map((x) => (
                    <li key={x}>✓ {x}</li>
                  ))}
              </ul>
            </section>
          </div>
        </>
      ) : (
        <>
          <section className="report-intro">
            <div>
              <span className="eyebrow">YOUR SAFETY, IN PERSPECTIVE</span>
              <h2>让安全状况，一目了然。</h2>
              <p>
                按时间整理风险事件，发现高频诈骗类型，
                <br />
                为自己与家人生成一份安心记录。
              </p>
              <button className="button" onClick={() => setConfig(true)}>
                创建我的报告
                <ArrowUpRight size={16} />
              </button>
            </div>
            <div className="report-illustration">
              <FileText size={76} />
              <span>安全监测报告</span>
              <div />
              <div />
            </div>
          </section>
          <h2 className="section-title">
            历史报告 <span className="muted">{reports.length}</span>
          </h2>
          {reports.length ? (
            <div className="report-cards">
              {reports.map((r) => (
                <article className="panel report-card" key={r.id}>
                  <span className="report-icon">
                    <FileText size={25} />
                  </span>
                  <h3>{r.type}</h3>
                  <p>
                    <CalendarDays size={14} />
                    {r.start} — {r.end}
                  </p>
                  <div>
                    <strong>{inRange(r).length}</strong> 条检测记录{" "}
                    <span>
                      {inRange(r).filter((a) => a.level === "high").length}{" "}
                      条高风险
                    </span>
                  </div>
                  <button className="text-button" onClick={() => setActive(r)}>
                    查看报告
                    <ArrowUpRight size={16} />
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <section className="panel">
              <Empty text="还没有报告，生成一份你的安全记录吧" />
            </section>
          )}
        </>
      )}
      {config && (
        <Modal title="生成安全报告" onClose={() => setConfig(false)}>
          <div className="form-grid">
            <label>
              开始日期
              <input
                type="date"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
            </label>
            <label>
              结束日期
              <input
                type="date"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
              />
            </label>
            <label className="col-span-full">
              报告类型
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option>综合安全报告</option>
                <option>监护人摘要</option>
              </select>
            </label>
          </div>
          <p className="muted mt-4">报告由所选时间内的本地预警记录生成。</p>
          <div className="modal-actions">
            <button
              className="button secondary"
              onClick={() => setConfig(false)}
            >
              取消
            </button>
            <button className="button" onClick={()=>void generate()}>
              确认生成
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}

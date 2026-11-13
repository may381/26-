import { useState } from "react";
import { Filter, CheckCheck, Users, ArrowUpRight, Bell } from "lucide-react";
import { useApp } from "../context/AppContext";
import { fraudTypes } from "../data/mockData";
import { Heading, Badge, AlertDetail, Empty } from "../components/UI";
export default function Alerts() {
  const { alerts, notify, handle } = useApp();
  const [risk, setRisk] = useState("all");
  const [days, setDays] = useState("all");
  const [type, setType] = useState("all");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<string[]>([]);
  const [detail, setDetail] = useState("");
  const filtered = alerts.filter(
    (a) =>
      (risk === "all" || a.level === risk) &&
      (type === "all" || a.type === type) &&
      (days === "all" ||
        Date.now() - Date.parse(a.time) < Number(days) * 86400000) &&
      (status === "all" || a.handled === (status === "done")),
  );
  const current = alerts.find((a) => a.id === detail);
  const selectable = filtered.filter((a) => !a.handled);
  return (
    <>
      <Heading
        eyebrow="RISK & ALERTS"
        title="预警中心"
        description="及时了解每一次风险，让守护从提醒走向行动。"
        action={
          <span className="date-chip">
            <Bell size={16} />
            {alerts.filter((a) => !a.handled).length} 条预警待处理
          </span>
        }
      />
      <div className="summary-tabs">
        {[
          { name: "全部预警", value: "all" },
          { name: "待处理", value: "pending" },
          { name: "已处理", value: "done" },
        ].map((s) => (
          <button
            key={s.value}
            className={status === s.value ? "active" : ""}
            onClick={() => {
              setStatus(s.value);
              setSelected([]);
            }}
          >
            {s.name}
            <span>
              {
                alerts.filter(
                  (a) =>
                    s.value === "all" || a.handled === (s.value === "done"),
                ).length
              }
            </span>
          </button>
        ))}
      </div>
      <section className="panel">
        <div className="filters">
          <span>
            <Filter size={17} />
            筛选
          </span>
          <select
            aria-label="风险等级"
            value={risk}
            onChange={(e) => {
              setRisk(e.target.value);
              setSelected([]);
            }}
          >
            <option value="all">全部风险等级</option>
            <option value="high">高风险</option>
            <option value="medium">中风险</option>
            <option value="low">低风险</option>
          </select>
          <select
            aria-label="时间范围"
            value={days}
            onChange={(e) => {
              setDays(e.target.value);
              setSelected([]);
            }}
          >
            <option value="all">全部时间</option>
            <option value="1">最近 24 小时</option>
            <option value="7">最近 7 天</option>
            <option value="30">最近 30 天</option>
          </select>
          <select
            aria-label="诈骗类型"
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setSelected([]);
            }}
          >
            <option value="all">全部诈骗类型</option>
            {[...fraudTypes, "正常社交", "待人工核实"].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <button
            className="button secondary ml-auto"
            disabled={!selected.length}
            onClick={() => {
              handle(selected);
              setSelected([]);
            }}
          >
            <CheckCheck size={16} />
            批量处理{selected.length ? ` (${selected.length})` : ""}
          </button>
        </div>
        <div className="list-toolbar">
          <label>
            <input
              type="checkbox"
              aria-label="选择所有未处理预警"
              checked={
                !!selectable.length &&
                selectable.every((a) => selected.includes(a.id))
              }
              onChange={(e) =>
                setSelected(e.target.checked ? selectable.map((a) => a.id) : [])
              }
            />
            全选未处理
          </label>
          <span>共 {filtered.length} 条记录</span>
        </div>
        {filtered.length ? (
          filtered.map((a) => (
            <article className="alert-list-item" key={a.id}>
              <input
                type="checkbox"
                aria-label={`选择${a.type}${a.id}`}
                disabled={a.handled}
                checked={selected.includes(a.id)}
                onChange={(e) =>
                  setSelected((s) =>
                    e.target.checked
                      ? [...s, a.id]
                      : s.filter((id) => id !== a.id),
                  )
                }
              />
              <div className={`event-icon ${a.level}`}>
                <Bell size={20} />
              </div>
              <div className="alert-list-content">
                <div className="flex flex-wrap items-center gap-3">
                  <h3>{a.type}</h3>
                  <Badge level={a.level} /><span className="muted">{a.origin === "backend" ? "真实模型" : "模拟"}</span>
                  <span className={`status ${a.handled ? "done" : ""}`}>
                    {a.handled ? "已处理" : "待处理"}
                  </span>
                </div>
                <p>{a.summary}</p>
                <div className="alert-meta">
                  <span>{new Date(a.time).toLocaleString("zh-CN")}</span>
                  <span>用户：{a.user}</span>
                  <span>{a.modality}</span>
                  {a.logs.length > 0 && (
                    <span className="green">
                      联动与处置记录 ({a.logs.length})
                    </span>
                  )}
                </div>
                <div className="inline-actions">
                  <button onClick={() => setDetail(a.id)}>
                    查看详情
                    <ArrowUpRight size={14} />
                  </button>
                  <button onClick={() => notify(a.id)}>
                    <Users size={14} />
                    通知监护人
                  </button>
                  <button disabled={a.handled} onClick={() => handle([a.id])}>
                    <CheckCheck size={14} />
                    {a.handled ? "已处理" : "标记已处理"}
                  </button>
                </div>
              </div>
            </article>
          ))
        ) : (
          <Empty text="没有符合筛选条件的预警" />
        )}
      </section>
      {current && <AlertDetail alert={current} onClose={() => setDetail("")} />}
    </>
  );
}

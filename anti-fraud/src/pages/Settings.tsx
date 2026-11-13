import { readBrowser } from "../services/browserStorage";
import { useEffect, useState } from "react";
import {
  UserRound,
  Users,
  Plus,
  Trash2,
  Send,
  Save,
  Accessibility,
  Briefcase,
  GraduationCap,
  Heart,
  Download,
  Brain,
} from "lucide-react";
import type { Alert } from "../types";
import { useApp } from "../context/AppContext";
import { Heading, Modal } from "../components/UI";
import { api } from "../services/api";
export default function Settings() {
  const { settings, setSettings, setToast } = useApp();
  const [draft, setDraft] = useState(settings);
  const [adding, setAdding] = useState(false);
  const [memory, setMemory] = useState<Alert[]>([]);
  const [guardian, setGuardian] = useState({
    name: "",
    relation: "家人",
    phone: "",
    email: "",
    isDefault: true,
  });
  useEffect(() => {
    void api.memory(settings.name).then(result => setMemory(result.items)).catch(() => setMemory([]));
  }, [settings.name]);
  async function clearMemory(){
    if(!confirm(`确认删除 ${settings.name} 的全部风险记忆？历史报告快照不会被删除。`)) return;
    try { const result=await api.deleteMemory(settings.name); setMemory([]); setToast(`已删除 ${result.deleted} 条风险记忆`); }
    catch(e){ setToast((e as Error).message); }
  }
  function save() {
    if (!draft.name.trim()) {
      setToast("请填写用户姓名");
      return;
    }
    if (draft.age && (Number(draft.age) < 1 || Number(draft.age) > 120)) {
      setToast("年龄应在 1 至 120 岁之间");
      return;
    }
    setSettings({ ...draft, largeFont: settings.largeFont });
    setToast("角色与监护人设置已保存");
  }
  function add() {
    if (!guardian.name.trim() || !/^1\d{10}$/.test(guardian.phone)) {
      setToast("请填写监护人姓名和有效的 11 位手机号");
      return;
    }
    setDraft({
      ...draft,
      guardians: [...draft.guardians, { ...guardian, id: crypto.randomUUID() }],
    });
    setAdding(false);
    setGuardian({ name: "", relation: "家人", phone: "", email: "", isDefault: true });
    setToast("监护人已添加，保存后生效");
  }
  async function backup(){
    try{
      const data=await api.backup();
      const browser={settings,reports:readBrowser('anzhi-reports'),localAlerts:readBrowser('anzhi-alerts')};
      const url=URL.createObjectURL(new Blob([JSON.stringify({...data,browser},null,2)],{type:'application/json'}));
      const a=document.createElement('a');a.href=url;a.download=`安知本地数据备份-${new Date().toISOString().slice(0,10)}.json`;a.click();URL.revokeObjectURL(url);
      setToast('本地数据备份已导出，不包含API密钥');
    }catch(e){setToast((e as Error).message)}
  }
  return (
    <>
      <Heading
        eyebrow="PERSONAL PROTECTION"
        title="角色与监护人"
        description="了解你的习惯，让每一份守护更贴近你。"
        action={
          <div className="flex gap-2">
            <button className="button secondary" onClick={backup}><Download size={17}/>导出数据</button>
            <button className="button" onClick={save}><Save size={17}/>保存设置</button>
          </div>
        }
      />
      <div className="settings-grid">
        <section className="panel form-panel">
          <h2>
            <UserRound size={20} />
            用户角色
          </h2>
          <p className="muted">根据角色特点，提供差异化防护建议。</p>
          <div className="role-grid">
            {[
              { name: "老人", icon: Heart },
              { name: "儿童", icon: GraduationCap },
              { name: "青壮年", icon: Briefcase },
              { name: "自定义", icon: UserRound },
            ].map((r) => (
              <label
                key={r.name}
                className={draft.role === r.name ? "selected" : ""}
              >
                <input
                  type="radio"
                  name="role"
                  value={r.name}
                  checked={draft.role === r.name}
                  onChange={() => setDraft({ ...draft, role: r.name })}
                />
                <r.icon size={25} />
                <span>{r.name}</span>
              </label>
            ))}
          </div>
          <div className="form-grid">
            <label>
              姓名
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </label>
            <label>
              年龄
              <input
                type="number"
                min="1"
                max="120"
                value={draft.age}
                onChange={(e) => setDraft({ ...draft, age: e.target.value })}
              />
            </label>
            <label>
              职业
              <input
                value={draft.job}
                onChange={(e) => setDraft({ ...draft, job: e.target.value })}
                placeholder="请输入职业"
              />
            </label>
            <label>
              性别（可选）
              <select
                value={draft.gender}
                onChange={(e) => setDraft({ ...draft, gender: e.target.value })}
              >
                <option>不透露</option>
                <option>女</option>
                <option>男</option>
              </select>
            </label>
          </div>
          <div className="range-field">
            <h3>
              风险偏好
              <span>
                {draft.preference < 34
                  ? "保守"
                  : draft.preference < 67
                    ? "平衡"
                    : "激进"}
              </span>
            </h3>
            <p className="muted">越保守，越倾向于对潜在风险提前提醒。</p>
            <input
              aria-label="风险偏好"
              type="range"
              min="0"
              max="100"
              value={draft.preference}
              onChange={(e) =>
                setDraft({ ...draft, preference: Number(e.target.value) })
              }
            />
            <div>
              <span>保守</span>
              <span>平衡</span>
              <span>激进</span>
            </div>
          </div>
          <div className="setting-toggle">
            <Accessibility size={23} />
            <div>
              <strong>大字号模式</strong>
              <p>全局文字放大 1.2 倍，阅读更轻松</p>
            </div>
            <button
              role="switch"
              aria-label="大字号模式"
              aria-checked={settings.largeFont}
              className={`switch ${settings.largeFont ? "on" : ""}`}
              onClick={() =>
                setSettings({ ...settings, largeFont: !settings.largeFont })
              }
            >
              <span />
            </button>
          </div>
        </section>
        <section className="panel form-panel">
          <div className="flex items-center justify-between">
            <h2>
              <Users size={20} />
              监护人管理
            </h2>
            <button className="text-button" onClick={() => setAdding(true)}>
              <Plus size={16} />
              添加监护人
            </button>
          </div>
          <p className="muted">高风险时，向默认联系人发送模拟通知。</p>
          <div className="guardian-list">
            {draft.guardians.length ? (
              draft.guardians.map((g) => (
                <article className="guardian-card" key={g.id}>
                  <span className="guardian-avatar">{g.name.slice(0, 1)}</span>
                  <div>
                    <strong>
                      {g.name}
                      <small>{g.relation}</small>
                    </strong>
                    <p>{g.phone}</p>
                    {g.email && <p>{g.email}</p>}
                    <label>
                      <input
                        type="checkbox"
                        checked={g.isDefault}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            guardians: draft.guardians.map((x) =>
                              x.id === g.id
                                ? { ...x, isDefault: e.target.checked }
                                : x,
                            ),
                          })
                        }
                      />
                      默认通知
                    </label>
                  </div>
                  <button
                    className="icon-button ml-auto"
                    aria-label={`删除${g.name}`}
                    onClick={() => {
                      setDraft({
                        ...draft,
                        guardians: draft.guardians.filter((x) => x.id !== g.id),
                      });
                      setToast("监护人已移除，保存后生效");
                    }}
                  >
                    <Trash2 size={17} />
                  </button>
                  <button
                    className="guardian-test"
                    onClick={() =>
                      setToast(`演示记录，未发送真实短信： ${g.name} (${g.phone})`)
                    }
                  >
                    <Send size={14} />
                    测试通知
                  </button>
                </article>
              ))
            ) : (
              <p className="empty">暂无监护人，请添加联系人</p>
            )}
          </div>
          <div className="info-box">
            <ShieldNote />
          </div>
        </section>
      </div>
      <section className="panel form-panel memory-panel">
        <div className="flex items-center justify-between">
          <h2><Brain size={20}/>长期风险记忆</h2>
          <button className="button secondary" disabled={!memory.length} onClick={clearMemory}><Trash2 size={16}/>删除我的记忆</button>
        </div>
        <p className="muted">这里展示学校模型后续分析会参考的历史风险摘要。删除后，这些记录不再参与个性化判断。</p>
        <div className="guardian-list">
          {memory.length ? memory.slice(0,10).map(item=><article className="guardian-card" key={item.id}>
            <div><strong>{item.type}<small>{item.level==='high'?'高风险':item.level==='medium'?'中风险':'低风险'}</small></strong><p>{item.time} · {item.modality}</p><p>{item.summary}</p></div>
          </article>) : <p className="empty">暂无长期风险记忆</p>}
        </div>
      </section>
      {adding && (
        <Modal title="添加监护人" onClose={() => setAdding(false)}>
          <div className="form-grid">
            <label>
              姓名
              <input
                autoFocus
                value={guardian.name}
                onChange={(e) =>
                  setGuardian({ ...guardian, name: e.target.value })
                }
              />
            </label>
            <label>
              关系
              <select
                value={guardian.relation}
                onChange={(e) =>
                  setGuardian({ ...guardian, relation: e.target.value })
                }
              >
                {["家人", "父亲", "母亲", "子女", "朋友"].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </label>
            <label className="col-span-full">
              手机号
              <input
                type="tel"
                maxLength={11}
                value={guardian.phone}
                onChange={(e) =>
                  setGuardian({ ...guardian, phone: e.target.value })
                }
              />
            </label>
            <label className="col-span-full">
              邮箱（可选，用于真实邮件通知）
              <input type="email" value={guardian.email} onChange={(e) => setGuardian({ ...guardian, email: e.target.value })} placeholder="guardian@example.com" />
            </label>
          </div>
          <div className="modal-actions">
            <button
              className="button secondary"
              onClick={() => setAdding(false)}
            >
              取消
            </button>
            <button className="button" onClick={add}>
              添加监护人
            </button>
          </div>
        </Modal>
      )}
    </>
  );
}
function ShieldNote() {
  return (
    <>
      <Heart size={22} />
      <strong>让关心，及时抵达</strong>
      <p>
        短信仅模拟；填写邮箱并确认收件人后，可请求后端发送邮件（需配置 SMTP）。角色、年龄、职业和风险偏好会传入学校模型，用于调整提醒重点；画像不会替代本次输入证据。
      </p>
    </>
  );
}

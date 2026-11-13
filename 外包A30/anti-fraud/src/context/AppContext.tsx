import {
  useCallback,
  useRef,
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { api } from "../services/api";
import { restoreStored } from "../services/storedState";
import { Alert, Settings, Report, Knowledge } from "../types";
import {
  defaultSettings,
  initialAlerts,
  initialKnowledge,
} from "../data/mockData";
function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return restoreStored(key, raw, fallback);
  } catch {
    return fallback;
  }
}
function useStored<T>(key: string, fallback: T) {
  const [value, setValue] = useState<T>(() => read(key, fallback));
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      console.warn("本地存储不可用");
    }
  }, [key, value]);
  return [value, setValue] as const;
}
function useAppState() {
  const [settings, setSettings] = useStored<Settings>(
    "anzhi-settings",
    defaultSettings,
  );
  const [localAlerts, setAlerts] = useStored<Alert[]>("anzhi-alerts", initialAlerts);
  const [realAlerts, setRealAlerts] = useState<Alert[]>([]);
  const alerts = [...realAlerts, ...localAlerts.filter(a => a.origin !== "backend")];
  const refreshRealAlerts = useCallback(async () => { setRealAlerts(await api.alerts()); }, []);
  useEffect(() => { void refreshRealAlerts().catch(() => {}); }, [refreshRealAlerts]);
  const [reports, setReports] = useStored<Report[]>("anzhi-reports", []);
  const [knowledge, setKnowledge] = useStored<Knowledge[]>(
    "anzhi-knowledge",
    initialKnowledge,
  );
  const [updates, setUpdates] = useStored<string[]>("anzhi-updates", [
    "典型案例库已初始化 · 10 类诈骗场景",
    "知识索引更新完成 · 文本与多模态案例",
  ]);
  const [loggedIn, setLoggedIn] = useStored("anzhi-session", false);
  const [toast, setToast] = useState("");
  useEffect(() => {
    document.documentElement.style.fontSize = settings.largeFont
      ? "19.2px"
      : "16px";
  }, [settings.largeFont]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(""), 3500);
    return () => clearTimeout(t);
  }, [toast]);
  const notificationsInFlight = useRef(new Set<string>());
  const notify = async (id: string) => {
    if (notificationsInFlight.current.has(id)) { setToast("正在处理本次联动，请勿重复点击"); return; }
    const gs = settings.guardians.filter((g) => g.isDefault);
    if (!gs.length) {
      setToast("请先在角色设置中添加默认通知的监护人");
      return;
    }
    if (realAlerts.some(a => a.id === id)) {
      const emails = [...new Set(gs.map(g => g.email?.trim()).filter((email): email is string => Boolean(email)))];
      const summary = emails.length
        ? `将向以下邮箱发送本条风险摘要与建议：\n${emails.join('、')}\n请确认收件人。邮件不等于报警，短信未接通。`
        : `仅记录向 ${gs.map(g => g.name).join('、')} 联动的演示操作，不发送真实短信或邮件。是否继续？`;
      if (!window.confirm(summary)) return;
      notificationsInFlight.current.add(id);
      try {
        if (emails.length) await api.emailNotify(id, emails);
        else await api.notify(id, gs.map(g => g.name));
        setToast(emails.length ? "邮件已提交 SMTP 服务；不代表收件人已阅读" : "演示联动记录已保存，未发送真实通知");
        void refreshRealAlerts().catch(() => setToast("联动请求已完成，但记录刷新失败；请刷新页面核对，勿重复发送"));
      } catch (e) { setToast((e as Error).message); }
      finally { notificationsInFlight.current.delete(id); }
      return;
    }
    const log = `${new Date().toLocaleString("zh-CN")} · 已模拟通知 ${gs.map((g) => g.name).join("、")} · 未发送真实短信`;
    setAlerts((a) =>
      a.map((x) => (x.id === id ? { ...x, logs: [...x.logs, log] } : x)),
    );
    setToast("演示联动记录已保存，未发送真实通知");
  };
  const handle = async (ids: string[]) => {
    const serverIds = ids.filter(id => realAlerts.some(a => a.id === id));
    if (serverIds.length) {
      try { await api.handle(serverIds); await refreshRealAlerts(); }
      catch (e) { setToast((e as Error).message); return; }
    }
    setAlerts((a) =>
      a.map((x) => (ids.includes(x.id) ? { ...x, handled: true } : x)),
    );
    setToast(`已将 ${ids.length} 条预警标记为已处理`);
  };
  const disposition = async (id:string, action:'viewed'|'safe'|'help') => {
    const labels={viewed:'监护人已查看',safe:'监护人确认安全',help:'监护人请求进一步帮助'};
    if(realAlerts.some(a=>a.id===id)){
      try{await api.disposition(id,action);await refreshRealAlerts();setToast(labels[action]);}
      catch(e){setToast((e as Error).message)}
      return;
    }
    setAlerts(items=>items.map(item=>item.id===id?{...item,disposition:action,handled:action==='safe'||item.handled,logs:[...item.logs,`${new Date().toLocaleString('zh-CN')} · ${labels[action]}`]}:item));
    setToast(labels[action]);
  };
  return {
    refreshRealAlerts,
    settings,
    setSettings,
    alerts,
    setAlerts,
    reports,
    setReports,
    knowledge,
    setKnowledge,
    updates,
    setUpdates,
    loggedIn,
    setLoggedIn,
    toast,
    setToast,
    notify,
    handle,
    disposition,
  };
}
const Context = createContext<ReturnType<typeof useAppState> | null>(null);
export function AppProvider({ children }: { children: ReactNode }) {
  return <Context.Provider value={useAppState()}>{children}</Context.Provider>;
}
export function useApp() {
  return useContext(Context)!;
}

import { ReactNode, useState } from "react";
import {
  ShieldCheck,
  LayoutDashboard,
  MessagesSquare,
  Bell,
  ChartNoAxesCombined,
  Users,
  Database,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronDown,
  Menu,
  Check,
  FlaskConical,
} from "lucide-react";
import { Page } from "../types";
import { useApp } from "../context/AppContext";
const nav = [
  ["dashboard", "仪表盘", LayoutDashboard],
  ["assistant", "智能助手", MessagesSquare],
  ["alerts", "预警中心", Bell],
  ["reports", "安全报告", ChartNoAxesCombined],
  ["settings", "角色设置", Users],
  ["knowledge", "知识库", Database],
  ["evaluation", "测评中心", FlaskConical],
] as const;
export default function Layout({
  page,
  navigate,
  children,
}: {
  page: Page;
  navigate: (p: Page) => void;
  children: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(false);
  const { settings, setSettings, alerts, setLoggedIn, toast } = useApp();
  const pending = alerts.filter((x) => !x.handled).length;
  return (
    <div className={`app-shell ${collapsed ? "collapsed" : ""}`}>
      <aside className={`sidebar ${mobile ? "mobile-open" : ""}`}>
        <a
          className="brand"
          href="#dashboard"
          onClick={() => navigate("dashboard")}
        >
          <span className="brand-icon">
            <ShieldCheck />
          </span>
          <span className="brand-text">
            安知<span>AI 安全守护助手</span>
          </span>
        </a>
        <div className="nav-label">工作空间</div>
        <nav>
          {nav.map(([id, name, Icon]) => (
            <button
              title={name}
              key={id}
              onClick={() => {
                navigate(id);
                setMobile(false);
              }}
              className={page === id ? "active" : ""}
            >
              <Icon size={20} />
              <span>{name}</span>
              {id === "alerts" && pending > 0 && <b>{pending}</b>}
              {page === id && <i />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="protection">
            <span className="pulse" />
            全天候安全守护中<small>每一次识别，多一份安心</small>
          </div>
          <button className="logout" onClick={() => { setLoggedIn(false); location.hash = "login"; }}>
            <LogOut size={18} />
            <span>退出登录</span>
          </button>
          <button
            className="collapse-control"
            onClick={() => setCollapsed(!collapsed)}
            aria-label="折叠侧边栏"
          >
            {collapsed ? (
              <PanelLeftOpen size={18} />
            ) : (
              <PanelLeftClose size={18} />
            )}
          </button>
        </div>
      </aside>
      {mobile && (
        <div className="mobile-overlay" onClick={() => setMobile(false)} />
      )}
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label="打开菜单"
              onClick={() => setMobile(!mobile)}
            >
              <Menu />
            </button>
            <span>工作空间</span>
            <span className="slash">/</span>
            <strong>{nav.find((n) => n[0] === page)?.[1]}</strong>
          </div>
          <div className="top-actions">
            <span className="score-badge">
              <ShieldCheck size={15} />
              安全评分 92
            </span>
            <button
              className={`font-toggle ${settings.largeFont ? "selected" : ""}`}
              onClick={() =>
                setSettings({ ...settings, largeFont: !settings.largeFont })
              }
              aria-pressed={settings.largeFont}
            >
              <span>Aa</span>
              <span>大字号</span>
            </button>
            <button
              className="notification"
              aria-label="查看未处理预警"
              onClick={() => navigate("alerts")}
            >
              <Bell size={20} />
              {pending > 0 && <i />}
            </button>
            <button
              type="button"
              className="guardian-shortcut"
              aria-label="监护人设置"
              onClick={() => navigate("settings")}
            >
              <span className="guardian-shortcut-surface" aria-hidden="true"><Users size={20} /></span>
              <span className="guardian-shortcut-tip" aria-hidden="true">监护人设置</span>
            </button>
            <span className="divider" />
            <button className="profile" onClick={() => navigate("settings")}>
              <span className="avatar">{settings.name.slice(0, 1)}</span>
              <span>
                {settings.name}
                <small>{settings.role} · 个人账户</small>
              </span>
              <ChevronDown size={14} />
            </button>
          </div>
        </header>
        <main>{children}</main>
        <footer className="app-footer">
          <span>
            <ShieldCheck size={13} /> 安知，守护每一份信任
          </span>
          <span>本地原型 · 文本可接真实模型，其他能力依页面标记</span>
        </footer>
      </div>
      {toast && (
        <div role="status" className="toast">
          <Check size={18} />
          {toast}
        </div>
      )}
    </div>
  );
}

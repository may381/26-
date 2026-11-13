import { useEffect, useState } from "react";
import { ShieldCheck, Phone, LockKeyhole } from "lucide-react";
import { useApp } from "../context/AppContext";
import FloatingStickers from "../components/FloatingStickers";
import { demoAccount } from "../data/demoAccount";
export default function Login({
  onLogin,
}: {
  onLogin: (register: boolean) => void;
}) {
  const { setLoggedIn, settings, setSettings, setToast, toast } = useApp();
  const [phone, setPhone] = useState(demoAccount.phone);
  const [code, setCode] = useState("");
  const [role, setRole] = useState("青壮年");
  const [register, setRegister] = useState(false);
  const [count, setCount] = useState(0);
  useEffect(() => {
    try { localStorage.setItem('anzhi-demo-account', JSON.stringify(demoAccount)); }
    catch { /* The bundled demo account still works when storage is unavailable. */ }
  }, []);
  useEffect(() => {
    if (!count) return;
    const t = setTimeout(() => setCount(count - 1), 1000);
    return () => clearTimeout(t);
  }, [count]);
  function login() {
    if (!/^1\d{10}$/.test(phone) || code !== "123456") {
      setToast("请输入有效手机号和演示验证码 123456");
      return;
    }
    setSettings({ ...settings, role, ...(phone === demoAccount.phone ? { name: demoAccount.name } : {}) });
    setLoggedIn(true);
    onLogin(register);
  }
  return (
    <div className="login-page">
      <div className="login-story">
        <a className="brand" href="#">
          <span className="brand-icon">
            <ShieldCheck />
          </span>
          <span className="brand-text">
            安知<span>AI 安全守护助手</span>
          </span>
        </a>
        <div>
          <span className="eyebrow">
            ANZHI / MULTIMODAL SECURITY
          </span>
          <h1>
            让每一份信任，
            <br />
            <span className="login-accent">都有安心的回应。</span>
          </h1>
          <p>
            懂文字，听声音，看见风险。
            <br />
            你的多模态反诈智能助手，时刻陪伴。
          </p>
          <div className="login-shield">
            <div className="login-demo-head"><span className="pulse"/>安知 · 安全识别引擎<span>在线</span></div>
            <div className="login-demo-body"><ShieldCheck size={32}/><div><strong>文字、声音、画面。</strong><p>一起，看清潜在风险。</p></div></div>
            <div className="login-demo-tags"><span>多模态感知</span><span>风险分析</span><span>家人联动</span></div>
          </div>
        </div>
        <small>多模态感知 · 个性化守护 · 监护人联动</small>
      </div>
      <div className="login-form">
        <FloatingStickers />
        <span className="brand-icon">
          <ShieldCheck />
        </span>
        <span className="login-form-kicker">你的专属安全空间</span>
        <h1>{register ? "创建你的安全账户" : "登录安知"}</h1>
        <p className="muted">
          {register ? "开启你与家人的安心守护" : "登录安知，继续你的安全守护"}
        </p>
        <div className="demo-account-box">
          <strong>已内置演示账号 · {demoAccount.name}</strong>
          <p>手机号：{demoAccount.phone}<br/>演示验证码：{demoAccount.code}</p>
          <button type="button" className="text-button" onClick={() => {
            setPhone(demoAccount.phone); setCode(demoAccount.code); setRole(demoAccount.role); setRegister(false);
            setToast('演示账号已填入，点击登录即可进入主页');
          }}>一键填入演示账号</button>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            login();
          }}
        >
          <label>
            手机号
            <div className="input-icon">
              <Phone size={17} />
              <input
                type="tel"
                placeholder="请输入手机号"
                value={phone}
                maxLength={11}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>
          </label>
          <label>
            验证码
            <div className="input-icon">
              <LockKeyhole size={17} />
              <input
                placeholder="演示验证码 123456"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
              <button
                type="button"
                disabled={count > 0}
                onClick={() => {
                  if (!/^1\d{10}$/.test(phone)) {
                    setToast("请先填写有效手机号");
                    return;
                  }
                  setCount(60);
                  setCode("123456");
                  setToast("模拟验证码为 123456，已自动填入");
                }}
              >
                {count ? `${count}s` : "获取验证码"}
              </button>
            </div>
          </label>
          <label>
            我的角色
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              {["老人", "儿童", "青壮年", "自定义"].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
          </label>
          <div className="login-glow-action">
            <div className="login-button-glow" aria-hidden="true" />
            <button className="login-glow-button" type="submit">
              {register ? "注册并完善资料" : "登录"}
              <svg aria-hidden="true" viewBox="0 0 10 10" height="10" width="10" fill="none" className="login-button-arrow">
                <path d="M0 5h7" className="arrow-shaft" />
                <path d="M1 1l4 4-4 4" className="arrow-head" />
              </svg>
            </button>
          </div>
        </form>
        <p className="text-center muted">
          {register ? "已有账户？" : "还没有账户？"}
          <button
            className="text-button inline-flex"
            onClick={() => setRegister(!register)}
          >
            {register ? "立即登录" : "创建账户"}
          </button>
        </p>
        <button type="button" className="button secondary w-full justify-center" onClick={() => onLogin(false)}>
          直接体验主页（免登录）
        </button>
        <div className="privacy-note">
          <ShieldCheck size={14} />
          原型演示，无真实鉴权或短信发送
        </div>
      </div>
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}

import { readBrowser, writeBrowser } from "../services/browserStorage";
import { useEffect, useMemo, useState } from "react";
import { Pause, Play, Volume2, VolumeX } from "lucide-react";
import type { Alert, Risk } from "../types";
import { useApp } from "../context/AppContext";
import type { DigitalHumanSignal } from "../services/digitalHuman";

type AvatarState = "idle" | "analyzing" | "speaking" | "error" | Risk;

function speechText(alert: Alert) {
  const level = alert.level === "high" ? "高风险" : alert.level === "medium" ? "中风险" : "低风险";
  return `小安提醒你：本次分析为${level}，识别类型是${alert.type}。${alert.evidence}。建议：${alert.advice.slice(0, 3).join("；")}`;
}

export default function DigitalHuman() {
  const { alerts, setToast } = useApp();
  const latest = useMemo(() => alerts.find(item => item.origin === "backend") ?? null, [alerts]);
  const [result, setResult] = useState<Alert | null>(latest);
  const [state, setState] = useState<AvatarState>(latest?.level ?? "idle");
  const [muted, setMuted] = useState(() => readBrowser("anzhi-avatar-muted") === "1");

  useEffect(() => {
    const listener = (event: Event) => {
      const signal = (event as CustomEvent<DigitalHumanSignal>).detail;
      if (signal.state === "result") { setResult(signal.alert); setState(signal.alert.level); }
      else setState(signal.state);
    };
    window.addEventListener("anzhi-digital-human", listener);
    return () => window.removeEventListener("anzhi-digital-human", listener);
  }, []);

  useEffect(() => {
    if (latest && !result) { setResult(latest); setState(latest.level); }
  }, [latest, result]);

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  function stop() {
    window.speechSynthesis?.cancel();
    setState(result?.level ?? "idle");
  }

  function speak() {
    if (!result) return setToast("完成一次真实分析后，小安才能播报结果");
    if (!("speechSynthesis" in window)) return setToast("当前浏览器不支持语音播报");
    if (muted) return setToast("请先关闭静音模式");
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(speechText(result));
    utterance.lang = "zh-CN";
    utterance.rate = .92;
    utterance.pitch = 1.06;
    utterance.onstart = () => setState("speaking");
    utterance.onend = () => setState(result.level);
    utterance.onerror = () => { setState(result.level); setToast("语音播报失败，文字建议仍可正常查看"); };
    window.speechSynthesis.speak(utterance);
  }

  function toggleMute() {
    const next = !muted;
    setMuted(next); writeBrowser("anzhi-avatar-muted", next ? "1" : "0");
    if (next) stop();
  }

  const label = state === "analyzing" ? "正在分析" : state === "speaking" ? "正在播报" : state === "error" ? "分析遇到问题" : state === "high" ? "发现高风险" : state === "medium" ? "需要进一步核实" : state === "low" ? "当前风险较低" : "随时为你守护";
  return <section className={`panel digital-human digital-human-${state}`} aria-label="小安数字人">
    <div className="digital-human-stage" aria-hidden="true">
      <span className="avatar-halo"/>
      <svg className="anzhi-avatar" viewBox="0 0 220 240" role="img">
        <defs><linearGradient id="avatarBody" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f7f1ff"/><stop offset="1" stopColor="#b59ad7"/></linearGradient></defs>
        <path className="avatar-body" d="M53 91c0-36 24-63 57-63s57 27 57 63v74c0 28-23 50-51 50H104c-28 0-51-22-51-50V91Z" fill="url(#avatarBody)"/>
        <path className="avatar-ear" d="M54 103c-18-1-24 12-18 29 3 9 10 14 19 13M166 103c18-1 24 12 18 29-3 9-10 14-19 13"/>
        <path className="avatar-hair" d="M58 88c7-44 42-61 73-50 23 8 36 26 37 51-13-1-27-10-36-23-17 16-43 25-74 22Z"/>
        <g className="avatar-eyes"><ellipse cx="83" cy="117" rx="7" ry="9"/><ellipse cx="137" cy="117" rx="7" ry="9"/></g>
        <path className="avatar-mouth" d="M94 149q16 12 32 0"/>
        <path className="avatar-shield" d="M110 173l21 8v15c0 15-10 25-21 30-11-5-21-15-21-30v-15l21-8Z"/><path className="avatar-check" d="m100 198 7 7 14-16"/>
        <g className="speech-waves"><path d="M190 97q13 15 0 30"/><path d="M199 88q22 24 0 48"/></g>
      </svg>
      <span className="avatar-status-dot"/>
    </div>
    <div className="digital-human-copy">
      <span className="eyebrow">DIGITAL GUARDIAN</span>
      <h2>小安 · 反诈守护员</h2>
      <strong>{label}</strong>
      <p>{result ? `${result.type} · ${result.evidence}` : "提交文字、图片、语音或视频后，我会解释风险并朗读防御建议。"}</p>
      <div className="digital-human-actions">
        {state === "speaking" ? <button className="button" onClick={stop}><Pause size={16}/>停止播报</button> : <button className="button" disabled={!result || muted || state === "analyzing"} onClick={speak}><Play size={16}/>播报建议</button>}
        <button className="button secondary" onClick={toggleMute}>{muted ? <VolumeX size={16}/> : <Volume2 size={16}/>}{muted ? "取消静音" : "静音"}</button>
      </div>
      <small>数字人仅呈现分析结果，不参与风险判定。</small>
    </div>
  </section>;
}

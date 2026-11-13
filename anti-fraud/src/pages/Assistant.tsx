import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Send,
  Image,
  Mic,
  Upload,
  ShieldCheck,
  Users,
  FileText,
  Sparkles,
  X,
  AudioLines,
  Check,
} from "lucide-react";
import { useApp } from "../context/AppContext";
import { scenarios } from "../data/mockData";
import { Scenario } from "../types";
import { Heading, Badge } from "../components/UI";
import RealTextAnalysis from "../components/RealTextAnalysis";
import RealImageAnalysis from "../components/RealImageAnalysis";
import RealAudioAnalysis from "../components/RealAudioAnalysis";
import RealMultimodalAnalysis from "../components/RealMultimodalAnalysis";
import RealVideoAnalysis from "../components/RealVideoAnalysis";
import Loader from "../components/Loader";
import DigitalHuman from "../components/DigitalHuman";
import FraudSafetyCenter from "../components/FraudSafetyCenter";
type Message = {
  id: string;
  who: "user" | "assistant";
  text: string;
  analysis?: Scenario;
  image?: string;
  audio?: string;
};
export default function Assistant({
  mode,
  onReport,
}: {
  mode: string;
  onReport: () => void;
}) {
  const { settings, alerts, setAlerts, notify, setToast } = useApp();
  const [realMode, setRealMode] = useState(true);
  const [scenario, setScenario] = useState("");
  const [analysis, setAnalysis] = useState<Scenario | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [textTemplate, setTextTemplate] = useState<{id:string;text:string}|null>(null);
  const [attachments, setAttachments] = useState<
    { name: string; kind: string; url: string }[]
  >([]);
  const [busy, setBusy] = useState(false);
  const [eventId, setEventId] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const audioRef = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const urls = useRef<string[]>([]);
  useEffect(
    () => () => {
      clearTimeout(timer.current);
      urls.current.forEach(URL.revokeObjectURL);
    },
    [],
  );
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, busy]);
  useEffect(() => {
    if (!realMode && messages.length === 0) openDemo();
    // 首次进入智能助手时展示完整演示态，用户仍可随时切换真实分析。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  function append(s: Scenario, text: string, media?: typeof attachments) {
    const id = crypto.randomUUID();
    setAnalysis(s);
    setEventId(id);
    setAlerts((a) => [
      {
        id,
        level: s.level,
        type: s.type,
        summary: text,
        time: new Date().toISOString(),
        user: settings.name,
        handled: s.level === "low",
        confidence: s.confidence,
        advice: s.advice,
        evidence: s.reply,
        logs: [],
        modality: media?.length
          ? [
              "文本",
              ...media.map((x) => (x.kind === "image" ? "图片" : "音频")),
            ].join(" + ")
          : s.modality,
      },
      ...a,
    ]);
  }
  function choose(id: string) {
    clearTimeout(timer.current);
    setBusy(false);
    const s = scenarios.find((x) => x.id === id)!;
    if (realMode) {
      setScenario(id);
      setAttachments([]);
      setInput(s.text);
      setTextTemplate({id:crypto.randomUUID(),text:s.text});
      setMessages([]);
      setAnalysis(null);
      setToast(`已载入${s.name}案例，请点击真实分析提交`);
      return;
    }
    setScenario(id);
    setAttachments([]);
    setInput("");
    setMessages([
      {
        id: crypto.randomUUID(),
        who: "user",
        text: s.text,
        image:
          id === "invest"
            ? "/invest-demo.svg"
            : id === "task"
              ? "/task-demo.svg"
              : undefined,
        audio: id === "voice" ? "模拟语音 · 00:12" : undefined,
      },
      { id: crypto.randomUUID(), who: "assistant", text: s.reply, analysis: s },
    ]);
    append(s, s.text);
    setToast(`已载入${s.name}演示场景`);
  }
  function openDemo() {
    const s = scenarios.find((item) => item.id === "invest") ?? scenarios[1];
    setRealMode(false);
    setScenario(s.id);
    setAttachments([]);
    setAnalysis(s);
    setMessages([
      { id: crypto.randomUUID(), who: "user", text: s.text, image: "/invest-demo.svg" },
      { id: crypto.randomUUID(), who: "assistant", text: s.reply, analysis: s },
    ]);
    append(s, s.text);
    setToast("已载入完整多模态演示效果");
  }
  function upload(file?: File) {
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
      setToast("请选择小于 10 MB 的文件");
      return;
    }
    if (!file.type.startsWith("image/") && !file.type.startsWith("audio/")) {
      setToast("仅支持图片或音频文件");
      return;
    }
    const url = URL.createObjectURL(file);
    urls.current.push(url);
    setAttachments((items) => [
      ...items.filter(
        (x) => x.kind !== (file.type.startsWith("image/") ? "image" : "audio"),
      ),
      {
        name: file.name,
        kind: file.type.startsWith("image/") ? "image" : "audio",
        url,
      },
    ]);
    setToast("文件已添加，可补充描述后发送分析");
  }
  function send() {
    if (busy || (!input.trim() && !attachments.length)) return;
    const text =
      input.trim() ||
      `请分析文件：${attachments.map((x) => x.name).join("、")}`;
    const media = attachments;
    setMessages((m) => [
      ...m,
      {
        id: crypto.randomUUID(),
        who: "user",
        text,
        image: media.find((x) => x.kind === "image")?.url,
        audio: media.find((x) => x.kind === "audio")?.url,
      },
    ]);
    setInput("");
    setAttachments([]);
    setBusy(true);
    timer.current = setTimeout(() => {
      let s: Scenario;
      if (/收益|投资|保本|理财/.test(text)) s = scenarios[1];
      else if (/刷单|充值|返佣|垫付/.test(text)) s = scenarios[3];
      else if (/回拨|妈|合成语音/.test(text)) s = scenarios[2];
      else if (media.length)
        s = {
          ...scenarios[0],
          level: "medium",
          type: "待人工核实",
          confidence: 65,
          reply:
            "已接收附件。本原型不执行真实语音识别或图像分析；请补充内容描述，或切换演示场景查看联合分析效果。",
          advice: [
            "通过已知官方渠道核实信息",
            "涉及资金操作时先暂停并联系家人",
          ],
        };
      else s = scenarios[0];
      s = {
        ...s,
        modality: [
          "文本",
          ...media.map((x) => (x.kind === "image" ? "图片" : "音频")),
        ].join(" + "),
      };
      setAnalysis(s);
      setMessages((m) => [
        ...m,
        {
          id: crypto.randomUUID(),
          who: "assistant",
          text: s.reply,
          analysis: s,
        },
      ]);
      append(s, text, media);
      setBusy(false);
    }, 1100);
  }
  const notified = alerts.find((a) => a.id === eventId)?.logs.length;
  return (
    <>
      <Heading
        eyebrow="AI SECURITY ASSISTANT"
        title="智能助手"
        description="文字、声音、画面，一起看清潜在风险。"
        action={
          <span className="model-chip">
            <span className="pulse" />
            {realMode ? "学校模型分析" : "多模态分析 · 演示模式"}
          </span>
        }
      />
      <div className="scenario-bar">
        <button className={realMode ? "selected" : ""} disabled={busy} onClick={() => setRealMode(true)}>真实文本 / 图片 / 语音分析</button>
        <button className={!realMode ? "selected" : ""} onClick={openDemo}>多模态模拟演示</button>
      </div>
      {realMode && <div className="case-template-bar">
        <span><Sparkles size={16}/>案例模板</span>
        {scenarios.map((s) => <button key={s.id} onClick={() => choose(s.id)}>{s.name}</button>)}
        <small>点击后会填入真实分析框，不会直接生成模拟结论</small>
      </div>}
      {realMode ? <div className="real-analysis-layout chat-style-layout">
        <DigitalHuman/>
        <div className="chat-workspace"><FraudSafetyCenter onAnalyze={text=>setTextTemplate({id:crypto.randomUUID(),text})}/><RealTextAnalysis template={textTemplate}/>
          <details className="secondary-analysis-tools">
            <summary>添加图片、音频或视频证据 <span>可选卡片</span></summary>
            <div className="secondary-analysis-grid"><RealMultimodalAnalysis/><RealImageAnalysis/><RealAudioAnalysis/><RealVideoAnalysis/></div>
          </details>
        </div>
      </div> : <>
      <div className="scenario-bar">
        <span>
          <Sparkles size={17} />
          体验模拟场景
        </span>
        {scenarios.map((s) => (
          <button
            className={scenario === s.id ? "selected" : ""}
            key={s.id}
            onClick={() => choose(s.id)}
          >
            {s.name}
          </button>
        ))}
      </div>
      <div className="assistant-grid">
        <section
          className="panel chat-panel"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            upload(e.dataTransfer.files[0]);
          }}
        >
          <div className="chat-header">
            <span className="bot-avatar">
              <Bot size={23} />
            </span>
            <div>
              <strong>安知 AI</strong>
              <small>
                <i />
                你的专属安全助手
              </small>
            </div>
            <span className="ml-auto muted text-xs">
              会话内容仅用于本地演示
            </span>
          </div>
          <div className="messages">
            {messages.length === 0 ? (
              <div className="chat-empty">
                <span className="large-bot">
                  <ShieldCheck size={40} />
                </span>
                <h2>你好，有什么需要我帮你辨别？</h2>
                <p>
                  把可疑的消息、语音或截图发给我，
                  <br />
                  我们一起确认，安心再行动。
                </p>
                <div className="suggestions">
                  {[
                    "这条投资消息靠谱吗？",
                    "帮我看看这段语音",
                    "兼职任务需要先充值？",
                  ].map((x, i) => (
                    <button
                      key={x}
                      onClick={() => choose(["invest", "voice", "task"][i])}
                    >
                      {x}
                      <Send size={13} />
                    </button>
                  ))}
                </div>
                {mode !== "text" && (
                  <button
                    className="button secondary"
                    onClick={() =>
                      mode === "audio"
                        ? audioRef.current?.click()
                        : fileRef.current?.click()
                    }
                  >
                    <Upload size={16} />
                    上传{mode === "audio" ? "音频" : "图片"}
                  </button>
                )}
              </div>
            ) : (
              messages.map((m) => (
                <div className={`message ${m.who}`} key={m.id}>
                  <span className="message-avatar">
                    {m.who === "assistant" ? (
                      <Bot size={19} />
                    ) : (
                      settings.name.slice(0, 1)
                    )}
                  </span>
                  <div className="message-content">
                    <small>
                      {m.who === "assistant" ? "安知 AI" : settings.name}
                    </small>
                    <div className="bubble">
                      {m.image && (
                        <img src={m.image} alt="用户上传的待分析图片" />
                      )}
                      {m.audio &&
                        (m.audio.startsWith("blob:") ? (
                          <audio controls src={m.audio} />
                        ) : (
                          <div className="wave">
                            <AudioLines />
                            {m.audio}
                          </div>
                        ))}
                      <p>{m.text}</p>
                      {m.analysis && (
                        <div className={`inline-analysis ${m.analysis.level}`}>
                          <div>
                            <ShieldCheck size={17} />
                            <strong>风险分析结果</strong>
                            <Badge level={m.analysis.level} />
                          </div>
                          <p>
                            {m.analysis.type} · 模拟置信度{" "}
                            {m.analysis.confidence}%
                          </p>
                          <small>{m.analysis.advice[0]}</small>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))
            )}
            {busy && (
              <Loader label="正在关联上下文并分析风险…" />
            )}
            <div ref={bottom} />
          </div>
          <div className="composer">
            {attachments.map((attachment) => (
              <div className="attachment" key={attachment.url}>
                {attachment.kind === "image" ? (
                  <img src={attachment.url} alt="待发送图片" />
                ) : (
                  <AudioLines />
                )}
                <span>{attachment.name}</span>
                <button
                  className="icon-button"
                  aria-label={`移除${attachment.name}`}
                  onClick={() =>
                    setAttachments((items) =>
                      items.filter((x) => x.url !== attachment.url),
                    )
                  }
                >
                  <X size={16} />
                </button>
              </div>
            ))}
            <textarea
              aria-label="消息内容"
              placeholder="粘贴可疑信息，或描述你遇到的情况…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <div className="composer-tools">
              <button
                title="上传图片"
                aria-label="上传图片"
                onClick={() => fileRef.current?.click()}
              >
                <Image size={19} />
                <span>图片</span>
              </button>
              <button
                title="上传语音"
                aria-label="上传语音"
                onClick={() => audioRef.current?.click()}
              >
                <Mic size={19} />
                <span>语音</span>
              </button>
              <span className="muted text-xs">支持拖拽 · 最大 10 MB</span>
              <button
                className="button send-button"
                disabled={busy || (!input.trim() && !attachments.length)}
                onClick={send}
              >
                发送
                <Send size={16} />
              </button>
            </div>
            <input
              hidden
              ref={fileRef}
              type="file"
              accept="image/*"
              onChange={(e) => {
                upload(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            <input
              hidden
              ref={audioRef}
              type="file"
              accept="audio/*"
              onChange={(e) => {
                upload(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </div>
          <div className="chat-disclaimer">
            分析结果为规则与场景模拟，不构成真实安全判定。
          </div>
        </section>
        <aside className="panel risk-panel">
          <div className="panel-heading">
            <h2>实时风险分析</h2>
            <span className="live-dot" />
          </div>
          <div className={`risk-orb ${analysis?.level || "idle"}`}>
            <ShieldCheck size={42} />
          </div>
          <h2 className="text-center">
            {analysis ? <Badge level={analysis.level} /> : "等待分析"}
          </h2>
          <p className="muted text-center">
            {analysis
              ? "已完成当前输入的模拟分析"
              : "发送信息后，风险结果将在这里呈现"}
          </p>
          <div className="risk-metric">
            <span>识别类型</span>
            <strong>{analysis?.type || "—"}</strong>
          </div>
          <div className="risk-metric">
            <span>模拟置信度</span>
            <strong>{analysis ? `${analysis.confidence}%` : "—"}</strong>
          </div>
          <div className="progress-track">
            <span style={{ width: `${analysis?.confidence || 0}%` }} />
          </div>
          <div className="risk-metric">
            <span>分析模态</span>
            <strong>{analysis?.modality || "文本 / 语音 / 图像"}</strong>
          </div>
          <h3>防御建议</h3>
          <ul className="advice">
            {(
              analysis?.advice || [
                "保持警惕，谨慎对待陌生请求",
                "涉及资金操作时，多方核实身份",
              ]
            ).map((a) => (
              <li key={a}>
                <ShieldCheck size={17} />
                {a}
              </li>
            ))}
          </ul>
          <div className="risk-actions">
            <button
              className="button"
              disabled={!analysis}
              onClick={() => notify(eventId)}
            >
              {notified ? <Check size={17} /> : <Users size={17} />}{" "}
              {notified ? "已有联动记录 · 查看并操作" : "通知监护人"}
            </button>
            <button
              className="button secondary"
              disabled={!analysis}
              onClick={onReport}
            >
              <FileText size={17} />
              生成报告
            </button>
          </div>
        </aside>
      </div>
      </>}
    </>
  );
}

import { useState } from 'react';
import { ArrowUpRight, ArrowRight, ShieldCheck, Bell, MessageSquareText, Mic, Image, CalendarDays, Sparkles, ChevronRight, LockKeyhole } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { Badge, AlertDetail, Empty } from '../components/UI';
import { TrendChart } from '../components/Charts';
import { Page } from '../types';
import FloatingStickers from '../components/FloatingStickers';

const inputs = [
  { name: '文本检测', desc: '粘贴聊天记录或可疑短信', icon: MessageSquareText, key: 'text' },
  { name: '语音检测', desc: '上传通话录音或语音消息', icon: Mic, key: 'audio' },
  { name: '图片检测', desc: '上传聊天截图或宣传图片', icon: Image, key: 'image' },
];

export default function Dashboard({ navigate, detect }: { navigate: (p: Page) => void; detect: (m: string) => void }) {
  const { alerts, settings } = useApp();
  const [detail, setDetail] = useState<string | null>(null);
  const demoCount = alerts.filter(a => a.origin !== "backend").length;
  const pending = alerts.filter(a => !a.handled).length;
  const todayKey = new Date().toLocaleDateString('sv-SE');
  const todayAlerts = alerts.filter(a => new Date(a.time).toLocaleDateString('sv-SE') === todayKey);
  const riskCount = todayAlerts.filter(a=>a.level!=='low').length;
  const score = Math.max(50, 100 - pending * 4 - alerts.filter(a=>a.level==='high'&&!a.handled).length * 3);
  const trend = Array.from({length:7},(_,i)=>{
    const d = new Date(); d.setDate(d.getDate()-6+i);
    const key = d.toLocaleDateString('sv-SE');
    const daily = alerts.filter(a=>new Date(a.time).toLocaleDateString('sv-SE')===key);
    return {date:`${d.getMonth()+1}/${d.getDate()}`,high:daily.filter(a=>a.level==='high').length,medium:daily.filter(a=>a.level==='medium').length};
  });
  const selected = alerts.find(a => a.id === detail);
  const recent = [...alerts].sort((a,b) => Date.parse(b.time)-Date.parse(a.time)).slice(0,5);
  return <div className="overview-v2">
    <header className="overview-heading">
      <div><span className="overview-kicker">你的安全空间</span><h1>安心，从了解开始。</h1><p>{settings.name}，欢迎回来。一起看看今天的安全状况。</p></div>
      <span className="overview-date"><CalendarDays size={16}/>{new Date().toLocaleDateString('zh-CN',{month:'long',day:'numeric',weekday:'long'})}</span>
    </header>

    <div className="overview-top">
      <section className="safety-surface" aria-label="今日安全概览">
        <div className="safety-topline"><span><span className="pulse"/>风险记录概览</span><ShieldCheck size={21}/></div>
        <div className="safety-primary">
          <div className="safety-copy"><span>提醒处理指数</span><h2>每一份信任，<br/>都值得守护。</h2><p>{pending ? `还有 ${pending} 条提醒等待确认，花一点时间，让安心多一点。` : '所有提醒均已处理。保持核验习惯，安心开启新的一天。'}</p><button className="text-button" onClick={()=>navigate('alerts')}>{pending?'查看待处理提醒':'查看安全记录'}<ArrowRight size={16}/></button></div>
          <div className="safety-dial" aria-label={`提醒处理指数${score}分`}><svg viewBox="0 0 180 180" aria-hidden="true"><circle cx="90" cy="90" r="76" className="dial-track"/><circle cx="90" cy="90" r="76" className="dial-value" style={{strokeDasharray:`${score * 4.775} 477.5`}}/></svg><div><strong>{score}<span>分</span></strong><span className="dial-caption">处理参考</span></div></div>
        </div>
        <div className="safety-stats"><div><span>今日检测</span><strong>{todayAlerts.length}<small>次</small></strong></div><div><span>今日风险</span><strong>{riskCount}<small>次</small></strong></div><button onClick={()=>navigate('alerts')}><span>待处理预警<ArrowUpRight size={14}/></span><strong className={pending?'pending-number':''}>{pending}<small>条</small></strong></button></div>
        <span className="sample-caption">按未处理记录计算，不代表诈骗概率或实际安全程度；当前含 {demoCount} 条演示记录</span>
      </section>

      <section className="detect-surface" aria-label="快速检测">
        <FloatingStickers compact />
        <div className="detect-heading"><span className="mini-ai"><Sparkles size={19}/></span><span>安知智能助手</span></div>
        <h2>拿不准？<br/>让安知帮你看看。</h2><p>一段文字、一条语音、一张截图。<br/>多一个确认，少一份担心。</p>
        <div className="detect-options">{inputs.map(m=><button key={m.key} onClick={()=>detect(m.key)}><span className="detect-icon"><m.icon size={22} strokeWidth={1.6}/></span><span><strong>{m.name}</strong><small>{m.desc}</small></span><ChevronRight size={17}/></button>)}</div>
        <div className="detect-privacy"><LockKeyhole size={13}/>实际分析会向本机后端及所选学校模型提交内容</div>
      </section>
    </div>

    <div className="overview-bottom">
      <section className="activity-surface"><div className="overview-section-title"><div><h2>最近的安全动态</h2><p>每一次提醒，都有迹可循。</p></div><button className="text-button" onClick={()=>navigate('alerts')}>全部记录<ArrowUpRight size={15}/></button></div>
        <div className="activity-list">{recent.length?recent.map(a=><button className="activity-item" key={a.id} onClick={()=>setDetail(a.id)} aria-label={`查看${a.type}详情`}><span className={`activity-risk-icon ${a.level}`}><Bell size={19} strokeWidth={1.6}/></span><span className="activity-description"><span className="activity-title"><strong>{a.type}</strong><Badge level={a.level}/><small>{a.origin === "backend" ? "模型分析" : "演示"}</small></span><span className="activity-excerpt">{a.summary}</span><span className="activity-metadata">{new Date(a.time).toLocaleDateString('zh-CN',{month:'2-digit',day:'2-digit'})} · {new Date(a.time).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}<i/>{a.handled?'已处理':'待处理'}{a.logs.length>0&&' · 有联动或处置记录'}</span></span><ChevronRight className="activity-chevron" size={17}/></button>):<Empty text="暂无安全动态"/>}</div>
      </section>
      <div className="overview-insights"><section className="insight-surface"><div className="overview-section-title"><div><h2>这一周，更安心。</h2><p>近 7 天预警记录趋势</p></div><span className="insight-period">7 天</span></div><TrendChart data={trend}/><div className="insight-legend"><span><i/>中风险</span><span><i/>高风险</span></div></section>
      <section className="learn-surface"><span className="learn-mark"><ShieldCheck size={24} strokeWidth={1.4}/></span><div><span className="learn-eyebrow">给你和家人的安全锦囊</span><h3>遇到“稳赚不赔”，先停一步。</h3><p>高回报承诺背后，可能是精心设计的陷阱。</p><button className="text-button" onClick={()=>navigate('knowledge')}>了解投资诈骗<ArrowRight size={15}/></button></div></section></div>
    </div>
    {selected&&<AlertDetail alert={selected} onClose={()=>setDetail(null)}/>}
  </div>;
}

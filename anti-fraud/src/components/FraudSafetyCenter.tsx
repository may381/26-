import { useEffect, useState } from 'react';
import { useApp } from '../context/AppContext';

const lessons = [
  {title:'冒充亲友', example:'“我是你孙子，手机坏了，马上给这个账户汇钱。”', signal:'身份紧急变化、催促汇款、要求保密', steps:['先停止汇款和提供验证码。','使用自己原先保存的电话联系本人。','把情况交给可信家人一起核对。']},
  {title:'投资养老', example:'“内部养老项目，保本高收益，今天交钱才有名额。”', signal:'承诺高收益、名额催促、陌生收款账户', steps:['先暂停支付，不因限时催促做决定。','独立查证机构与项目资料。','请可信家人共同核对合同和收款方。']},
  {title:'刷单返利', example:'“先垫付一笔，完成任务就能拿回本金和佣金。”', signal:'先付款才能返还、不断追加任务', steps:['停止追加付款。','保存聊天与付款凭证。','向可信家人说明经过，再通过独立渠道核实。']},
  {title:'冒充客服', example:'“退款必须先转账，或者打开屏幕共享。”', signal:'退款却要求付款、索要验证码、共享屏幕', steps:['停止转账、共享屏幕和提供验证码。','从自己安装的购物平台进入官方订单客服。','核对真实订单，不使用对方发来的入口。']},
  {title:'虚假中奖与补贴', example:'“补贴已经到账，先点链接交手续费才能领取。”', signal:'陌生链接、先交费、索要账户密码', steps:['先不打开链接、不交费。','从独立查到的机构渠道核实活动。','把通知交给可信家人一起确认。']},
];
const checks=['我已通过原先保存的电话或独立渠道核实对方身份','我已核对付款用途、金额和收款账户，不是仅听对方承诺','我没有被要求保密、提供验证码或共享屏幕'];

export default function FraudSafetyCenter({onAnalyze}: {onAnalyze:(text:string)=>void}){
  const {settings}=useApp();
  const [scene,setScene]=useState('transfer');
  const [checked,setChecked]=useState<boolean[]>([false,false,false]);
  const [review,setReview]=useState(false);
  const [sceneContent,setSceneContent]=useState('');
  const [lesson,setLesson]=useState(0);
  const [speechStatus,setSpeechStatus]=useState('');
  useEffect(()=>()=>{window.speechSynthesis?.cancel();},[]);
  const contacts=settings.guardians.filter(g=>/^\+?[\d ()-]{5,25}$/.test(g.phone.trim()));
  function stopSpeech(){window.speechSynthesis?.cancel();setSpeechStatus('朗读已停止');}
  function listen(){
    if(!('speechSynthesis' in window)){setSpeechStatus('当前浏览器不支持朗读，请阅读下方文字。');return;}
    window.speechSynthesis.cancel();const item=lessons[lesson];
    const speech=new SpeechSynthesisUtterance(item.title+'。教学示例：'+item.example+'。留意：'+item.signal+'。三步核对：'+item.steps.join('。'));
    speech.lang='zh-CN';speech.rate=0.8;speech.onend=()=>setSpeechStatus('朗读结束');speech.onerror=()=>setSpeechStatus('朗读不可用，请阅读文字。');
    window.speechSynthesis.speak(speech);setSpeechStatus('正在朗读教学案例');
  }
  return <section className="panel" aria-label="反诈学习与操作前核对">
    <h2>先停一下，一起核对</h2>
    <p className="muted">在本页面主动核对。系统无法监控其他应用的付款、链接或来电。</p>
    <nav className="scenario-bar" aria-label="当前场景">{[['transfer','准备转账'],['call','陌生来电'],['link','准备点链接']].map(([id,title])=><button key={id} aria-pressed={scene===id} className={scene===id?'selected':''} onClick={()=>{setScene(id);setChecked([false,false,false]);setReview(false);}}>{title}</button>)}</nav>
    <p className="info-box">{scene==='transfer'?'先暂停转账，再核对身份、用途和收款方。':scene==='call'?'先不按对方指示操作。挂断后，用自己保存的号码或独立找到的渠道回拨核实。':'先不打开未知链接。不要在陌生页面填写账户密码或验证码，改从自己安装的应用或独立查到的入口核实。'}</p>
    <fieldset><legend>逐项确认，有疑问就先留空</legend>{checks.map((text,index)=><label key={text} style={{display:'flex',gap:12,padding:'12px 0',alignItems:'start'}}><input type="checkbox" checked={checked[index]} onChange={event=>{const next=[...checked];next[index]=event.target.checked;setChecked(next);setReview(false);}}/>{text}</label>)}</fieldset>
    <label className="field-label">对方说了什么、要求您做什么？<textarea value={sceneContent} maxLength={6000} rows={3} onChange={event=>setSceneContent(event.target.value)} placeholder="填写实际短信或通话内容，不要填写密码和验证码"/></label>
    <button className="button" disabled={!sceneContent.trim()} onClick={()=>{
      setReview(true);
      onAnalyze('当前场景：'+({transfer:'准备转账',call:'陌生来电',link:'准备打开链接'}[scene]||scene)+'。用户自查（只是用户陈述，不代表已核验）：'+checks.map((item,index)=>item+'：'+(checked[index]?'用户表示已核对':'尚未核对')).join('；')+'。待分析的实际内容：'+sceneContent.trim());
    }}>填入学校模型分析框</button>
    <p className="muted">核对下方输入内容后，点击“提交真实分析”才会请求学校模型；此处不会自动提交。</p>
    {review&&<p role="status" className="info-box">{checked.every(Boolean)?'您已完成这三项自查，但这不构成安全保证，也不代表系统批准付款。仍有疑问请先暂停，交给可信家人核对。':'还有事项未核实，建议保持暂停，不要因对方催促继续操作。可以把可疑文字交给下方模型分析。'}</p>}
    <details><summary>问问家人 · 手动联系</summary><p>选择后由设备拨号；系统不会自动发送分析或通知，也不能确认对方是否接听。</p>{contacts.length?contacts.map(g=><p key={g.id}>{g.name}（{g.relation}） <a className="button secondary" href={'tel:'+g.phone.replace(/[^\d+]/g,'')}>拨打已保存的号码</a></p>):<p>尚无可拨打的家属号码，请到设置添加可信联系人，或使用手机通讯录联系家人。</p>}</details>
    <details><summary>五类常见套路 · 每类三步核对</summary><nav className="scenario-bar">{lessons.map((item,index)=><button key={item.title} aria-pressed={lesson===index} onClick={()=>{stopSpeech();setLesson(index);}}>{item.title}</button>)}</nav><article><h3>{lessons[lesson].title}</h3><p>教学示例：{lessons[lesson].example}</p><p>留意：{lessons[lesson].signal}</p><ol>{lessons[lesson].steps.map(step=><li key={step}>{step}</li>)}</ol><button className="button secondary" onClick={listen}>慢速听案例</button> <button className="text-button" onClick={stopSpeech}>停止朗读</button><p role="status">{speechStatus}</p></article></details>
  </section>;
}

import { Alert, Settings, Scenario, Knowledge } from "../types";
export const today = new Date().toISOString().slice(0, 10);
export const fraudTypes = [
  "投资理财",
  "兼职刷单",
  "AI合成语音",
  "虚假征信",
  "冒充公检法",
  "虚假贷款",
  "网络购物",
  "游戏交易",
  "冒充客服",
  "婚恋交友",
];
export const defaultSettings: Settings = {
  name: "林晓",
  role: "青壮年",
  age: "28",
  job: "产品设计师",
  gender: "女",
  preference: 35,
  largeFont: false,
  guardians: [
    {
      id: "g1",
      name: "林女士",
      relation: "母亲",
      phone: "13800138000",
      isDefault: true,
    },
    {
      id: "g2",
      name: "陈先生",
      relation: "家人",
      phone: "13900139000",
      isDefault: false,
    },
  ],
};
export const scenarios: Scenario[] = [
  {
    id: "normal",
    name: "正常聊天",
    level: "low",
    type: "正常社交",
    confidence: 96,
    text: "周末一起去公园散步吧，下午三点在东门见。",
    reply: "这段对话属于日常社交，暂未发现转账诱导、身份冒充或异常链接。",
    advice: ["保持正常交流即可", "遇到涉及资金的新要求时，再次核实身份"],
    modality: "文本",
  },
  {
    id: "invest",
    name: "投资诈骗",
    level: "high",
    type: "投资理财",
    confidence: 98,
    text: "老师有内部投资渠道，保证每天收益 15%。今天转入 5000 元即可加入，名额有限，不要告诉家人。",
    reply:
      "发现“保证高额收益”“限时转账”和“隐瞒家人”三项风险信号，与投资理财诈骗案例高度相似。",
    advice: [
      "立即停止转账，不点击对方发送的链接",
      "通过官方渠道核验平台资质",
      "保留聊天与转账凭证，并联系可信任的家人",
    ],
    modality: "文本 + 图片",
  },
  {
    id: "voice",
    name: "AI语音诈骗",
    level: "high",
    type: "AI合成语音",
    confidence: 94,
    text: "妈，我手机坏了，现在借同事电话。急需两万元，先转到这个账号，千万别回拨。",
    reply:
      "发现冒充亲属、紧急汇款及拒绝回拨的组合风险。音频真伪结果为场景模拟，建议通过已有联系方式核实。",
    advice: [
      "挂断后拨打亲属原有号码核实",
      "使用只有双方知道的信息交叉验证",
      "不要仅凭熟悉的声音进行转账",
    ],
    modality: "音频 + 文本",
  },
  {
    id: "task",
    name: "刷单诈骗",
    level: "high",
    type: "兼职刷单",
    confidence: 97,
    text: "在家做任务日赚 800 元，先充值 300 元激活账号，完成三单后本金佣金一起返还。",
    reply: "发现“充值激活”“垫付本金”“高额佣金”等典型刷单返利诈骗信号。",
    advice: [
      "停止充值与垫付",
      "不要安装陌生人提供的应用",
      "保存招聘信息和聊天记录",
    ],
    modality: "图片 + 文本",
  },
];
export const initialAlerts: Alert[] = Array.from({ length: 8 }, (_, i) => {
  const s = scenarios[[1, 2, 3, 1, 0, 3, 2, 0][i]];
  const d = new Date();
  d.setDate(d.getDate() - Math.floor(i / 3));
  d.setHours(14 - i, 32 - i * 3, 0, 0);
  return {
    id: `a${i}`,
    level: i === 3 ? "medium" : s.level,
    type: s.type,
    summary: s.text,
    time: d.toISOString(),
    user: "林晓",
    handled: i > 2,
    confidence: s.confidence,
    advice: s.advice,
    evidence: s.reply,
    logs: i === 1 ? ["演示联动：林女士 · 未发送真实短信"] : [],
    modality: s.modality,
  };
});
export const initialKnowledge: Knowledge[] = fraudTypes.map((type, i) => ({
  id: `k${i}`,
  type,
  keywords: [
    "高收益 · 内部渠道 · 保本",
    "垫付 · 返佣 · 做任务",
    "紧急转账 · 拒绝回拨",
    "注销账户 · 征信修复",
    "安全账户 · 涉案调查 · 保密",
    "贷款手续费 · 解冻费 · 提现失败",
    "低价商品 · 私下付款 · 虚假物流",
    "账号交易 · 押金 · 解除冻结",
    "退费理赔 · 共享屏幕 · 会员扣费",
    "培养感情 · 投资引导 · 拒绝见面",
  ][i],
  count: 128 + i * 17,
  updated: today,
}));
export const trend = Array.from({ length: 7 }, (_, i) => {
  const d = new Date();
  d.setDate(d.getDate() - 6 + i);
  return {
    date: `${d.getMonth() + 1}/${d.getDate()}`,
    high: [5, 3, 6, 4, 2, 4, 3][i],
    medium: [8, 6, 9, 7, 5, 6, 4][i],
    checks: [32, 40, 35, 51, 43, 56, 48][i],
  };
});

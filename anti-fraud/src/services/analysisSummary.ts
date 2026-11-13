import type { Alert } from '../types';

export function analysisSummary(alert: Alert): string {
  const levels = { low: '低风险', medium: '中风险', high: '高风险' };
  return [
    '反诈核对摘要',
    alert.origin === 'backend' ? '模型辅助分析，非官方认定；低风险不代表安全。' : '演示样例，不代表真实模型分析。',
    `风险：${levels[alert.level]} · ${alert.type}`,
    ...(alert.assessment === 'needs_review' ? ['当前结论需要进一步核实。'] : []),
    `分析依据：${alert.evidence}`,
    '建议：', ...alert.advice.map((item, index) => `${index + 1}. ${item}`),
    '引用案例：', ...(alert.sources?.length ? alert.sources.map(item => item.title) : ['无案例检索支撑']),
    '本摘要未包含原始聊天、姓名、联系方式或处置日志；分析文字仍可能含个人信息，请核对后再分享。',
  ].join('\n');
}

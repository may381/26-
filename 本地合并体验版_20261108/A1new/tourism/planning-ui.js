'use strict';
function travelDraftSummary(draft){
 const lines=[draft.title||'出游计划','建议草案，尚未预订；开放时间、无障碍条件及交通需出发前核实。'];
 for(const [index,day] of (draft.days||[]).entries()){
  lines.push('', '第'+(index+1)+'天 · '+day.date,(day.places||[]).map(p=>p.name).join(' → ')||'尚未选择地点');
  if(scheduledDay(day))for(const slot of compactSchedule(day.timeline)){
   const duration=slot.visitMinutes!=null?'游玩'+slot.visitMinutes+'分钟，休息'+slot.restMinutes+'分钟':slot.minutes!=null?slot.minutes+'分钟':'耗时待确认';
   lines.push((slot.start?(slot.start+(slot.end?'–'+slot.end:'')):'钟点待确认')+' '+slot.title+'（'+duration+'）'+(slot.evidence==='AMAP_ESTIMATE'?' [地图估算]':slot.evidence==='UNCONFIRMED'?' [待核实]':''));
   if(slot.note)lines.push('  '+slot.note);
  }else lines.push('地点已变化或缺少时间安排，请保存草案重新计算。');
  for(const reason of day.reasons||[])lines.push('安排说明：'+reason);
 }
 return lines.join('\n');
}
function scheduledDay(day){const ids=[...new Set((day.timeline||[]).filter(s=>s.kind==='visit').map(s=>s.placeId))];return Array.isArray(day.timeline)&&ids.join('|')===day.places.map(p=>p.id).join('|');}
function planEvidence(day){const box=node('details',null,'plan-evidence');box.append(node('summary','为什么这样安排 · 待确认事项'));for(const reason of day.reasons||[])box.append(node('p',reason));return box;}
function compactSchedule(slots){const rows=[];for(let i=0;i<slots.length;i++){const first=slots[i];if(first.kind!=='visit'){rows.push(first);continue;}const row={...first,visitMinutes:first.minutes||0,restMinutes:0};while(i+1<slots.length&&slots[i+1].placeId===first.placeId&&['visit','rest'].includes(slots[i+1].kind)){const next=slots[++i];if(next.kind==='visit')row.visitMinutes+=next.minutes||0;else row.restMinutes+=next.minutes||0;row.end=next.end;}row.note='建议分段游玩、间歇坐下休息；开放时间与休息座椅尚未核实。';rows.push(row);}return rows;}
function scheduleView(day){const section=node('section',null,'schedule-view');section.append(node('h3','当天时间安排'));
 if(!scheduledDay(day)){section.append(node('p','地点已变化或这是旧版草案，请保存以重新计算游玩、休息和交通时间。','schedule-note'));return section;}
 const labels={visit:'游玩建议',rest:'休息建议',meal:'用餐建议',transport:'交通',free:'弹性时间'};
 for(const slot of compactSchedule(day.timeline)){const row=node('article',null,'schedule-slot schedule-'+slot.kind);const time=node('span',slot.start?(slot.start+(slot.end?'–'+slot.end:'')):'钟点待确认','schedule-clock');const body=node('div');body.append(node('span',slot.evidence==='AMAP_ESTIMATE'?'高德估算':slot.evidence==='UNCONFIRMED'?'待确认':labels[slot.kind]||'建议安排','schedule-label'));
 const title=slot.kind==='visit'?choiceButton(slot.title,()=>window.focusTripPlace?.(slot.placeId)):node('strong',slot.title);body.append(title);
 const mode={walking:'步行',driving:'驾车 / 打车',transit:'公共交通'}[slot.mode];body.append(node('p',(mode?mode+' · ':'')+(slot.visitMinutes!=null?'游玩 '+slot.visitMinutes+' 分钟 · 休息 '+slot.restMinutes+' 分钟':slot.minutes!=null?slot.minutes+' 分钟':'耗时待确认')+(slot.distance!=null?' · '+(slot.distance/1000).toFixed(1)+' 公里':'')));
 body.append(node('p',slot.note,'schedule-note'));row.append(time,body);section.append(row);}
 section.append(planEvidence(day));return section;}
function stopScheduleLabel(day,id){if(!scheduledDay(day))return '地点已变化 · 保存后重新计算时间';const slots=day.timeline.filter(s=>s.kind==='visit'&&s.placeId===id);if(!slots.length)return '时间待安排';const first=slots[0],last=slots.at(-1);return first.start&&last.end?first.start+'–'+last.end+' 建议游玩（另有休息安排）':'建议游玩 '+slots.reduce((n,s)=>n+(s.minutes||0),0)+' 分钟 · 到达钟点待确认';}

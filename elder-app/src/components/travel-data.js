import {reactive} from 'vue'

// 本地演示数据（后端不可用时兜底），结构与后端适配后的 routes 一致。
const localRoutes=[{name:'轻松湖畔线',minutes:40,km:'1.2',terrain:'平缓为主',stairs:'无台阶',seats:3,toilets:2,desc:'沿湖慢走，途中可随时休息。',stops:['公园入口 · 出发','湖畔步道 · 慢走赏景','林荫休息点 · 坐下歇一会儿','返回入口 · 结束游览'],notes:['从公园入口开始，步入湖畔线路。','沿湖慢走，欣赏湖景与绿荫。','在树荫下的休息点稍作休息。','按原路返回入口，完成本次游览。']},{name:'绿荫漫步线',minutes:60,km:'1.8',terrain:'平缓为主',stairs:'少量台阶',seats:4,toilets:2,desc:'穿行在绿荫之间，享受清新自然。',stops:['公园入口 · 出发','绿荫步道 · 慢走赏景','林荫休息点 · 稍作休息','返回入口 · 结束游览'],notes:['从公园入口开始游览。','沿绿荫步道散步。','在沿途休息点坐下歇一会儿。','返回入口，结束本次游览。']},{name:'文化探索线',minutes:90,km:'2.6',terrain:'部分坡道',stairs:'有台阶',seats:5,toilets:3,desc:'游览主要景点，感受公园人文风光。',stops:['公园入口 · 出发','文化景点 · 了解人文','沿途休息点 · 稍作休息','返回入口 · 结束游览'],notes:['从公园入口开始游览。','按路线参观文化景点。','根据自己的体力安排休息。','返回入口，结束本次游览。']}]
localRoutes.forEach((r,id)=>{r.id=id;r.stations=r.stops.map((name,i)=>({id:i,name,at:Math.round(r.minutes*[0,.25,.625,1][i]),kind:i===2?'休息段':'步行段',text:r.notes[i]}))})

const localFacilities={厕所:[['湖畔公共厕所','约120米 · 步行约3分钟'],['公园入口公共厕所','约350米 · 步行约8分钟']],休息点:[['林荫休息点','约80米 · 步行约2分钟']],出口:[['公园入口','沿当前步道返回入口']],医务室:[['景区医务室','请联系工作人员核实位置']]}

const clone=value=>JSON.parse(JSON.stringify(value))

// 页面直接读 routes / facilities，用 reactive 保证后端数据到达后模板跟着更新。
export const routes=reactive(clone(localRoutes))
export const facilities=reactive(clone(localFacilities))

export function setServerRoutes(list){
  if(!Array.isArray(list)||!list.length)return false
  routes.splice(0,routes.length,...list)
  return true
}

export function resetRoutes(){
  routes.splice(0,routes.length,...clone(localRoutes))
}

// groups: {厕所:[[名称,说明]],休息点:[],出口:[],医务室:[],服务台:[]}
export function setServerFacilities(groups){
  if(!groups)return false
  Object.keys(facilities).forEach(key=>{facilities[key].splice(0,facilities[key].length)})
  Object.keys(groups).forEach(key=>{
    if(!facilities[key])facilities[key]=[]
    facilities[key].splice(0,facilities[key].length,...groups[key])
  })
  return true
}

export function resetFacilities(){
  Object.keys(localFacilities).forEach(key=>{
    if(!facilities[key])facilities[key]=[]
    facilities[key].splice(0,facilities[key].length,...clone(localFacilities[key]))
  })
}

export function clockAt(clock,at){const [h,m]=clock.split(':').map(Number);const total=(h*60+m+at)%1440;return String(Math.floor(total/60)).padStart(2,'0')+':'+String(total%60).padStart(2,'0')}
export function recommended(plan,pref){
  const flagged=routes.findIndex(r=>r.backend&&r.recommended)
  if(flagged>=0)return flagged
  if(plan?.energy==='有点累')return 0
  const duration=plan?.duration||Number(pref?.walkDuration)||40
  return duration<=40?0:duration<=60?1:2
}
export function recommendation(route,plan,pref){
  if(route?.backend&&route.reason)return route.reason
  const reasons=[]
  if(plan?.duration&&route.minutes>plan.duration)reasons.push('比您想逛的时间长约 '+(route.minutes-plan.duration)+' 分钟')
  if(route.stairs!=='无台阶')reasons.push(route.stairs)
  if(route.id===recommended(plan,pref))reasons.push(plan?.energy==='有点累'?'今天有点累，优先选择较短路线':plan?'按本次时长安排':pref?'参考已保存的步行习惯':'可先了解路线，再按体力选择')
  if(pref?.interests?.length)reasons.push('您喜欢'+pref.interests.join('、'))
  return reasons.join('；')||'可按自己的体力选择'
}

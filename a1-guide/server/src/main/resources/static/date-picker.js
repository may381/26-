'use strict';
function renderTravelDates(state,card){
 const today=planDateLocal(),dayMs=86400000;
 const dayNumber=s=>Date.parse(s+'T00:00:00Z')/dayMs;
 const plusDays=(s,n)=>new Date((dayNumber(s)+n)*dayMs).toISOString().slice(0,10);
 let mode='range',start=state.startDate||today,end=null,choosingEnd=false;
 let [year,month]=start.split('-').map(Number);month--;
 const panel=node('section',null,'travel-date-picker');card.append(panel);
 const announce=node('p','','date-announcement');announce.setAttribute('role','status');
 const finish=choiceButton('确认日期',()=>{
  if(!end){announce.textContent='请再选返程日期，当天往返可再次点击同一天。';return;}
  state.startDate=start;state.days=dayNumber(end)-dayNumber(start)+1;state.dateConfirmed=true;state.step=2;
  const label=start===end?start:start+' — '+end;
  card.replaceChildren(node('p','出游日期：'+label+' · '+state.days+'天'));message(label,{mine:true});showWizard();
 });finish.className='wizard-primary';
 function draw(){
  panel.replaceChildren();
  const tabs=node('div',null,'date-mode-tabs');tabs.setAttribute('role','group');tabs.setAttribute('aria-label','日期选择方式');
  for(const [value,label] of [['range','具体日期'],['flex','灵活的天数']]){const b=choiceButton(label,()=>{mode=value;if(mode==='flex'){end=plusDays(start,state.days-1);choosingEnd=false;}draw();});b.setAttribute('aria-pressed',String(mode===value));tabs.append(b);}panel.append(tabs);
  const summary=node('div',null,'date-range-summary');
  summary.append(node('span',start.slice(5).replace('-','月')+'日 出发'),node('span',end?end.slice(5).replace('-','月')+'日 返回':'请选择返程日期'));panel.append(summary);
  if(mode==='flex'){
   const options=node('div',null,'date-duration-options');
   for(let days=1;days<=4;days++){const b=choiceButton(days+'天',()=>{state.days=days;end=plusDays(start,days-1);draw();});b.setAttribute('aria-pressed',String(state.days===days));options.append(b);}panel.append(options);
   const label=node('label','预计出发日期（之后可以修改）');label.className='date-flex-label';const input=node('input');input.type='date';input.min=today;input.value=start;input.setAttribute('aria-label','预计出发日期');input.onchange=()=>{if(input.value>=today){start=input.value;end=plusDays(start,state.days-1);draw();}};panel.append(label,input);
  }else{
   const header=node('div',null,'calendar-header');
   const previous=choiceButton('‹',()=>{month--;if(month<0){month=11;year--;}draw();});const next=choiceButton('›',()=>{month++;if(month>11){month=0;year++;}draw();});
   previous.setAttribute('aria-label','上个月');next.setAttribute('aria-label','下个月');previous.disabled=year*12+month<=Number(today.slice(0,4))*12+Number(today.slice(5,7))-1;
   header.append(previous,node('strong',year+'年'+(month+1)+'月'),next);panel.append(header);
   const grid=node('div',null,'calendar-grid range-calendar'+(end?' range-complete':''));
   for(const title of ['日','一','二','三','四','五','六'])grid.append(node('span',title,'weekday'));
   const first=new Date(Date.UTC(year,month,1)).getUTCDay(),count=new Date(Date.UTC(year,month+1,0)).getUTCDate();
   const cells=Math.ceil((first+count)/7)*7;
   for(let cell=0;cell<cells;cell++){
    const value=new Date(Date.UTC(year,month,cell-first+1)).toISOString().slice(0,10),day=Number(value.slice(-2));
    const b=choiceButton(String(day),()=>{
     if(!choosingEnd){start=value;end=null;choosingEnd=true;announce.textContent='已选出发日期，请选择返程日期，最多4天。';}
     else if(value<start){start=value;end=null;announce.textContent='已更新出发日期，请再选返程日期。';}
     else if(dayNumber(value)-dayNumber(start)>3){announce.textContent='当前最多支持4天，请选择'+plusDays(start,3)+'或更早返程。';return;}
     else{end=value;state.days=dayNumber(end)-dayNumber(start)+1;choosingEnd=false;announce.textContent='已选择'+state.days+'天，再次点击可重新选日期。';}
     draw();
    });
    b.setAttribute('aria-label',value+(value===today?' 今天':''));b.setAttribute('aria-pressed',String(value===start||value===end));
    b.classList.toggle('outside-month',value.slice(0,7)!==year+'-'+String(month+1).padStart(2,'0'));
    b.classList.toggle('is-today',value===today);b.classList.toggle('range-start',value===start);b.classList.toggle('range-end',value===end);b.classList.toggle('in-range',!!end&&value>start&&value<end);
    b.disabled=value<today;grid.append(b);
   }panel.append(grid);
  }
  panel.append(node('p','最多4天 · 包含出发与返程当天','date-picker-hint'));
  finish.disabled=!end;finish.textContent=end?'确认 · '+(dayNumber(end)-dayNumber(start)+1)+'天':'请选择返程日期';
 }
 draw();card.append(announce,finish);
}

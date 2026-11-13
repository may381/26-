'use strict';
// Drawer actions stay outside the scrolling itinerary so they remain reachable.
const planDock=document.createElement('nav');
planDock.className='plan-dock';planDock.setAttribute('aria-label','计划操作');
function planAction(label,action,cls=''){const b=document.createElement('button');b.type='button';b.textContent=label;b.className=cls;b.onclick=action;return b;}
planDock.append(planAction('＋ 添加',()=>{const section=document.querySelector('#draft-detail .draft-editing');if(!section){showToast('请先选择具体日期');return;}section.open=true;window.setTripSheet(.86);section.scrollIntoView({block:'nearest'});section.querySelector('input')?.focus();}),
planAction('编辑',()=>{const list=[...document.querySelectorAll('#draft-detail .stop-edit-details')];if(!list.length){showToast('请先选择有地点的日期');return;}const open=!list[0].open;list.forEach(d=>d.open=open);window.setTripSheet(.86);}),
planAction('问小颐',()=>{draftDialog.close();input.value='请帮我看看这份'+(travelDraft?.preferences.destination||'')+'出游草案，我想调整：';input.focus();resizeInput();},'plan-ask'));
document.querySelector('#draft-sheet').append(planDock);

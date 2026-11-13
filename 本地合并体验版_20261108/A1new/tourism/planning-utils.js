'use strict';
function numericEstimate(value){
 if(typeof value!=='number'&&typeof value!=='string')return null;
 if(typeof value==='string'&&!value.trim())return null;
 const number=Number(value);
 return Number.isFinite(number)&&number>=0?number:null;
}

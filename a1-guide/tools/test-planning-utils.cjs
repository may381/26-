const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const context={};vm.createContext(context);
vm.runInContext(fs.readFileSync('server/src/main/resources/static/planning-utils.js','utf8'),context);
for(const value of [undefined,null,'',' ',[],{},true,false,'unknown',-1,'-1',Infinity,'Infinity'])assert.equal(context.numericEstimate(value),null);
for(const [value,expected] of [[0,0],['0',0],[' 1500 ',1500],[180,180],['12.5',12.5]])assert.equal(context.numericEstimate(value),expected);
console.log('18 transport numeric evidence checks passed');

const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict');
const output={};new Function('exports',ts.transpileModule(fs.readFileSync('src/services/analysisSummary.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(output);
const data={origin:'backend',level:'low',type:'通知核对',evidence:'未发现明显催促',advice:['独立核实'],assessment:'needs_review',summary:'PRIVATE ORIGINAL',user:'PRIVATE NAME',logs:['PRIVATE LOG'],sources:[]};
const result=output.analysisSummary(data);
assert(result.includes('低风险不代表安全'));assert(result.includes('需要进一步核实'));assert(result.includes('无案例检索支撑'));
assert(!result.includes('PRIVATE'));assert(output.analysisSummary({...data,origin:undefined}).includes('演示样例'));
console.log('PASS: analysis summary excludes raw input and preserves uncertainty');

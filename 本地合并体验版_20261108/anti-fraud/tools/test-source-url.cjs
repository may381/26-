const fs=require('fs'),ts=require('typescript'),exportsObject={};
new Function('exports',ts.transpileModule(fs.readFileSync('src/services/sourceUrl.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(exportsObject);
for(const value of ['javascript:alert(1)','data:text/html,test','file:///C:/test','manual source','https://user:pass@example.com',' https://example.com']){
 if(exportsObject.safeSourceUrl(value)!==undefined)throw Error('unsafe source URL accepted');
}
if(exportsObject.safeSourceUrl('https://www.spp.gov.cn/')!=='https://www.spp.gov.cn/')throw Error('valid URL rejected');
console.log('7 source URL checks passed');

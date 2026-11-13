const fs=require('fs'),ts=require('typescript'),exportsObject={};
new Function('exports',ts.transpileModule(fs.readFileSync('src/services/csv.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(exportsObject);
for(const value of ['=1+1','+cmd','-1+1','@SUM(1)','  =1','\t=1']) {
 if(!exportsObject.csvCell(value).startsWith('"\''))throw Error('formula not escaped');
}
if(exportsObject.csvCell('normal')!=='"normal"')throw Error('ordinary value changed');
console.log('7 CSV export checks passed');

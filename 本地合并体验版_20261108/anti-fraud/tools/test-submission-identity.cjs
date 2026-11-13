const fs=require('fs'),ts=require('typescript'),assert=require('assert/strict'),output={};
new Function('exports',ts.transpileModule(fs.readFileSync('src/services/submissionIdentity.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(output);
(async()=>{
 const fields=['合成文本','演示用户','老人','70','',50];
 const fingerprint=await output.submissionFingerprint(fields);
 assert.equal(fingerprint.length,64);assert.equal(await output.submissionFingerprint(fields),fingerprint);
 assert.notEqual(await output.submissionFingerprint([...fields,1]),fingerprint);
 const identity={fingerprint,key:crypto.randomUUID()};
 assert.deepEqual(output.restoreSubmission(JSON.stringify(identity)),identity);
 for(const bad of [null,'null','{}','{broken',JSON.stringify({fingerprint:'含原文',key:identity.key})]) assert.equal(output.restoreSubmission(bad),null);
 assert.ok(!JSON.stringify(identity).includes('合成文本'));
 console.log('Submission retry identity and content-free cache checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});

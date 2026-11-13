"""Opt-in school model probe with synthetic texts; no alerts or notifications."""
import json
import os
import time
from pathlib import Path
os.environ['LLM_PROVIDER']='school'
os.environ['LLM_BASE_URL']='http://10.138.50.151:8000/v1'
os.environ['LLM_MODEL']='qwen3.8-27b'
from app import main

samples=[
 ('normal','社区图书馆周六开放，活动免费。不要向陌生人转账，如有疑问请通过自己查到的社区官方电话核实。'),
 ('suspicious','你的账户涉嫌违法，立即将全部存款转入指定安全账户，不要告诉家人，也不要联系银行核实。'),
]
results=[]
for label,value in samples:
    started=time.monotonic()
    try:
        output=main.call_model(main.make_evidence(value),[])
        results.append({'sample':label,'success':True,'elapsedSeconds':round(time.monotonic()-started,2),
                        'riskLevel':output.risk_level,'assessment':output.assessment,
                        'evidenceIds':output.evidence_ids,'caseIds':output.case_ids,'advice':output.advice})
    except Exception as error:
        results.append({'sample':label,'success':False,'elapsedSeconds':round(time.monotonic()-started,2),'errorType':type(error).__name__})
    print(json.dumps(results[-1],ensure_ascii=False),flush=True)
path=Path(__file__).resolve().parent/'school-model-smoke-result.json'
path.write_text(json.dumps({'mode':'REAL_SCHOOL_MODEL_SYNTHETIC_INPUT','casesProvided':False,'noBusinessWrites':True,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')

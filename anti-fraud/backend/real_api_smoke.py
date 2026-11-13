"""Real model + FastAPI lifecycle test, without opening a listening server.
Uses a temporary database and synthetic text; no guardian notification calls.
"""
import json
import os
import tempfile
import time
from pathlib import Path
os.environ['LLM_PROVIDER']='school'
os.environ['LLM_BASE_URL']='http://10.138.50.151:8000/v1'
os.environ['LLM_MODEL']='qwen3.8-27b'
from sqlalchemy import create_engine
from fastapi.testclient import TestClient
from app import main

root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='asgi-smoke-',dir=root) as directory:
    original=main.engine
    main.engine=create_engine('sqlite:///'+(Path(directory)/'smoke.db').as_posix(),connect_args={'check_same_thread':False})
    try:
        with TestClient(main.app) as client:
            body={'text':'对方说我的账户涉案，要求把存款转入指定安全账户，不要告诉家人，也不要联系银行核实。','username':'合成验收用户'}
            headers={'Idempotency-Key':'contest-asgi-synthetic-001'}
            response=client.post('/api/analyses',json=body,headers=headers)
            assert response.status_code==202,response.text
            identity=response.json()['analysis_id']
            assert client.post('/api/analyses',json=body,headers=headers).json()['analysis_id']==identity
            started=time.monotonic()
            while time.monotonic()-started<240:
                task=client.get('/api/analyses/'+identity).json()
                if task['status'] not in ('queued','processing'):break
                time.sleep(.5)
            assert task['status']=='completed',task.get('error')
            result=task['result']
            assert result['origin']=='backend' and result['evidenceItems']
            alerts=client.get('/api/alerts').json()
            assert len(alerts)==1,'duplicate alert'
            report={'mode':'REAL_SCHOOL_MODEL_FASTAPI_ASGI','listeningServerStarted':False,'temporaryDatabase':True,
                    'status':task['status'],'riskLevel':result['level'],'evidenceCount':len(result['evidenceItems']),
                    'caseCitationCount':len(result['sources']),'duplicateReturnedSameJob':True,
                    'alertCount':len(alerts),'notificationRequested':False,'elapsedSeconds':round(time.monotonic()-started,2)}
            (root/'school-api-smoke-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    finally:
        main.engine.dispose()
        main.engine=original

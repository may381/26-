import json
import time
import uuid
import pytest
from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient
from app import main

@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + (tmp_path / "test.db").as_posix(), connect_args={"check_same_thread": False})
    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(main, "configured", lambda: True)
    monkeypatch.setattr(main, "model_ready", lambda: True)
    monkeypatch.setattr(main, "embedding_model_ready", lambda: False)
    monkeypatch.setattr(main, "call_model", lambda e, c, profile=None, memory=None: main.ModelResult(
        risk_level="high", assessment="assessed", fraud_type="投资理财",
        explanation="测试桩结论，不代表真实模型效果", evidence_ids=[e[0]["id"]],
        case_ids=[c[0]["id"]] if c else [], advice=["暂停操作并核实"]))
    with TestClient(main.app) as instance:
        yield instance
    engine.dispose()

def submit(client, value="保证投资高收益，转账入金", key=None):
    return client.post("/api/analyses", json={"text": value}, headers={"Idempotency-Key": key or str(uuid.uuid4())})

def wait(client, identity):
    for _ in range(60):
        job = client.get("/api/analyses/" + identity).json()
        if job["status"] not in ("queued", "processing"):
            return job
        time.sleep(.05)
    raise AssertionError("worker did not complete")

def test_persist_evidence_citations_and_handled(client):
    identity = submit(client).json()["analysis_id"]
    job = wait(client, identity)
    assert job["status"] == "completed"
    assert job["result"]["sources"][0]["source"].startswith("https://www.spp.gov.cn/")
    evidence = job["result"]["evidenceItems"][0]
    assert job["result"]["summary"][evidence["start"]:evidence["end"]] == evidence["excerpt"]
    assert client.post("/api/alerts/handle", json={"ids":[identity]}).status_code == 200
    main.init_db()
    assert client.get("/api/alerts").json()[0]["handled"] is True

def test_completed_result_keeps_source_evidence_when_model_ids_are_empty(client, monkeypatch):
    monkeypatch.setattr(main, "call_model", lambda e, c, profile=None, memory=None: main.ModelResult(
        risk_level="medium", assessment="needs_review", fraud_type="信息不足",
        explanation="需要补充对方身份和转账原因", evidence_ids=[], case_ids=[],
        advice=["暂停转账并核实身份"]))
    original = "有人让我转钱，但我不知道他是谁。"
    job = wait(client, submit(client, original).json()["analysis_id"])
    assert job["status"] == "completed"
    evidence = job["result"]["evidenceItems"]
    assert evidence and original[evidence[0]["start"]:evidence[0]["end"]] == evidence[0]["excerpt"]

def test_idempotency_and_conflict(client):
    key = str(uuid.uuid4())
    first = submit(client, key=key)
    second = submit(client, key=key)
    assert first.json() == second.json()
    assert submit(client, "不同输入", key).status_code == 409
    wait(client, first.json()["analysis_id"])
    assert len(client.get("/api/alerts").json()) == 1

def test_missing_configuration_creates_no_alert(client, monkeypatch):
    monkeypatch.setattr(main, "configured", lambda: False)
    assert submit(client).status_code == 503
    assert client.get("/api/alerts").json() == []

def test_local_ollama_does_not_require_api_key(monkeypatch):
    monkeypatch.setattr(main, "configuration", lambda: {
        "LLM_PROVIDER":"ollama", "LLM_BASE_URL":"http://127.0.0.1:11434/v1",
        "LLM_API_KEY":"", "LLM_MODEL":"qwen3.5:4b"
    })
    assert main.configured() is True

def test_image_analysis_is_saved_as_real_alert(client, monkeypatch):
    monkeypatch.setattr(main, "prepare_image_data_url", lambda binary: "data:image/jpeg;base64,dGVzdA==")
    monkeypatch.setattr(main, "call_image_model", lambda image, note, profile=None, memory=None: (
        main.ImageModelResult(risk_level="high", assessment="assessed", fraud_type="冒充公检法",
            explanation="图片含安全账户转账要求", observed_text=["转入安全账户"],
            case_ids=[], advice=["立即停止转账"]),
        [{k:v for k,v in case.items() if k != "keywords"} for case in main.CASES]
    ))
    response = client.post("/api/image-analyses", json={
        "image_data_url":"data:image/png;base64,iVBORw0KGgo=", "note":"测试图片", "username":"测试用户"
    })
    assert response.status_code == 200
    assert response.json()["modality"] == "图片"
    assert response.json()["evidenceItems"][0]["excerpt"] == "转入安全账户"
    assert client.get("/api/alerts").json()[0]["id"].startswith("image-")

def test_multimodal_fusion_persists_one_combined_alert(client, monkeypatch):
    monkeypatch.setattr(main, "prepare_image_data_url", lambda binary: "data:image/jpeg;base64,dGVzdA==")
    monkeypatch.setattr(main, "call_image_model", lambda image, note, profile=None, memory=None: (
        main.ImageModelResult(risk_level="high", assessment="assessed", fraud_type="兼职刷单",
            explanation="图片要求先垫资", observed_text=["完成任务后返佣"], case_ids=[], advice=["停止付款"]), []))
    monkeypatch.setattr(main, "transcribe_audio", lambda path: (
        [{"id":"audio-e0","excerpt":"请先充值完成任务","start":0.0,"end":2.0}], 2.0, "zh"))
    response = client.post("/api/multimodal-analyses", data={
        "text_input":"对方说做完平台任务会发奖励", "username":"测试用户", "profile":"{}"
    }, files={
        "image":("shot.png", b"fake-image", "image/png"),
        "audio":("voice.wav", b"fake-audio" * 20, "audio/wav")
    })
    assert response.status_code == 200
    body = response.json()
    assert body["id"].startswith("fusion-")
    assert body["modality"] == "文本 + 图片 + 音频"
    assert body["transcript"] == "请先充值完成任务"
    assert body["imageObservedText"] == ["完成任务后返佣"]
    assert body["fusionStrategy"].startswith("分模态提取证据")
    assert len(client.get("/api/alerts").json()) == 1

def test_provider_failure_does_not_fallback(client, monkeypatch):
    def fail(*args):
        raise RuntimeError("secret-provider-body")
    monkeypatch.setattr(main, "call_model", fail)
    identity = submit(client).json()["analysis_id"]
    result = wait(client, identity)
    assert result["status"] == "failed"
    assert "secret" not in result["error"]
    assert client.get("/api/alerts").json() == []

def test_reject_empty_and_oversized(client):
    assert submit(client, "   ").status_code == 422
    assert submit(client, "字" * 10001).status_code == 422

def test_no_irrelevant_retrieval_and_unicode_offsets():
    assert main.retrieve("周末公园见") == []
    value = "😀你好。请先转账！"
    assert all(value[e["start"]:e["end"]] == e["excerpt"] for e in main.make_evidence(value))

def test_interrupted_recovery(client):
    with main.engine.begin() as db:
        db.execute(text("INSERT INTO jobs(id,request_key,fingerprint,input,username,status,result,error,created,profile) VALUES ('restart','restart-key','hash','input','user','processing',NULL,NULL,'time','{}')"))
    main.init_db()
    assert client.get("/api/analyses/restart").json()["status"] == "interrupted"

def test_cross_site_origin_rejected(client):
    assert client.post("/api/alerts/handle", json={"ids":[]}, headers={"Origin":"https://unrelated.example"}).status_code == 403

def test_model_rejects_invented_evidence(monkeypatch):
    monkeypatch.setattr(main, "configuration", lambda: {"LLM_PROVIDER":"test","LLM_BASE_URL":"https://test.invalid/v1","LLM_API_KEY":"test","LLM_MODEL":"test"})
    class Response:
        def raise_for_status(self): pass
        def json(self):
            return {"choices":[{"message":{"content":json.dumps({
                "risk_level":"high","assessment":"assessed","fraud_type":"投资理财",
                "explanation":"test","evidence_ids":["invented"],"case_ids":[],"advice":["核实"]
            })}}]}
    class Client:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, *args, **kwargs): return Response()
    monkeypatch.setattr(main.httpx, "Client", Client)
    with pytest.raises(ValueError, match="INVALID_EVIDENCE"):
        main.call_model(main.make_evidence("测试"), [])

def test_guardian_notification_is_persisted(client):
    identity = submit(client).json()["analysis_id"]
    wait(client, identity)
    response = client.post(f"/api/alerts/{identity}/notify", json={"guardians":["林女士"]})
    assert response.status_code == 200
    assert "未发送真实短信" in response.json()["logs"][0]
    assert client.get("/api/alerts").json()[0]["logs"]

def test_knowledge_ingest_deduplicates_and_reports_counts(client):
    payload = {"fraud_type":"兼职刷单", "content":"先充值完成任务，承诺完成后返还本金与高额佣金。", "source_name":"test.txt"}
    first = client.post("/api/knowledge", json=payload)
    assert first.status_code == 201
    assert first.json()["cleaned"] is True
    assert client.post("/api/knowledge", json=payload).status_code == 409
    stats = client.get("/api/knowledge").json()
    assert stats["user_count"] == 1
    assert stats["groups"][0]["fraud_type"] == "兼职刷单"
    retrieved = main.retrieve("对方让我先充值做刷单任务，再返还佣金")
    assert any(item["id"].startswith("case-") for item in retrieved)

def test_ollama_text_configuration_allows_empty_key(monkeypatch):
    monkeypatch.setattr(main, "configuration", lambda: {
        "LLM_PROVIDER":"ollama", "LLM_BASE_URL":"http://127.0.0.1:11434/v1",
        "LLM_API_KEY":"", "LLM_MODEL":"qwen3.5:4b"
    })
    assert main.configured() is True

def test_profile_is_persisted_and_passed_to_model(client, monkeypatch):
    captured = {}
    def analyze(evidence, cases, profile=None, memory=None):
        captured["profile"] = profile
        captured["memory"] = memory
        return main.ModelResult(risk_level="medium", assessment="needs_review", fraud_type="游戏交易",
            explanation="学生用户遇到游戏交易资金要求，应进一步核实", evidence_ids=[evidence[0]["id"]],
            case_ids=[], advice=["联系家长并通过官方平台核实"])
    monkeypatch.setattr(main, "call_model", analyze)
    response = client.post("/api/analyses", json={"text":"购买游戏账号需要先交押金", "username":"小林",
        "profile":{"role":"儿童","age":"15","job":"学生","preference":20}},
        headers={"Idempotency-Key":str(uuid.uuid4())})
    result = wait(client, response.json()["analysis_id"])
    assert result["result"]["profile"]["role"] == "儿童"
    assert captured["profile"]["preference"] == 20
    assert isinstance(captured["memory"], list)

def test_rule_evaluation_produces_traceable_metrics(client):
    cases = client.get("/api/evaluation-cases").json()
    assert len(cases) == 20
    assert sum(case["label"] == "fraud" for case in cases) == 10
    assert len({case["type"] for case in cases if case["label"] == "fraud"}) == 10
    assert sum(case["modality"] == "image" for case in cases) == 4
    assert sum(case["modality"] == "audio" for case in cases) == 4
    image = next(case for case in cases if case["modality"] == "image")
    assert client.get(image["asset_url"]).status_code == 200
    created = client.post("/api/evaluations", json={"mode":"rules"})
    assert created.status_code == 202
    identity = created.json()["evaluation_id"]
    for _ in range(50):
        run = client.get("/api/evaluations/" + identity).json()
        if run["status"] != "running":
            break
        time.sleep(.02)
    assert run["status"] == "completed"
    assert len(run["result"]["items"]) == 20
    metrics = run["result"]["metrics"]
    assert metrics["tp"] + metrics["tn"] + metrics["fp"] + metrics["fn"] == 20
    assert 0 <= metrics["f1"] <= 1
    assert run["result"]["dataset"] == {"total":20, "fraud":10, "normal":10, "fraud_types":10}
    assert set(run["result"]["modality_metrics"]) == {"text", "image", "audio"}
    assert sum(item["total"] for item in run["result"]["modality_metrics"].values()) == 20

def test_knowledge_crud_and_retrieval_preview(client):
    created = client.post("/api/knowledge", json={"fraud_type":"虚假贷款","content":"贷款提现前需要缴纳解冻费，否则账户将被冻结。","source_name":"case.txt"})
    identity = created.json()["id"]
    listed = client.get("/api/knowledge/cases?query=解冻费").json()
    assert listed[0]["id"] == identity
    assert client.put(f"/api/knowledge/cases/{identity}", json={"fraud_type":"虚假贷款","content":"贷款提现前要求支付手续费和解冻费，这是可疑话术。"}).status_code == 200
    preview = client.post("/api/knowledge/retrieve", json={"text":"贷款无法提现，需要先交解冻费"}).json()
    assert preview["items"]
    assert client.delete(f"/api/knowledge/cases/{identity}").status_code == 200
    assert client.get("/api/knowledge/cases").json() == []

def test_hybrid_rag_returns_semantic_match_with_scores(client, monkeypatch):
    with main.engine.begin() as db:
        db.execute(text("""INSERT INTO knowledge_chunks
            (id,case_id,fraud_type,content,source_name,content_hash,embedding_model,embedding,created)
            VALUES ('chunk-1','semantic-case','兼职刷单','完成平台任务前要求先垫资，随后承诺发放报酬','unit.txt','hash','bge-m3','[1.0,0.0]','now')"""))
    monkeypatch.setattr(main, "embedding_model_ready", lambda: True)
    monkeypatch.setattr(main, "embed_texts", lambda values: [[1.0, 0.0] for _ in values])
    response = client.post("/api/knowledge/retrieve", json={"text":"要我先交钱做任务，结束后给奖励"})
    assert response.status_code == 200
    body = response.json()
    assert body["method"].startswith("混合检索")
    assert body["items"][0]["id"] == "semantic-case"
    assert body["items"][0]["semantic_score"] == 1.0

def test_guardian_disposition_updates_timeline(client):
    identity = submit(client).json()["analysis_id"]
    wait(client, identity)
    response = client.post(f"/api/alerts/{identity}/disposition", json={"action":"safe"})
    assert response.status_code == 200
    assert response.json()["handled"] is True
    assert response.json()["disposition"] == "safe"
    assert "确认安全" in response.json()["logs"][-1]

def test_backup_excludes_credentials_and_contains_persisted_data(client):
    identity = submit(client).json()["analysis_id"]
    wait(client, identity)
    backup = client.get("/api/backup")
    assert backup.status_code == 200
    body = backup.json()
    assert body["schema_version"] == 1
    assert body["alerts"][0]["id"] == identity
    assert "api_key" not in json.dumps(body).lower()

def test_report_is_a_persisted_alert_snapshot(client):
    identity = submit(client).json()["analysis_id"]
    wait(client, identity)
    date = main.now()[:10]
    response = client.post("/api/reports", json={"start":date,"end":date,"type":"综合安全报告","user":"小林"})
    assert response.status_code == 201
    report = response.json()
    assert report["summary"]["total"] == 1
    assert report["events"][0]["id"] == identity
    assert report["data_source"] == "SQLite预警快照"
    assert client.get("/api/reports").json()[0]["id"] == report["id"]
    assert client.get("/api/reports/" + report["id"]).json()["summary"] == report["summary"]

def test_user_memory_can_be_viewed_and_deleted(client):
    identity = client.post("/api/analyses", json={"text":"请先转账", "username":"小林"},
        headers={"Idempotency-Key":str(uuid.uuid4())}).json()["analysis_id"]
    wait(client, identity)
    memory = client.get("/api/memory/小林").json()
    assert memory["count"] == 1 and memory["items"][0]["id"] == identity
    deleted = client.delete("/api/memory/小林").json()
    assert deleted == {"ok": True, "deleted": 1}
    assert client.get("/api/memory/小林").json()["items"] == []

def test_knowledge_review_and_version_restore(client):
    payload = {"fraud_type":"兼职刷单","content":"先垫资完成任务，再承诺返还本金和高额佣金。","source_name":"review.txt"}
    identity = client.post("/api/knowledge", json=payload).json()["id"]
    assert client.post(f"/api/knowledge/cases/{identity}/review", json={"status":"disabled"}).status_code == 200
    assert client.get("/api/knowledge").json()["user_count"] == 0
    assert client.post(f"/api/knowledge/cases/{identity}/review", json={"status":"approved"}).status_code == 200
    version = client.post("/api/knowledge/versions", json={"name":"基线版本"}).json()
    assert version["case_count"] == 1
    assert client.delete(f"/api/knowledge/cases/{identity}").status_code == 200
    restored = client.post(f"/api/knowledge/versions/{version['id']}/restore").json()
    assert restored["case_count"] == 1
    assert client.get("/api/knowledge/cases").json()[0]["id"] == identity

def test_evaluation_splits_are_isolated(client):
    cases = client.get("/api/evaluation-cases").json()
    assert {item["split"] for item in cases} == {"development", "validation", "blind"}
    created = client.post("/api/evaluations", json={"mode":"rules", "dataset_split":"blind", "ablation":"no_rag"})
    identity = created.json()["evaluation_id"]
    for _ in range(50):
        run = client.get("/api/evaluations/" + identity).json()
        if run["status"] != "running": break
        time.sleep(.02)
    assert run["result"]["dataset"]["total"] == 4
    assert run["result"]["dataset_split"] == "blind"
    assert run["result"]["ablation"] == "no_rag"

def test_video_rejects_unsupported_file(client):
    response = client.post("/api/video-analyses", data={"username":"测试用户", "profile":"{}"},
        files={"file":("sample.txt", b"not-a-video", "text/plain")})
    assert response.status_code == 422


def test_model_probe_does_not_hold_database_write_lock(client, monkeypatch):
    checked = []
    def probe():
        # Simulate another request obtaining the writer slot while probing the network.
        with main.engine.connect() as db:
            db.execute(text("BEGIN IMMEDIATE"))
            checked.append(True)
            db.rollback()
        return False
    monkeypatch.setattr(main, "model_ready", probe)
    response = submit(client)
    assert response.status_code == 503
    assert checked == [True]
    assert client.get('/api/alerts').json() == []


def test_replay_does_not_require_model_network(client, monkeypatch):
    key = str(uuid.uuid4())
    first = submit(client, key=key)
    def unavailable():
        raise AssertionError('A replay must not probe the network')
    monkeypatch.setattr(main, 'model_ready', unavailable)
    assert submit(client, key=key).json() == first.json()
    assert submit(client, '改变内容', key).status_code == 409

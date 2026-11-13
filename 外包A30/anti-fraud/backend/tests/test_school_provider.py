import json
import httpx
import pytest
from app import main


def test_school_protocol(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'school')
    monkeypatch.setenv('LLM_API_KEY', 'never-forward')
    assert main.configured()
    real_client = httpx.Client
    def respond(request):
        body=json.loads(request.content)
        assert str(request.url)=='http://10.138.50.151:8000/v1/chat/completions'
        assert 'authorization' not in request.headers
        assert body['model']=='qwen3.8-27b'
        assert body['chat_template_kwargs']['enable_thinking'] is False
        result=dict(risk_level='medium',assessment='needs_review',fraud_type='待核实',explanation='证据不足',evidence_ids=['e1'],case_ids=[],advice=['核实来源'])
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]})
    monkeypatch.setattr(main.httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(respond)))
    assert main._call_model_once([{'id':'e1','text':'测试资料'}],[]).assessment=='needs_review'


def test_school_failure_not_ready(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','school')
    def fail(*a,**kw):raise httpx.ConnectError('unreachable')
    monkeypatch.setattr(main.httpx,'get',fail)
    assert not main.model_ready()
    assert '学校模型当前不可达' in main.model_unavailable_message()
    assert 'ollama pull' not in main.model_unavailable_message()


def test_school_truncation_rejected(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','school')
    real_client=httpx.Client
    monkeypatch.setattr(main.httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}))))
    with pytest.raises(ValueError,match='MODEL_INCOMPLETE'):
        main._call_model_once([{'id':'e1'}],[])


def test_school_vision_rejection_is_explicit(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','school')
    real_client=httpx.Client
    monkeypatch.setattr(main.httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(lambda request:httpx.Response(400,json={'error':'unsupported image'}))))
    with pytest.raises(main.HTTPException) as error:
        main.call_image_model('data:','test')

    assert error.value.status_code == 503


def test_school_vision_sends_image_and_rejects_truncation(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','school')
    real_client=httpx.Client
    def respond(request):
        body=json.loads(request.content)
        assert body['messages'][1]['content'][1]['image_url']['url']=='data:image/png;base64,TEST'
        assert body['chat_template_kwargs']['enable_thinking'] is False
        return httpx.Response(200,json={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]})
    monkeypatch.setattr(main.httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(respond)))
    with pytest.raises(ValueError,match='INCOMPLETE_VISION_OUTPUT'):
        main.call_image_model('data:image/png;base64,TEST','test')


def test_unverified_safety_guarantee_is_rejected(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER','school')
    real_client=httpx.Client
    result=dict(risk_level='low',assessment='assessed',fraud_type='正常内容',explanation='没有明显风险',evidence_ids=['e1'],case_ids=[],advice=['活动信息真实有效，可放心参与'])
    def respond(request):
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]})
    monkeypatch.setattr(main.httpx,'Client',lambda **kw:real_client(transport=httpx.MockTransport(respond)))
    with pytest.raises(ValueError,match='UNSUPPORTED_SAFETY_GUARANTEE'):
        main._call_model_once([{'id':'e1','text':'社区活动通知'}],[])

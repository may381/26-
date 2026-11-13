import pytest
from app.v3_result import fraud_result_card


def alert():
    return dict(origin='backend',level='high',evidence='发现先交保证金的要求，需要独立核实。',evidenceItems=[{'id':'local-e1'}],advice=['暂缓转账'])


def source():
    return dict(sourceId='p2-message-1',sourceType='USER_MESSAGE',label='本次输入',retrievedAt='2026-10-31T00:00:00Z',verifiedAt=None)


def test_v3_card_does_not_invent_server_ids_or_effects():
    result=fraud_result_card(alert(),[source()])
    assert result['payload']['riskLevel']=='HIGH'
    assert result['availability']=='NEEDS_VERIFICATION'
    assert result['payload']['findings'][0]['evidenceRefs']==['p2-message-1']
    assert not {'resultId','confirmationId','effectId'} & result.keys()
    assert result['businessRef'] is None


def test_demo_and_missing_evidence_rejected():
    value=alert();value['origin']='mock'
    with pytest.raises(ValueError):fraud_result_card(value,[source()])
    value=alert();value['evidenceItems']=[]
    with pytest.raises(ValueError):fraud_result_card(value,[source()])


def test_sources_require_authorized_context():
    with pytest.raises(ValueError):fraud_result_card(alert(),[])
    with pytest.raises(ValueError):fraud_result_card(alert(),[{'sourceId':'fake'}])

"""Convert a verified domain result into a v3 draft card; P2 owns IDs and permissions.
This module does not execute notifications, write memory, or pretend P2 is connected.
"""
from datetime import datetime, timezone


def fraud_result_card(alert, authorized_sources):
    if alert.get('origin') != 'backend':
        raise ValueError('DEMO_RESULT_NOT_ACCEPTED')
    risk={'low':'LOW','medium':'MEDIUM','high':'HIGH'}.get(alert.get('level'))
    if risk is None:
        raise ValueError('INVALID_RISK_LEVEL')
    if not alert.get('evidenceItems') or not isinstance(alert.get('advice'),list) or not alert['advice']:
        raise ValueError('INCOMPLETE_ANALYSIS')
    # source IDs must come from P2's already authorized message/attachment context.
    # Local evidence IDs and local SQLite IDs must never impersonate P2 source IDs.
    sources=[]
    for source in authorized_sources:
        if not all(source.get(k) for k in ('sourceId','sourceType','label','retrievedAt')):
            raise ValueError('INVALID_AUTHORIZED_SOURCE')
        sources.append({k:source.get(k) for k in ('sourceId','sourceType','label','retrievedAt','verifiedAt')})
    if not sources:
        raise ValueError('AUTHORIZED_SOURCE_REQUIRED')
    explanation=alert.get('evidence')
    if not isinstance(explanation,str) or not explanation.strip():
        raise ValueError('EXPLANATION_REQUIRED')
    if any(not isinstance(item,str) or not item.strip() for item in alert['advice']):
        raise ValueError('INVALID_ADVICE')
    return {
      'type':'FRAUD_ANALYSIS','schemaVersion':'1.0','title':'可疑内容风险核实建议',
      'businessRef':None,'availability':'NEEDS_VERIFICATION',
      'generatedAt':datetime.now(timezone.utc).isoformat(), 'sources':sources,
      'pendingChecks':['尚未通过独立官方渠道核实对方身份和业务真实性'],
      'payload':{'riskLevel':risk,
        'findings':[{'evidenceRefs':[s['sourceId'] for s in sources], 'explanation':explanation}],
        'recommendedActions':list(alert['advice']),
        'limitations':['仅分析用户提供内容，不作最终诈骗认定；低风险不等于安全保证。',
                       '未执行转账、报警、家属通知或长期记忆写入。']}
    }

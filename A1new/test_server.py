import json
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import Mock,patch
from http.server import ThreadingHTTPServer
import server

class PreviewTests(unittest.TestCase):
 def test_failed_coordinator_returns_actual_stage_for_ui(self):
  chat=Mock();chat.state='READY';chat.trace=[{'stage':'dispatch','label':'委派领域服务','status':'failed','detail':'旅游服务请求失败'}]
  chat.send.side_effect=server.DomainError('旅游服务不可用')
  with patch.object(server,'DomainChat',return_value=chat):
   with self.assertRaises(urllib.error.HTTPError) as error:self.post('/api/message',{'topic':'auto','text':'杭州旅游'})
   result=json.load(error.exception)
   self.assertEqual(result['executionTrace'],chat.trace)
   self.assertFalse(result['submissionUncertain'])
   self.assertNotIn('domainResult',result)
 def setUp(self):
  server.sessions.clear()
  self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
  threading.Thread(target=self.http.serve_forever,daemon=True).start()
  self.base='http://127.0.0.1:'+str(self.http.server_port)
 def tearDown(self):self.http.shutdown();self.http.server_close()
 def post(self,path,body):
  request=urllib.request.Request(self.base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
  return urllib.request.urlopen(request)
 def test_page_and_assets(self):
  for path in ('/','/app.js','/style.css','/ticket-ui.js','/fraud-ui.js','/rich-replies.js'):
   with urllib.request.urlopen(self.base+path) as response:self.assertEqual(response.status,200)
  with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(self.base+'/../server.py')
  self.assertEqual(error.exception.code,404)
 def test_tourism_routes_to_existing_service(self):
  chat=Mock();chat.state='READY';chat.client.tourism.return_value={'text':'真实服务测试替身'}
  with patch.object(server,'DomainChat',return_value=chat):
   with self.post('/api/message',{'topic':'tourism','text':'介绍景点'}) as response:
    result=json.load(response);self.assertEqual(result['domainResult']['text'],'真实服务测试替身');self.assertIn('HttpOnly',response.headers['Set-Cookie'])
    self.assertEqual(result['executionTrace'][0]['stage'],'selection')
    self.assertEqual(result['executionTrace'][-1]['status'],'completed')
    chat.send.assert_not_called()
   chat.client.tourism.assert_called_once_with('介绍景点')
 def test_invalid_message_does_not_call_domain(self):
  chat=Mock()
  with patch.object(server,'DomainChat',return_value=chat):
   with self.assertRaises(urllib.error.HTTPError) as error:self.post('/api/message',{'text':'','topic':'tourism'})
   self.assertEqual(error.exception.code,400);chat.client.tourism.assert_not_called()
 def test_tool_proxy_only_uses_registered_routes(self):
  chat=Mock();chat.client.transport.return_value={'code':'OK','data':{'base':'CNY'}}
  with patch.object(server,'DomainChat',return_value=chat):
   with self.post('/api/tool',{'action':'exchange','payload':{'base':'CNY'}}) as response:
    self.assertEqual(json.load(response)['base'],'CNY')
   chat.client.transport.assert_called_once_with('GET','/api/a1/exchange?base=CNY',None)
   with self.assertRaises(urllib.error.HTTPError) as error:self.post('/api/tool',{'action':'http://evil.test','payload':{}})
   self.assertEqual(error.exception.code,400);self.assertEqual(chat.client.transport.call_count,1)
 def test_ticket_errors_are_not_successful_quotes(self):
  with patch.object(server.tickets,'search',side_effect=server.tickets.TicketError('凭证未配置')):
   with self.assertRaises(urllib.error.HTTPError) as error:self.post('/api/tool',{'action':'tickets','payload':{'kind':'flight'}})
   self.assertEqual(error.exception.code,502)
   result=json.load(error.exception);self.assertIn('凭证未配置',result['error']);self.assertNotIn('offers',result)
 def test_next_fraud_analysis_drops_only_completed_task_reference(self):
  chat=Mock();chat.state='COMPLETE';chat.client.fraud.return_value={'analysisId':'real-next'};chat.packet.return_value={'domain':'fraud','domainResult':{'analysisId':'real-next'}}
  with patch.object(server,'DomainChat',return_value=chat):
   with self.post('/api/message',{'topic':'fraud','text':'新的可疑内容'}) as response:self.assertEqual(response.status,200)
  chat.client.new.assert_called_once();chat.client.fraud.assert_called_once_with('新的可疑内容');self.assertEqual(chat.state,'WAIT_RESULT')
 def test_uncertain_fraud_submission_preserves_retry_state(self):
  chat=Mock();chat.trace=[];chat.state='READY';chat.client.pending=('text','key');chat.client.fraud.side_effect=server.DomainError('暂未确认')
  with patch.object(server,'DomainChat',return_value=chat):
   with self.assertRaises(urllib.error.HTTPError) as error:self.post('/api/message',{'topic':'fraud','text':'可疑内容'})
   self.assertTrue(json.load(error.exception)['submissionUncertain']);self.assertEqual(chat.state,'SUBMISSION_UNCERTAIN')
 def test_wait_feedback_hook_is_wired(self):
  with urllib.request.urlopen(self.base+'/wait-feedback.js',timeout=10) as response:
   hook=response.read().decode('utf-8')
  self.assertIn('正在查询真实地点与交通',hook)
  self.assertIn('inner.apply',hook)
  with urllib.request.urlopen(self.base+'/',timeout=10) as response:
   self.assertIn('/wait-feedback.js',response.read().decode('utf-8'))
 def test_chat_page_wires_payment_guard_hook(self):
  with urllib.request.urlopen(self.base+'/payment-guard-ui.js',timeout=10) as response:
   hook=response.read().decode('utf-8')
  self.assertIn("fetch('/api/payment-guard'",hook)
  self.assertIn('originalApi',hook)
  with urllib.request.urlopen(self.base+'/',timeout=10) as response:
   self.assertIn('/payment-guard-ui.js',response.read().decode('utf-8'))
 def test_fraud_result_card_has_help_entry(self):
  with urllib.request.urlopen(self.base+'/fraud-ui.js',timeout=10) as response:
   script=response.read().decode('utf-8')
  self.assertIn('打 96110 / 找家里人',script)
  self.assertIn('tel:96110',script)
  self.assertIn('fraudHelpSheet',script)
 def test_fraud_cases_fall_back_to_local_fixture(self):
  with self.post('/api/payment-guard',{'text':'先交保证金再发验证码'}) as response:self.assertTrue(json.load(response)['triggered'])
  with urllib.request.urlopen(self.base+'/api/fraud-cases',timeout=10) as response:
   data=json.load(response)
  self.assertGreaterEqual(data['count'],1)
  self.assertEqual(data['target'],5)
  self.assertEqual(len(data['missing'])+len(data['covered']),5)
  for item in data['items']:
   self.assertTrue(item['content']);self.assertTrue(item['source'],'案例必须有可核实来源')
 def test_fraud_cases_page_served(self):
  with urllib.request.urlopen(self.base+'/cases.html',timeout=10) as response:
   self.assertEqual(response.status,200)
   self.assertIn('常见诈骗'.encode(),response.read())
 def test_payment_guard_triggers_without_touching_chat_or_domain(self):
  chat=Mock()
  with patch.object(server,'DomainChat',return_value=chat):
   with self.post('/api/payment-guard',{'text':'请先交300元保证金，再把验证码发给客服'}) as response:
    result=json.load(response)
  self.assertTrue(result['triggered']);self.assertIn('先付款',result['groups'])
  self.assertEqual(result['risk'],'high')
  chat.send.assert_not_called();chat.client.fraud.assert_not_called()
 def test_payment_guard_ignores_normal_text(self):
  with self.post('/api/payment-guard',{'text':'本周六社区读书会，免费参加，不需要任何信息。'}) as response:
   result=json.load(response)
  self.assertEqual(result,{'triggered':False})
 def test_payment_guard_rejects_bad_text(self):
  with self.assertRaises(urllib.error.HTTPError) as error:self.post('/api/payment-guard',{'text':''})
  self.assertEqual(error.exception.code,400)
 def test_p2_mode_is_explicitly_disabled_without_user_configuration(self):
  with patch.object(server,'new_p2_session',return_value=None):
   with self.assertRaises(urllib.error.HTTPError) as error:self.post('/api/p2/message',{'text':'杭州两天'})
  self.assertEqual(error.exception.code,503)
  self.assertIn('A1_P2_USER_ID',json.load(error.exception)['error'])
 def test_p2_message_returns_persisted_task_identifiers(self):
  p2=Mock();p2.conversation_id='conv-1';p2.task_id='task-1';p2.task_version=1
  p2.submit.return_value={'conversationId':'conv-1','taskId':'task-1','taskVersion':1,'taskStatus':'QUEUED'}
  with patch.object(server,'new_p2_session',return_value=p2):
   with self.post('/api/p2/message',{'text':'杭州两天'}) as response:result=json.load(response)
  self.assertEqual(result['mode'],'P2_V3');self.assertEqual(result['taskId'],'task-1')
  p2.submit.assert_called_once_with('杭州两天',continue_task_id=None,response_to=None)
 def test_p2_default_mode_reuses_existing_chat_route(self):
  p2=Mock();p2.conversation_id='conv-1';p2.task_id='task-1';p2.task_version=1
  p2.submit.return_value={'conversationId':'conv-1','taskId':'task-1','taskVersion':1,'taskStatus':'QUEUED'}
  with patch.object(server,'new_p2_session',return_value=p2),patch.object(server,'p2_default_enabled',return_value=True):
   with self.post('/api/message',{'topic':'auto','text':'杭州两天'}) as response:result=json.load(response)
  self.assertEqual(result['state'],'QUEUED');self.assertEqual(result['mode'],'P2_V3')
  p2.submit.assert_called_once()
if __name__=='__main__':unittest.main()

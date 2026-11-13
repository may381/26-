import io,json,unittest
from urllib.error import HTTPError
from unittest.mock import Mock
from local_domains import DomainClient,DomainError
class DomainErrors(unittest.TestCase):
 def error(self,code,detail):
  client=DomainClient();client.opener=Mock();client.opener.open.side_effect=HTTPError('http://127.0.0.1',code,'error',{},io.BytesIO(json.dumps({'detail':detail}).encode()));return client
 def test_school_unavailable(self):
  with self.assertRaisesRegex(DomainError,'校园内网'):self.error(503,'学校模型当前不可达，请重试')._request('POST','/api/image-analyses',{})
 def test_unknown_body_not_leaked(self):
  with self.assertRaises(DomainError) as error:self.error(503,'secret-provider-body')._request('GET','/api/analyses/real-test')
  self.assertNotIn('secret',str(error.exception))
 def test_image_timeout(self):
  client=DomainClient();client.opener=Mock();client.opener.open.side_effect=HTTPError('http://local',504,'error',{},io.BytesIO(b'{}'))
  with self.assertRaisesRegex(DomainError,'超时'):client._request('POST','/api/image-analyses',{})
  self.assertEqual(client.opener.open.call_args.kwargs['timeout'],220)
if __name__=='__main__':unittest.main()

import io
import json
import unittest
import uuid
from http.client import IncompleteRead, RemoteDisconnected
from urllib.error import HTTPError, URLError
from unittest.mock import Mock

from local_domains import DomainClient, DomainError, _NoRedirect


class DomainClientTests(unittest.TestCase):
    def response(self, raw):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = raw
        client = DomainClient()
        client.opener = Mock()
        client.opener.open.return_value = response
        return client, response

    def test_fixed_origins_timeouts_and_read_limit(self):
        for path, origin, timeout in [
            ('/api/agent/messages', 'http://127.0.0.1:8091', 15.0),
            ('/api/analyses', 'http://127.0.0.1:8000', 100),
            ('/api/a1/images/analyze', 'http://127.0.0.1:8091', 220),
            ('/api/image-analyses', 'http://127.0.0.1:8000', 220),
        ]:
            with self.subTest(path=path):
                client, response = self.response(b'{}')
                self.assertEqual(client._request('POST', path, {'text': 'test'}), {})
                args, kwargs = client.opener.open.call_args
                self.assertEqual(args[0].full_url, origin + path)
                self.assertEqual(kwargs['timeout'], timeout)
                response.read.assert_called_once_with(1024 * 1024 + 1)

    def test_bad_paths_never_open(self):
        client = DomainClient()
        client.opener = Mock()
        for path in [None, 1, '', 'api/test', '//evil.test/a',
                     'http://evil.test/a', '/\\evil', '/a\r\nHost:x', '/a#fragment']:
            with self.subTest(path=path), self.assertRaises(DomainError):
                client._request('GET', path)
        client.opener.open.assert_not_called()

    def test_redirect_is_not_followed(self):
        self.assertIsNone(_NoRedirect().redirect_request(
            None, None, 302, '', {}, 'http://evil.test'))
        self.assertTrue(any(isinstance(h, _NoRedirect) for h in DomainClient().opener.handlers))

    def test_one_mb_boundary(self):
        for size, accepted in [(1024 * 1024, True), (1024 * 1024 + 1, False)]:
            client, _ = self.response(b'{}' + b' ' * (size - 2))
            if accepted:
                self.assertEqual(client._request('GET', '/api/analyses'), {})
            else:
                with self.assertRaises(DomainError):
                    client._request('GET', '/api/analyses')

    def test_http_errors_never_read_or_expose_body(self):
        messages = []
        for code in [503, 413, 504, 500, 302]:
            body = Mock(wraps=io.BytesIO(b'SECRET upstream response'))
            error = HTTPError('http://127.0.0.1:8000', code, 'SECRET', {}, body)
            client = DomainClient()
            client.opener = Mock()
            client.opener.open.side_effect = error
            with self.assertRaises(DomainError) as caught:
                client._request('GET', '/api/analyses')
            body.read.assert_not_called()
            self.assertNotIn('SECRET', str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)
            messages.append(str(caught.exception))
        self.assertEqual(len(set(messages[:3])), 3)

    def test_network_and_interrupted_reads_sanitized(self):
        for error in [URLError('SECRET'), URLError(TimeoutError('SECRET')),
                      TimeoutError('SECRET'), ConnectionResetError('SECRET'),
                      RemoteDisconnected('SECRET'), IncompleteRead(b'SECRET', 100)]:
            for during_read in [False, True]:
                with self.subTest(error=type(error).__name__, read=during_read):
                    client, response = self.response(b'{}')
                    if during_read:
                        response.read.side_effect = error
                    else:
                        client.opener.open.side_effect = error
                    with self.assertRaises(DomainError) as caught:
                        client._request('GET', '/api/analyses')
                    self.assertNotIn('SECRET', str(caught.exception))

    def test_invalid_json_and_non_object(self):
        for raw in [b'SECRET', b'\xff', b'[]', b'null', b'"SECRET"']:
            client, _ = self.response(raw)
            with self.assertRaises(DomainError) as caught:
                client._request('GET', '/api/analyses')
            self.assertNotIn('SECRET', str(caught.exception))

    def test_tourism_validation(self):
        transport = Mock(return_value={'code': 'OK', 'data': {'text': '有效咨询'}})
        client = DomainClient(transport)
        for text in [None, 1, '', '   ', 'x' * 2001]:
            with self.assertRaises(DomainError):
                client.tourism(text)
        transport.assert_not_called()
        for text in ['x', 'x' * 2000]:
            self.assertEqual(client.tourism(text), {'text': '有效咨询'})
        for response in [None, [], {}, {'code': 'OK', 'data': []},
                         {'code': 'ERROR', 'data': {}}]:
            transport.return_value = response
            with self.assertRaises(DomainError):
                client.tourism('x')

    def test_fraud_validation_pending_and_retry(self):
        transport = Mock(side_effect=DomainError('offline'))
        client = DomainClient(transport)
        for text in [None, 1, '', '   ', 'x' * 10001]:
            with self.assertRaises(DomainError):
                client.fraud(text)
        transport.assert_not_called()
        with self.assertRaises(DomainError):
            client.fraud('x' * 10000)
        original = transport.call_args
        key = original.args[3]['Idempotency-Key']
        self.assertTrue(key.startswith('local-'))
        uuid.UUID(key[6:])
        with self.assertRaises(DomainError):
            client.fraud('replacement')
        self.assertEqual(transport.call_count, 1)
        transport.side_effect = None
        transport.return_value = {'analysis_id': 'real-test'}
        client.fraud('ignored replacement', retry=True)
        self.assertEqual(transport.call_args, original)
        self.assertIsNone(client.pending)
        self.assertEqual(client.analysis_id, 'real-test')

    def test_invalid_submission_keeps_pending(self):
        for value in [None, {}, {'analysis_id': '//evil'}, {'analysis_id': 1}]:
            client = DomainClient(Mock(return_value=value))
            with self.assertRaises(DomainError):
                client.fraud('x')
            self.assertIsNotNone(client.pending)
            self.assertIsNone(client.analysis_id)

    def test_status_contract(self):
        transport = Mock()
        client = DomainClient(transport)
        with self.assertRaises(DomainError):
            client.status()
        transport.assert_not_called()
        client.analysis_id = 'real-test'
        for state in ['queued', 'processing', 'completed', 'failed', 'interrupted']:
            value = {'analysis_id': client.analysis_id, 'status': state, 'result': {'id': client.analysis_id, 'level': 'high', 'evidence': '依据', 'advice': ['核实']} if state == 'completed' else None}
            transport.return_value = value
            self.assertEqual(client.status(), value)
        for value in [None, [], {}, {'status': 'success'}, {'status': []},
                      {'status': 'completed'}, {'status': 'completed', 'result': []}]:
            transport.return_value = value
            with self.assertRaises(DomainError):
                client.status()


if __name__ == '__main__':
    unittest.main()

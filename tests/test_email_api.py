import io
import json
import unittest
from email.message import EmailMessage
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
from app.core import email


class BrevoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        for name, value in {'brevo_api_key': 'test-key-not-a-real-secret', 'email_from_email': 'sender@example.com', 'smtp_host': None, 'smtp_username': None, 'smtp_password': None, 'smtp_from_email': None, 'frontend_url': 'https://knygolubi-1.onrender.com'}.items():
            patcher = patch.object(email.settings, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def response(self, body=b'{"messageId":"accepted-id"}', status=201):
        response = MagicMock()
        response.status = status
        response.read.return_value = body
        context = MagicMock()
        context.__enter__.return_value = response
        return context

    async def test_https_delivery_without_smtp_credentials(self):
        self.assertTrue(email.email_is_configured())
        with patch.object(email, 'urlopen', return_value=self.response()) as send, patch.object(email, '_send_email') as smtp:
            await email.send_verification_email('reader@example.com', 'test-token')
        smtp.assert_not_called()
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.get_header('Api-key'), 'test-key-not-a-real-secret')
        payload = json.loads(request.data)
        self.assertEqual(payload['sender']['email'], 'sender@example.com')
        self.assertEqual(payload['to'], [{'email':'reader@example.com'}])
        self.assertIn('https://knygolubi-1.onrender.com/verify-email?token=test-token', payload['textContent'])
        self.assertIn('https://knygolubi-1.onrender.com/verify-email?token=test-token', payload['htmlContent'])
        self.assertEqual(send.call_args.kwargs['timeout'], 15)

    async def test_provider_errors_do_not_fall_back_to_blocked_smtp(self):
        errors = [HTTPError('https://api.brevo.com', status, 'rejected', {}, io.BytesIO(b'private response')) for status in (400, 401, 403, 429, 500)]
        errors.extend([URLError('unavailable'), TimeoutError('timeout')])
        for error in errors:
            with self.subTest(error=type(error).__name__), patch.object(email, 'urlopen', side_effect=error), patch.object(email, '_send_email') as smtp:
                with self.assertRaises(email.EmailDeliveryError):
                    await email.send_verification_email('reader@example.com', 'test-token')
                smtp.assert_not_called()

    async def test_unconfirmed_and_invalid_response_is_failure(self):
        for body, status in ((b'{}',201),(b'{"messageId":"id"}',200),(b'not-json',201),(b'[]',201)):
            with self.subTest(body=body), patch.object(email, 'urlopen', return_value=self.response(body,status)):
                with self.assertRaises(email.EmailDeliveryError):
                    await email.send_verification_email('reader@example.com','test-token')

    async def test_missing_sender_is_unconfigured(self):
        with patch.object(email.settings, 'email_from_email', None):
            self.assertFalse(email.email_is_configured())

    async def test_existing_smtp_sender_can_be_reused(self):
        with patch.object(email.settings, 'email_from_email', None), patch.object(email.settings, 'smtp_from_email', 'old-sender@example.com'), patch.object(email, 'urlopen', return_value=self.response()) as send:
            self.assertTrue(email.email_is_configured())
            await email.send_verification_email('reader@example.com','test-token')
            self.assertEqual(json.loads(send.call_args.args[0].data)['sender']['email'], 'old-sender@example.com')

    async def test_without_key_smtp_remains_available(self):
        with patch.object(email.settings, 'brevo_api_key', None):
            self.assertFalse(email.email_is_configured())
        with patch.object(email.settings, 'brevo_api_key', None), patch.object(email, 'email_is_configured', return_value=True), patch.object(email, '_send_email') as smtp, patch.object(email, '_send_brevo_email') as api:
            await email.send_verification_email('reader@example.com','test-token')
            smtp.assert_called_once()
            api.assert_not_called()

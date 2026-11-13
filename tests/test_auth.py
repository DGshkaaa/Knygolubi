"""Authentication contract tests. Run: python -m unittest discover -s tests -v.

Uses an isolated in-memory collection and SMTP mock; never writes to live data.
"""
import copy
import hashlib
import json
import smtplib
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock
from urllib.parse import urlencode

from bson import ObjectId
from fastapi import FastAPI
from pymongo.errors import DuplicateKeyError

from app.api import auth
from app.core import email
from app.core.security import decode_access_token, verify_password


class Users:
    def __init__(self, unique_email=True):
        self.documents = []
        self.unique_email = unique_email

    def matches(self, document, query):
        for key, value in query.items():
            current = document.get(key)
            if isinstance(value, dict) and '$gt' in value:
                if current is None or current <= value['$gt']:
                    return False
            elif current != value:
                return False
        return True

    async def find_one(self, query, sort=None):
        documents = self.documents
        for key, direction in reversed(sort or []):
            documents = sorted(documents, key=lambda item: item[key], reverse=direction < 0)
        return next((copy.deepcopy(d) for d in documents if self.matches(d, query)), None)

    async def insert_one(self, document):
        if self.unique_email and any(d['email'] == document['email'] for d in self.documents):
            raise DuplicateKeyError('email')
        document['_id'] = ObjectId()
        self.documents.append(copy.deepcopy(document))
        return SimpleNamespace(inserted_id=document['_id'])

    async def update_one(self, query, update):
        for document in self.documents:
            if self.matches(document, query):
                document.update(update.get('$set', {}))
                for key in update.get('$unset', {}):
                    document.pop(key, None)
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)


    async def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if self.matches(document, query):
                del self.documents[index]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def delete_many(self, query):
        original = len(self.documents)
        self.documents[:] = [d for d in self.documents if not self.matches(d, query)]
        return SimpleNamespace(deleted_count=original-len(self.documents))


class AuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.users = Users()
        self.pending = Users(unique_email=False)
        self.app = FastAPI()
        self.app.include_router(auth.router)
        async def test_database():
            return SimpleNamespace(users=self.users, pending_registrations=self.pending)
        self.app.dependency_overrides[auth.database_dependency] = test_database
        self.configured = patch.object(auth, 'email_is_configured', return_value=True)
        self.delivery = patch.object(auth, 'send_verification_email', new_callable=AsyncMock)
        self.configured.start()
        self.send = self.delivery.start()
        self.addCleanup(self.configured.stop)
        self.addCleanup(self.delivery.stop)
        self.payload = dict(name='  Читач  ', email='Reader@example.com', password='test-password-123')

    async def request(self, path, payload=None, query=None):
        body = json.dumps(payload).encode() if payload is not None else b''
        scope = dict(type='http', asgi={'version': '3.0'}, http_version='1.1',
                     method='POST' if payload is not None else 'GET', scheme='http',
                     path='/api/auth/' + path, raw_path=('/api/auth/' + path).encode(),
                     query_string=urlencode(query or {}).encode(),
                     headers=[(b'content-type', b'application/json')],
                     client=('127.0.0.1', 1000), server=('test', 80))
        output = []
        async def receive():
            return {'type': 'http.request', 'body': body, 'more_body': False}
        async def send(message):
            output.append(message)
        await self.app(scope, receive, send)
        return output[0]['status'], json.loads(b''.join(m.get('body', b'') for m in output[1:]))

    async def register(self):
        status, data = await self.request('register', self.payload)
        self.assertEqual(status, 201, data)
        return self.send.call_args.args[1]

    async def test_registration_only_stores_temporary_hashed_application(self):
        token = await self.register()
        self.assertEqual(self.users.documents, [])
        document = self.pending.documents[0]
        self.assertEqual(document['email'], 'reader@example.com')
        self.assertEqual(document['name'], 'Читач')
        self.assertTrue(verify_password(self.payload['password'], document['password_hash']))
        self.assertNotEqual(document['password_hash'], self.payload['password'])
        self.assertEqual(document['email_verification_token_hash'], hashlib.sha256(token.encode()).hexdigest())
        self.assertNotIn('role', document)
        self.send.assert_awaited_once_with('reader@example.com', token)

    async def test_full_register_verify_login_flow(self):
        token = await self.register()
        credentials = {k: self.payload[k] for k in ('email', 'password')}
        self.assertEqual((await self.request('login', credentials))[0], 403)
        self.assertEqual(self.users.documents, [])
        self.assertEqual((await self.request('verify-email', query={'token': token}))[0], 200)
        self.assertEqual(len(self.users.documents), 1)
        document = self.users.documents[0]
        self.assertTrue(document['email_verified'])
        self.assertFalse(document['is_approved'])
        self.assertEqual(document['role'], 'student')
        status, response = await self.request('login', credentials)
        self.assertEqual(status, 200)
        self.assertEqual(decode_access_token(response['access_token'])['sub'], str(document['_id']))
        self.assertEqual(self.pending.documents, [])
        self.assertEqual((await self.request('verify-email', query={'token': token}))[0], 400)

    async def test_unconfirmed_address_does_not_block_registration(self):
        await self.register()
        await self.register()
        self.assertEqual(self.users.documents, [])
        self.assertEqual(len(self.pending.documents), 2)

    async def test_confirmed_address_does_block_registration(self):
        token = await self.register()
        await self.request('verify-email', query={'token': token})
        self.assertEqual((await self.request('register', self.payload))[0], 409)
        self.assertEqual(len(self.users.documents), 1)

    async def test_concurrent_confirmation_returns_conflict(self):
        token = await self.register()
        with patch.object(self.users, 'insert_one', side_effect=DuplicateKeyError('email')):
            self.assertEqual((await self.request('verify-email', query={'token': token}))[0], 409)
        self.assertEqual(self.users.documents, [])

    async def test_competing_registration_never_overwrites_confirmed_password(self):
        first = await self.register()
        await self.request('register', {**self.payload, 'password':'different-password-123'})
        second = self.send.call_args.args[1]
        self.assertEqual((await self.request('verify-email', query={'token': first}))[0], 200)
        self.assertEqual((await self.request('verify-email', query={'token': second}))[0], 400)
        self.assertTrue(verify_password(self.payload['password'], self.users.documents[0]['password_hash']))
        self.assertEqual(len(self.users.documents), 1)

    async def test_invalid_input(self):
        for changes in ({'password': 'short'}, {'email': 'invalid'}, {'name': '   '}, {'role': 'admin'}):
            with self.subTest(changes=changes):
                self.assertEqual((await self.request('register', {**self.payload, **changes}))[0], 422)
        self.assertEqual(self.users.documents, [])
        self.assertEqual(self.pending.documents, [])

    async def test_unconfigured_mail_does_not_create_account(self):
        with patch.object(auth, 'email_is_configured', return_value=False):
            self.assertEqual((await self.request('register', self.payload))[0], 503)
            self.assertEqual((await self.request('resend-verification', {'email': self.payload['email']}))[0], 503)
        self.assertEqual(self.users.documents, [])
        self.assertEqual(self.pending.documents, [])

    async def test_mail_failure_creates_no_account_and_allows_retry(self):
        self.send.side_effect = smtplib.SMTPException('unavailable')
        self.assertEqual((await self.request('register', self.payload))[0], 502)
        self.assertEqual(self.users.documents, [])
        self.send.side_effect = None
        status, _ = await self.request('resend-verification', {'email': self.payload['email']})
        self.assertEqual(status, 200)
        token = self.send.call_args.args[1]
        self.assertEqual((await self.request('verify-email', query={'token': token}))[0], 200)
        self.assertEqual(len(self.users.documents), 1)

    async def test_mail_failure_does_not_block_new_registration(self):
        self.send.side_effect = smtplib.SMTPException('unavailable')
        self.assertEqual((await self.request('register', self.payload))[0], 502)
        self.send.side_effect = None
        await self.register()
        self.assertEqual(self.users.documents, [])

    async def test_provider_configuration_failure_leaves_no_account(self):
        self.send.side_effect = email.EmailDeliveryError('private internal cause', public_message=email.MAIL_CONFIGURATION_MESSAGE)
        status, response = await self.request('register', self.payload)
        self.assertEqual(status, 502)
        self.assertEqual(response['detail'], email.MAIL_CONFIGURATION_MESSAGE)
        self.assertNotIn('private', response['detail'])
        self.assertEqual(self.users.documents, [])

    async def test_expired_and_unknown_tokens(self):
        token = await self.register()
        self.pending.documents[0]['email_verification_expires_at'] = datetime.now(timezone.utc) - timedelta(seconds=1)
        for value in (token, 'invalid'):
            self.assertEqual((await self.request('verify-email', query={'token': value}))[0], 400)
        self.assertEqual(self.users.documents, [])
        await self.register()

    async def test_resend_rotates_token_after_success(self):
        old = await self.register()
        await self.request('resend-verification', {'email': self.payload['email']})
        new = self.send.call_args.args[1]
        self.assertNotEqual(old, new)
        self.assertEqual((await self.request('verify-email', query={'token': old}))[0], 400)
        self.assertEqual((await self.request('verify-email', query={'token': new}))[0], 200)

    async def test_failed_resend_preserves_previous_link(self):
        old = await self.register()
        self.send.side_effect = email.EmailDeliveryError('unavailable')
        self.assertEqual((await self.request('resend-verification', {'email': self.payload['email']}))[0], 502)
        self.assertEqual((await self.request('verify-email', query={'token': old}))[0], 200)
        self.assertEqual(len(self.users.documents), 1)

    async def test_resend_unknown_and_verified_are_private(self):
        token = await self.register()
        await self.request('verify-email', query={'token': token})
        self.send.reset_mock()
        verified = await self.request('resend-verification', {'email': self.payload['email']})
        unknown = await self.request('resend-verification', {'email': 'unknown@example.com'})
        self.assertEqual(verified, unknown)
        self.send.assert_not_awaited()

    async def test_expired_application_cannot_be_resurrected_by_resend(self):
        await self.register()
        self.pending.documents[0]['email_verification_expires_at'] = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.send.reset_mock()
        self.assertEqual((await self.request('resend-verification', {'email': self.payload['email']}))[0], 200)
        self.send.assert_not_awaited()
        self.assertEqual(self.users.documents, [])

    async def test_wrong_password_and_unknown_account(self):
        await self.register()
        for address in (self.payload['email'], 'unknown@example.com'):
            self.assertEqual((await self.request('login', {'email': address, 'password': 'wrong-password'}))[0], 401)

    async def add_legacy_user(self, role='student'):
        await self.users.insert_one({
            'email':'reader@example.com', 'name':'Old name',
            'password_hash': auth.hash_password('old-password'),
            'email_verified':False, 'is_approved':False, 'role':role,
            'favorites':['preserved-book'],
        })
        return self.users.documents[0]['_id']

    async def test_old_unconfirmed_record_does_not_block_and_is_preserved(self):
        user_id = await self.add_legacy_user()
        token = await self.register()
        self.assertFalse(self.users.documents[0]['email_verified'])
        self.assertEqual((await self.request('verify-email', query={'token':token}))[0], 200)
        document = self.users.documents[0]
        self.assertEqual(document['_id'], user_id)
        self.assertEqual(document['favorites'], ['preserved-book'])
        self.assertTrue(document['email_verified'])
        self.assertTrue(verify_password(self.payload['password'],document['password_hash']))

    async def test_resend_supports_old_unconfirmed_record(self):
        await self.add_legacy_user()
        self.assertEqual((await self.request('resend-verification', {'email': self.payload['email']}))[0], 200)
        token = self.send.call_args.args[1]
        self.assertEqual((await self.request('verify-email', query={'token': token}))[0], 200)
        self.assertTrue(verify_password('old-password',self.users.documents[0]['password_hash']))

    async def test_predeployment_verification_links_still_work(self):
        await self.add_legacy_user()
        document = self.users.documents[0]
        document['email_verification_token_hash'] = hashlib.sha256(b'old-link').hexdigest()
        document['email_verification_expires_at'] = datetime.now(timezone.utc) + timedelta(hours=1)
        self.assertEqual((await self.request('verify-email',query={'token':'old-link'}))[0], 200)
        self.assertTrue(document['email_verified'])
        self.assertNotIn('email_verification_token_hash', document)

    async def test_staff_address_is_not_reclaimable(self):
        await self.add_legacy_user(role='admin')
        self.assertEqual((await self.request('register',self.payload))[0], 409)
        self.send.assert_not_awaited()


class EmailTests(unittest.IsolatedAsyncioTestCase):
    async def test_multipart_letter_contains_verification_url(self):
        with patch.object(email, 'email_is_configured', return_value=True), patch.object(email, '_send_email') as send:
            await email.send_verification_email('reader@example.com', 'safe-token')
        message = send.call_args.args[0]
        self.assertEqual(message['To'], 'reader@example.com')
        self.assertIn('/verify-email?token=safe-token', message.get_body(('plain',)).get_content())
        self.assertIn('/verify-email?token=safe-token', message.get_body(('html',)).get_content())
        self.assertIn('24', message.get_body(('plain',)).get_content())

    async def test_unconfigured_mail_fails_explicitly(self):
        with patch.object(email, 'email_is_configured', return_value=False):
            with self.assertRaises(RuntimeError):
                await email.send_verification_email('reader@example.com', 'token')

    async def test_ssl_and_starttls_delivery(self):
        for use_ssl in (False, True):
            with self.subTest(ssl=use_ssl), patch.object(email.settings, 'smtp_use_ssl', use_ssl), patch.object(email.smtplib, 'SMTP_SSL') as ssl, patch.object(email.smtplib, 'SMTP') as tls:
                server = (ssl if use_ssl else tls).return_value.__enter__.return_value
                server.send_message.return_value = {}
                message = MagicMock()
                email._send_email(message)
                server.login.assert_called_once()
                server.send_message.assert_called_once_with(message)
                if not use_ssl:
                    server.starttls.assert_called_once()

    async def test_rejected_recipient_is_not_success(self):
        with patch.object(email.settings, 'smtp_use_ssl', False), patch.object(email.smtplib, 'SMTP') as smtp:
            smtp.return_value.__enter__.return_value.send_message.return_value = {'reader@example.com': (550, b'refused')}
            with self.assertRaises(smtplib.SMTPRecipientsRefused):
                email._send_email(MagicMock())


if __name__ == '__main__':
    unittest.main()

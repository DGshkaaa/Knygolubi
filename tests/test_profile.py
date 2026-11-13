"""Profile contact validation, storage, access and email privacy regression tests."""
import json
import unittest
from types import SimpleNamespace
from bson import ObjectId
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError
from app.api import users
from app.api.deps import get_current_user
from app.schemas.profile import ProfileUpdate
from app.schemas.user import UserInDatabase
from tests.test_board import Collection


class TelegramValidationTests(unittest.TestCase):
    def test_nick_at_and_link_normalize_to_same_contact(self):
        for value in ('Book_Reader',' @Book_Reader ','https://t.me/Book_Reader','t.me/Book_Reader/','https://www.t.me/Book_Reader'):
            self.assertEqual(ProfileUpdate(telegram_username=value).telegram_username,'book_reader')

    def test_empty_contact_is_removable_and_omitted_field_is_untouched(self):
        for value in ('','   ',None):
            self.assertEqual(ProfileUpdate(telegram_username=value).model_dump(exclude_unset=True),{'telegram_username':None})
        self.assertNotIn('telegram_username',ProfileUpdate(name='Reader').model_dump(exclude_unset=True))

    def test_malformed_external_links_and_phone_numbers_are_rejected(self):
        for value in ('https://evil.example/book_reader','https://t.me.evil.example/book_reader','https://t.me/book_reader?foo=bar','https://t.me/+123456789','javascript:alert(1)','@bad nick','@@book_reader','user/name','abcd','1name','читач','a'*33,123):
            with self.subTest(value=value),self.assertRaises(ValidationError): ProfileUpdate(telegram_username=value)


class ProfileContactTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.owner=UserInDatabase.model_validate({'_id':ObjectId(),'name':'Owner','email':'owner@example.com','password_hash':'unused'})
        self.other=UserInDatabase.model_validate({'_id':ObjectId(),'name':'Other','email':'other@example.com','password_hash':'unused'})
        self.reader=self.owner
        self.db=SimpleNamespace(users=Collection(),books=Collection(),reviews=Collection())
        for user in (self.owner,self.other): self.db.users.documents.append({**user.model_dump(by_alias=True), '_id':user.id})
        self.app=FastAPI(); self.app.include_router(users.router)
        async def database(): return self.db
        async def current():
            if self.reader is None: raise HTTPException(401,'Sign in')
            return self.reader
        self.app.dependency_overrides[users.database_dependency]=database
        self.app.dependency_overrides[get_current_user]=current

    async def request(self, method, path, payload=None):
        body=json.dumps(payload).encode() if payload is not None else b''
        scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':method,'scheme':'http','path':'/api/users/'+path,'raw_path':('/api/users/'+path).encode(),'query_string':b'','headers':[(b'content-type',b'application/json')],'client':('127.0.0.1',1000),'server':('test',80)}
        output=[]
        async def receive(): return {'type':'http.request','body':body,'more_body':False}
        async def send(value): output.append(value)
        await self.app(scope,receive,send)
        return output[0]['status'],json.loads(b''.join(item.get('body',b'') for item in output[1:]))

    async def test_save_contact_shown_in_own_and_other_profile_without_email_leak(self):
        status,data=await self.request('PUT','me/profile',{'telegram_username':'https://t.me/Book_Reader'})
        self.assertEqual(status,200,data); self.assertEqual(data['telegram_username'],'book_reader')
        self.assertEqual(data['email'],'owner@example.com')
        self.assertEqual(self.db.users.documents[0]['telegram_username'],'book_reader')
        self.reader=self.other
        status,data=await self.request('GET',f'{self.owner.id}/profile')
        self.assertEqual(status,200); self.assertEqual(data['telegram_username'],'book_reader')
        self.assertIsNone(data['email'])
        self.assertNotIn('owner@example.com',json.dumps(data))

    async def test_removal_is_persisted_and_name_update_keeps_contact(self):
        await self.request('PUT','me/profile',{'telegram_username':'@book_reader'})
        self.assertEqual((await self.request('PUT','me/profile',{'name':'New name'}))[1]['telegram_username'],'book_reader')
        self.assertIsNone((await self.request('PUT','me/profile',{'telegram_username':''}))[1]['telegram_username'])
        self.assertIsNone((await self.request('GET','me/profile'))[1]['telegram_username'])

    async def test_old_profile_without_contact_works(self):
        status,data=await self.request('GET','me/profile')
        self.assertEqual(status,200); self.assertIsNone(data['telegram_username'])

    async def test_invalid_input_changes_nothing(self):
        status,_=await self.request('PUT','me/profile',{'telegram_username':'https://evil.example'})
        self.assertEqual(status,422)
        self.assertNotIn('telegram_username',self.db.users.documents[0])

    async def test_another_users_contact_cannot_be_changed(self):
        self.reader=self.other
        await self.request('PUT','me/profile',{'telegram_username':'other_reader'})
        self.assertNotIn('telegram_username',self.db.users.documents[0])
        self.assertEqual(self.db.users.documents[1]['telegram_username'],'other_reader')

    async def test_unapproved_or_anonymous_cannot_edit(self):
        for user in (None,self.owner.model_copy(update={'is_approved':False})):
            self.reader=user
            status,_=await self.request('PUT','me/profile',{'telegram_username':'book_reader'})
            self.assertEqual(status,401 if user is None else 403)

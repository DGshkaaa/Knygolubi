"""Board HTTP contract tests, with isolated Mongo-like collections and no emails."""
import copy
import json
import re
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlencode
from bson import ObjectId
from fastapi import FastAPI, HTTPException
from pymongo.errors import DuplicateKeyError
from app.api import board
from app.api.deps import get_current_user
from app.schemas.user import UserInDatabase


def matches(document, query):
    for key, value in query.items():
        if key == '$or':
            if not any(matches(document, item) for item in value): return False
            continue
        current = document
        for part in key.split('.'):
            if isinstance(current, list):
                current = current[int(part)] if int(part) < len(current) else None
            else: current = current.get(part) if isinstance(current, dict) else None
        if isinstance(value, dict):
            if '$gt' in value and (current is None or current <= value['$gt']): return False
            if '$exists' in value and (current is not None) != value['$exists']: return False
            if '$regex' in value and not re.search(value['$regex'], current or '', re.I): return False
        elif current != value: return False
    return True


class Cursor:
    def __init__(self, values): self.values = copy.deepcopy(values)
    def sort(self, key, direction): self.values.sort(key=lambda d:d[key], reverse=direction < 0); return self
    def skip(self, count): self.values = self.values[count:]; return self
    def limit(self, count): self.values = self.values[:count]; return self
    async def to_list(self, length=None): return self.values[:length] if length is not None else self.values
    def __aiter__(self):
        async def iterate():
            for value in self.values: yield value
        return iterate()


class Collection:
    def __init__(self, unique=None): self.documents=[]; self.unique=unique
    def find(self, query): return Cursor([d for d in self.documents if matches(d,query)])
    async def find_one(self, query): return next((copy.deepcopy(d) for d in self.documents if matches(d,query)),None)
    async def count_documents(self, query): return sum(matches(d,query) for d in self.documents)
    async def insert_one(self, document):
        if self.unique and any(all(d[key] == document[key] for key in self.unique) for d in self.documents): raise DuplicateKeyError('duplicate')
        document['_id'] = ObjectId(); self.documents.append(copy.deepcopy(document)); return SimpleNamespace(inserted_id=document['_id'])
    async def update_one(self, query, update):
        for document in self.documents:
            if matches(document,query):
                document.update(update.get('$set',{}))
                for key,value in update.get('$push',{}).items(): document.setdefault(key,[]).append(copy.deepcopy(value))
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)
    async def delete_one(self, query):
        for index, document in enumerate(self.documents):
            if matches(document,query): del self.documents[index]; break
    async def delete_many(self, query): self.documents[:]=[d for d in self.documents if not matches(d,query)]


class BoardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = SimpleNamespace(board_posts=Collection(), board_threads=Collection(unique=('post_id','responder_id')), users=Collection())
        self.owner = UserInDatabase.model_validate({'_id':ObjectId(),'name':'Author','email':'owner@example.com','password_hash':'unused'})
        self.responder = UserInDatabase.model_validate({'_id':ObjectId(),'name':'Reader','email':'reader@example.com','password_hash':'unused'})
        self.outsider = UserInDatabase.model_validate({'_id':ObjectId(),'name':'Other','email':'other@example.com','password_hash':'unused'})
        for user in (self.owner,self.responder,self.outsider): self.db.users.documents.append({'_id':user.id,'notifications':[]})
        self.reader = self.owner
        self.app=FastAPI(); self.app.include_router(board.router)
        async def database(): return self.db
        async def user():
            if self.reader is None: raise HTTPException(401,'Sign in')
            return self.reader
        self.app.dependency_overrides[board.database_dependency]=database
        self.app.dependency_overrides[get_current_user]=user
        self.payload={'kind':'wanted','book_title':' Дюна [1] ','book_author':'Френк Герберт','description':'Шукаю українське видання книги для читання.','location':'Київ'}

    async def request(self, method, path='', payload=None, query=None):
        body=json.dumps(payload).encode() if payload is not None else b''
        scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':method,'scheme':'http','path':'/api/board'+path,'raw_path':('/api/board'+path).encode(),'query_string':urlencode(query or {}).encode(),'headers':[(b'content-type',b'application/json')],'client':('127.0.0.1',1000),'server':('test',80)}
        output=[]
        async def receive(): return {'type':'http.request','body':body,'more_body':False}
        async def send(value): output.append(value)
        await self.app(scope,receive,send)
        raw=b''.join(item.get('body',b'') for item in output[1:])
        return output[0]['status'],json.loads(raw) if raw else None, dict(output[0].get('headers',[]))

    async def create(self, **changes):
        status,data,_=await self.request('POST',payload={**self.payload,**changes})
        self.assertEqual(status,201,data)
        return data['_id']

    async def response(self, post_id):
        self.reader=self.responder
        status,data,_=await self.request('POST',f'/{post_id}/responses',{'text':'Маю цю книгу, можемо домовитися тут.'})
        self.assertEqual(status,201,data)
        return data

    async def test_create_public_list_and_no_email_disclosure(self):
        post=await self.create()
        self.reader=None
        status,data,headers=await self.request('GET')
        self.assertEqual(status,200); self.assertEqual(data[0]['_id'],post)
        self.assertEqual(data[0]['book_title'],'Дюна [1]')
        self.assertNotIn('email',json.dumps(data))
        self.assertEqual(headers[b'x-total-count'],b'1')
        self.assertEqual((await self.request('GET',f'/{post}'))[0],200)

    async def test_only_approved_users_can_publish_and_respond(self):
        post=await self.create()
        for user in (None,self.responder.model_copy(update={'email_verified':False}),self.responder.model_copy(update={'is_approved':False})):
            self.reader=user
            expected=401 if user is None else 403
            self.assertEqual((await self.request('POST',payload=self.payload))[0],expected)
            self.assertEqual((await self.request('POST',f'/{post}/responses',{'text':'Hello'}))[0],expected)

    async def test_search_kind_pagination_and_expiration(self):
        await self.create()
        await self.create(kind='giveaway',book_title='Інша книга')
        expired=await self.create(book_title='Давня книга')
        self.db.board_posts.documents[-1]['expires_at']=datetime.now(timezone.utc)-timedelta(seconds=1)
        self.reader=None
        status,data,headers=await self.request('GET',query={'search':'[','kind':'wanted','page_size':1})
        self.assertEqual(status,200); self.assertEqual(len(data),1)
        self.assertEqual(headers[b'x-total-count'],b'1')
        self.assertEqual((await self.request('GET',f'/{expired}'))[1]['status'],'expired')
        _,data,headers=await self.request('GET',query={'page_size':1})
        self.assertEqual(len(data),1); self.assertEqual(headers[b'x-has-next'],b'true')

    async def test_private_conversations_are_scoped_to_participants(self):
        post=await self.create(); thread=await self.response(post)
        self.reader=self.outsider
        self.assertEqual((await self.request('GET',f'/{post}/responses'))[1],[])
        status,data,_=await self.request('POST',f"/threads/{thread['_id']}/messages",{'text':'read private'})
        self.assertEqual(status,403)
        self.assertNotIn('Маю',json.dumps(data))
        self.reader=self.owner
        self.assertEqual(len((await self.request('GET',f'/{post}/responses'))[1]),1)
        self.reader=self.responder
        self.assertEqual(len((await self.request('GET',f'/{post}/responses'))[1]),1)

    async def test_response_sends_one_notification_and_duplicates_are_rejected(self):
        post=await self.create(); await self.response(post)
        self.assertEqual((await self.request('POST',f'/{post}/responses',{'text':'Again'}))[0],409)
        notification=self.db.users.documents[0]['notifications']
        self.assertEqual(len(notification),1)
        self.assertEqual(str(notification[0]['board_post_id']),post)
        self.assertEqual(notification[0]['type'],'board_message')

    async def test_owner_reply_and_notification_to_reader(self):
        post=await self.create(); thread=await self.response(post)
        self.reader=self.owner
        status,data,_=await self.request('POST',f"/threads/{thread['_id']}/messages",{'text':'Домовилися, дякую!'})
        self.assertEqual(status,200); self.assertEqual(len(data['messages']),2)
        self.assertEqual(data['messages'][-1]['sender_id'],str(self.owner.id))
        self.assertEqual(len(self.db.users.documents[1]['notifications']),1)

    async def test_owner_controls_status_and_existing_chat_survives_closure(self):
        post=await self.create(); thread=await self.response(post)
        self.reader=self.owner
        self.assertEqual((await self.request('POST',f'/{post}/responses',{'text':'Self'}))[0],400)
        self.assertEqual((await self.request('PATCH',f'/{post}/status',{'status':'closed'}))[1]['status'],'closed')
        self.assertEqual((await self.request('GET'))[1],[])
        self.assertEqual(len((await self.request('GET','/mine'))[1]),1)
        self.reader=self.outsider
        self.assertEqual((await self.request('POST',f'/{post}/responses',{'text':'New response'}))[0],409)
        self.reader=self.responder
        self.assertEqual((await self.request('POST',f"/threads/{thread['_id']}/messages",{'text':'Завтра передамо'}))[0],200)
        self.reader=self.owner
        self.assertEqual((await self.request('PATCH',f'/{post}/status',{'status':'open'}))[1]['status'],'open')

    async def test_non_owner_cannot_edit_close_delete(self):
        post=await self.create(); self.reader=self.outsider
        self.assertEqual((await self.request('PUT',f'/{post}',self.payload))[0],403)
        self.assertEqual((await self.request('PATCH',f'/{post}/status',{'status':'closed'}))[0],403)
        self.assertEqual((await self.request('DELETE',f'/{post}'))[0],403)
        self.assertEqual((await self.request('GET','/mine'))[1],[])

    async def test_owner_edit_and_moderator_removal_cleans_threads(self):
        post=await self.create(); await self.response(post)
        self.reader=self.owner
        self.assertEqual((await self.request('PUT',f'/{post}',{**self.payload,'book_title':'Оновлена назва'}))[1]['book_title'],'Оновлена назва')
        self.reader=self.outsider.model_copy(update={'role':'moderator'})
        self.assertEqual((await self.request('DELETE',f'/{post}'))[0],204)
        self.assertEqual(self.db.board_threads.documents,[])
        self.assertEqual((await self.request('GET',f'/{post}'))[0],404)

    async def test_limits_and_validation(self):
        for changes in ({'book_title':'   '},{'description':'short'},{'kind':'spam'},{'owner_id':str(self.outsider.id)}):
            self.assertEqual((await self.request('POST',payload={**self.payload,**changes}))[0],422)
        for _ in range(10): await self.create()
        self.assertEqual((await self.request('POST',payload=self.payload))[0],409)
        post=str(self.db.board_posts.documents[0]['_id']); thread=await self.response(post)
        self.db.board_threads.documents[0]['messages']*=50
        self.assertEqual((await self.request('POST',f"/threads/{thread['_id']}/messages",{'text':'too many'}))[0],409)
        self.assertEqual((await self.request('POST',f"/threads/{thread['_id']}/messages",{'text':'   '}))[0],422)
        self.assertEqual((await self.request('GET','/not-an-id'))[0],400)

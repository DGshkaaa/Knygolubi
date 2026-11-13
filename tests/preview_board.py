"""Local-only board UI preview; never uses MongoDB or a real email account.
Run: python -m uvicorn tests.preview_board:app --host 127.0.0.1 --port 8000
Demo login: author@example.com or reader@example.com, password: board-preview.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from bson import ObjectId
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from app.api import board
from app.api.deps import get_current_user
from app.schemas.user import UserInDatabase
from tests.test_board import Collection

app=FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5174','http://localhost:5174','http://localhost:5173'],allow_methods=['*'],allow_headers=['*'],expose_headers=['X-Has-Next','X-Total-Count'])
db=SimpleNamespace(board_posts=Collection(),board_threads=Collection(unique=('post_id','responder_id')),users=Collection())
people={address:UserInDatabase.model_validate({'_id':ObjectId(),'name':name,'email':address,'password_hash':'unused'}) for address,name in [('author@example.com','Марія Коваль'),('reader@example.com','Денис Читач')]}
for person in people.values(): db.users.documents.append({'_id':person.id,'notifications':[]})
owner=people['author@example.com']
now=datetime.now(timezone.utc)
for kind,title,author,description,location in [
    ('wanted','Місто','Валер’ян Підмогильний','Шукаю українське видання для спільного читання. Можливо, ваша книга саме зараз чекає нового читача?','Бібліотека коледжу'),
    ('exchange','Дюна','Френк Герберт','Маю паперове видання у хорошому стані. Обміняю на фантастику або щось із сучасної української прози.','Київ'),
    ('giveaway','Маленький принц','Антуан де Сент-Екзюпері','Дарую книгу з ілюстраціями. Уже прочитала й хочу передати комусь, хто ще не знайомий із цією історією.','Бібліотека коледжу')]:
    db.board_posts.documents.append({'_id':ObjectId(),'owner_id':owner.id,'owner_name':owner.name,'kind':kind,'book_title':title,'book_author':author,'description':description,'location':location,'status':'open','created_at':now,'expires_at':now+timedelta(days=30)})

async def database(): return db
async def current_user(request:Request):
    address=request.headers.get('authorization','').removeprefix('Bearer ')
    if address not in people: raise HTTPException(401,'Увійдіть у тестовий профіль.')
    return people[address]
app.dependency_overrides[board.database_dependency]=database
app.dependency_overrides[get_current_user]=current_user
app.include_router(board.router)

@app.post('/api/auth/login')
async def login(payload:dict):
    if payload.get('email') not in people or payload.get('password') != 'board-preview': raise HTTPException(401,'Використайте author@example.com / reader@example.com та board-preview')
    return {'access_token':payload['email'],'token_type':'bearer'}

@app.get('/api/auth/me')
async def me(request:Request):
    user=await current_user(request)
    return user.model_dump(mode='json',by_alias=True,exclude={'password_hash'})

@app.get('/api/books')
async def books(response:Response):
    response.headers['X-Has-Next']='false'
    return []

@app.get('/api/users/me/notifications')
async def notifications(request:Request):
    user=await current_user(request)
    data=await db.users.find_one({'_id':user.id})
    return [{**note,'board_post_id':str(note['board_post_id'])} for note in data['notifications']]

@app.patch('/api/users/me/notifications/read',status_code=204)
async def mark_read(request:Request):
    user=await current_user(request)
    for document in db.users.documents:
        if document['_id']==user.id:
            for note in document['notifications']: note['is_read']=True

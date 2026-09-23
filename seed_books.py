import asyncio
from datetime import datetime, timezone

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings


BOOKS = [
    {
        "title": "Clean Architecture",
        "author": "Robert C. Martin",
        "description": "Практичний посібник про архітектуру програмного забезпечення, якість коду та підтримуваність систем.",
        "genre": "Programming",
        "cover_image_url": "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?auto=format&fit=crop&w=800&q=80",
        "rating": 4.8,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "FastAPI: Modern Python Web Development",
        "author": "Bill Lubanovic",
        "description": "Покрокова книга про побудову API та вебсервісів на FastAPI з акцентом на практику та архітектуру.",
        "genre": "Programming",
        "cover_image_url": "https://images.unsplash.com/photo-1555949963-aa79dcee981c?auto=format&fit=crop&w=800&q=80",
        "rating": 4.7,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "MongoDB in Action",
        "author": "Kyle Banker",
        "description": "Книга про проєктування схем баз даних, індексування, масштабування та роботу зі складними документними даними.",
        "genre": "Programming",
        "cover_image_url": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?auto=format&fit=crop&w=800&q=80",
        "rating": 4.5,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "The Pragmatic Programmer",
        "author": "Andrew Hunt, David Thomas",
        "description": "Класична книга про професійні навички інженерів, ефективну роботу, автоматизацію та культуру якості.",
        "genre": "Programming",
        "cover_image_url": "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=800&q=80",
        "rating": 4.9,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "Unity 3D Game Development Essentials",
        "author": "Will Goldstone",
        "description": "Вичерпний посібник із розробки ігор на Unity 3D: введення в сцену, фізику, анімацію та поведінку гри.",
        "genre": "Mechanics",
        "cover_image_url": "https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=800&q=80",
        "rating": 4.6,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "Unreal Engine 5 for Beginners",
        "author": "Tom Looman",
        "description": "Практичний курс для початківців з Unreal Engine 5: світло, матеріали, Blueprints, анімація та створення прототипів.",
        "genre": "Mechanics",
        "cover_image_url": "https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=800&q=80",
        "rating": 4.4,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "The Art of Game Design",
        "author": "Jesse Schell",
        "description": "Книга про формування ідей, геймплейні цикли, механіку та креативний процес проектування ігор.",
        "genre": "Mechanics",
        "cover_image_url": "https://images.unsplash.com/photo-1526379095098-d400fd0bf935?auto=format&fit=crop&w=800&q=80",
        "rating": 4.8,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "Dota 2: The Ultimate Guide",
        "author": "Gabe T. Morris",
        "description": "Історія eSports, механіки Dota 2, статистика, метагейм, мікро-і макро-ігрові рішення та аналітика гри.",
        "genre": "Science",
        "cover_image_url": "https://images.unsplash.com/photo-1545239351-1141bd82e8a6?auto=format&fit=crop&w=800&q=80",
        "rating": 4.3,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "The Black Prism",
        "author": "Brent Weeks",
        "description": "Темне фентезі про магію, розпад людяності та етику сили в світі, де жорстокість і політика переплетені.",
        "genre": "Fantasy",
        "cover_image_url": "https://images.unsplash.com/photo-1512820790803-83ca734da794?auto=format&fit=crop&w=800&q=80",
        "rating": 4.7,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "The Haunting of Hill House",
        "author": "Shirley Jackson",
        "description": "Психологічний роман жахів, який змушує читача сумніватися в тому, чи самі будинки є вбивцями, чи людська психіка.",
        "genre": "Fiction",
        "cover_image_url": "https://images.unsplash.com/photo-1507842217343-583bb7270b66?auto=format&fit=crop&w=800&q=80",
        "rating": 4.9,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "Berserk, Vol. 1",
        "author": "Kentaro Miura",
        "description": "Чорне фентезі та психологічний жах, що розповідає про життя, втрати та руйнівну силу людської жорстокості.",
        "genre": "Fantasy",
        "cover_image_url": "https://images.unsplash.com/photo-1515377905703-c4788e51af15?auto=format&fit=crop&w=800&q=80",
        "rating": 4.8,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
    {
        "title": "C# in Depth",
        "author": "Jon Skeet",
        "description": "Глибоке занурення в мову C#, її типи, об’єктну модель, розширення, асинхронність і практичне використання.",
        "genre": "Programming",
        "cover_image_url": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=800&q=80",
        "rating": 4.6,
        "status": "available",
        "current_reader_id": None,
        "return_deadline": None,
        "queue": [],
        "reserved_for_user_id": None,
        "reservation_expires_at": None,
    },
]


async def main() -> None:
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_database]

    inserted = 0
    for book in BOOKS:
        existing = await db.books.find_one({"title": book["title"], "author": book["author"]})
        if existing is None:
            await db.books.insert_one(book)
            inserted += 1

    total = await db.books.count_documents({})
    print(f"Inserted {inserted} new books. Total books in {settings.mongodb_database}: {total}")


if __name__ == "__main__":
    asyncio.run(main())

from motor.motor_asyncio import AsyncIOMotorClient
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    db_name: str = "artfolio"
    admin_secret: str = "change-this-secret-key"
    cors_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.db_name]
    # Create indexes
    await db.artworks.create_index([("tags", 1)])
    await db.artworks.create_index([("medium", 1)])
    await db.artworks.create_index([("collection_id", 1)])
    await db.artworks.create_index([("created_at", -1)])
    await db.collections.create_index([("slug", 1)], unique=True)


async def close_db():
    global client
    if client:
        client.close()


def get_db():
    return client[settings.db_name]
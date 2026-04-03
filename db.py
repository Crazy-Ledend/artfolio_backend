from motor.motor_asyncio import AsyncIOMotorClient
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    db_name: str = "artfolio"
    admin_secret: str = "change-this-secret-key"
    cors_origins: str = "https://shellyeah.art"

    # Discord OAuth
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = "https://artfolio-api.onrender.com/auth/discord/callback"

    # JWT Session
    jwt_secret: str = "fallback-secret-for-dev-only"
    jwt_algorithm: str = "HS256"
    frontend_url: str = "https://shellyeah.art"

    class Config:
        env_file = ".env"


settings = Settings()

client: AsyncIOMotorClient = None


async def connect_db():
    global client
    client = AsyncIOMotorClient(
        settings.mongodb_url,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=10000,
        maxPoolSize=10,
        minPoolSize=2,        # keep 2 connections warm
    )
    db = client[settings.db_name]
    # Indexes for fast queries
    await db.artworks.create_index([("tags", 1)])
    await db.artworks.create_index([("medium", 1)])
    await db.artworks.create_index([("collection_id", 1)])
    await db.artworks.create_index([("sort_order", 1)])
    await db.artworks.create_index([("fusions", 1)])   # for fusion map lookups
    await db.artworks.create_index([("created_at", -1)])
    await db.collections.create_index([("slug", 1)], unique=True)
    await db.collections.create_index([("sort_order", 1)])
    await db.fusion_requests.create_index([("poke1", 1), ("poke2", 1)], unique=True)
    await db.fusion_requests.create_index([("votes", -1)])


async def close_db():
    global client
    if client:
        client.close()


def get_db():
    return client[settings.db_name]
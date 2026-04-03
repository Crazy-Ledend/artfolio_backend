from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import connect_db, close_db, settings
from routers import artworks, collections, contact, pokemon, profile, fusion_requests, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(title="Artfolio API", version="1.0.0", lifespan=lifespan, redirect_slashes=False)

origins = [o.strip() for o in settings.cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(artworks.router)
app.include_router(collections.router)
app.include_router(contact.router)
app.include_router(pokemon.router)
app.include_router(profile.router)
app.include_router(fusion_requests.router)
app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/ping")
async def ping():
    return "pong"

import time
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from pydantic import BaseModel
from db import settings

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_AUTH_URL = "https://discord.com/oauth2/authorize"
DISCORD_API_URL = "https://discord.com/api/v10"

security = HTTPBearer()


class DiscordUser(BaseModel):
    id: str
    username: str
    avatar: str | None = None
    global_name: str | None = None  # replaces deprecated discriminator


def create_access_token(data: dict, expires_days: int = 30) -> str:
    to_encode = data.copy()
    to_encode["exp"] = int(time.time()) + (expires_days * 86400)
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.get("/discord")
async def discord_login():
    params = {
        "client_id": settings.discord_client_id,
        "redirect_uri": settings.discord_redirect_uri,
        "response_type": "code",
        "scope": "identify",
    }
    async with httpx.AsyncClient() as client:
        url = client.build_request("GET", DISCORD_AUTH_URL, params=params).url
    return RedirectResponse(str(url))


@router.get("/discord/callback")
async def discord_callback(code: str | None = None, error: str | None = None):
    # Handle user cancellation or OAuth errors from Discord
    if error or not code:
        raise HTTPException(
            status_code=400,
            detail=f"Discord OAuth error: {error or 'no code received'}",
        )

    # 1. Exchange code for access token
    data = {
        "client_id": settings.discord_client_id,
        "client_secret": settings.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.discord_redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            f"{DISCORD_API_URL}/oauth2/token", data=data, headers=headers
        )
        if token_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Discord token")

        access_token = token_res.json()["access_token"]

        # 2. Fetch user info from Discord
        user_res = await client.get(
            f"{DISCORD_API_URL}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Discord user")

        user_data = user_res.json()

    # 3. Create JWT session token (30-day expiry)
    session_token = create_access_token(
        {
            "id": user_data["id"],
            "username": user_data["username"],
            "avatar": user_data.get("avatar"),
            "global_name": user_data.get("global_name"),  # may be None
        }
    )

    # 4. Redirect to frontend with token
    return RedirectResponse(
        f"{settings.frontend_url}/auth/callback?token={session_token}"
    )


@router.get("/me")
async def get_me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Returns the current user from the JWT.
    Requires: Authorization: Bearer <token>
    """
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
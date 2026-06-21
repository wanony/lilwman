from urllib.parse import urlencode

import aiohttp
from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

router = APIRouter()


class LoginRequired(Exception):
    def __init__(self, redirect_to: str = "/login") -> None:
        self.redirect_to = redirect_to


def make_serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key)


def get_session_data(cookie: str | None, serializer: URLSafeTimedSerializer) -> dict | None:
    if not cookie:
        return None
    try:
        return serializer.loads(cookie, max_age=86400)
    except (SignatureExpired, BadSignature):
        return None


def build_oauth_url(client_id: str, redirect_uri: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
    }
    return f"https://discord.com/oauth2/authorize?{urlencode(params)}"


def require_login(request: Request) -> dict:
    serializer = URLSafeTimedSerializer(request.app.state.secret_key)
    cookie = request.cookies.get("session")
    data = get_session_data(cookie, serializer)
    if data is None:
        if cookie:
            raise LoginRequired("/login?error=session_expired")
        raise LoginRequired("/login")
    return data


def get_flash(request: Request) -> str | None:
    return request.cookies.get("flash")


def redirect_with_flash(url: str, message: str) -> RedirectResponse:
    response = RedirectResponse(url, status_code=303)
    response.set_cookie("flash", message, max_age=10, httponly=True, samesite="lax")
    return response


@router.get("/login")
async def login_page(request: Request, error: str = ""):
    templates = request.app.state.templates
    return templates.TemplateResponse(request, "login.html", {"error": error})


@router.get("/auth/discord")
async def discord_oauth_redirect(request: Request) -> RedirectResponse:
    redirect_uri = f"{request.app.state.web_base_url}/auth/callback"
    url = build_oauth_url(request.app.state.client_id, redirect_uri)
    return RedirectResponse(url)


@router.get("/auth/callback")
async def discord_oauth_callback(request: Request, code: str = "") -> Response:
    if not code:
        return RedirectResponse("/login?error=auth_failed")

    redirect_uri = f"{request.app.state.web_base_url}/auth/callback"
    token_data = {
        "client_id": request.app.state.client_id,
        "client_secret": request.app.state.client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://discord.com/api/oauth2/token", data=token_data
        ) as resp:
            if resp.status != 200:
                return RedirectResponse("/login?error=auth_failed")
            token_json = await resp.json()

        access_token = token_json.get("access_token")
        if not access_token:
            return RedirectResponse("/login?error=auth_failed")

        headers = {"Authorization": f"Bearer {access_token}"}

        async with session.get("https://discord.com/api/users/@me", headers=headers) as resp:
            if resp.status != 200:
                return RedirectResponse("/login?error=auth_failed")
            user_data = await resp.json()

        async with session.get("https://discord.com/api/users/@me/guilds", headers=headers) as resp:
            if resp.status != 200:
                return RedirectResponse("/login?error=auth_failed")
            guilds = await resp.json()

    bot_guild_id = request.app.state.web_guild_id
    ADMINISTRATOR = 0x8
    authorized = any(
        str(g["id"]) == str(bot_guild_id) and (int(g.get("permissions", 0)) & ADMINISTRATOR)
        for g in guilds
    )
    if not authorized:
        return RedirectResponse("/login?error=not_authorized")

    session_data = {
        "user_id": str(user_data["id"]),
        "username": user_data["username"],
        "avatar": user_data.get("avatar") or "",
    }
    serializer = URLSafeTimedSerializer(request.app.state.secret_key)
    cookie_value = serializer.dumps(session_data)

    response = RedirectResponse("/", status_code=303)
    response.set_cookie("session", cookie_value, httponly=True, samesite="lax", max_age=86400)
    return response


@router.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("session")
    return response

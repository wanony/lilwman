from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import require_login, get_flash, redirect_with_flash

router = APIRouter()


@router.get("/config", response_class=HTMLResponse)
async def config_page(request: Request, user: dict = Depends(require_login)) -> HTMLResponse:
    flash = get_flash(request)
    config = await request.app.state.get_guild_config.execute(request.app.state.web_guild_id)
    response = request.app.state.templates.TemplateResponse(
        request, "config.html", {"config": config, "user": user, "flash": flash}
    )
    response.delete_cookie("flash")
    return response


@router.post("/config")
async def config_save(
    request: Request,
    user: dict = Depends(require_login),
    store_restricted: str = Form(""),
) -> RedirectResponse:
    value = store_restricted.lower() in ("true", "on", "1", "yes")
    await request.app.state.set_guild_config.execute(request.app.state.web_guild_id, value)
    return redirect_with_flash("/config", "Configuration saved.")

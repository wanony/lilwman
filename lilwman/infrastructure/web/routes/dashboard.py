from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..auth import require_login, get_flash

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(require_login)) -> HTMLResponse:
    flash = get_flash(request)
    stats = await request.app.state.get_stats.execute(request.app.state.web_guild_id)
    response = request.app.state.templates.TemplateResponse(
        request, "dashboard.html", {"stats": stats, "user": user, "flash": flash}
    )
    response.delete_cookie("flash")
    return response

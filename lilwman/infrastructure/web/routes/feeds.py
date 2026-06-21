from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import require_login, get_flash, redirect_with_flash

router = APIRouter(prefix="/feeds")


@router.get("", response_class=HTMLResponse)
async def feeds_list(request: Request, user: dict = Depends(require_login)) -> HTMLResponse:
    flash = get_flash(request)
    feeds = await request.app.state.list_all_feeds.execute()
    response = request.app.state.templates.TemplateResponse(
        request, "feeds.html", {"feeds": feeds, "user": user, "flash": flash}
    )
    response.delete_cookie("flash")
    return response


@router.post("/{feed_id}/delete")
async def feed_delete(
    request: Request, feed_id: int, user: dict = Depends(require_login)
) -> RedirectResponse:
    await request.app.state.delete_feed.execute(feed_id, channel_id="", admin=True)
    return redirect_with_flash("/feeds", f"Feed #{feed_id} deleted.")

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..auth import require_login, get_flash, redirect_with_flash

router = APIRouter(prefix="/entries")


@router.get("", response_class=HTMLResponse)
async def entries_list(
    request: Request,
    user: dict = Depends(require_login),
    q: str = "",
    author_id: str = "",
    page: int = 1,
) -> HTMLResponse:
    flash = get_flash(request)
    per_page = 20
    if q:
        all_entries, _ = await request.app.state.list_all_entries.execute(page=1, per_page=9999)
        filtered = [
            e for e in all_entries
            if q.lower() in e.content.lower() or any(q.lower() in t for t in e.tags)
        ]
        total = len(filtered)
        offset = (page - 1) * per_page
        entries_page = filtered[offset:offset + per_page]
    elif author_id:
        entries_page = await request.app.state.list_by_author.execute(author_id)
        total = len(entries_page)
    else:
        entries_page, total = await request.app.state.list_all_entries.execute(page=page, per_page=per_page)

    has_next = (page * per_page) < total
    response = request.app.state.templates.TemplateResponse(
        request, "entries.html",
        {
            "entries": entries_page, "user": user,
            "flash": flash, "q": q, "author_id": author_id,
            "page": page, "has_next": has_next, "total": total,
        },
    )
    response.delete_cookie("flash")
    return response


@router.get("/{entry_id}/edit", response_class=HTMLResponse)
async def entry_edit_form(
    request: Request, entry_id: int, user: dict = Depends(require_login)
) -> HTMLResponse:
    entry = await request.app.state.get_entry.execute(entry_id)
    if entry is None:
        return redirect_with_flash("/entries", f"Entry #{entry_id} not found.")
    flash = get_flash(request)
    response = request.app.state.templates.TemplateResponse(
        request, "entry_edit.html", {"entry": entry, "user": user, "flash": flash}
    )
    response.delete_cookie("flash")
    return response


@router.post("/{entry_id}/edit")
async def entry_edit_save(
    request: Request,
    entry_id: int,
    user: dict = Depends(require_login),
    content: str = Form(...),
    tags: str = Form(""),
) -> RedirectResponse:
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    entry = await request.app.state.edit_entry.execute(entry_id, content, tag_list)
    if entry is None:
        return redirect_with_flash("/entries", f"Entry #{entry_id} not found.")
    return redirect_with_flash("/entries", f"Entry #{entry_id} updated.")


@router.post("/{entry_id}/delete")
async def entry_delete(
    request: Request, entry_id: int, user: dict = Depends(require_login)
) -> RedirectResponse:
    await request.app.state.delete_entry.execute(entry_id, "web-admin", is_admin=True)
    return redirect_with_flash("/entries", f"Entry #{entry_id} deleted.")


@router.post("/purge/user")
async def purge_user(
    request: Request,
    user: dict = Depends(require_login),
    author_id: str = Form(...),
) -> RedirectResponse:
    count = await request.app.state.purge_by_author.execute(author_id)
    return redirect_with_flash("/entries", f"Deleted {count} entries.")


@router.post("/purge/tag")
async def purge_tag(
    request: Request,
    user: dict = Depends(require_login),
    tag: str = Form(...),
) -> RedirectResponse:
    count = await request.app.state.purge_by_tag.execute(tag)
    return redirect_with_flash("/entries", f"Deleted {count} entries tagged '{tag}'.")

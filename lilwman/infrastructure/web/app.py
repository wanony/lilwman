from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .auth import LoginRequired, router as auth_router


def create_app(
    *,
    secret_key: str,
    client_id: str,
    client_secret: str,
    web_base_url: str,
    web_guild_id: str,
    get_stats,
    get_entry,
    edit_entry,
    list_all_entries,
    list_by_author,
    purge_by_author,
    purge_by_tag,
    delete_entry,
    list_all_feeds,
    delete_feed,
    get_guild_config,
    set_guild_config,
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None)

    app.state.secret_key = secret_key
    app.state.client_id = client_id
    app.state.client_secret = client_secret
    app.state.web_base_url = web_base_url
    app.state.web_guild_id = web_guild_id
    app.state.get_stats = get_stats
    app.state.get_entry = get_entry
    app.state.edit_entry = edit_entry
    app.state.list_all_entries = list_all_entries
    app.state.list_by_author = list_by_author
    app.state.purge_by_author = purge_by_author
    app.state.purge_by_tag = purge_by_tag
    app.state.delete_entry = delete_entry
    app.state.list_all_feeds = list_all_feeds
    app.state.delete_feed = delete_feed
    app.state.get_guild_config = get_guild_config
    app.state.set_guild_config = set_guild_config

    templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
    app.state.templates = templates

    @app.exception_handler(LoginRequired)
    async def login_required_handler(request: Request, exc: LoginRequired):
        return RedirectResponse(exc.redirect_to)

    app.include_router(auth_router)

    from .routes.dashboard import router as dashboard_router
    from .routes.entries import router as entries_router
    from .routes.feeds import router as feeds_router
    from .routes.config_route import router as config_router

    app.include_router(dashboard_router)
    app.include_router(entries_router)
    app.include_router(feeds_router)
    app.include_router(config_router)

    return app

"""The whole site in one process: the API at SITE_URL/api and (optionally) the
built React frontend at SITE_URL/.

Path prefixes: requests may arrive with the site's prefix (e.g. /cse1010/api/me)
or with it stripped by the reverse proxy (/api/me). `HuskyPollSite` first puts
every request into the full form, so the rest of the app only ever sees one
shape and never has to know how the proxy is configured.

One frontend build works under any prefix: Vite builds it with relative asset
paths (base './'), and when index.html is served we add
    <base href="/cse1010/">                       so assets and links resolve under the prefix
    window.__HUSKYPOLL__ = {apiBase, basePath}    so the frontend knows where the API is
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from starlette.requests import Request
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)

from .config import Settings


def _starts(path: str, prefix: str) -> bool:
    return not prefix or path == prefix or path.startswith(prefix + "/")


class HuskyPollSite:
    """ASGI app: normalizes the path prefix, then routes to the API or the frontend."""

    def __init__(self, api, settings: Settings):
        self.api = api
        self.settings = settings
        self.site_base = settings.site_base_path
        self.api_base = settings.base_path
        self.frontend = FrontendFiles(settings) if settings.frontend_dist else None

    @property
    def state(self):  # lets code and tests use app.state like a FastAPI app
        return self.api.state

    def _full_path(self, path: str) -> str:
        if self.frontend is not None:                     # serving the whole site
            return path if _starts(path, self.site_base) else self.site_base + path
        if _starts(path, self.api_base):                  # API only, prefix kept
            return path
        if self.site_base and _starts(self.site_base + path, self.api_base):
            return self.site_base + path                  # proxy stripped the site prefix
        return self.api_base + path                       # proxy stripped the whole API prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            full = self._full_path(scope["path"])
            if full != scope["path"]:
                scope = dict(scope, path=full, raw_path=full.encode())
            scope = dict(scope, root_path="")
            if self.frontend is not None and not _starts(full, self.api_base):
                await self.frontend(scope, receive, send)
                return
        await self.api(scope, receive, send)


class FrontendFiles:
    """Serves frontend/dist. Unknown paths get index.html so React can route them (/courses/3)."""

    def __init__(self, settings: Settings):
        self.dist = settings.frontend_dist.resolve()
        self.site_base = settings.site_base_path
        index = self.dist / "index.html"
        if not index.is_file():
            raise RuntimeError(f"HUSKYPOLL_FRONTEND_DIST={settings.frontend_dist} has no index.html; "
                               "run `npm run build` in the frontend folder first")
        config = {"basePath": self.site_base, "apiBase": settings.base_path, "siteUrl": settings.site_url,
                  "devLogin": settings.dev_login}
        script = json.dumps(config).replace("</", "<\\/")
        inject = (f'<base href="{html.escape(self.site_base)}/">'
                  f"<script>window.__HUSKYPOLL__ = {script};</script>")
        page = index.read_text(encoding="utf-8")
        page, n = re.subn(r"(<head[^>]*>)", lambda m: m.group(1) + inject, page, count=1, flags=re.IGNORECASE)
        if n == 0:
            page = inject + page
        self.index_html = page

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return  # websockets only exist on the API
        request = Request(scope)
        rel = scope["path"][len(self.site_base):]
        if rel == "":  # /cse1010 -> /cse1010/ so relative links resolve inside the prefix
            url = self.site_base + "/" + (f"?{request.url.query}" if request.url.query else "")
            response: Response = RedirectResponse(url, status_code=308)
        elif request.method not in ("GET", "HEAD"):
            response = PlainTextResponse("Method Not Allowed", status_code=405)
        else:
            response = self._file_or_index(rel.lstrip("/"))
        await response(scope, receive, send)

    def _file_or_index(self, rel: str) -> Response:
        if rel and rel != "index.html":
            candidate = (self.dist / rel).resolve()
            if candidate.is_file() and self.dist in candidate.parents:
                hashed = rel.startswith("assets/")  # Vite names these by content hash
                cache = "public, max-age=31536000, immutable" if hashed else "no-cache"
                return FileResponse(candidate, headers={"Cache-Control": cache})
            if rel.startswith("assets/") or Path(rel).suffix in (".js", ".css", ".map", ".png", ".svg", ".ico"):
                return PlainTextResponse("Not Found", status_code=404)  # don't answer a missing file with HTML
        return HTMLResponse(self.index_html, headers={"Cache-Control": "no-cache"})

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from kataribe import __version__
from kataribe.access import is_public, is_team
from kataribe.api import sessions, talk, visitors
from kataribe.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="kataribe", version=__version__)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.team_password:
        password = settings.team_password

        @app.middleware("http")
        async def team_only(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
        ) -> Response:
            # Remembered for routes that serve both, such as the talk screen.
            request.state.team = is_team(request.headers.get("authorization"), password)
            if request.state.team or is_public(request.url.path):
                return await call_next(request)
            return Response(
                status_code=401, headers={"WWW-Authenticate": 'Basic realm="kataribe team"'}
            )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(sessions.router)
    app.include_router(talk.router)
    app.include_router(visitors.router)

    if settings.static_dir:
        pages = settings.static_dir.resolve()

        # Last, so every API route is matched first.
        @app.get("/{path:path}", include_in_schema=False)
        def page(path: str) -> FileResponse:
            """The built frontend. A path that is not a file is a page of the
            single-page app, which decides from the path what to show."""
            if path == "api" or path.startswith("api/"):
                raise HTTPException(status_code=404)
            file = (pages / path).resolve()
            if file.is_file() and file.is_relative_to(pages):
                return FileResponse(file)
            return FileResponse(pages / "index.html")

    return app


app = create_app()

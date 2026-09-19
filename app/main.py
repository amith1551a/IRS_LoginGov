"""FastAPI application: IRIS Etel IAM demo with ZITADEL sign-in."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app import auth, config

app = FastAPI(root_path=config.APP_ROOT_PATH)

# Session middleware (required for OIDC state/nonce and user session)
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    session_cookie="iam_demo_session",
    max_age=3600,
    same_site="lax",
    https_only=config.SESSION_HTTPS_ONLY,
)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)

templates = Jinja2Templates(directory="templates")


def url_for(request: Request, name: str, **path_params) -> str:
    """Build an absolute URL that respects root_path."""
    return request.url_for(name, **path_params)


@app.get("/", response_class=HTMLResponse, name="index")
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": request.session.get("user"),
            "roles": request.session.get("roles", []),
            "root_path": config.APP_ROOT_PATH,
        },
    )


@app.get("/auth/login", name="login")
async def login(request: Request):
    """Initiate the OIDC authorization code flow with PKCE."""
    pkce = auth.generate_pkce()
    state = auth.generate_state_nonce()
    nonce = auth.generate_state_nonce()

    request.session["oidc_state"] = state
    request.session["oidc_nonce"] = nonce

    redirect_uri = config.OIDC_REDIRECT_URI

    zitadel = auth.oauth.create_client("zitadel")
    return await zitadel.authorize_redirect(
        request,
        redirect_uri,
        response_type="code",
        state=state,
        nonce=nonce,
        code_verifier=pkce["verifier"],
        prompt="select_account",
    )


@app.get("/auth/callback", name="callback")
async def auth_callback(request: Request):
    """Handle the OIDC callback, validate tokens, and start the session."""
    # ZITADEL redirects here after logout when this callback is configured as
    # the post-logout URI. Unlike an authorization response, it has no code.
    if "code" not in request.query_params:
        return RedirectResponse(url=config.APP_ROOT_PATH or "/", status_code=303)

    # Validate state to prevent CSRF
    returned_state = request.query_params.get("state")
    expected_state = request.session.get("oidc_state")
    if not returned_state or returned_state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid OIDC state parameter")

    nonce = request.session.get("oidc_nonce")

    zitadel = auth.oauth.create_client("zitadel")
    token = await zitadel.authorize_access_token(request)

    id_token = token.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="ID token missing from token response")

    jwks = await auth.fetch_jwks()
    try:
        claims = auth.decode_id_token(
            id_token, jwks, nonce=nonce, access_token=token.get("access_token")
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"ID token validation failed: {exc}")

    print(f"DEBUG ID token claims: {claims}")

    auth.store_oidc_session(request, token, claims)

    # Clean up transient OIDC session keys
    request.session.pop("oidc_state", None)
    request.session.pop("oidc_nonce", None)

    return RedirectResponse(url=f"{config.APP_ROOT_PATH}/success", status_code=303)


@app.get("/success", response_class=HTMLResponse, name="success")
async def success(request: Request):
    user = request.session.get("user")
    if not user:
        return RedirectResponse(url=config.APP_ROOT_PATH or "/", status_code=303)

    roles = request.session.get("roles", [])
    if not roles:
        return templates.TemplateResponse(
            "no_access.html",
            {
                "request": request,
                "user": user,
                "root_path": config.APP_ROOT_PATH,
            },
        )

    return templates.TemplateResponse(
        "success.html",
        {
            "request": request,
            "user": user,
            "roles": roles,
            "root_path": config.APP_ROOT_PATH,
        },
    )


@app.get("/auth/logout", name="logout")
async def logout(request: Request):
    """Clear local session and redirect to ZITADEL end_session_endpoint."""
    id_token = request.session.get("id_token")
    auth.clear_oidc_session(request)

    # Fetch end_session_endpoint from discovery
    import httpx
    from urllib.parse import urlencode

    async with httpx.AsyncClient() as client:
        meta_resp = await client.get(config.OIDC_DISCOVERY_URL)
        meta_resp.raise_for_status()
        metadata = meta_resp.json()
        end_session = metadata.get("end_session_endpoint")

    if end_session:
        params = {
            "client_id": config.OIDC_CLIENT_ID,
            "post_logout_redirect_uri": config.OIDC_POST_LOGOUT_URI,
        }
        if id_token:
            params["id_token_hint"] = id_token
        logout_url = f"{end_session}?{urlencode(params)}"
        return RedirectResponse(url=logout_url, status_code=303)

    return RedirectResponse(url=config.APP_ROOT_PATH or "/", status_code=303)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "root_path": config.APP_ROOT_PATH,
        },
        status_code=exc.status_code,
    )

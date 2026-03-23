import base64
import json
import os

import httpx
from fastapi import APIRouter, FastAPI
from fastapi.responses import RedirectResponse

app = FastAPI(title="Star OAuth Backend")
router = APIRouter()

GITHUB_OAUTH_CLIENT_ID = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
GITHUB_OAUTH_CLIENT_SECRET = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")


@router.get("/star/callback")
async def star_callback(code: str, state: str):
    # 1. 解码 state
    try:
        state_data = json.loads(base64.b64decode(state + "==").decode("utf-8"))
        return_url = state_data["return_url"]
        owner = state_data["owner"]
        repo = state_data["repo"]
    except Exception:
        return RedirectResponse(url="/?star_error=1", status_code=302)

    error_url = f"{return_url}?star_error=1"

    async with httpx.AsyncClient() as client:
        # 2. 用 code 交换 access_token
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_OAUTH_CLIENT_ID,
                "client_secret": GITHUB_OAUTH_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(url=error_url, status_code=302)

        # 3. Star 仓库
        star_resp = await client.put(
            f"https://api.github.com/user/starred/{owner}/{repo}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Length": "0",
            },
        )
        if star_resp.status_code != 204:
            return RedirectResponse(url=error_url, status_code=302)

    return RedirectResponse(url=f"{return_url}?starred=1", status_code=302)


@router.get("/star/status")
async def star_status(owner: str, repo: str, token: str | None = None):
    """查询用户是否已 Star 指定仓库（可选端点）"""
    if not token:
        return {"starred": None}

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/user/starred/{owner}/{repo}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if resp.status_code == 204:
            return {"starred": True}
        elif resp.status_code == 404:
            return {"starred": False}
        else:
            return {"starred": None}


@router.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(router)

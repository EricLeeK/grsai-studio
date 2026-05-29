"""WeChat Official Account API client."""

from __future__ import annotations

import json
import mimetypes
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app import config

WECHAT_BASE_URL = "https://api.weixin.qq.com"


class WeChatError(RuntimeError):
    """Raised when WeChat returns an API error."""


def _check_wechat_response(data: dict[str, Any]) -> dict[str, Any]:
    errcode = data.get("errcode")
    if errcode not in (None, 0):
        errmsg = data.get("errmsg", "Unknown WeChat API error")
        raise WeChatError(f"WeChat API error {errcode}: {errmsg}")
    return data


def _get_json(url: str, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full_url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise WeChatError(f"WeChat HTTP error: {detail}") from exc
    except urllib.error.URLError as exc:
        raise WeChatError(f"WeChat request failed: {exc.reason}") from exc


def _post_json(url: str, payload: dict[str, Any], params: dict[str, Any], timeout: int) -> dict[str, Any]:
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        full_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise WeChatError(f"WeChat HTTP error: {detail}") from exc
    except urllib.error.URLError as exc:
        raise WeChatError(f"WeChat request failed: {exc.reason}") from exc


def _post_file(url: str, file_path: Path, params: dict[str, Any], timeout: int) -> dict[str, Any]:
    boundary = f"----grsai-studio-{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    full_url = f"{url}?{urllib.parse.urlencode(params)}"

    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{file_path.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    tail = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = head + file_path.read_bytes() + tail

    request = urllib.request.Request(
        full_url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise WeChatError(f"WeChat HTTP error: {detail}") from exc
    except urllib.error.URLError as exc:
        raise WeChatError(f"WeChat request failed: {exc.reason}") from exc


class WeChatClient:
    def __init__(
        self,
        *,
        appid: str | None = None,
        secret: str | None = None,
        base_url: str = WECHAT_BASE_URL,
        get_json: Callable[[str, dict[str, Any], int], dict[str, Any]] = _get_json,
        post_json: Callable[[str, dict[str, Any], dict[str, Any], int], dict[str, Any]] = _post_json,
        post_file: Callable[[str, Path, dict[str, Any], int], dict[str, Any]] = _post_file,
        now: Callable[[], float] = time.time,
    ):
        self.appid = appid if appid is not None else config.WECHAT_APPID
        self.secret = secret if secret is not None else config.WECHAT_SECRET
        self.base_url = base_url.rstrip("/")
        self._get_json = get_json
        self._post_json = post_json
        self._post_file = post_file
        self._now = now
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

    def get_access_token(self) -> str:
        if self._access_token and self._now() < self._access_token_expires_at:
            return self._access_token
        if not self.appid or not self.secret:
            raise WeChatError("WECHAT_APPID and WECHAT_SECRET are required")

        data = self._get_json(
            f"{self.base_url}/cgi-bin/token",
            {
                "grant_type": "client_credential",
                "appid": self.appid,
                "secret": self.secret,
            },
            30,
        )
        _check_wechat_response(data)
        token = data.get("access_token")
        if not token:
            raise WeChatError("WeChat response did not include access_token")

        expires_in = int(data.get("expires_in", 7200))
        self._access_token = token
        self._access_token_expires_at = self._now() + max(60, expires_in - 300)
        return token

    def upload_image(self, file_path: str | Path) -> str:
        path = Path(file_path)
        if not path.exists():
            raise WeChatError(f"Cover image does not exist: {path}")

        data = self._post_file(
            f"{self.base_url}/cgi-bin/material/add_material",
            path,
            {"access_token": self.get_access_token(), "type": "image"},
            90,
        )
        _check_wechat_response(data)
        media_id = data.get("media_id")
        if not media_id:
            raise WeChatError("WeChat response did not include media_id")
        return media_id

    def create_draft(
        self,
        *,
        title: str,
        content_html: str,
        cover_media_id: str,
        author: str = "",
        digest: str = "",
    ) -> str:
        article = {
            "title": title,
            "author": author,
            "digest": digest,
            "content": content_html,
            "thumb_media_id": cover_media_id,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }
        data = self._post_json(
            f"{self.base_url}/cgi-bin/draft/add",
            {"articles": [article]},
            {"access_token": self.get_access_token()},
            60,
        )
        _check_wechat_response(data)
        media_id = data.get("media_id")
        if not media_id:
            raise WeChatError("WeChat response did not include draft media_id")
        return media_id

"""Markdown to WeChat-ready HTML conversion through Gemini."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from app import config

STYLE_LABELS = {
    "minimal": "简洁",
    "business": "商务",
    "tech": "科技",
}

STYLE_PALETTES = {
    "minimal": "主题色 #5F7F3A，浅背景 #F6F8EF，正文 #222222，辅助文字 #666666",
    "business": "主题色 #1F5C99，浅背景 #F2F6FA，正文 #20242A，辅助文字 #667085",
    "tech": "主题色 #1D7A8C，浅背景 #EEF8FA，正文 #182026，辅助文字 #5D6B73",
}


class ConverterError(RuntimeError):
    """Raised when Gemini cannot produce usable HTML."""


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ConverterError(f"Gemini API error: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ConverterError(f"Gemini request failed: {exc.reason}") from exc


def _build_prompt(markdown: str, style: str) -> str:
    label = STYLE_LABELS.get(style, STYLE_LABELS["minimal"])
    palette = STYLE_PALETTES.get(style, STYLE_PALETTES["minimal"])
    return f"""你是微信公众号排版专家。你的任务是把 Markdown 做无损排版转换为适合微信公众号图文编辑器粘贴的 HTML。

硬性要求：
- 只输出 HTML 片段，不要解释，不要 Markdown 代码围栏。
- 这是格式转换，不是改写。不得摘要，不得概括，不得润色，不得删减，不得合并段落，不得加入原文没有的信息。
- 必须保留原文每一句、每个列表项、每个引用、每段代码、每个链接文字和 URL，以及原文的表达顺序。
- 除了把 Markdown 语法转换成 HTML 标签和添加内联样式，不要改变正文内容；标点、数字、专有名词、中文/英文原句都要原样保留。
- 如果内容很长，也必须继续输出完整 HTML，不要用“省略”“等等”“其余同上”或 ellipsis 代替正文。
- 所有样式必须写成内联 style，不能依赖外部 CSS、script、class 或 id。
- 使用微信公众号兼容标签：section、p、h1、h2、h3、blockquote、ul、ol、li、strong、em、span、img、a、table。
- 输出必须是微信草稿后台更容易保留颜色的兼容 HTML：不要输出 <style> 标签，不要使用 class/id，不要使用 rgba/rgb/hsl/oklch/color-mix，不要使用渐变、阴影、滤镜、动画、position、float、flex、grid、transform。
- 颜色必须使用十六进制颜色，例如 #1D7A8C。不要使用 rgba 或透明色。
- 必须使用主题色和浅色背景做出可见的彩色排版，避免上传到微信后只剩黑白。
- 推荐使用这些微信兼容 CSS 属性：color、background-color、border-left、border-bottom、padding、margin、font-size、font-weight、line-height、text-align、display。
- 宽度适配手机阅读，正文行高舒适，段落间距明确。
- 风格采用「{label}」：层级清晰、适合公众号发布。调色板：{palette}。
- 代码块用等宽字体和浅色背景表达，但代码文本必须逐字保留。

Markdown：
{markdown}
"""


def _extract_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        raise ConverterError("Gemini returned no candidates")

    finish_reason = candidates[0].get("finishReason")
    if finish_reason == "MAX_TOKENS":
        raise ConverterError("Gemini hit the output token limit. Try splitting the article or using a shorter section.")

    parts = candidates[0].get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts)
    if not text.strip():
        raise ConverterError("Gemini returned empty content")
    return text


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:html)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else stripped


def convert_markdown_to_wechat_html(
    markdown: str,
    style: str = "minimal",
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    post_json: Callable[[str, dict[str, Any], dict[str, str], int], dict[str, Any]] = _post_json,
) -> str:
    """Convert Markdown into inline-styled WeChat-compatible HTML."""
    markdown = markdown.strip()
    if not markdown:
        raise ConverterError("Markdown content is required")

    resolved_api_key = api_key if api_key is not None else config.GEMINI_API_KEY
    if not resolved_api_key:
        raise ConverterError("GEMINI_API_KEY is not configured")

    resolved_base_url = (base_url or config.GEMINI_BASE_URL).rstrip("/")
    resolved_model = model or config.GEMINI_MODEL
    url = f"{resolved_base_url}/models/{resolved_model}:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": _build_prompt(markdown, style)}],
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "topP": 0.9,
            "maxOutputTokens": 65536,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": resolved_api_key,
    }

    response = post_json(url, payload, headers, 60)
    return _strip_code_fence(_extract_text(response))

"""SOLO ``llm_utils_chat`` upstream channel: native tools in, structured tool_calls out.

Wire protocol verified 2026-09-27 against Trae CN with ``function=solo_work_lite``:

- ``POST /api/agent/v3/llm_utils_chat`` with ``Authorization: Cloud-IDE-JWT <token>``
  plus the full desktop-client header set.  ``X-Ide-Version`` unlocks the model
  catalog: ``0.1.52`` (code 20260811) returns the current models (glm-5.3,
  DeepSeek-V4.1, Seed-2.1-Pro...), older versions get business code 4001.
- The request body carries OpenAI-style ``tools`` natively (``parameters``
  serialized as a JSON string) and assistant tool history in the upstream
  ``function_call`` shape.
- SSE ``event:output`` frames carry ``{response, reasoning_content, tool_calls}``.
  Tool calls stream incrementally: the first fragment holds ``id``/``name``, later
  fragments carry argument deltas keyed by ``index``.
- ``event:token_usage`` reports this request's own prompt/completion counts
  (unlike the remote agent channel's cumulative agent bill).

Risk-control notes (account safety):
- Per-account concurrency is capped (upstream tolerates ~2 parallel sessions).
- Upstream business codes are classified instead of blindly retried: 1001 auth,
  4001 bad params, 4008 quota exhausted, 4011 rate limited.  A failed turn is
  never replayed automatically — replays would double-bill the account.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, AsyncIterator, Mapping, Optional

import httpx

logger = logging.getLogger("trae2api.solo")

SOLO_GATEWAY = "https://trae-api-cn.mchost.guru"
CHAT_PATH = "/api/agent/v3/llm_utils_chat"
MODELS_PATH = "/api/ide/v1/get_detail_param"
EXCHANGE_PATH = "/cloudide/api/v3/trae/oauth/ExchangeToken"
APP_ID = "6eefa01c-1036-4c7e-9ca5-d891f63bfcd8"
IDE_VERSION = "0.1.52"
IDE_VERSION_CODE = "20260811"
DEVICE_BRAND = "83DG"
OS_VERSION = "Windows 11 Pro"
USER_AGENT = "Trae/" + IDE_VERSION

# Upstream business codes worth naming explicitly.
CODE_AUTH = 1001
CODE_PLAN_LIMIT = 1005
CODE_BAD_PARAM = 4001
CODE_QUOTA = 4008
CODE_RATE_LIMIT = 4011


class SoloUpstreamError(RuntimeError):
    """Upstream business or transport failure with a stable classification."""

    def __init__(self, message: str, *, code: int = 0, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable

    @property
    def kind(self) -> str:
        if self.code == CODE_AUTH:
            return "auth"
        if self.code == CODE_QUOTA:
            return "quota"
        if self.code in (CODE_RATE_LIMIT, CODE_PLAN_LIMIT):
            return "rate_limit"
        if self.code == CODE_BAD_PARAM:
            return "bad_param"
        return "upstream"


def solo_base_url() -> str:
    return (os.environ.get("TRAE_SOLO_BASE_URL") or SOLO_GATEWAY).rstrip("/")


def solo_headers(token: str, user_id: str, *, stream: bool = True) -> dict[str, str]:
    """Full header set matching the Trae CN desktop client.

    Risk control watches header consistency: keep the version triple and the
    device fields stable instead of varying them per request.
    """
    return {
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
        "User-Agent": USER_AGENT,
        "Authorization": "Cloud-IDE-JWT " + token,
        "X-Cloudide-Token": token,
        "X-Ide-Token": token,
        "X-Uid": str(user_id or ""),
        "X-App-Id": APP_ID,
        "X-App-Version": "default",
        "X-Ide-Version": IDE_VERSION,
        "X-Ide-Version-Code": IDE_VERSION_CODE,
        "X-App-Version-Code": IDE_VERSION_CODE,
        "X-Ide-Version-Type": "stable",
        "X-Device-Type": "windows",
        "X-OS-Version": OS_VERSION,
        "X-Device-Brand": DEVICE_BRAND,
        "Request-Traffic-Type": "prod",
    }


# ──────────────────────────── request body ────────────────────────────


def _text_parts(content: Any) -> Any:
    """Convert OpenAI content to the upstream block-list shape."""
    if content is None:
        return None
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return content
    return [{"type": "text", "text": str(content)}]


def _wire_messages(messages: Any) -> list[dict]:
    """Convert OpenAI messages to SOLO wire shapes (tool history included)."""
    converted: list[dict] = []
    for message in messages or []:
        if not isinstance(message, Mapping):
            continue
        item = dict(message)
        parts = _text_parts(item.get("content"))
        if parts is None:
            item.pop("content", None)
        else:
            item["content"] = parts
        if item.get("role") == "assistant" and isinstance(item.get("tool_calls"), list):
            calls = []
            for call in item["tool_calls"]:
                if not isinstance(call, Mapping):
                    continue
                function = call.get("function")
                function = function if isinstance(function, Mapping) else call
                name = str(function.get("name") or "").strip()
                if not name:
                    continue
                arguments = function.get("arguments", function.get("input", {}))
                if not isinstance(arguments, str):
                    arguments = json.dumps(
                        arguments, ensure_ascii=False, separators=(",", ":"), default=str
                    )
                native = dict(call)
                native.pop("function", None)
                native["function_call"] = {"name": name, "arguments": arguments}
                calls.append(native)
            if calls:
                item["tool_calls"] = calls
            else:
                item.pop("tool_calls", None)
        converted.append(item)
    return converted


def _wire_tools(tools: Any) -> list[dict]:
    """Normalize OpenAI tools for the upstream function schema.

    The upstream wants ``parameters`` as a JSON string rather than an object.
    """
    result: list[dict] = []
    if not isinstance(tools, list):
        return result
    for tool in tools:
        if not isinstance(tool, Mapping):
            continue
        function = tool.get("function")
        if not isinstance(function, Mapping) or not function.get("name"):
            continue
        item = dict(tool)
        item["function"] = dict(function)
        parameters = item["function"].get("parameters")
        if isinstance(parameters, Mapping):
            item["function"]["parameters"] = json.dumps(
                parameters, ensure_ascii=False, separators=(",", ":"), default=str
            )
        result.append(item)
    return result


def _wire_tool_choice(tool_choice: Any) -> Optional[str]:
    """Flatten OpenAI tool_choice to the upstream scalar form (or suppress)."""
    if tool_choice is None:
        return None
    if isinstance(tool_choice, Mapping):
        selected = tool_choice.get("function") if tool_choice.get("type") == "function" else tool_choice
        if isinstance(selected, Mapping) and selected.get("name"):
            return str(selected["name"])
        kind = str(tool_choice.get("type") or "").lower()
        return kind if kind in {"auto", "required"} else None
    value = str(tool_choice).strip().lower()
    return None if value == "none" else value or None


def build_solo_body(
    messages: Any,
    model: str,
    *,
    tools: Any = None,
    tool_choice: Any = None,
    max_tokens: Optional[int] = None,
    session_id: str = "",
) -> dict[str, Any]:
    """Build one ``llm_utils_chat`` request body."""
    name = str(model or "").strip() or "glm-5.2"
    body: dict[str, Any] = {
        "messages": _wire_messages(messages),
        "function": "solo_work_lite",
        "stream": True,
        "config_name": name,
        "model": name,
    }
    if session_id:
        body["session_id"] = session_id
    normalized = _wire_tools(tools)
    choice = _wire_tool_choice(tool_choice)
    if normalized and choice != "none":
        body["tools"] = normalized
        if choice:
            body["tool_choice"] = choice
    if isinstance(max_tokens, (int, float)) and not isinstance(max_tokens, bool) and max_tokens > 0:
        body["max_tokens"] = min(int(max_tokens), 32768)
    return body


# ──────────────────────────── SSE parsing ────────────────────────────


def _data_json(payload: str) -> dict:
    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError):
        return {"_raw": payload}
    return parsed if isinstance(parsed, dict) else {"_raw": payload}


async def stream_events(
    client: httpx.AsyncClient, token: str, user_id: str, body: Mapping[str, Any]
) -> AsyncIterator[tuple[str, dict]]:
    """Yield normalized ``(event, data)`` pairs from the upstream SSE stream."""
    url = solo_base_url() + CHAT_PATH
    async with client.stream(
        "POST",
        url,
        headers=solo_headers(token, user_id, stream=True),
        json=dict(body),
        timeout=httpx.Timeout(300.0, connect=30.0),
    ) as response:
        if response.status_code != 200:
            raw = (await response.aread()).decode("utf-8", "replace")[:500]
            code = 0
            try:
                code = int(_data_json(raw).get("code") or 0)
            except (TypeError, ValueError):
                pass
            raise SoloUpstreamError(
                f"SOLO chat HTTP {response.status_code}: {raw}",
                code=code,
                retryable=response.status_code in (429, 500, 502, 503),
            )
        event = ""
        data_lines: list[str] = []
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line == "":
                if event or data_lines:
                    yield event, _data_json("".join(data_lines))
                event = ""
                data_lines = []
        if event or data_lines:
            yield event, _data_json("".join(data_lines))


async def fetch_model_catalog(
    client: httpx.AsyncClient, token: str, user_id: str
) -> list[dict]:
    """Return the union of the remote and lite config catalogs.

    Agent slot configs (file_search_agent, summary, ...) are dropped: only
    chat models belong in ``/v1/models``.
    """
    headers = solo_headers(token, user_id, stream=False)
    seen: dict[str, dict] = {}
    for function in ("solo_work_remote", "solo_work_lite"):
        try:
            response = await client.post(
                solo_base_url() + MODELS_PATH,
                headers=headers,
                json={"function": function},
                timeout=30.0,
            )
            payload = response.json()
        except Exception as exc:  # noqa: BLE001 - catalog is best-effort
            logger.warning("solo catalog %s failed: %s", function, exc)
            continue
        if response.status_code != 200 or payload.get("code") not in (None, 0):
            logger.warning(
                "solo catalog %s rejected: %s", function, str(payload)[:200]
            )
            continue
        for config in payload.get("config_info_list") or []:
            if not isinstance(config, Mapping):
                continue
            name = str(config.get("config_name") or "").strip()
            if not name or name.startswith("custom_model"):
                continue
            if name in {"summary"} or name.endswith("_agent") or name.endswith("_subagent") or name.endswith("_sub_agent_v2"):
                continue
            seen.setdefault(name, dict(config))
    return list(seen.values())


def catalog_model_entry(config: Mapping[str, Any]) -> dict[str, Any]:
    """Project one catalog config onto the OpenAI models entry shape."""
    name = str(config.get("config_name") or "")
    display = config.get("display_config") or {}
    window = config.get("context_window_tokens") or {}
    if isinstance(window, Mapping):
        context = int(window.get("dev") or window.get("default") or 0)
    else:
        context = 0
    try:
        contact = json.loads(config.get("display_contact_config") or "{}")
    except (TypeError, ValueError):
        contact = {}
    rate = ((contact.get("consumption_rate") or {}).get("data") or {}).get("rate")
    return {
        "id": name,
        "object": "model",
        "owned_by": "trae",
        "display_name": display.get("display_name") or name,
        "context_window": context,
        "capability": display.get("model_capability") or "",
        "multimodal": bool(display.get("multimodal")),
        "is_new": bool(display.get("is_new")),
        "credit_rate": rate,
    }


_models_cache: list[dict] = []
_models_cached_at = 0.0


async def get_models(
    client: httpx.AsyncClient, token: str, user_id: str, *, force: bool = False
) -> list[dict]:
    """Catalog with a TTL cache so /v1/models never hammers the upstream."""
    global _models_cache, _models_cached_at
    ttl = float(os.environ.get("TRAE_SOLO_MODELS_TTL", "600") or "600")
    if not force and _models_cache and (time.monotonic() - _models_cached_at) < ttl:
        return list(_models_cache)
    catalog = await fetch_model_catalog(client, token, user_id)
    if catalog:
        _models_cache = [catalog_model_entry(config) for config in catalog]
        _models_cached_at = time.monotonic()
    return list(_models_cache)


# ──────────────────────────── risk control ────────────────────────────


_account_gates: dict[str, asyncio.Semaphore] = {}
_gates_lock = asyncio.Lock()


async def account_gate(account_id: str) -> asyncio.Semaphore:
    """Per-account concurrency cap; upstream tolerates ~2 parallel sessions."""
    key = str(account_id or "default")
    async with _gates_lock:
        gate = _account_gates.get(key)
        if gate is None:
            limit = int(os.environ.get("TRAE_SOLO_MAX_PARALLEL", "2") or "2")
            gate = asyncio.Semaphore(max(1, min(limit, 4)))
            _account_gates[key] = gate
        return gate


def classify_payload_error(data: Mapping[str, Any]) -> Optional[SoloUpstreamError]:
    """Map an in-stream business error to a classified failure."""
    code = data.get("code")
    try:
        code = int(code or 0)
    except (TypeError, ValueError):
        code = 0
    if not code:
        return None
    message = str(data.get("message") or data.get("msg") or f"SOLO error {code}")
    return SoloUpstreamError(
        f"SOLO business code {code}: {message}",
        code=code,
        retryable=code in (CODE_RATE_LIMIT,),
    )


_ENV_NAME_RE = re.compile(r"[A-Za-z0-9_-]{12,}")


def redact(text: str) -> str:
    """Strip anything that looks like a JWT before logging upstream errors."""
    return _ENV_NAME_RE.sub(lambda m: m.group(0)[:6] + "…" if "." in m.group(0) else m.group(0), str(text))

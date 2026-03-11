from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from loguru import logger

from .config import NapCatConfig
from .connection import OneBotActionClient, get_action_client
from .event import OneBotEvent, parse_event


PersistCallback = Callable[[OneBotEvent], Awaitable[None]]


@dataclass(frozen=True)
class RefreshAttempt:
    action: str
    params: dict[str, Any]
    ok: bool
    detail: str
    url: str | None = None


@dataclass(frozen=True)
class RefreshResult:
    url: str | None
    attempts: list[RefreshAttempt]
    final_phase: str
    error: str | None


async def handle_raw_event(
    raw: dict[str, Any],
    persist_callback: PersistCallback | None = None,
) -> None:
    try:
        event = parse_event(raw)
    except ValueError as exc:
        logger.warning("Rejected invalid OneBot event: {}", exc)
        return
    logger.debug(
        "Received event: post_type={} message_type={} user_id={} group_id={}",
        event.post_type,
        event.message_type,
        event.user_id,
        event.group_id,
    )
    if persist_callback is not None:
        try:
            await persist_callback(event)
        except Exception as exc:
            logger.error("Persistence callback failed: {}", exc)


def is_probably_expired_url_error(error: BaseException | str) -> bool:
    message = str(error).lower()
    expired_keywords = (
        "expire",
        "expired",
        "rkey",
        "forbidden",
        "signature",
        "access denied",
        "status=401",
        "status=403",
        "status 401",
        "status 403",
        "status=410",
        "status 410",
    )
    return any(keyword in message for keyword in expired_keywords)


def _extract_first_http_url(payload: Any) -> str | None:
    stack = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, str):
            text = html.unescape(current.strip())
            if text.startswith("http://") or text.startswith("https://"):
                return text
            continue
        if isinstance(current, list):
            stack.extend(reversed(current))
            continue
        if isinstance(current, dict):
            for value in reversed(list(current.values())):
                stack.append(value)
    return None


def _extract_file_id(payload: Any) -> str | None:
    stack = [payload]
    candidate_keys = {"file_id", "file", "fileid", "fid"}
    while stack:
        current = stack.pop()
        if isinstance(current, list):
            stack.extend(reversed(current))
            continue
        if isinstance(current, dict):
            for key, value in current.items():
                if (
                    key.lower() in candidate_keys
                    and isinstance(value, str)
                    and value.strip()
                ):
                    return value.strip()
                stack.append(value)
    return None


def _is_action_ok(response: dict[str, Any]) -> bool:
    status = str(response.get("status", "")).lower()
    retcode = response.get("retcode")
    if status in {"ok", "success"}:
        return True
    if retcode in {0, "0"}:
        return True
    return False


async def _try_action(
    client: OneBotActionClient,
    *,
    action: str,
    params_candidates: list[dict[str, Any]],
    timeout_sec: float,
    attempts: list[RefreshAttempt],
) -> tuple[str | None, str | None]:
    refreshed_url: str | None = None
    discovered_file_id: str | None = None

    for params in params_candidates:
        try:
            response = await client.call_action(
                action,
                params=params,
                timeout_sec=timeout_sec,
            )
        except Exception as exc:
            attempts.append(
                RefreshAttempt(
                    action=action,
                    params=params,
                    ok=False,
                    detail=str(exc),
                )
            )
            continue

        ok = _is_action_ok(response)
        data = response.get("data")
        refreshed_url = _extract_first_http_url(data)
        discovered_file_id = _extract_file_id(data)
        status = response.get("status")
        retcode = response.get("retcode")
        attempts.append(
            RefreshAttempt(
                action=action,
                params=params,
                ok=ok,
                detail=f"status={status} retcode={retcode}",
                url=refreshed_url,
            )
        )
        if refreshed_url:
            return refreshed_url, discovered_file_id

    return None, discovered_file_id


async def refresh_image_url(
    file_id: str | None,
    config: NapCatConfig,
    *,
    message_id: str | None = None,
) -> RefreshResult:
    client = get_action_client()
    if client is None:
        return RefreshResult(
            url=None,
            attempts=[
                RefreshAttempt(
                    action="connection",
                    params={},
                    ok=False,
                    detail="NapCat action channel is not connected",
                )
            ],
            final_phase="error",
            error="NapCat action channel is not connected",
        )

    attempts: list[RefreshAttempt] = []
    working_file_id = file_id.strip() if isinstance(file_id, str) else None
    timeout_sec = max(0.1, config.action_timeout_sec)

    for action in ["nc_get_rkey", "get_image", "get_file", "get_msg"]:
        if action == "get_msg":
            if not message_id:
                continue
            params_candidates = [
                {"message_id": int(message_id)}
                if isinstance(message_id, str) and message_id.isdigit()
                else {"message_id": message_id}
            ]
        elif working_file_id:
            params_candidates = [
                {"file_id": working_file_id},
                {"file": working_file_id},
            ]
        else:
            params_candidates = [{}]

        if not params_candidates:
            continue

        refreshed_url, discovered_file_id = await _try_action(
            client,
            action=action,
            params_candidates=params_candidates,
            timeout_sec=timeout_sec,
            attempts=attempts,
        )
        if discovered_file_id:
            working_file_id = discovered_file_id
        if refreshed_url:
            return RefreshResult(
                url=refreshed_url,
                attempts=attempts,
                final_phase="response",
                error=None,
            )

    logger.warning(
        "Image URL refresh exhausted: file_id={} message_id={} attempts={}",
        file_id,
        message_id,
        len(attempts),
    )
    return RefreshResult(
        url=None,
        attempts=attempts,
        final_phase="error",
        error="refresh_chain_exhausted",
    )

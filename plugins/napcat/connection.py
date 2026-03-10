from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Awaitable, Callable

import aiohttp
import aiohttp.web
from loguru import logger

from .config import NapCatConfig


class OneBotActionError(RuntimeError):
    pass


class OneBotActionClient:
    def __init__(self, ws: aiohttp.web.WebSocketResponse) -> None:
        self._ws = ws
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._send_lock = asyncio.Lock()
        self._closed = False

    async def call_action(
        self,
        action: str,
        params: dict[str, Any] | None = None,
        *,
        timeout_sec: float,
    ) -> dict[str, Any]:
        if self._closed or self._ws.closed:
            raise OneBotActionError("NapCat action channel is not connected")

        echo = f"rpc_{uuid.uuid4().hex}"
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[echo] = future

        payload = {
            "action": action,
            "params": params or {},
            "echo": echo,
        }

        try:
            async with self._send_lock:
                await self._ws.send_json(payload)
            response = await asyncio.wait_for(future, timeout=timeout_sec)
            return response
        except asyncio.TimeoutError as exc:
            self._pending.pop(echo, None)
            raise OneBotActionError(
                f"NapCat action timeout: action={action} timeout_sec={timeout_sec}"
            ) from exc
        except Exception as exc:
            self._pending.pop(echo, None)
            raise OneBotActionError(f"NapCat action failed: action={action}") from exc

    def consume_action_response(self, payload: dict[str, Any]) -> bool:
        echo = payload.get("echo")
        if not isinstance(echo, str):
            return False

        future = self._pending.pop(echo, None)
        if future is None:
            return False

        if not future.done():
            future.set_result(payload)
        return True

    def close(self, reason: str) -> None:
        if self._closed:
            return
        self._closed = True
        error = OneBotActionError(reason)
        for future in self._pending.values():
            if not future.done():
                future.set_exception(error)
        self._pending.clear()


_ACTION_CLIENT: OneBotActionClient | None = None


def get_action_client() -> OneBotActionClient | None:
    return _ACTION_CLIENT


def _set_action_client(client: OneBotActionClient | None) -> None:
    global _ACTION_CLIENT
    old = _ACTION_CLIENT
    _ACTION_CLIENT = client
    if old is not None and old is not client:
        old.close("NapCat action channel replaced by newer connection")


async def run_server(
    config: NapCatConfig,
    on_event: Callable[[dict], Awaitable[None]],
) -> None:
    app = aiohttp.web.Application()
    app.router.add_route("GET", config.ws_path, _make_ws_handler(config, on_event))
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, config.ws_host, config.ws_port)
    await site.start()
    logger.info(
        "NapCat reverse WS server listening: host={} port={} path={}",
        config.ws_host,
        config.ws_port,
        config.ws_path,
    )
    try:
        await _block_forever()
    finally:
        await runner.cleanup()


async def _block_forever() -> None:
    await asyncio.Future()


def _make_ws_handler(
    config: NapCatConfig,
    on_event: Callable[[dict], Awaitable[None]],
) -> Callable[[aiohttp.web.Request], Awaitable[aiohttp.web.WebSocketResponse]]:
    async def _handler(request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
        if config.token:
            auth_header = request.headers.get("Authorization", "")
            expected = f"Bearer {config.token}"
            if auth_header != expected:
                logger.warning(
                    "NapCat auth failed: remote={} header={!r}",
                    request.remote,
                    auth_header,
                )
                raise aiohttp.web.HTTPUnauthorized()

        ws = aiohttp.web.WebSocketResponse()
        await ws.prepare(request)
        action_client = OneBotActionClient(ws)
        _set_action_client(action_client)
        logger.info("NapCat connected: remote={}", request.remote)

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        raw = json.loads(msg.data)
                    except (json.JSONDecodeError, ValueError):
                        logger.warning(
                            "NapCat JSON parse error: remote={} data={!r}",
                            request.remote,
                            msg.data[:200],
                        )
                        continue
                    if isinstance(raw, dict):
                        if action_client.consume_action_response(raw):
                            continue
                        await on_event(raw)
                    else:
                        logger.warning(
                            "NapCat unexpected payload type: remote={} type={}",
                            request.remote,
                            type(raw).__name__,
                        )
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.warning(
                        "NapCat WS error: remote={} error={}",
                        request.remote,
                        ws.exception(),
                    )
        finally:
            action_client.close("NapCat action channel disconnected")
            if get_action_client() is action_client:
                _set_action_client(None)
            logger.info("NapCat disconnected: remote={}", request.remote)
        return ws

    return _handler

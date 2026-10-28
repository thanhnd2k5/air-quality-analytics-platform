"""In-memory response cache for the read-only GET API.

The marts only change when the pipeline (dbt run / loaders) rewrites them, so a response
stays valid until a table in `mart` or `dwh` changes. A fingerprint over
pg_stat_user_tables (table oid + insert/update/delete counters) is re-read at most every
`check_seconds`: dbt's drop-and-recreate gives new oids and in-place loads bump the
counters, so either one empties the cache.

Slow parameter-free endpoints listed in `warm_paths` are computed in the background at
startup and after every data change, so the first page view does not pay for them.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict

from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.db import get_engine

logger = logging.getLogger(__name__)

_VERSION_SQL = text(
    """
    select md5(coalesce(string_agg(
        relid::text || ':' || n_tup_ins || ':' || n_tup_upd || ':' || n_tup_del,
        ',' order by relid
    ), ''))
    from pg_stat_user_tables
    where schemaname in ('mart', 'dwh')
    """
)

Entry = tuple[int, list[tuple[bytes, bytes]], bytes]  # status, headers, body


def _read_version() -> str:
    with get_engine().connect() as conn:
        return conn.execute(_VERSION_SQL).scalar_one()


async def _receive_empty() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}


async def _discard(_message: Message) -> None:
    pass


class ResponseCache:
    """ASGI middleware: replay 200 responses of GET /api/* (except health and quality) from memory."""

    def __init__(
        self,
        app: ASGIApp,
        max_mb: int = 128,
        check_seconds: float = 15.0,
        warm_paths: tuple[str, ...] = (),
    ) -> None:
        self.app = app
        self.max_bytes = max_mb * 1024 * 1024
        self.check_seconds = check_seconds
        self.warm_paths = warm_paths
        self._entries: OrderedDict[str, Entry] = OrderedDict()
        self._size = 0
        self._inflight: dict[str, asyncio.Event] = {}
        self._version: str | None = None
        self._checked_at = 0.0
        self._tasks: set[asyncio.Task] = set()
        self._root_app: ASGIApp | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            self._root_app = scope.get("app")  # warm-up requests need it like real ones
            await self.app(scope, receive, self._on_lifespan(send))
            return
        if not self._cacheable(scope):
            await self.app(scope, receive, send)
            return
        version = await self._data_version()
        if version is None:  # DB unreachable: let the route answer (and fail) as usual
            await self.app(scope, receive, send)
            return

        key = f"{scope['path']}?{scope['query_string'].decode('latin-1')}"
        # A request for a key that is already being computed waits for it instead of
        # sending the same query to Postgres again.
        while (pending := self._inflight.get(key)) is not None:
            await pending.wait()
        if (entry := self._entries.get(key)) is not None:
            self._entries.move_to_end(key)
            await self._replay(entry, send)
            return

        done = self._inflight[key] = asyncio.Event()
        try:
            await self._fill(key, version, scope, receive, send)
        finally:
            del self._inflight[key]
            done.set()

    @staticmethod
    def _cacheable(scope: Scope) -> bool:
        if scope["type"] != "http" or scope["method"] != "GET":
            return False
        path = scope["path"]
        # /api/quality reads artifact files too, which can change while the tables do not.
        return path.startswith("/api/") and not path.startswith(("/api/health", "/api/quality"))

    async def _data_version(self) -> str | None:
        now = time.monotonic()
        if self._version is not None and now - self._checked_at < self.check_seconds:
            return self._version
        try:
            version = await run_in_threadpool(_read_version)
        except Exception:
            logger.warning("response cache bypassed: cannot read data version", exc_info=True)
            return None
        if version != self._version:
            changed = self._version is not None
            self._entries.clear()
            self._size = 0
            self._version = version
            if changed:
                logger.info("mart/dwh changed, response cache cleared")
                self._spawn_warm()
        self._checked_at = now
        return version

    async def _fill(self, key: str, version: str, scope: Scope, receive: Receive, send: Send) -> None:
        status = 0
        headers: list[tuple[bytes, bytes]] = []
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal status, headers
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = list(message.get("headers", []))
                message = {**message, "headers": [*headers, (b"x-cache", b"MISS")]}
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, capture)
        # Skip errors, and results computed while the data was being replaced.
        if status == 200 and version == self._version:
            self._store(key, (status, headers, b"".join(chunks)))

    def _store(self, key: str, entry: Entry) -> None:
        size = len(entry[2])
        if size > self.max_bytes:
            return
        if (old := self._entries.pop(key, None)) is not None:
            self._size -= len(old[2])
        self._entries[key] = entry
        self._size += size
        while self._size > self.max_bytes:
            _, evicted = self._entries.popitem(last=False)
            self._size -= len(evicted[2])

    @staticmethod
    async def _replay(entry: Entry, send: Send) -> None:
        status, headers, body = entry
        await send(
            {"type": "http.response.start", "status": status, "headers": [*headers, (b"x-cache", b"HIT")]}
        )
        await send({"type": "http.response.body", "body": body})

    def _on_lifespan(self, send: Send) -> Send:
        async def wrapped(message: Message) -> None:
            await send(message)
            if message["type"] == "lifespan.startup.complete":
                self._spawn_warm()

        return wrapped

    def _spawn_warm(self) -> None:
        if not self.warm_paths:
            return
        task = asyncio.get_running_loop().create_task(self._warm())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _warm(self) -> None:
        for target in self.warm_paths:
            path, _, query = target.partition("?")
            scope: Scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": query.encode(),
                "root_path": "",
                "headers": [],
                "client": ("127.0.0.1", 0),
                "server": ("127.0.0.1", 0),
            }
            if self._root_app is not None:
                scope["app"] = self._root_app
            try:
                await self(scope, _receive_empty, _discard)
            except Exception:
                logger.warning("cache warm-up failed for %s", target, exc_info=True)
        logger.info("response cache warmed: %d paths", len(self.warm_paths))

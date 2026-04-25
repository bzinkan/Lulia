"""Shared database helper — connection factory for tools and routers.

Threaded connection pool
------------------------
Before Phase 28, every request opened a fresh TCP connection to Postgres. Under
even modest Fargate fan-out (10 tasks × ~50 concurrent req) that exhausts the
RDS `max_connections` ceiling almost immediately. This module now maintains a
process-wide ThreadedConnectionPool and wraps the borrowed connection so that
`conn.close()` RETURNS the connection to the pool rather than terminating it.

Caller contract is UNCHANGED — existing code that does:

    conn = get_connection()
    try:
        cur = conn.cursor()
        ...
        conn.commit()
    finally:
        conn.close()

...keeps working. The only difference is "close" now means "release to pool".

Sizing
------
Pool bounds are env-driven. Defaults (5-min / 20-max) are conservative for local
Docker. In prod, set DB_POOL_MIN=5 and DB_POOL_MAX=25 per-task so that
tasks × max stays well under RDS `max_connections` (default 100 on small
instances).
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any

import psycopg2
from psycopg2 import pool as _psycopg_pool
from psycopg2.extras import RealDictCursor

log = logging.getLogger(__name__)


def _db_kwargs() -> dict[str, Any]:
    return dict(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
        # Per-connection statement timeout guard: no single query can hog a
        # pool slot forever. Individual callers can still raise this via
        # `SET LOCAL statement_timeout = ...` when they know a job is slow.
        options=f"-c statement_timeout={os.environ.get('DB_STATEMENT_TIMEOUT_MS', '30000')}",
    )


_pool: _psycopg_pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_or_create_pool() -> _psycopg_pool.ThreadedConnectionPool:
    """Lazy, thread-safe pool init.

    We don't build the pool at import time because (a) scripts that import this
    module for its helpers shouldn't require DB creds just to run, and (b) in
    tests we want to mock `get_connection` without ever opening a socket.
    """
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        minconn = int(os.environ.get("DB_POOL_MIN", "2"))
        maxconn = int(os.environ.get("DB_POOL_MAX", "20"))
        _pool = _psycopg_pool.ThreadedConnectionPool(minconn, maxconn, **_db_kwargs())
        log.info(
            "db_pool_initialized",
            extra={"minconn": minconn, "maxconn": maxconn},
        )
        return _pool


class _PooledConnection:
    """Thin wrapper: `.close()` returns the conn to the pool.

    Everything else is forwarded via __getattr__ so callers using the full
    psycopg2 connection surface (cursor, commit, rollback, autocommit, etc.)
    don't notice the wrapping. Context-manager support mirrors psycopg2's own
    semantics (`with conn:` opens an implicit transaction block).
    """

    __slots__ = ("_pool", "_conn", "_released")

    def __init__(self, owning_pool: _psycopg_pool.ThreadedConnectionPool, conn) -> None:
        self._pool = owning_pool
        self._conn = conn
        self._released = False

    def __getattr__(self, name: str):
        # Called only if the attribute is NOT on _PooledConnection itself.
        return getattr(self._conn, name)

    def close(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            # If the connection entered a broken state, discard it rather than
            # poisoning the pool. psycopg2's putconn(close=True) closes it.
            if self._conn.closed:
                self._pool.putconn(self._conn, close=True)
            elif getattr(self._conn, "info", None) and self._conn.info.transaction_status not in (0, 1):
                # In a failed/unknown tx — roll back before releasing.
                try:
                    self._conn.rollback()
                except Exception:
                    self._pool.putconn(self._conn, close=True)
                    return
                self._pool.putconn(self._conn)
            else:
                self._pool.putconn(self._conn)
        except Exception:  # pragma: no cover — defensive
            log.exception("pool_release_failed")

    # psycopg2 connections support `with conn:` for transactions. Preserve that
    # by delegating to the underlying connection's context manager and keeping
    # the pool release bound to our own `close()` (caller-driven).
    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, exc_type, exc, tb):
        return self._conn.__exit__(exc_type, exc, tb)


def get_connection(cursor_factory=None):
    """Borrow a connection from the pool.

    `cursor_factory` kept for API compatibility — callers that pass it today
    expect to be able to use `conn.cursor()` without explicitly passing the
    factory. We set it on the borrowed connection.
    """
    p = _get_or_create_pool()
    conn = p.getconn()
    if cursor_factory is not None:
        conn.cursor_factory = cursor_factory
    return _PooledConnection(p, conn)


def get_dict_cursor(conn):
    """Return a RealDictCursor for the given connection."""
    # Works transparently whether `conn` is a raw psycopg2 conn or a
    # _PooledConnection (thanks to __getattr__).
    return conn.cursor(cursor_factory=RealDictCursor)


def close_pool() -> None:
    """Release all pooled connections. Useful in tests and on graceful shutdown."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None

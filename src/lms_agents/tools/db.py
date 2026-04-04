"""Shared database helper — connection factory for tools and routers."""
import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection(cursor_factory=None):
    """Return a new psycopg2 connection using env vars."""
    return psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )


def get_dict_cursor(conn):
    """Return a RealDictCursor for the given connection."""
    return conn.cursor(cursor_factory=RealDictCursor)

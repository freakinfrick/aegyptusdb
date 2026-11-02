"""Shared DB helpers for Oracle tools. Thin wrapper over psycopg2 pool."""

import os
import psycopg2
import psycopg2.pool

DB_URL = os.environ.get("DB_URL", "postgresql://aegyptus:dev@localhost:5434/aegyptus")

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def get_conn():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 4, DB_URL)
    conn = _pool.getconn()
    conn.autocommit = True
    return conn


def put_conn(conn):
    if _pool:
        _pool.putconn(conn)

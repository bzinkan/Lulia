"""Lulings routes — list, detail, categories, random. Public (no auth)."""
import os
import random
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter(prefix="/lulings", tags=["Lulings"])


def get_db():
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "db"),
        port=int(os.environ.get("DB_PORT", 5432)),
        dbname=os.environ.get("DB_NAME", "lulia"),
        user=os.environ.get("DB_USER", "lulia"),
        password=os.environ.get("DB_PASSWORD", "devpassword"),
    )
    try:
        yield conn
    finally:
        conn.close()


@router.get("")
async def list_lulings(
    category: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    conn=Depends(get_db),
):
    """List all Lulings, optionally filtered by category or subject."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    conditions = []
    params = []
    if category:
        conditions.append("category = %s")
        params.append(category)
    if subject:
        conditions.append("(subject_affinity = %s OR subject_affinity = 'all')")
        params.append(subject)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur.execute(f"SELECT * FROM lulings {where} ORDER BY category, name", params)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"lulings": rows, "total": len(rows)}


@router.get("/categories")
async def list_categories(conn=Depends(get_db)):
    """List Luling categories with counts."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        "SELECT category, COUNT(*) as count FROM lulings GROUP BY category ORDER BY category"
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    return {"categories": rows}


@router.get("/random")
async def random_luling(conn=Depends(get_db)):
    """Get a random Luling (for 'surprise me')."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM lulings ORDER BY RANDOM() LIMIT 1")
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "No Lulings available"}, status_code=404)
    return dict(row)


@router.get("/{luling_id}")
async def get_luling(luling_id: UUID, conn=Depends(get_db)):
    """Get specific Luling details."""
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM lulings WHERE luling_id = %s", (str(luling_id),))
    row = cur.fetchone()
    cur.close()
    if not row:
        return JSONResponse({"error": "Luling not found"}, status_code=404)
    return dict(row)

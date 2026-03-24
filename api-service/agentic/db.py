import re
import logging
from contextlib import contextmanager
from typing import List, Dict, Any, Tuple

import psycopg2
from psycopg2 import sql

from .config import settings

logger = logging.getLogger(__name__)


def _parse_ident(ident: str) -> List[str]:
    parts = ident.split(".")
    for p in parts:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", p):
            raise ValueError(f"Unsafe SQL identifier: {ident}")
    return parts


@contextmanager
def db_conn():
    conn = psycopg2.connect(
        host=settings.db_host,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_pass,
        sslmode=settings.db_sslmode,
        connect_timeout=settings.db_connect_timeout,
        options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
    )
    conn.set_session(readonly=True, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def schema_context() -> str:
    try:
        allowlist_raw = settings.db_table_allowlist.strip()
        allowlist = [t.strip() for t in allowlist_raw.split(",") if t.strip()]
        table_filter = ""
        params: Tuple[Any, ...] = ()
        if allowlist:
            table_filter = "AND c.table_name = ANY(%s)"
            params = (allowlist,)
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name, column_name
                    FROM information_schema.columns c
                    WHERE 1=1
                    """
                    + f" {table_filter} "
                    + """
                    ORDER BY table_name, ordinal_position;
                    """,
                    params,
                )
                rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT
                        tc.table_name,
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                    """
                    + (" AND tc.table_name = ANY(%s)" if allowlist else ""),
                    params if allowlist else (),
                )
                fk_rows = cur.fetchall()
        schema: Dict[str, List[str]] = {}
        for table, col in rows:
            schema.setdefault(table, []).append(col)
        if not schema:
            raise RuntimeError("Empty schema result.")
        lines = ["SCHEMA:"]
        for table, cols in schema.items():
            lines.append(f"- {table}: {', '.join(cols)}")
        if fk_rows:
            lines.append("RELATIONSHIPS:")
            for t, col, ft, fcol in fk_rows:
                lines.append(f"- {t}.{col} -> {ft}.{fcol}")
        return "\n".join(lines)
    except Exception:
        logger.exception("Schema lookup failed.")
        return "SCHEMA: unavailable."


def metadata_mappings(embed: List[float], limit: int = 8) -> List[Dict[str, str]]:
    with db_conn() as conn:
        with conn.cursor() as cur:
            table_ident = sql.Identifier(*_parse_ident(settings.dd_table))
            cols = [
                sql.Identifier(settings.dd_concept),
                sql.Identifier(settings.dd_column),
                sql.Identifier(settings.dd_value),
                sql.Identifier(settings.dd_desc),
            ]
            embed_ident = sql.Identifier(settings.dd_embed)
            query = sql.SQL(
                "SELECT {c1}, {c2}, {c3}, {c4} FROM {t} ORDER BY {emb} <-> %s::vector LIMIT %s;"
            ).format(c1=cols[0], c2=cols[1], c3=cols[2], c4=cols[3], t=table_ident, emb=embed_ident)
            cur.execute(query, (embed, limit))
            rows = cur.fetchall()
    return [
        {"concept_name": r[0], "db_column": r[1], "db_value": r[2], "description": r[3]}
        for r in rows
    ]


def policy_doc(embed: List[float]) -> str:
    with db_conn() as conn:
        with conn.cursor() as cur:
            table_ident = sql.Identifier(*_parse_ident(settings.policy_table))
            content_ident = sql.Identifier(settings.policy_content)
            embed_ident = sql.Identifier(settings.policy_embed)
            query = sql.SQL("SELECT {content} FROM {t} ORDER BY {emb} <-> %s::vector LIMIT 1;").format(
                content=content_ident, t=table_ident, emb=embed_ident
            )
            cur.execute(query, (embed,))
            row = cur.fetchone()
    return row[0] if row else "No policy found."

import os
import re
import psycopg2
from psycopg2 import sql
import logging
from typing import TypedDict, List, Optional, Dict, Any, Tuple
from decimal import Decimal
from contextlib import contextmanager
from openai import AzureOpenAI
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_SQL_RETRIES = 3
MAX_ROWS = 500
MAX_QUERY_CHARS = 4000

# --- 1. The Unified Production Contract ---

class ProReport(BaseModel):
    """The standard reporting structure for all financial queries."""
    title: str = Field(description="Executive title of the analysis.")
    summary: str = Field(description="The primary answer including specific numbers found.")
    details: str = Field(description="Supporting breakdown or violation details.")
    is_violation: bool = Field(description="True if the data breaks a company rule.")
    recommended_action: str = Field(description="Next steps for the user.")
    chart_type: str = Field(description="The best visual: 'bar', 'pie', or 'none'.")

class SQLGeneration(BaseModel):
    query: str
    explanation: str

class RouterDecision(BaseModel):
    intent: str # 'analysis' or 'audit'

# --- 2. State & Client ---

class AgentState(TypedDict):
    question: str
    intent: str 
    metadata_context: Optional[str]
    rag_context: Optional[str]
    sql_query: Optional[str]
    sql_error: Optional[str]
    db_data: Optional[List[Dict[str, Any]]]
    final_result: Optional[Dict[str, Any]] # THE UNIFIED KEY
    mapping_rows: Optional[List[Dict[str, str]]]
    iteration: int

client = AzureOpenAI(
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
)

# --- 2b. Helpers ---

def _get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value or ""

def _get_ident(name: str, default: str) -> str:
    value = _get_env(name, default).strip()
    if not value:
        return default
    return value

def _parse_ident(ident: str) -> List[str]:
    parts = ident.split(".")
    for p in parts:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", p):
            raise ValueError(f"Unsafe SQL identifier: {ident}")
    return parts

@contextmanager
def _db_conn():
    conn = psycopg2.connect(
        host=_get_env("DB_HOST", required=True),
        database=_get_env("DB_NAME", required=True),
        user=_get_env("DB_USER", required=True),
        password=_get_env("DB_PASS", required=True),
        sslmode=_get_env("DB_SSLMODE", "require"),
        connect_timeout=int(_get_env("DB_CONNECT_TIMEOUT", "10")),
        options=f"-c statement_timeout={int(_get_env('DB_STATEMENT_TIMEOUT_MS', '15000'))}"
    )
    conn.set_session(readonly=True, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()

_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|copy|vacuum|analyze)\b",
    re.IGNORECASE,
)

def _normalize_sql(query: str) -> str:
    return query.strip().rstrip(";")

def _validate_sql(query: str) -> Tuple[bool, str]:
    if not query:
        return False, "Empty SQL."
    if len(query) > MAX_QUERY_CHARS:
        return False, "SQL exceeds max length."
    if ";" in query.strip().rstrip(";"):
        return False, "Multiple statements are not allowed."
    lowered = query.strip().lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return False, "Only SELECT queries are allowed."
    if _FORBIDDEN_SQL.search(query):
        return False, "Forbidden SQL operation detected."
    if "--" in query or "/*" in query:
        return False, "SQL comments are not allowed."
    return True, ""

def _enforce_limit(query: str, limit: int) -> str:
    if re.search(r"\blimit\b", query, re.IGNORECASE):
        return query
    return f"{query} LIMIT {limit}"

def _value_pattern(value: str) -> str:
    # Build a regex pattern for a SQL literal (string/number/boolean)
    v = value.strip()
    if re.fullmatch(r"true|false", v, re.IGNORECASE):
        return r"\b" + re.escape(v) + r"\b"
    if re.fullmatch(r"-?\d+(\.\d+)?", v):
        return r"\b" + re.escape(v) + r"\b"
    # string literal
    return r"['\"]" + re.escape(v) + r"['\"]"

def _column_patterns(db_column: str) -> List[str]:
    col = db_column.strip()
    if "." in col:
        _, name = col.split(".", 1)
        return [re.escape(col), re.escape(name)]
    return [re.escape(col)]

def _literal_used(query: str, value: str) -> bool:
    if not value:
        return False
    pat = _value_pattern(value)
    return re.search(pat, query, re.IGNORECASE) is not None

def _extract_string_literals(query: str) -> List[str]:
    # Simple extractor for single-quoted literals
    return list({m.group(1) for m in re.finditer(r"'([^']*)'", query)})

def _error_result(title: str, message: str, code: str, sql: Optional[str] = None) -> Dict[str, Any]:
    return {
        "status": "error",
        "title": title,
        "explanation": message,
        "is_violation": False,
        "action": "Retry with a more specific question or contact support.",
        "chart_type": "none",
        "sql": sql,
        "policy": None,
        "data": [],
        "error": {"code": code, "message": message},
    }

def _schema_context() -> str:
    try:
        allowlist_raw = _get_env("DB_TABLE_ALLOWLIST", "").strip()
        allowlist = [t.strip() for t in allowlist_raw.split(",") if t.strip()]
        table_filter = ""
        params: Tuple[Any, ...] = ()
        if allowlist:
            table_filter = "AND c.table_name = ANY(%s)"
            params = (allowlist,)
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name, column_name
                    FROM information_schema.columns c
                    WHERE 1=1
                    """
                    + f" {table_filter} " +
                    """
                    ORDER BY table_name, ordinal_position;
                    """,
                    params
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
                    + ( " AND tc.table_name = ANY(%s)" if allowlist else "" )
                ,
                    params if allowlist else ()
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

def router_node(state: AgentState) -> Dict[str, str]:
    logger.info("--- ROUTING ---")
    prompt = (
        "Categorize intent: 'analysis' (totals, trends, listings) or 'audit' "
        "(policy, compliance, violations, approvals, limits). "
        "If the user does NOT mention policy/violation/compliance/approval/limit, use 'analysis'."
    )
    try:
        res = client.beta.chat.completions.parse(
            model=_get_env("AZURE_OPENAI_CHAT_DEPLOYMENT", required=True),
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": state["question"]}],
            response_format=RouterDecision,
            temperature=0
        )
        return {"intent": res.choices[0].message.parsed.intent}
    except Exception:
        logger.exception("Router failed, defaulting to analysis.")
        return {"intent": "analysis"}

def discovery_node(state: AgentState) -> Dict[str, str]:
    logger.info("--- DISCOVERY ---")
    try:
        schema = _schema_context()
        embed_input = state["question"]
        if state.get("rag_context") and state["intent"] == "audit" and "No policy required" not in state["rag_context"]:
            embed_input = f"{state['question']}\n\nPOLICY:\n{state['rag_context']}"
        embed = client.embeddings.create(
            input=embed_input,
            model=_get_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", required=True)
        ).data[0].embedding
        with _db_conn() as conn:
            with conn.cursor() as cur:
                dd_table = _get_ident("DATA_DICTIONARY_TABLE", "data_dictionary")
                dd_concept = _get_ident("DATA_DICTIONARY_CONCEPT_COL", "concept_name")
                dd_col = _get_ident("DATA_DICTIONARY_COLUMN_COL", "db_column")
                dd_value = _get_ident("DATA_DICTIONARY_VALUE_COL", "db_value")
                dd_desc = _get_ident("DATA_DICTIONARY_DESC_COL", "description")
                dd_embed = _get_ident("DATA_DICTIONARY_EMBED_COL", "embedding")

                table_ident = sql.Identifier(*_parse_ident(dd_table))
                cols = [
                    sql.Identifier(dd_concept),
                    sql.Identifier(dd_col),
                    sql.Identifier(dd_value),
                    sql.Identifier(dd_desc),
                ]
                embed_ident = sql.Identifier(dd_embed)
                query = sql.SQL("SELECT {c1}, {c2}, {c3}, {c4} FROM {t} ORDER BY {emb} <-> %s::vector LIMIT 8;").format(
                    c1=cols[0], c2=cols[1], c3=cols[2], c4=cols[3], t=table_ident, emb=embed_ident
                )
                cur.execute(query, (embed,))
                rows = cur.fetchall()
        mapping_rows = [
            {"concept_name": r[0], "db_column": r[1], "db_value": r[2], "description": r[3]}
            for r in rows
        ]
        mappings = "DB MAPPINGS:\n" + "\n".join(
            [f"- {r['concept_name']}: {r['db_column']}='{r['db_value']}' ({r['description']})" for r in mapping_rows]
        )
        return {"metadata_context": f"{schema}\n\n{mappings}", "mapping_rows": mapping_rows}
    except Exception:
        logger.exception("Discovery failed.")
        return {"metadata_context": f"{_schema_context()}\n\nDB MAPPINGS: unavailable due to retrieval error.", "mapping_rows": []}

def policy_rag_node(state: AgentState) -> Dict[str, str]:
    logger.info("--- POLICY RAG ---")
    if state["intent"] == "analysis": return {"rag_context": "No policy required for general totals."}
    try:
        embed = client.embeddings.create(
            input=state["question"],
            model=_get_env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", required=True)
        ).data[0].embedding
        with _db_conn() as conn:
            with conn.cursor() as cur:
                policy_table = _get_ident("POLICY_TABLE", "policy_documents")
                policy_content = _get_ident("POLICY_CONTENT_COL", "content")
                policy_embed = _get_ident("POLICY_EMBED_COL", "embedding")
                table_ident = sql.Identifier(*_parse_ident(policy_table))
                content_ident = sql.Identifier(policy_content)
                embed_ident = sql.Identifier(policy_embed)
                query = sql.SQL("SELECT {content} FROM {t} ORDER BY {emb} <-> %s::vector LIMIT 1;").format(
                    content=content_ident, t=table_ident, emb=embed_ident
                )
                cur.execute(query, (embed,))
                row = cur.fetchone()
        return {"rag_context": row[0] if row else "No policy found."}
    except Exception:
        logger.exception("Policy RAG failed.")
        return {"rag_context": "No policy found due to retrieval error."}

def sql_generator_node(state: AgentState) -> Dict[str, Any]:
    logger.info("--- SQL GENERATION ---")
    last_error = state.get("sql_error")
    last_query = state.get("sql_query")
    system_prompt = f"""
    You are a PostgreSQL expert. Use the schema and relationships to form correct joins.
    Context: {state['metadata_context']}
    {f"Apply policy constraints: {state['rag_context']}" if state['intent'] == 'audit' else ""}
    {f"Last SQL Error: {last_error}. Fix the SQL." if last_error else ""}
    {f"Previous SQL: {last_query}" if last_query else ""}
    
    Use metadata mappings (DB MAPPINGS) to map business terms to columns/values.
    Only apply a mapping if its concept name or value is explicitly mentioned in the question or policy.
    Do NOT invent literal values or filter on display-name columns when a mapping provides an ID/value.
    When applying a mapping, filter using the mapped db_column (column name, any alias ok).
    Only include is_budget filters if the user explicitly asks for budget, non-budget, or actuals.
    If the policy text includes a numeric threshold (e.g., "exceeding 50,000 EUR"), include a numeric filter that enforces it.
    Use any relevant numeric column from the schema that matches the policy context; do not invent columns.
    Use TRUE/FALSE (booleans), not string literals.
    Use ONLY columns listed in SCHEMA.
    Return ONLY SQL. Must be a single SELECT statement. Max rows {MAX_ROWS}.
    """
    try:
        res = client.beta.chat.completions.parse(
            model=_get_env("AZURE_OPENAI_CHAT_DEPLOYMENT", required=True),
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": state["question"]}],
            response_format=SQLGeneration,
            temperature=0
        )
        query = _normalize_sql(res.choices[0].message.parsed.query)
    except Exception as e:
        logger.exception("SQL generation failed.")
        return {"sql_error": f"SQL generation failed: {e}", "iteration": state["iteration"] + 1}
    is_valid, reason = _validate_sql(query)
    if not is_valid:
        logger.warning(f"SQL validation failed: {reason}")
        return {"sql_error": reason, "iteration": state["iteration"] + 1, "sql_query": query}

    # NOTE: MVP mode - skip metadata literal validation to reduce retries.
    query = _enforce_limit(query, MAX_ROWS)
    try:
        with _db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                colnames = [d[0] for d in cur.description]
                data = []
                for r in cur.fetchall():
                    item = dict(zip(colnames, r))
                    for k, v in item.items():
                        if isinstance(v, (Decimal, float)):
                            item[k] = float(v)
                    item["label"] = str(item.get("description") or item.get("name") or "Entry")
                    data.append(item)
        return {"db_data": data, "sql_query": query, "sql_error": None}
    except Exception as e:
        logger.exception("SQL execution failed.")
        return {"sql_error": str(e), "iteration": state["iteration"] + 1, "sql_query": query}

def synthesis_node(state: AgentState) -> Dict[str, Any]:
    logger.info("--- SYNTHESIS ---")
    if not state.get("db_data"):
        return {
            "final_result": {
                "status": "ok",
                "title": "No Matching Records",
                "explanation": "No records matched your request. Try narrowing the time range or adding filters.",
                "is_violation": False,
                "action": "Refine the question or provide a specific date range.",
                "chart_type": "none",
                "sql": state.get("sql_query"),
                "policy": state["rag_context"] if state["intent"] == "audit" else None,
                "data": [],
            }
        }
    data_sample = str(state["db_data"][:10])
    rows = state["db_data"]
    numeric_cols: Dict[str, List[float]] = {}
    for r in rows:
        for k, v in r.items():
            if isinstance(v, (int, float)):
                numeric_cols.setdefault(k, []).append(float(v))
    stats: Dict[str, Any] = {"row_count": len(rows), "numeric": {}}
    for col, vals in numeric_cols.items():
        if not vals:
            continue
        stats["numeric"][col] = {
            "sum": round(sum(vals), 2),
            "avg": round(sum(vals) / len(vals), 2),
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
        }
    
    system_prompt = f"""
    You are a Lead Financial Analyst. 
    INTENT: {state['intent']}
    POLICY: {state['rag_context']}
    DATA FOUND: {data_sample}
    STATS: {stats}
    
    TASK: Report the numbers clearly using STATS or DATA FOUND only.
    Do NOT invent facts, totals, dates, or years.
    Do NOT infer underlying record counts beyond row_count unless explicitly present in DATA FOUND.
    Avoid statements like "single entry" unless DATA FOUND explicitly shows only one record.
    If intent is analysis, focus on totals. If intent is audit, focus on violations.
    """

    try:
        res = client.beta.chat.completions.parse(
            model=_get_env("AZURE_OPENAI_CHAT_DEPLOYMENT", required=True),
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": state["question"]}],
            response_format=ProReport,
            temperature=0
        )
        report = res.choices[0].message.parsed
        violation_flag = report.is_violation
        if state["intent"] == "audit" and state.get("db_data"):
            violation_flag = True
    except Exception as e:
        logger.exception("Synthesis failed.")
        return {"final_result": _error_result("Synthesis Failed", f"Report generation failed: {e}", "SYNTHESIS_FAILED")}
    
    # UNIFIED OUTPUT STRUCTURE
    return {"final_result": {
        "status": "ok",
        "title": report.title,
        "explanation": f"{report.summary}\n\n{report.details}",
        "is_violation": violation_flag,
        "action": report.recommended_action,
        "chart_type": report.chart_type,
        "sql": state["sql_query"],
        "policy": state["rag_context"] if state["intent"] == "audit" else None,
        "data": state["db_data"]
    }}

def failure_node(state: AgentState) -> Dict[str, Any]:
    logger.info("--- FAILURE ---")
    message = "We could not execute a safe query for this request."
    if state.get("sql_error"):
        message = f"{message} Error: {state['sql_error']}"
    return {"final_result": _error_result("Query Failed", message, "SQL_EXECUTION_FAILED", state.get("sql_query"))}

# --- 4. Flow ---

def should_retry(state: AgentState):
    if state["sql_error"] and state["iteration"] < MAX_SQL_RETRIES:
        return "sql_gen"
    if state["sql_error"]:
        return "failure"
    return "synthesis"

builder = StateGraph(AgentState)
builder.add_node("router", router_node); builder.add_node("discovery", discovery_node)
builder.add_node("policy_rag", policy_rag_node); builder.add_node("sql_gen", sql_generator_node)
builder.add_node("synthesis", synthesis_node); builder.add_node("failure", failure_node)

builder.set_entry_point("router")
builder.add_edge("router", "policy_rag"); builder.add_edge("policy_rag", "discovery")
builder.add_edge("discovery", "sql_gen")
builder.add_conditional_edges("sql_gen", should_retry)
builder.add_edge("synthesis", END)
builder.add_edge("failure", END)

app_graph = builder.compile()

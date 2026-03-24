import logging
from decimal import Decimal
from typing import Dict, Any, List

from .config import settings
from .llm import client
from .models import AgentState, RouterDecision, SQLGeneration, ProReport
from .db import schema_context, metadata_mappings, policy_doc, db_conn
from .sql_utils import normalize_sql, validate_sql, enforce_limit

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def router_node(state: AgentState) -> Dict[str, str]:
    logger.info("--- ROUTING ---")
    prompt = (
        "Categorize intent: 'analysis' (totals, trends, listings) or 'audit' "
        "(policy, compliance, violations, approvals, limits). "
        "If the user does NOT mention policy/violation/compliance/approval/limit, use 'analysis'."
    )
    try:
        res = client.beta.chat.completions.parse(
            model=settings.aoai_chat_deployment,
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": state["question"]}],
            response_format=RouterDecision,
            temperature=0,
        )
        return {"intent": res.choices[0].message.parsed.intent}
    except Exception:
        logger.exception("Router failed, defaulting to analysis.")
        return {"intent": "analysis"}


def policy_rag_node(state: AgentState) -> Dict[str, str]:
    logger.info("--- POLICY RAG ---")
    if state["intent"] == "analysis":
        return {"rag_context": "No policy required for general totals."}
    try:
        embed = client.embeddings.create(
            input=state["question"],
            model=settings.aoai_embedding_deployment,
        ).data[0].embedding
        return {"rag_context": policy_doc(embed)}
    except Exception:
        logger.exception("Policy RAG failed.")
        return {"rag_context": "No policy found due to retrieval error."}


def discovery_node(state: AgentState) -> Dict[str, Any]:
    logger.info("--- DISCOVERY ---")
    try:
        schema = schema_context()
        embed_input = state["question"]
        if state.get("rag_context") and state["intent"] == "audit" and "No policy required" not in state["rag_context"]:
            embed_input = f"{state['question']}\n\nPOLICY:\n{state['rag_context']}"
        embed = client.embeddings.create(
            input=embed_input,
            model=settings.aoai_embedding_deployment,
        ).data[0].embedding
        mapping_rows = metadata_mappings(embed, limit=8)
        mappings = "DB MAPPINGS:\n" + "\n".join(
            [f"- {r['concept_name']}: {r['db_column']}='{r['db_value']}' ({r['description']})" for r in mapping_rows]
        )
        return {"metadata_context": f"{schema}\n\n{mappings}", "mapping_rows": mapping_rows}
    except Exception:
        logger.exception("Discovery failed.")
        return {
            "metadata_context": f"{schema_context()}\n\nDB MAPPINGS: unavailable due to retrieval error.",
            "mapping_rows": [],
        }


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
    Return ONLY SQL. Must be a single SELECT statement. Max rows {settings.max_rows}.
    """
    try:
        res = client.beta.chat.completions.parse(
            model=settings.aoai_chat_deployment,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": state["question"]}],
            response_format=SQLGeneration,
            temperature=0,
        )
        query = normalize_sql(res.choices[0].message.parsed.query)
    except Exception as e:
        logger.exception("SQL generation failed.")
        return {"sql_error": f"SQL generation failed: {e}", "iteration": state["iteration"] + 1}

    is_valid, reason = validate_sql(query)
    if not is_valid:
        logger.warning(f"SQL validation failed: {reason}")
        return {"sql_error": reason, "iteration": state["iteration"] + 1, "sql_query": query}

    query = enforce_limit(query, settings.max_rows)
    try:
        with db_conn() as conn:
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
            model=settings.aoai_chat_deployment,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": state["question"]}],
            response_format=ProReport,
            temperature=0,
        )
        report = res.choices[0].message.parsed
        violation_flag = report.is_violation
        if state["intent"] == "audit" and state.get("db_data"):
            violation_flag = True
    except Exception as e:
        logger.exception("Synthesis failed.")
        return {"final_result": error_result("Synthesis Failed", f"Report generation failed: {e}", "SYNTHESIS_FAILED")}

    return {
        "final_result": {
            "status": "ok",
            "title": report.title,
            "explanation": f"{report.summary}\n\n{report.details}",
            "is_violation": violation_flag,
            "action": report.recommended_action,
            "chart_type": report.chart_type,
            "sql": state["sql_query"],
            "policy": state["rag_context"] if state["intent"] == "audit" else None,
            "data": state["db_data"],
        }
    }


def error_result(title: str, message: str, code: str, sql_query: str | None = None) -> Dict[str, Any]:
    return {
        "status": "error",
        "title": title,
        "explanation": message,
        "is_violation": False,
        "action": "Retry with a more specific question or contact support.",
        "chart_type": "none",
        "sql": sql_query,
        "policy": None,
        "data": [],
        "error": {"code": code, "message": message},
    }


def failure_node(state: AgentState) -> Dict[str, Any]:
    logger.info("--- FAILURE ---")
    message = "We could not execute a safe query for this request."
    if state.get("sql_error"):
        message = f"{message} Error: {state['sql_error']}"
    return {"final_result": error_result("Query Failed", message, "SQL_EXECUTION_FAILED", state.get("sql_query"))}

import os
import psycopg2
import logging
from typing import TypedDict, List, Optional, Dict, Any
from decimal import Decimal
from openai import AzureOpenAI
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

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
    iteration: int

client = AzureOpenAI(
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
)

# --- 3. Nodes ---

def router_node(state: AgentState) -> Dict[str, str]:
    logger.info("--- ROUTING ---")
    prompt = "Categorize intent: 'analysis' (for totals/revenue) or 'audit' (for rules/violations)."
    res = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=[{"role": "system", "content": prompt}, {"role": "user", "content": state["question"]}],
        response_format=RouterDecision
    )
    return {"intent": res.choices[0].message.parsed.intent}

def discovery_node(state: AgentState) -> Dict[str, str]:
    logger.info("--- DISCOVERY ---")
    embed = client.embeddings.create(input=state["question"], model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")).data[0].embedding
    conn = psycopg2.connect(host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASS"), sslmode="require")
    cur = conn.cursor()
    cur.execute("SELECT concept_name, db_column, db_value, description FROM data_dictionary ORDER BY embedding <-> %s::vector LIMIT 3;", (embed,))
    rows = cur.fetchall()
    cur.close(); conn.close()
    mappings = "DB MAPPINGS:\n" + "\n".join([f"- {r[0]}: {r[1]}='{r[2]}' ({r[3]})" for r in rows])
    return {"metadata_context": mappings}

def policy_rag_node(state: AgentState) -> Dict[str, str]:
    logger.info("--- POLICY RAG ---")
    if state["intent"] == "analysis": return {"rag_context": "No policy required for general totals."}
    embed = client.embeddings.create(input=state["question"], model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")).data[0].embedding
    conn = psycopg2.connect(host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASS"), sslmode="require")
    cur = conn.cursor()
    cur.execute("SELECT content FROM policy_documents ORDER BY embedding <-> %s::vector LIMIT 1;", (embed,))
    row = cur.fetchone()
    cur.close(); conn.close()
    return {"rag_context": row[0] if row else "No policy found."}

def sql_generator_node(state: AgentState) -> Dict[str, Any]:
    logger.info("--- SQL GENERATION ---")
    system_prompt = f"""
    PostgreSQL Expert. Join: transactions t JOIN cost_centers cc ON t.cost_center_id = cc.id.
    Context: {state['metadata_context']}
    {f"Apply Limit: {state['rag_context']}" if state['intent'] == 'audit' else ""}
    
    If 'Revenue' is mentioned, filter gl_account_id = 'REV100'.
    If 'Spend' is mentioned, filter gl_account_id = 'EXP200'.
    Return ONLY SQL.
    """
    res = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": state["question"]}],
        response_format=SQLGeneration
    )
    query = res.choices[0].message.parsed.query
    try:
        conn = psycopg2.connect(host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASS"), sslmode="require")
        cur = conn.cursor()
        cur.execute(query)
        colnames = [d[0] for d in cur.description]
        data = []
        for r in cur.fetchall():
            item = dict(zip(colnames, r))
            for k, v in item.items():
                if isinstance(v, (Decimal, float)): item[k] = float(v)
            item['label'] = str(item.get('description') or item.get('name') or "Entry")
            data.append(item)
        cur.close(); conn.close()
        return {"db_data": data, "sql_query": query, "sql_error": None}
    except Exception as e:
        return {"sql_error": str(e), "iteration": state["iteration"] + 1}

def synthesis_node(state: AgentState) -> Dict[str, Any]:
    logger.info("--- SYNTHESIS ---")
    data_sample = str(state["db_data"][:10])
    
    system_prompt = f"""
    You are a Lead Financial Analyst. 
    INTENT: {state['intent']}
    POLICY: {state['rag_context']}
    DATA FOUND: {data_sample}
    
    TASK: Report the numbers clearly. If intent is analysis, focus on totals. If intent is audit, focus on violations.
    """

    res = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": state["question"]}],
        response_format=ProReport
    )
    report = res.choices[0].message.parsed
    
    # UNIFIED OUTPUT STRUCTURE
    return {"final_result": {
        "title": report.title,
        "explanation": f"{report.summary}\n\n{report.details}",
        "is_violation": report.is_violation,
        "action": report.recommended_action,
        "chart_type": report.chart_type,
        "sql": state["sql_query"],
        "policy": state["rag_context"] if state["intent"] == "audit" else None,
        "data": state["db_data"]
    }}

# --- 4. Flow ---

def should_retry(state: AgentState):
    if state["sql_error"] and state["iteration"] < 3: return "sql_gen"
    return "synthesis"

builder = StateGraph(AgentState)
builder.add_node("router", router_node); builder.add_node("discovery", discovery_node)
builder.add_node("policy_rag", policy_rag_node); builder.add_node("sql_gen", sql_generator_node)
builder.add_node("synthesis", synthesis_node)

builder.set_entry_point("router")
builder.add_edge("router", "discovery"); builder.add_edge("discovery", "policy_rag")
builder.add_edge("policy_rag", "sql_gen")
builder.add_conditional_edges("sql_gen", should_retry)
builder.add_edge("synthesis", END)

app_graph = builder.compile()
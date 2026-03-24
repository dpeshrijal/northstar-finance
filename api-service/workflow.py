import os
import psycopg2
import logging
from typing import TypedDict, List, Optional, Dict, Any
from decimal import Decimal
from openai import AzureOpenAI
from pydantic import BaseModel
from langgraph.graph import StateGraph, END

# Configure logging for Azure Log Stream
logger = logging.getLogger(__name__)

# --- Schema Definitions ---

class AgentState(TypedDict):
    """Maintains the data flow and discovered context between nodes."""
    question: str
    next_step: str 
    metadata_context: Optional[str]
    rag_context: Optional[str]
    sql_query: Optional[str]
    db_results: Optional[List[Dict[str, Any]]]
    final_json: Optional[Dict[str, Any]]

class RouterDecision(BaseModel):
    """Schema for the initial routing decision."""
    decision: str 
    reasoning: str

class SQLGeneration(BaseModel):
    """Schema for deterministic SQL output."""
    query: str
    explanation: str

class FinancialResponse(BaseModel):
    """Schema for final UI synthesis."""
    sql_query: str
    explanation: str
    chart_type: str
    suggested_title: str

# --- Client Setup ---

client = AzureOpenAI(
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
)

# --- Node 1: Smart Router ---

def smart_router_node(state: AgentState) -> Dict[str, str]:
    """Determines if the question needs SQL data, Policy RAG, or both."""
    logger.info("--- NODE: SMART ROUTER ---")
    
    system_prompt = """
    You are an expert financial query router. Analyze the request.
    - If they want numbers, totals, or comparisons of ERP data: 'sql_only'
    - If they ask about rules, limits, or policies WITHOUT data: 'rag_only'
    - If they ask about violations, audits, or compliance: 'both'
    """

    try:
        completion = client.beta.chat.completions.parse(
            model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": state["question"]}
            ],
            response_format=RouterDecision
        )
        decision = completion.choices[0].message.parsed.decision
        return {"next_step": decision}
    except Exception as e:
        logger.error(f"Router Error: {e}")
        return {"next_step": "sql_only"}

# --- Node 2: Discovery (Mappings) ---

def discovery_node(state: AgentState) -> Dict[str, str]:
    """Searches the Data Dictionary for exact DB column/value mappings."""
    logger.info("--- NODE: DISCOVERY ---")
    if state["next_step"] == "rag_only":
        return {"metadata_context": "Not required for policy-only search."}
    
    embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    embed_response = client.embeddings.create(input=state["question"], model=embedding_model)
    vector = embed_response.data[0].embedding

    conn = psycopg2.connect(host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASS"), sslmode="require")
    cur = conn.cursor()
    cur.execute("SELECT concept_name, db_column, db_value FROM data_dictionary ORDER BY embedding <-> %s::vector LIMIT 3;", (vector,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    context = "VERIFIED DB MAPPINGS:\n" + "\n".join([f"- {r[0]}: Use {r[1]}='{r[2]}'" for r in rows])
    return {"metadata_context": context}

# --- Node 3: Policy RAG ---

def policy_rag_node(state: AgentState) -> Dict[str, str]:
    """Retrieves relevant company policy text."""
    logger.info("--- NODE: POLICY RAG ---")
    if state["next_step"] == "sql_only":
        return {"rag_context": None}
    
    embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    embed_response = client.embeddings.create(input=state["question"], model=embedding_model)
    vector = embed_response.data[0].embedding

    conn = psycopg2.connect(host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASS"), sslmode="require")
    cur = conn.cursor()
    cur.execute("SELECT content FROM policy_documents ORDER BY embedding <-> %s::vector LIMIT 1;", (vector,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return {"rag_context": row[0] if row else "No specific policy found."}

# --- Node 4: SQL Agent ---

def sql_agent_node(state: AgentState) -> Dict[str, Any]:
    """Generates and executes SQL queries."""
    logger.info("--- NODE: SQL AGENT ---")
    if state["next_step"] == "rag_only":
        return {"db_results": [], "sql_query": "N/A"}
    
    system_prompt = f"""
    You are a PostgreSQL expert for an SAP-style ERP.
    {state['metadata_context']}
    {f'POLICY LIMITS: {state["rag_context"]}' if state['rag_context'] else ''}
    
    RULES:
    1. Use 'amount > limit' for violations. 
    2. is_budget = FALSE for actuals.
    3. JOIN transactions (t) with cost_centers (cc) on t.cost_center_id = cc.id.
    """

    completion = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": state["question"]}],
        response_format=SQLGeneration
    )
    sql_query = completion.choices[0].message.parsed.query
    
    conn = psycopg2.connect(host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASS"), sslmode="require")
    cur = conn.cursor()
    cur.execute(sql_query)
    colnames = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    
    data = []
    for row in rows:
        item = dict(zip(colnames, row))
        for k in item:
            if isinstance(item[k], (int, float, Decimal)):
                item[k] = float(item[k])
        item['label'] = str(item.get('description') or item.get('cost_center_name') or "Item")
        data.append(item)
    
    cur.close()
    conn.close()
    return {"db_results": data, "sql_query": sql_query}

# --- Node 5: Synthesis ---

def synthesis_node(state: AgentState) -> Dict[str, Any]:
    """Final analysis combining data and policy."""
    logger.info("--- NODE: SYNTHESIS ---")
    
    system_prompt = f"""
    You are a Senior Financial Controller. 
    DATA FOUND: {state['db_results']}
    POLICY FOUND: {state['rag_context']}
    
    TASK: Compare the data to the policy. If violations exist, highlight them.
    If no data is present, simply explain the policy rule.
    """

    try:
        completion = client.beta.chat.completions.parse(
            model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": state["question"]}],
            response_format=FinancialResponse
        )
        plan = completion.choices[0].message.parsed

        return {"final_json": {
            "title": plan.suggested_title or "Analysis Result",
            "explanation": plan.explanation or "Data processing complete.",
            "chart_type": plan.chart_type or "none",
            "sql": state.get("sql_query", "N/A"),
            "policy": state.get("rag_context", "N/A"),
            "data": state.get("db_results", [])
        }}
    except Exception as e:
        logger.error(f"Synthesis Error: {e}")
        return {"final_json": {
            "title": "Analysis Completed",
            "explanation": "I have processed your request. Please see the data below.",
            "chart_type": "none",
            "sql": state.get("sql_query", "N/A"),
            "policy": state.get("rag_context", "N/A"),
            "data": state.get("db_results", [])
        }}

# --- Graph Flow ---

builder = StateGraph(AgentState)
builder.add_node("router", smart_router_node)
builder.add_node("discovery", discovery_node)
builder.add_node("policy_rag", policy_rag_node)
builder.add_node("sql_agent", sql_agent_node)
builder.add_node("synthesis", synthesis_node)

builder.set_entry_point("router")
builder.add_edge("router", "discovery")
builder.add_edge("discovery", "policy_rag")
builder.add_edge("policy_rag", "sql_agent")
builder.add_edge("sql_agent", "synthesis")
builder.add_edge("synthesis", END)

app_graph = builder.compile()
import os
import psycopg2
import logging
from typing import TypedDict, List, Optional, Dict, Any
from decimal import Decimal
from openai import AzureOpenAI
from pydantic import BaseModel
from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

# --- Schema Definitions ---

class AgentState(TypedDict):
    """Maintains the data flow and discovered context between nodes."""
    question: str
    metadata_context: Optional[str]  # Discovered DB mappings
    rag_context: Optional[str]       # Discovered Policy rules
    sql_query: Optional[str]
    db_results: Optional[List[Dict[str, Any]]]
    final_json: Optional[Dict[str, Any]]

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

# --- Node 1: Metadata Discovery (The "Librarian") ---

def metadata_discovery_node(state: AgentState) -> Dict[str, str]:
    """Searches the Data Dictionary to find exact DB mappings for human terms."""
    logger.info("--- NODE: METADATA DISCOVERY ---")
    
    embedding_model = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    embed_response = client.embeddings.create(input=state["question"], model=embedding_model)
    vector = embed_response.data[0].embedding

    conn = psycopg2.connect(host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASS"), sslmode="require")
    cur = conn.cursor()
    
    # Semantic search to find relevant mappings (Top 3)
    cur.execute("""
        SELECT concept_name, db_column, db_value, description 
        FROM data_dictionary 
        ORDER BY embedding <-> %s::vector 
        LIMIT 3;
    """, (vector,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    context = "RELEVANT DATABASE MAPPINGS FOUND:\n"
    for r in rows:
        context += f"- Concept '{r[0]}': Use column {r[1]} with value '{r[2]}' ({r[3]})\n"
    
    logger.info(f"Discovered Mappings: {len(rows)}")
    return {"metadata_context": context}

# --- Node 2: Policy RAG Agent (The "Legal Expert") ---

def policy_rag_node(state: AgentState) -> Dict[str, str]:
    """Retrieves relevant company policy rules."""
    logger.info("--- NODE: POLICY RAG ---")
    
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

# --- Node 3: SQL Agent (The "Engineer") ---

def sql_agent_node(state: AgentState) -> Dict[str, Any]:
    """Generates SQL using the discovered Metadata and Policy rules."""
    logger.info("--- NODE: SQL AGENT ---")
    
    system_prompt = f"""
    You are a PostgreSQL expert. Write a query based on these tables:
    - transactions (date, amount, description, gl_account_id, cost_center_id, is_budget)
    - cost_centers (id, name, region)
    
    {state['metadata_context']}
    
    {f"POLICY RULES: {state['rag_context']}" if state['rag_context'] else ""}
    
    RULES:
    1. Write standard, flat PostgreSQL. NEVER use json_agg or row_to_json.
    2. Use the 'db_column' and 'db_value' from the mappings above.
    3. If 'violations' are requested, filter by the amount limit in the POLICY RULES.
    4. Always JOIN transactions (t) with cost_centers (cc) on t.cost_center_id = cc.id.
    5. Return ONLY the JSON object with the 'query' field.
    """

    completion = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["question"]}
        ],
        response_format=SQLGeneration
    )
    sql_plan = completion.choices[0].message.parsed

    conn = psycopg2.connect(host=os.getenv("DB_HOST"), database=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASS"), sslmode="require")
    cur = conn.cursor()
    
    try:
        cur.execute(sql_plan.query)
        colnames = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        data = []
        for row in rows:
            item = dict(zip(colnames, row))
            # Clean numeric types for JSON
            for key in item:
                if isinstance(item[key], (int, float, Decimal)):
                    item[key] = float(item[key])
            
            # Smart Labeling for UI
            if 'is_budget' in item:
                item['label'] = "Budget" if item['is_budget'] else "Actual"
            else:
                item['label'] = str(item.get('description') or item.get('concept_name') or "Entry")
            data.append(item)

        return {"db_results": data, "sql_query": sql_plan.query}
    finally:
        cur.close()
        conn.close()

# --- Node 4: Synthesis (The "Controller") ---

def synthesis_node(state: AgentState) -> Dict[str, Any]:
    """Final business analysis combining data and rules."""
    logger.info("--- NODE: SYNTHESIS ---")
    
    system_prompt = f"""
    You are a Senior Financial Controller.
    DATA FOUND: {str(state['db_results'])}
    POLICY RULES: {state['rag_context']}
    
    INSTRUCTIONS:
    1. Analyze the data against the policy. 
    2. If violations exist (like the 1200 EUR Munich Dinner), name them clearly.
    3. Provide a concise summary.
    """

    completion = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["question"]}
        ],
        response_format=FinancialResponse
    )
    plan = completion.choices[0].message.parsed
    
    return {"final_json": {
        "title": plan.suggested_title,
        "explanation": plan.explanation,
        "chart_type": plan.chart_type,
        "sql": state["sql_query"],
        "policy": state["rag_context"],
        "metadata": state["metadata_context"],
        "data": state["db_results"]
    }}

# --- LangGraph Orchestration ---

workflow = StateGraph(AgentState)

workflow.add_node("discovery", metadata_discovery_node)
workflow.add_node("policy_rag", policy_rag_node)
workflow.add_node("sql_agent", sql_agent_node)
workflow.add_node("synthesis", synthesis_node)

workflow.set_entry_point("discovery")
workflow.add_edge("discovery", "policy_rag")
workflow.add_edge("policy_rag", "sql_agent")
workflow.add_edge("sql_agent", "synthesis")
workflow.add_edge("synthesis", END)

app_graph = workflow.compile()
import os
import psycopg2
from typing import TypedDict, List, Optional, Dict, Any
from decimal import Decimal
from openai import AzureOpenAI
from pydantic import BaseModel
from langgraph.graph import StateGraph, END

# --- Model Definitions ---

class AgentState(TypedDict):
    """Represents the state of the agentic workflow."""
    question: str
    decision: str
    sql_query: Optional[str]
    db_results: Optional[List[Dict[str, Any]]]
    final_json: Optional[Dict[str, Any]]

class FinancialResponse(BaseModel):
    """Structured schema for AI-generated financial analysis."""
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

# --- Graph Nodes ---

def router_node(state: AgentState) -> Dict[str, str]:
    """Determines the data source required to answer the question."""
    # Logic will be expanded here for RAG/Semantic routing later
    return {"decision": "sql"}

def sql_agent_node(state: AgentState) -> Dict[str, Any]:
    """Generates and executes a PostgreSQL query based on the user question."""
    system_prompt = """
    You are a Senior Financial Analyst for a PostgreSQL environment.
    Tables: transactions, cost_centers, gl_accounts.
    
    CRITICAL RULES:
    1. For "Comparison" or "Total" questions, use 'SUM(amount)' and 'GROUP BY'. 
    2. To compare Actual vs Budget, group by the 'is_budget' column.
    3. Use 'is_budget = FALSE' for Actuals and 'is_budget = TRUE' for Budget.
    4. JOIN transactions (t) with cost_centers (cc) on t.cost_center_id = cc.id.
    """

    # AI Query Generation
    completion = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": state["question"]},
        ],
        response_format=FinancialResponse,
    )
    plan = completion.choices[0].message.parsed

    # Database Execution
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        sslmode="require"
    )
    cur = conn.cursor()
    
    try:
        cur.execute(plan.sql_query)
        colnames = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        data = []
        for row in rows:
            item = dict(zip(colnames, row))
            # Data transformation for visualization
            for key in item:
                if isinstance(item[key], (int, float, Decimal)):
                    item[key] = abs(float(item[key]))
            
            if 'is_budget' in item:
                item['label'] = "Budget" if item['is_budget'] else "Actual"
            else:
                item['label'] = next((v for v in item.values() if isinstance(v, str)), "Total")
            
            data.append(item)

        return {
            "sql_query": plan.sql_query,
            "db_results": data,
            "final_json": {
                "title": plan.suggested_title,
                "explanation": plan.explanation,
                "chart_type": plan.chart_type,
                "sql": plan.sql_query
            }
        }
    finally:
        cur.close()
        conn.close()

def formatter_node(state: AgentState) -> Dict[str, Any]:
    """Prepares the final payload for the frontend UI."""
    payload = state["final_json"]
    payload["data"] = state["db_results"]
    return {"final_json": payload}

# --- Graph Compilation ---

builder = StateGraph(AgentState)

builder.add_node("router", router_node)
builder.add_node("sql_agent", sql_agent_node)
builder.add_node("formatter", formatter_node)

builder.set_entry_point("router")
builder.add_edge("router", "sql_agent")
builder.add_edge("sql_agent", "formatter")
builder.add_edge("formatter", END)

app_graph = builder.compile()
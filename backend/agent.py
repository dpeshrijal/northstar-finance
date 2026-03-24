import os
import psycopg2
from typing import List, Optional
from pydantic import BaseModel
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

# --- 1. Define our Data Structure ---
class FinancialResponse(BaseModel):
    sql_query: str
    explanation: str
    chart_type: str
    suggested_title: str

# --- 2. Setup Client ---
client = AzureOpenAI(
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
)

def get_structured_response(user_question):
    print(f"--- AI is generating structured plan... ---")
    
    system_prompt = """
    You are a Senior Financial Data Analyst for a PostgreSQL environment. 
    
    The database schema is:
    - gl_accounts (id, name, category)
    - cost_centers (id, name, region)
    - transactions (id, date, amount, gl_account_id, cost_center_id, description, is_budget)
    
    CRITICAL POSTGRESQL RULES:
    - 'is_budget' is a BOOLEAN. Use 'is_budget = FALSE' or 'is_budget = TRUE'. NEVER use 0 or 1.
    - To get 'Actual Spend', you MUST use 'WHERE is_budget = FALSE'.
    - Use 'SUM(amount)' for totals. 
    - Always JOIN transactions with cost_centers for region-based queries.
    - Use 'GROUP BY' when using aggregation functions like SUM.
    """

    try:

        completion = client.beta.chat.completions.parse(
            model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question},
            ],
            response_format=FinancialResponse,
        )
        
        return completion.choices[0].message.parsed
    except Exception as e:
        print(f"AI Error: {e}")
        return None

def run_query(sql):
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            sslmode="require"
        )
        cur = conn.cursor()
        cur.execute(sql)
        # Get column names to make the data more useful for the frontend
        colnames = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        
        # Convert rows to a list of dictionaries (Perfect for JSON/Frontend)
        result_data = [dict(zip(colnames, row)) for row in rows]
        
        cur.close()
        conn.close()
        return result_data
    except Exception as e:
        print(f"Database Error: {e}")
        return None

if __name__ == "__main__":
    question = "Compare our actual spend vs budget for the Sales DACH cost center."
    
    # 1. Get the Plan from AI
    ai_plan = get_structured_response(question)
    
    if ai_plan:
        print(f"AI suggests a {ai_plan.chart_type} chart.")
        print(f"Explanation: {ai_plan.explanation}")
        
        # 2. Execute the SQL
        data = run_query(ai_plan.sql_query)
        
        # 3. Final Package (This is exactly what the Frontend will receive)
        final_payload = {
            "title": ai_plan.suggested_title,
            "explanation": ai_plan.explanation,
            "chart_type": ai_plan.chart_type,
            "sql": ai_plan.sql_query,
            "data": data
        }
        
        print("\n--- Final Payload for Frontend ---")
        import json
        print(json.dumps(final_payload, indent=2, default=str))
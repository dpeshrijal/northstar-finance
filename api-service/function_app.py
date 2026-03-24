import azure.functions as func
import json
import os
import psycopg2
from openai import AzureOpenAI
from pydantic import BaseModel

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

class FinancialResponse(BaseModel):
    sql_query: str
    explanation: str
    chart_type: str
    suggested_title: str

def get_ai_response(user_question):
    client = AzureOpenAI(
        api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"),
    )

    system_prompt = """
    You are a Senior Financial Analyst for a PostgreSQL environment.
    Schema: transactions, cost_centers, gl_accounts.
    
    CRITICAL RULES:
    1. For "Comparison" or "Total" questions, you MUST use 'SUM(amount)' and 'GROUP BY'. 
    2. Never return raw transaction rows unless specifically asked for "list" or "individual entries".
    3. To compare Actual vs Budget, group by the 'is_budget' column.
    4. Use 'is_budget = FALSE' for Actuals and 'is_budget = TRUE' for Budget.
    5. Join transactions (t) with cost_centers (cc) on t.cost_center_id = cc.id.
    """

    completion = client.beta.chat.completions.parse(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ],
        response_format=FinancialResponse,
    )
    return completion.choices[0].message.parsed

def run_db_query(sql):
    print(f"--- DEBUG: EXECUTING SQL: {sql} ---") # <--- THIS IS THE KEY
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        sslmode="require"
    )
    cur = conn.cursor()
    try:
        cur.execute(sql)
        colnames = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        data = []
        for row in rows:
            item = dict(zip(colnames, row))
            if 'is_budget' in item:
                item['type'] = "Budget" if item['is_budget'] else "Actual"
            data.append(item)
        return data
    finally:
        cur.close()
        conn.close()

@app.route(route="chat")
def chat_agent(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        user_message = req_body.get('message')
        print(f"--- DEBUG: USER QUESTION: {user_message} ---")

        ai_plan = get_ai_response(user_message)
        data = run_db_query(ai_plan.sql_query)

        result = {
            "title": ai_plan.suggested_title,
            "explanation": ai_plan.explanation,
            "chart_type": ai_plan.chart_type,
            "sql": ai_plan.sql_query,
            "data": data
        }

        return func.HttpResponse(
            json.dumps(result, default=str),
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"} # Local CORS fix
        )
    except Exception as e:
        print(f"--- DEBUG ERROR: {str(e)} ---") # <--- SEE THE ERROR
        error_json = {"error": str(e), "title": "Database Error"}
        return func.HttpResponse(
            json.dumps(error_json), 
            status_code=500, 
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
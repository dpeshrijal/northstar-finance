import azure.functions as func
import json
import logging
from workflow import app_graph

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="chat", methods=["POST"])
def chat_agent(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        user_message = req_body.get('message')

        # Initialize State - Match workflow keys exactly
        initial_state = {
            "question": user_message, "intent": "", "metadata_context": "",
            "rag_context": "", "sql_query": "", "sql_error": None,
            "db_data": [], "final_result": {}, "iteration": 0
        }
        
        final_state = app_graph.invoke(initial_state)

        # Retrieve the unified result
        result = final_state.get("final_result", {})

        return func.HttpResponse(
            json.dumps(result, default=str),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
    except Exception as e:
        logging.error(f"SYSTEM CRASH: {str(e)}")
        return func.HttpResponse(
            json.dumps({"title": "System Crash", "explanation": str(e)}),
            status_code=500, mimetype="application/json", headers={"Access-Control-Allow-Origin": "*"}
        )
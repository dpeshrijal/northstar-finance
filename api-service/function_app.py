import azure.functions as func
import json
import logging
from agentic.graph import app_graph

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="chat", methods=["POST", "OPTIONS"])
def chat_agent(req: func.HttpRequest) -> func.HttpResponse:
    try:
        if req.method == "OPTIONS":
            return func.HttpResponse(
                "",
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type",
                },
            )
        req_body = req.get_json()
        user_message = (req_body.get("message") or "").strip()
        if not user_message:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "title": "Invalid Request",
                    "explanation": "Missing or empty 'message' field.",
                    "is_violation": False,
                    "action": "Provide a question about the data.",
                    "chart_type": "none",
                    "sql": None,
                    "policy": None,
                    "data": [],
                    "error": {"code": "BAD_REQUEST", "message": "Empty message."}
                }),
                status_code=400,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        # Initialize State - Match workflow keys exactly
        initial_state = {
            "question": user_message, "intent": "", "metadata_context": "",
            "rag_context": "", "sql_query": "", "sql_error": None,
            "db_data": [], "final_result": {}, "mapping_rows": [], "iteration": 0
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
            json.dumps({
                "status": "error",
                "title": "System Crash",
                "explanation": "The service encountered an unexpected error.",
                "is_violation": False,
                "action": "Try again later or contact support.",
                "chart_type": "none",
                "sql": None,
                "policy": None,
                "data": [],
                "error": {"code": "INTERNAL_ERROR", "message": str(e)}
            }),
            status_code=500, mimetype="application/json", headers={"Access-Control-Allow-Origin": "*"}
        )

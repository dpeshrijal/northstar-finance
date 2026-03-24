import azure.functions as func
import json
from workflow import app_graph

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="chat", methods=["POST"])
def chat_agent(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Parse incoming user message
        req_body = req.get_json()
        user_message = req_body.get('message')

        if not user_message:
            return func.HttpResponse(
                json.dumps({"error": "No message provided"}),
                status_code=400,
                mimetype="application/json"
            )

        # Initialize and execute the LangGraph workflow
        initial_state = {
            "question": user_message,
            "decision": "",
            "sql_query": None,
            "db_results": None,
            "final_json": None
        }
        
        final_state = app_graph.invoke(initial_state)

        # Return the structured payload to the frontend
        return func.HttpResponse(
            json.dumps(final_state["final_json"], default=str),
            status_code=200,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST"
            }
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
import azure.functions as func
import json
from workflow import app_graph

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="chat", methods=["POST"])
def chat_agent(req: func.HttpRequest) -> func.HttpResponse:
    try:
        req_body = req.get_json()
        user_message = req_body.get('message')

        # Initialize Graph State
        initial_state = {
            "question": user_message,
            "metadata_context": None,
            "rag_context": None,
            "sql_query": None,
            "db_results": None,
            "final_json": None
        }
        
        # Execute Workflow
        final_state = app_graph.invoke(initial_state)

        return func.HttpResponse(
            json.dumps(final_state["final_json"], default=str),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e), "title": "Orchestration Error"}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import agent # <--- Import your existing agent.py logic

app = FastAPI()

# Enable CORS so our Next.js frontend can talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change this to your frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # 1. Get the plan from the AI
    ai_plan = agent.get_structured_response(request.message)
    
    if not ai_plan:
        return {"error": "AI failed to generate a plan"}
    
    # 2. Execute the SQL against Azure
    data = agent.run_query(ai_plan.sql_query)
    
    # 3. Return the payload to the Frontend
    return {
        "title": ai_plan.suggested_title,
        "explanation": ai_plan.explanation,
        "chart_type": ai_plan.chart_type,
        "sql": ai_plan.sql_query,
        "data": data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
from typing import TypedDict, List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ProReport(BaseModel):
    """The standard reporting structure for all financial queries."""
    title: str = Field(description="Executive title of the analysis.")
    summary: str = Field(description="The primary answer including specific numbers found.")
    details: str = Field(description="Supporting breakdown or violation details.")
    is_violation: bool = Field(description="True if the data breaks a company rule.")
    recommended_action: str = Field(description="Next steps for the user.")
    chart_type: str = Field(description="The best visual: 'bar', 'pie', or 'none'.")


class SQLGeneration(BaseModel):
    query: str
    explanation: str


class RouterDecision(BaseModel):
    intent: str  # 'analysis' or 'audit'


class AgentState(TypedDict):
    question: str
    intent: str
    metadata_context: Optional[str]
    rag_context: Optional[str]
    sql_query: Optional[str]
    sql_error: Optional[str]
    db_data: Optional[List[Dict[str, Any]]]
    final_result: Optional[Dict[str, Any]]
    mapping_rows: Optional[List[Dict[str, str]]]
    iteration: int

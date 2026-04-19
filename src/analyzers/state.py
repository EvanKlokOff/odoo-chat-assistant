from typing import List, Dict, Any, Optional, Literal, Annotated
from typing_extensions import TypedDict
import operator

class AgentState(TypedDict):
    """State for the LangGraph agent"""
    query_type: Literal["review", "compliance"]
    chat_id: str
    messages: Annotated[List[Dict[str, Any]], operator.add]
    date_start: Optional[str]
    date_end: Optional[str]
    instruction: Optional[str]
    chat_messages: List[Dict[str, Any]]
    analysis_result: Optional[str]
    deviations: Optional[List[Dict[str, Any]]]
    current_step: str
    error: Optional[str]
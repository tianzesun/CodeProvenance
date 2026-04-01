from pydantic import BaseModel
from typing import List, Optional

class CompareRequest(BaseModel):
    code_a: str
    code_b: str

class BatchRequest(BaseModel):
    pairs: List[CompareRequest]

class TaskResponse(BaseModel):
    task_id: str

class ResultResponse(BaseModel):
    status: str
    result: Optional[Dict] = None

class CompareResult(BaseModel):
    score: float
    risk: str  # CRITICAL/HIGH/MEDIUM/LOW

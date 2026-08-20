from pydantic import BaseModel


class CompareRequest(BaseModel):
    code_a: str
    code_b: str


class BatchRequest(BaseModel):
    pairs: list[CompareRequest]


class TaskResponse(BaseModel):
    task_id: str


class ResultResponse(BaseModel):
    status: str
    result: Dict | None = None


class CompareResult(BaseModel):
    score: float
    risk: str  # CRITICAL/HIGH/MEDIUM/LOW

from pydantic import BaseModel


class InspectRequest(BaseModel):
    dataset_id: int


class ReInspectRequest(BaseModel):
    dataset_id: int
    reopen_from_batch_id: int


class ReopenRequest(BaseModel):
    reason: str


class RuleEnablePatch(BaseModel):
    enabled: bool

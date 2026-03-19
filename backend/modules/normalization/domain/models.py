from pydantic import BaseModel


class NormalizationStatus(BaseModel):
    pipeline_name: str
    status: str
    canonical_schema_ready: bool
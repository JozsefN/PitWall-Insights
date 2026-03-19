from pydantic import BaseModel


class IngestionSourceStatus(BaseModel):
    source_name: str
    configured: bool
    status: str
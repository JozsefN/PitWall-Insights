from pydantic import BaseModel


class FeatureMetricsStatus(BaseModel):
    metrics_set_name: str
    status: str
    computed_fields_available: int
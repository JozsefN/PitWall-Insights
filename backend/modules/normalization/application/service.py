from modules.normalization.domain.models import NormalizationStatus


class NormalizationService:
    def get_status(self) -> NormalizationStatus:
        return NormalizationStatus(
            pipeline_name="session_normalization",
            status="stub",
            canonical_schema_ready=False,
        )
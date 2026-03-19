from modules.feature_metrics.domain.models import FeatureMetricsStatus


class FeatureMetricsService:
    def get_status(self) -> FeatureMetricsStatus:
        return FeatureMetricsStatus(
            metrics_set_name="core_session_metrics",
            status="stub",
            computed_fields_available=0,
        )
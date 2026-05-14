from __future__ import annotations

from datetime import datetime, timezone

from modules.decision_engine.domain.models import (
    DecisionEngineStatus,
    DecisionSignalId,
    DecisionSignalListResponse,
    DecisionSignalRequest,
)
from modules.decision_engine.domain.registry import (
    SUPPORTED_SIGNAL_IDS,
    get_rules,
    get_signal_definitions,
    required_metrics_for,
)
from modules.feature_metrics.application.service import FeatureMetricsService
from modules.feature_metrics.domain.models import AnalysisScope, FeatureMetricsConfig
from modules.feature_metrics.infrastructure.config import load_feature_metrics_config
from modules.feature_metrics.infrastructure.input_provider import FeatureMetricInputProvider


class DecisionEngineService:
    def __init__(
        self,
        input_provider: FeatureMetricInputProvider | None = None,
        config: FeatureMetricsConfig | None = None,
    ) -> None:
        self.input_provider = input_provider
        self.config = config or load_feature_metrics_config()

    def get_status(self) -> DecisionEngineStatus:
        return DecisionEngineStatus(
            engine_name="rule_based_decision_engine",
            status="ready",
            rule_count=len(SUPPORTED_SIGNAL_IDS),
            signal_definitions=get_signal_definitions(),
        )

    def get_signals(
        self,
        session_id: str,
        *,
        signal_ids: list[DecisionSignalId] | None = None,
        analysis_scope: AnalysisScope = "field",
        entry_ids: list[str] | None = None,
        recent_laps: int | None = None,
        lap_from: int | None = None,
        lap_to: int | None = None,
    ) -> DecisionSignalListResponse | None:
        if self.input_provider is None:
            raise RuntimeError("FeatureMetricInputProvider is required for decision signals")

        request = DecisionSignalRequest(
            signal_ids=signal_ids or list(SUPPORTED_SIGNAL_IDS),
            analysis_scope=analysis_scope,
            entry_ids=entry_ids,
            recent_laps=recent_laps or self.config.recent_lap_count,
            lap_from=lap_from,
            lap_to=lap_to,
        )
        for rule in get_rules(request.signal_ids):
            if request.analysis_scope not in rule.definition.supported_scopes:
                raise ValueError(
                    f'Signal "{rule.definition.signal_id}" does not support analysis scope "{request.analysis_scope}".'
                )

        metrics_service = FeatureMetricsService(
            input_provider=self.input_provider,
            config=self.config,
        )
        metrics = metrics_service.compute_driver_scores(
            session_id,
            metric_ids=required_metrics_for(request.signal_ids),
            analysis_scope=request.analysis_scope,
            entry_ids=request.entry_ids,
            recent_laps=request.recent_laps,
            lap_from=request.lap_from,
            lap_to=request.lap_to,
        )
        if metrics is None:
            return None

        signals = [
            signal
            for rule in get_rules(request.signal_ids)
            if (signal := rule.evaluate(metrics, self.config)) is not None
        ]

        return DecisionSignalListResponse(
            session_id=session_id,
            analysis_scope=request.analysis_scope,
            computed_at=datetime.now(timezone.utc),
            signals=signals,
        )

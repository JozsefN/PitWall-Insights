export interface ModuleHealthResponse<TDetails = unknown> {
  module: string;
  status: string;
  details?: TDetails;
}

export interface IngestionHealthDetails {
  source_name: string;
  configured: boolean;
  status: string;
  cache_dir?: string | null;
  import_timeout_seconds?: number | null;
}

export interface NormalizationHealthDetails {
  pipeline_name: string;
  status: string;
  canonical_schema_ready: boolean;
}

export interface FeatureMetricsHealthDetails {
  metrics_set_name: string;
  status: string;
  computed_fields_available: number;
}

export interface StoryFeedHealthDetails {
  feed_name: string;
  status: string;
  enabled: boolean;
}

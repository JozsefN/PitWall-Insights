import { useQuery } from "@tanstack/react-query";
import { getFeatureMetricsHealth } from "../api/feature-metrics.api";
import { getStoryFeedHealth } from "../api/story-feed.api";
import { getIngestionHealth } from "../api/ingestion.api";
import { getNormalizationHealth } from "../api/normalization.api";

export function useFeatureMetricsHealthQuery() {
  return useQuery({
    queryKey: ["module-health", "feature-metrics"],
    queryFn: getFeatureMetricsHealth,
  });
}

export function useStoryFeedHealthQuery() {
  return useQuery({
    queryKey: ["module-health", "story-feed"],
    queryFn: getStoryFeedHealth,
  });
}

export function useIngestionHealthQuery() {
  return useQuery({
    queryKey: ["module-health", "ingestion"],
    queryFn: getIngestionHealth,
  });
}

export function useNormalizationHealthQuery() {
  return useQuery({
    queryKey: ["module-health", "normalization"],
    queryFn: getNormalizationHealth,
  });
}
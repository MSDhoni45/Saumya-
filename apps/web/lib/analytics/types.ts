export interface DayStat {
  date: string; // YYYY-MM-DD
  count: number;
}

export interface LeadSourceStat {
  source: string;
  count: number;
}

export interface MetricTrend {
  value: number;
  change_pct: number | null;
}

export interface AnalyticsOverview {
  period_days: number;
  conversations: MetricTrend;
  leads: MetricTrend;
  conversion_rate: MetricTrend;
  ai_response_time_ms: number | null;
  ai_response_time_p95_ms: number | null;
  human_takeovers: number;
  human_takeover_rate: number;
  qualification_rate: MetricTrend;
  lead_sources: LeadSourceStat[];
  conversation_series: DayStat[];
  lead_series: DayStat[];
}

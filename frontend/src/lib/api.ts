// Thin API client. The dashboard reads ONLY from our backend (never Meta/X).
const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  service: string;
  version: string;
  dependencies: { name: string; ok: boolean; detail?: string | null }[];
}

export interface Politician {
  id: number;
  name: string;
  constituency: string | null;
  state: string | null;
  token_status: string;
}

export interface TrendPoint {
  bucket_hour: string;
  sentiment_score: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  is_spike: boolean;
}

export interface CommandCenter {
  politician_id: number;
  sentiment_score: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  total_mentions: number;
  active_spike: boolean;
  trend: TrendPoint[];
  calibrating: boolean;
  generated_at: string;
}

export interface TopPost {
  post_id: string;
  platform: string;
  likes: number;
  comments_count: number;
  shares: number;
  reach: number;
  engagement: number;
}

export interface CityGeo {
  city: string;
  follower_pct: number;
  age_band: string | null;
  gender: string | null;
}

export interface Identity {
  politician_id: number;
  top_posts: TopPost[];
  audience: CityGeo[];
  generated_at: string;
}

export interface Crisis {
  politician_id: number;
  active_spike: boolean;
  recent_spikes: TrendPoint[];
  dm_count: number;
  generated_at: string;
}

export interface MentionSample {
  text: string;
  sentiment_label: string | null;
  platform: string;
  likes: number;
  topics: string[];
  platform_ts: string | null;
}

export interface PublicVoice {
  politician_id: number;
  by_sentiment: Record<string, number>;
  by_platform: Record<string, number>;
  samples: MentionSample[];
  generated_at: string;
}

export interface Trends {
  politician_id: number;
  top_topics: { topic: string; count: number }[];
  series: { bucket_hour: string; total: number; positive: number; negative: number }[];
  generated_at: string;
}

export interface AIBrief {
  politician_id: number;
  summary: string;
  actions: string[];
  generated_at: string | null;
  available: boolean;
}

export interface GeoCity {
  city: string;
  lat: number;
  lon: number;
  mentions: number;
  negative: number;
  avg_sentiment: number;
}
export interface Geo {
  politician_id: number;
  cities: GeoCity[];
  generated_at: string;
}
export interface Misinfo {
  politician_id: number;
  flagged: boolean;
  claim_volume: number;
  window_hours: number;
  sample_texts: string[];
}
export interface Growth {
  politician_id: number;
  series: { day: string; reach: number; engagement: number }[];
}
export interface GroundInputResult {
  stored: boolean;
  mention_id: number;
  sentiment_label: string | null;
  topics: string[];
  inferred_city: string | null;
}

export const getHealth = () => getJson<HealthResponse>("/health");
export const getPoliticians = () => getJson<Politician[]>("/api/politicians");
export const getCommandCenter = (id: number) => getJson<CommandCenter>(`/api/command-center/${id}`);
export const getIdentity = (id: number) => getJson<Identity>(`/api/identity/${id}`);
export const getCrisis = (id: number) => getJson<Crisis>(`/api/crisis/${id}`);
export const getPublicVoice = (id: number) => getJson<PublicVoice>(`/api/public-voice/${id}`);
export const getTrends = (id: number) => getJson<Trends>(`/api/trends/${id}`);
export const getAIBrief = (id: number) => getJson<AIBrief>(`/api/ai-brief/${id}`);
export const getGeo = (id: number) => getJson<Geo>(`/api/geo/${id}`);
export const getMisinfo = (id: number) => getJson<Misinfo>(`/api/misinfo/${id}`);
export const getGrowth = (id: number) => getJson<Growth>(`/api/growth/${id}`);
export const exportCsvUrl = (id: number) => `${BASE}/api/export/${id}/mentions.csv`;

export async function postGroundInput(
  politician_id: number,
  text: string,
): Promise<GroundInputResult> {
  const res = await fetch(`${BASE}/api/ground-input`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ politician_id, text }),
  });
  if (!res.ok) throw new Error(`ground-input ${res.status}`);
  return res.json();
}

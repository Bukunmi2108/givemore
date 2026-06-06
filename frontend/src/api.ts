export const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export interface Health {
  status: "healthy" | "unhealthy";
  database: "ok" | "error";
}

export interface Stats {
  dataset_name: string;
  user_count: number;
  movie_count: number;
  rating_count: number;
}

export interface MovieDetail {
  movie_id: number;
  title: string;
  genres: string[];
  year: number | null;
}

export interface MovieItem extends MovieDetail {
  rank: number;
  score: number;
}

export interface Recommendations {
  source: "personalized" | "fallback";
  reason?: "unknown_user";
  user_id: number;
  items: MovieItem[];
}

export interface Similar {
  source: "similarity" | "fallback";
  reason?: "no_similar_movies";
  movie_id: number;
  items: MovieItem[];
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { signal: AbortSignal.timeout(10_000) });
  if (!response.ok) {
    throw new Error(`${response.status} ${path}`);
  }
  return response.json() as Promise<T>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const health = await get<Health>("/health");
    return health.status === "healthy";
  } catch {
    return false;
  }
}

export function getStats(): Promise<Stats> {
  return get<Stats>("/stats");
}

export function getRecommendations(userId: number): Promise<Recommendations> {
  return get<Recommendations>(`/users/${userId}/recommendations`);
}

export async function searchMovies(q: string, limit = 12): Promise<MovieDetail[]> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  const result = await get<{ query: string; items: MovieDetail[] }>(`/movies?${params}`);
  return result.items;
}

export function getMovie(movieId: number): Promise<MovieDetail> {
  return get<MovieDetail>(`/movies/${movieId}`);
}

export function getSimilar(movieId: number): Promise<Similar> {
  return get<Similar>(`/movies/${movieId}/similar`);
}

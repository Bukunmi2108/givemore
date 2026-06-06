import type { MovieDetail, MovieItem, Recommendations, Similar, Stats } from "./api";

export type AppState = "checking" | "waking" | "failed" | "ready";

export function setAppState(state: AppState): void {
  document.body.dataset.appState = state;
}

function hasRank(movie: MovieDetail | MovieItem): movie is MovieItem {
  return "rank" in movie;
}

export function movieCard(movie: MovieDetail | MovieItem): HTMLAnchorElement {
  const template = document.querySelector<HTMLTemplateElement>("#movie-card");
  if (!template) {
    throw new Error("movie-card template missing");
  }

  const fragment = template.content.cloneNode(true) as DocumentFragment;
  const card = fragment.querySelector<HTMLAnchorElement>(".movie-card");
  const title = fragment.querySelector<HTMLElement>(".mc-title");
  const year = fragment.querySelector<HTMLElement>(".mc-year");
  const genres = fragment.querySelector<HTMLElement>(".mc-genres");
  const rank = fragment.querySelector<HTMLElement>(".mc-rank");

  if (!card || !title || !year || !genres || !rank) {
    throw new Error("movie-card template is incomplete");
  }

  card.href = `/movie.html?id=${movie.movie_id}`;
  card.dataset.movieId = String(movie.movie_id);
  card.dataset.title = movie.title;
  title.textContent = movie.title;
  year.textContent = movie.year == null ? "" : String(movie.year);
  genres.textContent = movie.genres.join(" · ");
  rank.textContent = hasRank(movie) ? `#${movie.rank}` : "";

  return card;
}

export function renderList(container: HTMLElement, movies: MovieDetail[], empty = "No movies found."): void {
  container.replaceChildren();
  if (!movies.length) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-state";
    emptyState.textContent = empty;
    container.append(emptyState);
    return;
  }

  container.append(
    ...movies.map((movie, index) => {
      const card = movieCard(movie);
      card.style.setProperty("--i", String(index));
      return card;
    }),
  );
}

export function renderSkeletons(container: HTMLElement, count: number): void {
  container.replaceChildren(
    ...Array.from({ length: count }, () => {
      const skeleton = document.createElement("div");
      skeleton.className = "skeleton-card";
      return skeleton;
    }),
  );
}

export function recLabel(recommendations: Recommendations): string {
  if (recommendations.source === "fallback") {
    return "Showing popular movies because this user is not in the MovieLens dataset.";
  }
  return `Personalized for MovieLens user ${recommendations.user_id}`;
}

export function similarLabel(similar: Similar): string {
  if (similar.source === "fallback") {
    return "No similar movies found. This film is too obscure for the similarity data.";
  }
  return "Ranked by the precomputed similarity model.";
}

export function renderStats(container: HTMLElement, stats: Stats): void {
  container.replaceChildren();
  const items = [
    ["Users", stats.user_count],
    ["Movies", stats.movie_count],
    ["Ratings", stats.rating_count],
  ] as const;

  for (const [label, value] of items) {
    const term = document.createElement("dt");
    const detail = document.createElement("dd");
    term.textContent = label;
    detail.textContent = value.toLocaleString();
    container.append(term, detail);
  }
}

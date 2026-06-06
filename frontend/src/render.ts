import type { MovieDetail, MovieItem, MovieSummary, Recommendations, Similar, Stats } from "./api";

export type AppState = "checking" | "waking" | "failed" | "ready";

export function setAppState(state: AppState): void {
  document.body.dataset.appState = state;
}

function hasRank(movie: MovieSummary | MovieItem): movie is MovieItem {
  return "rank" in movie;
}

const TMDB_IMG = "https://image.tmdb.org/t/p/";

export function poster(movie: MovieSummary, container: HTMLElement, size: "w342" | "w500"): void {
  if (movie.poster_path) {
    const img = document.createElement("img");
    img.src = `${TMDB_IMG}${size}${movie.poster_path}`;
    img.alt = "";
    img.loading = "lazy";
    container.append(img);
    return;
  }
  container.classList.add("poster-empty");
  container.textContent = movie.title.charAt(0);
}

export function movieCard(movie: MovieSummary | MovieItem): HTMLAnchorElement {
  const template = document.querySelector<HTMLTemplateElement>("#movie-card");
  if (!template) {
    throw new Error("movie-card template missing");
  }

  const fragment = template.content.cloneNode(true) as DocumentFragment;
  const card = fragment.querySelector<HTMLAnchorElement>(".movie-card");
  const posterBox = fragment.querySelector<HTMLElement>(".mc-poster");
  const title = fragment.querySelector<HTMLElement>(".mc-title");
  const year = fragment.querySelector<HTMLElement>(".mc-year");
  const genres = fragment.querySelector<HTMLElement>(".mc-genres");
  const rank = fragment.querySelector<HTMLElement>(".mc-rank");

  if (!card || !posterBox || !title || !year || !genres || !rank) {
    throw new Error("movie-card template is incomplete");
  }

  card.href = `/movie.html?id=${movie.movie_id}`;
  card.dataset.movieId = String(movie.movie_id);
  card.dataset.title = movie.title;
  poster(movie, posterBox, "w342");
  title.textContent = movie.title;
  year.textContent = movie.year == null ? "" : String(movie.year);
  genres.textContent = movie.genres.join(" · ");
  rank.textContent = hasRank(movie) ? `#${movie.rank}` : "";

  return card;
}

export function renderList(container: HTMLElement, movies: MovieSummary[], empty = "No movies found."): void {
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

export function heroLinks(movie: MovieDetail): HTMLElement {
  const wrap = document.createElement("p");
  wrap.className = "hero-links";

  const imdb = document.createElement("a");
  imdb.href = `https://www.imdb.com/title/tt${movie.imdb_id}/`;
  imdb.textContent = "IMDb ↗";
  imdb.target = "_blank";
  imdb.rel = "noopener noreferrer";
  wrap.append(imdb);

  if (movie.tmdb_id != null) {
    const tmdb = document.createElement("a");
    tmdb.href = `https://www.themoviedb.org/movie/${movie.tmdb_id}`;
    tmdb.textContent = "TMDB ↗";
    tmdb.target = "_blank";
    tmdb.rel = "noopener noreferrer";
    wrap.append(tmdb);
  }

  return wrap;
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

import "./style.css";
import { getMovie, getSimilar } from "./api";
import { renderList, renderSkeletons, similarLabel } from "./render";
import type { MovieDetail } from "./api";

function requireElement<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) {
    throw new Error(`${selector} missing`);
  }
  return element;
}

const els = {
  error: requireElement<HTMLElement>("#movie-error"),
  errorMessage: requireElement<HTMLElement>("#movie-error-message"),
  hero: requireElement<HTMLElement>("#movie-hero"),
  heroTitle: requireElement<HTMLElement>("#hero-title"),
  heroMeta: requireElement<HTMLElement>("#hero-meta"),
  similarPanel: requireElement<HTMLElement>("#similar-panel"),
  similarNote: requireElement<HTMLElement>("#similar-note"),
  similarList: requireElement<HTMLElement>("#similar-list"),
};

function showError(message: string): void {
  els.errorMessage.textContent = message;
  els.error.hidden = false;
  els.hero.hidden = true;
  els.similarPanel.hidden = true;
}

function renderHero(movie: MovieDetail): void {
  document.title = `${movie.title} — givemore`;
  els.heroTitle.textContent = movie.title;
  const parts = [movie.year == null ? "" : String(movie.year), movie.genres.join(" · ")];
  els.heroMeta.textContent = parts.filter(Boolean).join("  ·  ");
}

async function init(): Promise<void> {
  const id = Number(new URLSearchParams(location.search).get("id"));
  if (!Number.isInteger(id) || id < 1) {
    showError("No movie selected.");
    return;
  }

  renderSkeletons(els.similarList, 6);
  try {
    const [movie, similar] = await Promise.all([getMovie(id), getSimilar(id)]);
    renderHero(movie);
    els.similarNote.textContent = similarLabel(similar);
    renderList(els.similarList, similar.items, "No similar movies found.");
  } catch {
    showError("Could not load this movie. It may not exist, or the engine may be asleep.");
  }
}

void init();

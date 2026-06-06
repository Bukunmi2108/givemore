import { beforeEach, describe, expect, it } from "vitest";
import type { MovieDetail, Recommendations } from "./api";
import { movieCard, recLabel, renderList, setAppState } from "./render";

function installTemplate(): void {
  document.body.innerHTML = `
    <template id="movie-card">
      <a class="movie-card">
        <span class="mc-rank"></span>
        <h3 class="mc-title"></h3>
        <p class="mc-year"></p>
        <p class="mc-genres"></p>
      </a>
    </template>
  `;
}

describe("render helpers", () => {
  beforeEach(() => {
    installTemplate();
  });

  it("renders movie cards with title, year, genres, and data attributes", () => {
    const movie: MovieDetail = {
      movie_id: 1,
      title: "Toy Story",
      genres: ["Adventure", "Animation"],
      year: 1995,
    };

    const card = movieCard(movie);

    expect(card.dataset.movieId).toBe("1");
    expect(card.getAttribute("href")).toBe("/movie.html?id=1");
    expect(card.textContent).toContain("Toy Story");
    expect(card.textContent).toContain("1995");
    expect(card.textContent).toContain("Adventure · Animation");
  });

  it("does not render null for missing years", () => {
    const card = movieCard({
      movie_id: 10,
      title: "Yearless",
      genres: ["Drama"],
      year: null,
    });

    expect(card.textContent).not.toContain("null");
  });

  it("renders empty genres without placeholder text", () => {
    const card = movieCard({
      movie_id: 11,
      title: "No Genre",
      genres: [],
      year: 2001,
    });

    expect(card.textContent).not.toContain("(no genres listed)");
  });

  it("labels personalized and fallback recommendations", () => {
    const personalized: Recommendations = {
      source: "personalized",
      user_id: 414,
      items: [],
    };
    const fallback: Recommendations = {
      source: "fallback",
      reason: "unknown_user",
      user_id: 9999,
      items: [],
    };

    expect(recLabel(personalized)).toContain("414");
    expect(recLabel(fallback)).toContain("not in the MovieLens dataset");
  });

  it("sets app state on the body dataset", () => {
    setAppState("failed");

    expect(document.body.dataset.appState).toBe("failed");
  });

  it("renders an empty state for empty lists", () => {
    const container = document.createElement("div");

    renderList(container, []);

    expect(container.textContent).toContain("No movies found.");
  });
});

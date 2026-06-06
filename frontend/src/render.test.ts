import { beforeEach, describe, expect, it } from "vitest";
import type { MovieDetail, MovieSummary, Recommendations } from "./api";
import { heroLinks, movieCard, recLabel, renderList, setAppState } from "./render";

function installTemplate(): void {
  document.body.innerHTML = `
    <template id="movie-card">
      <a class="movie-card">
        <div class="mc-poster"></div>
        <div class="mc-scrim">
          <span class="mc-rank"></span>
          <h3 class="mc-title"></h3>
          <p class="mc-year"></p>
          <p class="mc-genres"></p>
        </div>
      </a>
    </template>
  `;
}

describe("render helpers", () => {
  beforeEach(() => {
    installTemplate();
  });

  it("renders movie cards with title, year, genres, and data attributes", () => {
    const movie: MovieSummary = {
      movie_id: 1,
      title: "Toy Story",
      genres: ["Adventure", "Animation"],
      year: 1995,
      poster_path: "/uXDfjJbdP4ijW5hWSBrPrlKpxab.jpg",
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
      poster_path: null,
    });

    expect(card.textContent).not.toContain("null");
  });

  it("renders empty genres without placeholder text", () => {
    const card = movieCard({
      movie_id: 11,
      title: "No Genre",
      genres: [],
      year: 2001,
      poster_path: null,
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

  it("builds external links with the zero-padded imdb id", () => {
    const movie: MovieDetail = {
      movie_id: 1,
      title: "Toy Story",
      genres: ["Adventure"],
      year: 1995,
      poster_path: "/uXDfjJbdP4ijW5hWSBrPrlKpxab.jpg",
      imdb_id: "0114709",
      tmdb_id: 862,
    };

    const links = heroLinks(movie);
    const anchors = links.querySelectorAll("a");

    expect(anchors).toHaveLength(2);
    expect(anchors[0].getAttribute("href")).toBe("https://www.imdb.com/title/tt0114709/");
    expect(anchors[0].getAttribute("rel")).toBe("noopener noreferrer");
    expect(anchors[1].getAttribute("href")).toBe("https://www.themoviedb.org/movie/862");
  });

  it("omits the tmdb link when tmdb_id is null", () => {
    const links = heroLinks({
      movie_id: 791,
      title: "The Last Klezmer",
      genres: ["Documentary"],
      year: 1994,
      poster_path: null,
      imdb_id: "0113610",
      tmdb_id: null,
    });

    const anchors = links.querySelectorAll("a");
    expect(anchors).toHaveLength(1);
    expect(anchors[0].textContent).toContain("IMDb");
  });

  it("renders a lazy poster image from the TMDB CDN", () => {
    const card = movieCard({
      movie_id: 1,
      title: "Toy Story",
      genres: ["Adventure"],
      year: 1995,
      poster_path: "/uXDfjJbdP4ijW5hWSBrPrlKpxab.jpg",
    });

    const img = card.querySelector("img");
    expect(img?.getAttribute("src")).toBe("https://image.tmdb.org/t/p/w342/uXDfjJbdP4ijW5hWSBrPrlKpxab.jpg");
    expect(img?.getAttribute("loading")).toBe("lazy");
  });

  it("renders a placeholder instead of an image when poster_path is null", () => {
    const card = movieCard({
      movie_id: 791,
      title: "The Last Klezmer",
      genres: ["Documentary"],
      year: 1994,
      poster_path: null,
    });

    expect(card.querySelector("img")).toBeNull();
    expect(card.querySelector(".poster-empty")?.textContent).toBe("T");
  });
});

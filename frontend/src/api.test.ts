import { afterEach, describe, expect, it, vi } from "vitest";
import { checkHealth, getRecommendations, searchMovies } from "./api";

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: () => Promise.resolve(body),
  } as Response;
}

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("unwraps search result items", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            query: "matrix",
            items: [{ movie_id: 2571, title: "Matrix, The", genres: ["Action", "Sci-Fi"], year: 1999 }],
          }),
        ),
      ),
    );

    await expect(searchMovies("matrix")).resolves.toEqual([
      { movie_id: 2571, title: "Matrix, The", genres: ["Action", "Sci-Fi"], year: 1999 },
    ]);
  });

  it("returns false when health fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new Error("offline"))));

    await expect(checkHealth()).resolves.toBe(false);
  });

  it("passes recommendation source and reason through untouched", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          jsonResponse({
            source: "fallback",
            reason: "unknown_user",
            user_id: 9999,
            items: [],
          }),
        ),
      ),
    );

    await expect(getRecommendations(9999)).resolves.toMatchObject({
      source: "fallback",
      reason: "unknown_user",
      user_id: 9999,
    });
  });
});

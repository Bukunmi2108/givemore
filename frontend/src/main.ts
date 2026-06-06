import "./style.css";
import { BASE, checkHealth, getRecommendations, getStats, searchMovies } from "./api";
import { recLabel, renderList, renderSkeletons, renderStats, setAppState } from "./render";

const quickPickIds = [1, 57, 111, 414, 610];

function requireElement<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) {
    throw new Error(`${selector} missing`);
  }
  return element;
}

const els = {
  retryButton: requireElement<HTMLButtonElement>("#retry-btn"),
  apiUrl: requireElement<HTMLElement>("#api-url"),
  stats: requireElement<HTMLElement>("#stats"),
  quickPicks: requireElement<HTMLElement>("#quick-picks"),
  userForm: requireElement<HTMLFormElement>("#user-form"),
  userInput: requireElement<HTMLInputElement>("#user-input"),
  recLabel: requireElement<HTMLElement>("#rec-label"),
  recList: requireElement<HTMLElement>("#rec-list"),
  searchInput: requireElement<HTMLInputElement>("#search-input"),
  searchList: requireElement<HTMLElement>("#search-list"),
};

const HEALTH_KEY = "givemore:healthy";

async function runHealthGate(): Promise<void> {
  if (sessionStorage.getItem(HEALTH_KEY)) {
    setAppState("ready");
    try {
      await loadInitialData();
      return;
    } catch {
      sessionStorage.removeItem(HEALTH_KEY);
    }
  }

  setAppState("checking");
  let resolved = false;
  const wakingTimer = window.setTimeout(() => {
    if (!resolved) {
      setAppState("waking");
    }
  }, 2_500);

  for (let attempt = 0; attempt < 5; attempt += 1) {
    if (await checkHealth()) {
      resolved = true;
      window.clearTimeout(wakingTimer);
      sessionStorage.setItem(HEALTH_KEY, "1");
      setAppState("ready");
      await loadInitialData();
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 2_000));
  }

  resolved = true;
  window.clearTimeout(wakingTimer);
  setAppState("failed");
}

async function loadInitialData(): Promise<void> {
  const [statsResult] = await Promise.all([getStats(), loadRecommendations(Number(els.userInput.value))]);
  renderStats(els.stats, statsResult);
}

function syncQuickPicks(userId: number): void {
  for (const button of els.quickPicks.querySelectorAll("button")) {
    button.setAttribute("aria-pressed", String(Number(button.textContent) === userId));
  }
}

async function loadRecommendations(userId: number): Promise<void> {
  syncQuickPicks(userId);
  els.recList.classList.add("loading");
  renderSkeletons(els.recList, 8);
  try {
    const recommendations = await getRecommendations(userId);
    els.recLabel.textContent = recLabel(recommendations);
    renderList(els.recList, recommendations.items);
  } finally {
    els.recList.classList.remove("loading");
  }
}

async function doSearch(query: string): Promise<void> {
  if (query.length < 2) {
    els.searchList.replaceChildren();
    return;
  }

  els.searchList.classList.add("loading");
  renderSkeletons(els.searchList, 4);
  try {
    const movies = await searchMovies(query);
    renderList(els.searchList, movies, `No movies found for "${query}".`);
  } finally {
    els.searchList.classList.remove("loading");
  }
}

function renderQuickPicks(): void {
  els.quickPicks.replaceChildren();
  for (const id of quickPickIds) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = String(id);
    button.setAttribute("aria-pressed", "false");
    button.addEventListener("click", () => {
      els.userInput.value = String(id);
      void loadRecommendations(id);
    });
    els.quickPicks.append(button);
  }
}

function bindEvents(): void {
  els.retryButton.addEventListener("click", () => {
    void runHealthGate();
  });

  els.userForm.addEventListener("submit", (event) => {
    event.preventDefault();
    void loadRecommendations(Number(els.userInput.value));
  });

  let searchTimer: number | undefined;
  els.searchInput.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      void doSearch(els.searchInput.value.trim());
    }, 300);
  });
}

els.apiUrl.textContent = BASE;
renderQuickPicks();
bindEvents();
void runHealthGate();

/**
 * BD Editorials Static Web App (Phase 2)
 * Features: 26-newspaper config, Chunked JSON + Infinite Scroll, Fuse.js + Bangla Unicode search,
 * Multi-select source/category/language/date filters, Author Directory & Author Profile Pages,
 * Today's Editorials, Reader Mode (#/read/<id>) with Light/Sepia/Dark & A-/A+, Bookmarks, PWA.
 */

(() => {
  "use strict";

  const STORAGE_KEYS = {
    theme: "bde_site_theme",
    readerTheme: "bde_reader_theme",
    readerFontRem: "bde_reader_font_rem",
    numerals: "bde_numerals",
    bookmarks: "bde_bookmarks_v1",
  };

  const CATEGORY_LABELS = {
    editorial: "সম্পাদকীয়",
    "op-ed": "উপ-সম্পাদকীয়",
    column: "কলাম",
    opinion: "মতামত",
    analysis: "বিশ্লেষণ",
  };

  const METHOD_LABELS = {
    extractive: "এক্সট্রাক্টিভ সারাংশ",
    meta: "মেটা সারাংশ",
    ai: "সংক্ষিপ্ত AI সারাংশ",
  };

  const GENERIC_BYLINES = new Set([
    "সম্পাদকীয়",
    "সম্পাদকীয়",
    "editorial",
    "মতামত ডেস্ক",
    "opinion desk",
  ]);

  const BN_DIGITS = ["০", "১", "২", "৩", "৪", "৫", "৬", "৭", "৮", "৯"];

  const state = {
    dataBaseUrl: "./data",
    manifest: null,
    loadedPage: 0,
    loadingChunk: false,
    allLoaded: false,
    articles: [],
    articleMap: new Map(),
    sources: [],
    sourcesMap: new Map(),
    health: null,
    fuse: null,

    // Active UI & Filter state
    view: "feed", // 'feed' | 'editorials' | 'authors' | 'bookmarks' | 'health'
    searchQuery: "",
    authorSearchQuery: "",
    selectedSources: new Set(),
    showAllSourcePills: false,
    selectedCategory: "all",
    selectedLanguage: "all",
    dateRange: "all",
    dateFrom: "",
    dateTo: "",
    selectedAuthor: "",

    // Preferences
    siteTheme: localStorage.getItem(STORAGE_KEYS.theme) || "light",
    readerTheme: localStorage.getItem(STORAGE_KEYS.readerTheme) || "light",
    readerFontRem: parseFloat(localStorage.getItem(STORAGE_KEYS.readerFontRem) || "1.15"),
    numeralMode: localStorage.getItem(STORAGE_KEYS.numerals) || "bn",
    bookmarks: loadBookmarks(),

    // Reader state
    filteredList: [],
    activeReaderId: null,
  };

  function loadBookmarks() {
    try {
      const raw = JSON.parse(localStorage.getItem(STORAGE_KEYS.bookmarks) || "{}");
      return typeof raw === "object" && raw !== null ? raw : {};
    } catch {
      return {};
    }
  }

  function saveBookmarks() {
    localStorage.setItem(STORAGE_KEYS.bookmarks, JSON.stringify(state.bookmarks));
    updateBookmarkBadge();
  }

  function formatNumber(num) {
    const str = String(num);
    if (state.numeralMode !== "bn") return str;
    return str.replace(/\d/g, (d) => BN_DIGITS[Number(d)]);
  }

  function countWordsSimple(str) {
    if (!str) return 0;
    return str.trim().split(/\s+/).filter(Boolean).length;
  }

  function getMonogram(name) {
    const clean = String(name || "").trim();
    if (!clean) return "লে";
    const words = clean.split(/\s+/);
    if (/^[A-Za-z]/.test(clean)) {
      return words
        .slice(0, 2)
        .map((w) => w[0].toUpperCase())
        .join("");
    }
    return Array.from(words[0]).slice(0, 2).join("");
  }

  function formatRelativeTime(isoStr) {
    if (!isoStr) return "";
    const date = new Date(isoStr);
    if (Number.isNaN(date.getTime())) return "";
    const diffSec = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));

    if (diffSec < 60) return "এইমাত্র";
    const mins = Math.floor(diffSec / 60);
    if (mins < 60) return `${formatNumber(mins)} মিনিট আগে`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${formatNumber(hours)} ঘণ্টা আগে`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${formatNumber(days)} দিন আগে`;

    const locale = state.numeralMode === "bn" ? "bn-BD" : "en-GB";
    return date.toLocaleDateString(locale, {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "Asia/Dhaka",
    });
  }

  function formatFullDate(isoStr) {
    if (!isoStr) return "";
    const date = new Date(isoStr);
    if (Number.isNaN(date.getTime())) return "";
    const locale = state.numeralMode === "bn" ? "bn-BD" : "en-GB";
    return date.toLocaleString(locale, {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Dhaka",
    });
  }

  function dhakaDateString(isoStr) {
    const d = isoStr ? new Date(isoStr) : new Date();
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-CA", { timeZone: "Asia/Dhaka" });
  }

  async function resolveDataBase() {
    const candidates = [];
    // When running inside a packaged Android APK (Capacitor), check live GitHub Pages URL first
    // so the APK automatically receives every 3-hour update, falling back to bundled ./data offline!
    if (window.BDE_REMOTE_DATA_URL) {
      candidates.push(String(window.BDE_REMOTE_DATA_URL).replace(/\/+$/, ""));
    }
    candidates.push("./data", "../data");

    for (const candidate of candidates) {
      try {
        const resp = await fetch(`${candidate}/chunks/manifest.json`, { cache: "no-cache" });
        if (resp.ok) {
          state.dataBaseUrl = candidate;
          state.manifest = await resp.json();
          return;
        }
      } catch {
        // Offline or unreachable; fall back to next candidate (bundled ./data)
      }
    }
    throw new Error("Could not locate data/chunks/manifest.json");
  }

  async function fetchJson(relPath) {
    const resp = await fetch(`${state.dataBaseUrl}/${relPath}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status} for ${relPath}`);
    return resp.json();
  }

  function ingestArticles(items) {
    let changed = false;
    for (const item of items) {
      if (!item || !item.id) continue;
      if (!state.articleMap.has(item.id)) {
        state.articleMap.set(item.id, item);
        state.articles.push(item);
        changed = true;
      }
    }
    if (changed) {
      state.articles.sort((a, b) => (b.published_at || "").localeCompare(a.published_at || ""));
      rebuildSearchIndex();
    }
  }

  function rebuildSearchIndex() {
    if (typeof window.Fuse === "function") {
      state.fuse = new window.Fuse(state.articles, {
        keys: [
          { name: "title", weight: 0.45 },
          { name: "author", weight: 0.25 },
          { name: "snippet", weight: 0.15 },
          { name: "summary", weight: 0.15 },
          { name: "tags", weight: 0.1 },
        ],
        threshold: 0.32,
        ignoreLocation: true,
        minMatchCharLength: 2,
      });
    }
  }

  async function loadNextChunk() {
    if (state.loadingChunk || state.allLoaded || !state.manifest) return false;
    const nextPage = state.loadedPage + 1;
    if (nextPage > state.manifest.total_pages) {
      state.allLoaded = true;
      return false;
    }

    state.loadingChunk = true;
    try {
      const items = await fetchJson(`chunks/page-${nextPage}.json`);
      ingestArticles(items);
      state.loadedPage = nextPage;
      if (state.loadedPage >= state.manifest.total_pages) {
        state.allLoaded = true;
      }
      return true;
    } catch (err) {
      console.error("Chunk load failed:", err);
      return false;
    } finally {
      state.loadingChunk = false;
    }
  }

  async function ensureAllChunksLoaded() {
    while (!state.allLoaded && state.manifest && state.loadedPage < state.manifest.total_pages) {
      const ok = await loadNextChunk();
      if (!ok) break;
    }
  }

  function getFilteredArticles() {
    let pool = [];
    if (state.view === "bookmarks") {
      pool = Object.values(state.bookmarks).sort((a, b) =>
        (b.published_at || "").localeCompare(a.published_at || "")
      );
    } else if (state.searchQuery.trim().length >= 2) {
      const q = state.searchQuery.normalize("NFC").trim();
      const qLower = q.toLowerCase();

      const exactSet = new Set();
      const merged = [];

      for (const art of state.articles) {
        const hay = `${art.title || ""} ${art.author || ""} ${art.snippet || ""} ${art.summary || ""} ${(art.tags || []).join(" ")}`
          .normalize("NFC")
          .toLowerCase();
        if (hay.includes(qLower)) {
          exactSet.add(art.id);
          merged.push(art);
        }
      }

      if (state.fuse) {
        for (const res of state.fuse.search(q)) {
          if (!exactSet.has(res.item.id)) {
            merged.push(res.item);
          }
        }
      }
      pool = merged;
    } else {
      pool = state.articles.slice();
    }

    if (state.view === "editorials") {
      const editorials = pool.filter((a) => a.category === "editorial");
      const todayDhaka = dhakaDateString();
      const todaysOnly = editorials.filter((a) => dhakaDateString(a.published_at) === todayDhaka);
      pool = todaysOnly.length > 0 ? todaysOnly : editorials;
    }

    if (state.selectedSources.size > 0) {
      pool = pool.filter((a) => state.selectedSources.has(a.source));
    }

    if (state.view !== "editorials" && state.selectedCategory !== "all") {
      pool = pool.filter((a) => a.category === state.selectedCategory);
    }

    if (state.selectedLanguage !== "all") {
      pool = pool.filter((a) => a.language === state.selectedLanguage);
    }

    if (state.selectedAuthor) {
      pool = pool.filter((a) => (a.author || "").trim() === state.selectedAuthor);
    }

    if (state.dateRange !== "all") {
      const nowMs = Date.now();
      if (state.dateRange === "today") {
        const todayStr = dhakaDateString();
        pool = pool.filter((a) => dhakaDateString(a.published_at) === todayStr);
      } else if (state.dateRange === "7d") {
        pool = pool.filter((a) => nowMs - new Date(a.published_at).getTime() <= 7 * 86400 * 1000);
      } else if (state.dateRange === "30d") {
        pool = pool.filter((a) => nowMs - new Date(a.published_at).getTime() <= 30 * 86400 * 1000);
      } else if (state.dateRange === "custom") {
        pool = pool.filter((a) => {
          const dStr = dhakaDateString(a.published_at);
          if (state.dateFrom && dStr < state.dateFrom) return false;
          if (state.dateTo && dStr > state.dateTo) return false;
          return true;
        });
      }
    }

    return pool;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function getSourceDisplay(sourceId, lang = "bn") {
    const s = state.sourcesMap.get(sourceId);
    if (!s) return { name: sourceId, logo: "assets/icon.svg", website: "#" };
    return {
      name: lang === "en" ? s.name_en : s.name_bn || s.name_en,
      logo: s.logo || "assets/icon.svg",
      website: s.section_url || s.website || "#",
    };
  }

  function getSourceArticleCounts() {
    const counts = {};
    if (state.health && state.health.sources) {
      for (const [sid, h] of Object.entries(state.health.sources)) {
        counts[sid] = h.stored_article_count || 0;
      }
    } else {
      for (const a of state.articles) {
        counts[a.source] = (counts[a.source] || 0) + 1;
      }
    }
    return counts;
  }

  function renderSourcePills() {
    const container = document.getElementById("source-pills");
    const toggleBtn = document.getElementById("toggle-all-sources-btn");
    const counts = getSourceArticleCounts();

    let activeSources = state.sources.filter((s) => s.enabled);
    if (state.selectedLanguage !== "all") {
      activeSources = activeSources.filter((s) => s.language === state.selectedLanguage);
    }

    const COLLAPSE_LIMIT = 50;
    const needsCollapse = activeSources.length > COLLAPSE_LIMIT;
    const visibleSources =
      needsCollapse && !state.showAllSourcePills
        ? activeSources.filter((s, idx) => idx < COLLAPSE_LIMIT || state.selectedSources.has(s.id))
        : activeSources;

    container.innerHTML = visibleSources
      .map((s) => {
        const isSelected = state.selectedSources.has(s.id);
        const label = s.language === "en" ? s.name_en : s.name_bn;
        const cnt = counts[s.id] ? ` <span class="pill-count">(${formatNumber(counts[s.id])})</span>` : "";
        return `
          <button
            type="button"
            class="filter-pill ${isSelected ? "active" : ""}"
            data-source-id="${escapeHtml(s.id)}"
          >
            <img src="${escapeHtml(s.logo)}" alt="" loading="lazy" />
            <span>${escapeHtml(label)}${cnt}</span>
          </button>
        `;
      })
      .join("");

    if (needsCollapse) {
      toggleBtn.classList.remove("hidden");
      toggleBtn.textContent = state.showAllSourcePills
        ? "সংক্ষিপ্ত করুন ▴"
        : `সব পত্রিকা দেখুন (${formatNumber(activeSources.length)}টি) ▾`;
    } else {
      toggleBtn.classList.add("hidden");
    }
  }

  function buildAuthorDirectory() {
    const paperNamesSet = new Set();
    for (const s of state.sources) {
      if (s.name_bn) paperNamesSet.add(s.name_bn.toLowerCase());
      if (s.name_en) paperNamesSet.add(s.name_en.toLowerCase());
    }

    const map = new Map();
    for (const art of state.articles) {
      const name = (art.author || "").trim();
      if (!name) continue;
      const lower = name.toLowerCase();
      if (GENERIC_BYLINES.has(lower) || paperNamesSet.has(lower)) continue;

      let rec = map.get(name);
      if (!rec) {
        rec = {
          name,
          count: 0,
          sources: new Set(),
          latestAt: art.published_at || "",
        };
        map.set(name, rec);
      }
      rec.count += 1;
      rec.sources.add(getSourceDisplay(art.source, art.language).name);
      if ((art.published_at || "") > rec.latestAt) {
        rec.latestAt = art.published_at;
      }
    }

    let list = Array.from(map.values());
    const q = state.authorSearchQuery.normalize("NFC").trim().toLowerCase();
    if (q) {
      list = list.filter((a) => a.name.normalize("NFC").toLowerCase().includes(q));
    }

    list.sort((a, b) => b.count - a.count || b.latestAt.localeCompare(a.latestAt));
    return list;
  }

  function renderAuthorsDirectory() {
    const list = buildAuthorDirectory();
    const labelEl = document.getElementById("authors-total-label");
    labelEl.textContent = `মোট ${formatNumber(list.length)} জন কলামিস্ট ও লেখকের নিবন্ধ সংগৃহীত হয়েছে। নামের ওপর ক্লিক করে লেখকের সব লেখা দেখুন।`;

    const grid = document.getElementById("authors-grid");
    if (list.length === 0) {
      grid.innerHTML = `<div class="empty-state"><p>কোনো লেখক খুঁজে পাওয়া যায়নি।</p></div>`;
      return;
    }

    grid.innerHTML = list
      .map((item) => {
        const papers = Array.from(item.sources).join(", ");
        return `
          <button
            type="button"
            class="author-dir-card"
            data-author-card="${escapeHtml(item.name)}"
          >
            <div class="author-avatar" aria-hidden="true">${escapeHtml(getMonogram(item.name))}</div>
            <div class="author-dir-info">
              <span class="author-dir-name">${escapeHtml(item.name)}</span>
              <span class="author-dir-sub">${formatNumber(item.count)}টি লেখা • ${escapeHtml(papers)}</span>
            </div>
          </button>
        `;
      })
      .join("");
  }

  function renderFeed() {
    const controlsPanel = document.getElementById("controls-panel");
    const editorialsIntro = document.getElementById("editorials-intro");
    const bookmarksIntro = document.getElementById("bookmarks-intro");
    const authorsSection = document.getElementById("authors-section");
    const grid = document.getElementById("articles-grid");
    const healthSection = document.getElementById("health-section");
    const loadMoreWrap = document.getElementById("load-more-wrap");

    document.querySelectorAll(".nav-tab").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.view === state.view);
    });

    if (state.view === "health") {
      controlsPanel.classList.add("hidden");
      editorialsIntro.classList.add("hidden");
      bookmarksIntro.classList.add("hidden");
      authorsSection.classList.add("hidden");
      grid.classList.add("hidden");
      loadMoreWrap.classList.add("hidden");
      healthSection.classList.remove("hidden");
      renderHealthDashboard();
      return;
    }

    if (state.view === "authors") {
      controlsPanel.classList.add("hidden");
      editorialsIntro.classList.add("hidden");
      bookmarksIntro.classList.add("hidden");
      healthSection.classList.add("hidden");
      grid.classList.add("hidden");
      loadMoreWrap.classList.add("hidden");
      authorsSection.classList.remove("hidden");
      renderAuthorsDirectory();
      return;
    }

    healthSection.classList.add("hidden");
    authorsSection.classList.add("hidden");
    controlsPanel.classList.remove("hidden");
    grid.classList.remove("hidden");
    editorialsIntro.classList.toggle("hidden", state.view !== "editorials");
    bookmarksIntro.classList.toggle("hidden", state.view !== "bookmarks");

    const list = getFilteredArticles();
    state.filteredList = list;

    // Author Profile Header
    const authorBanner = document.getElementById("author-banner");
    if (state.selectedAuthor) {
      authorBanner.classList.remove("hidden");
      document.getElementById("author-avatar").textContent = getMonogram(state.selectedAuthor);
      document.getElementById("author-banner-name").textContent = state.selectedAuthor;
      const authorPapers = Array.from(
        new Set(list.map((a) => getSourceDisplay(a.source, a.language).name))
      ).join(", ");
      document.getElementById("author-banner-meta").textContent =
        `${formatNumber(list.length)}টি সংগৃহীত লেখা` + (authorPapers ? ` • প্রকাশিত: ${authorPapers}` : "");
    } else {
      authorBanner.classList.add("hidden");
    }

    const hasFilters =
      state.searchQuery.trim() !== "" ||
      state.selectedSources.size > 0 ||
      state.selectedCategory !== "all" ||
      state.selectedLanguage !== "all" ||
      state.dateRange !== "all" ||
      state.selectedAuthor !== "";

    document.getElementById("reset-filters-btn").classList.toggle("hidden", !hasFilters);
    document.getElementById("results-summary").textContent = `${formatNumber(list.length)}টি লেখা পাওয়া গেছে`;

    if (list.length === 0) {
      grid.innerHTML = `
        <div class="empty-state">
          <p>এই ফিল্টার বা অনুসন্ধানে কোনো লেখা পাওয়া যায়নি।</p>
        </div>
      `;
    } else {
      grid.innerHTML = list.map((art) => renderCardHtml(art)).join("");
    }

    const showLoadMore = state.view === "feed" && !state.allLoaded && !hasFilters;
    loadMoreWrap.classList.toggle("hidden", !showLoadMore);
  }

  function renderCardHtml(art) {
    const src = getSourceDisplay(art.source, art.language);
    const catLabel = CATEGORY_LABELS[art.category] || "মতামত";
    const isSaved = Boolean(state.bookmarks[art.id]);
    const relTime = formatRelativeTime(art.published_at);
    const fullTime = formatFullDate(art.published_at);
    const readMin = art.reading_time_min
      ? ` • ~${formatNumber(art.reading_time_min)} মিনিট`
      : "";
    const snippet = art.snippet || art.summary || "";

    return `
      <article class="article-card" data-article-id="${escapeHtml(art.id)}">
        <div>
          <div class="card-header">
            <a href="${escapeHtml(src.website)}" target="_blank" rel="noopener noreferrer" class="source-chip">
              <img src="${escapeHtml(src.logo)}" alt="" loading="lazy" />
              <span>${escapeHtml(src.name)}</span>
            </a>
            <div class="card-badges">
              <span class="category-badge ${art.category === "editorial" ? "cat-editorial" : ""}">
                ${escapeHtml(catLabel)}
              </span>
              <button
                type="button"
                class="bookmark-icon-btn ${isSaved ? "saved" : ""}"
                data-action="bookmark"
                data-id="${escapeHtml(art.id)}"
                title="${isSaved ? "বুকমার্ক সরান" : "পরে পড়ার জন্য সংরক্ষণ করুন"}"
                aria-label="বুকমার্ক"
              >
                ${isSaved ? "★" : "☆"}
              </button>
            </div>
          </div>

          <h2 class="card-title">
            <button type="button" data-action="open-reader" data-id="${escapeHtml(art.id)}">
              ${escapeHtml(art.title)}
            </button>
          </h2>

          <div class="card-meta">
            <button
              type="button"
              class="author-link-btn"
              data-action="filter-author"
              data-author="${escapeHtml(art.author)}"
            >
              ${escapeHtml(art.author)}
            </button>
            <span>•</span>
            <time datetime="${escapeHtml(art.published_at)}" title="${escapeHtml(fullTime)}">${escapeHtml(relTime)}</time>
            <span>${escapeHtml(readMin)}</span>
          </div>

          <p class="card-snippet">${escapeHtml(snippet)}</p>
        </div>

        <div class="card-actions">
          <button
            type="button"
            class="reader-open-btn"
            data-action="open-reader"
            data-id="${escapeHtml(art.id)}"
          >
            পাঠক মোড
          </button>
          <a
            href="${escapeHtml(art.url)}"
            target="_blank"
            rel="noopener noreferrer"
            class="original-site-link"
          >
            পূর্ণ লেখা মূল সাইটে পড়ুন →
          </a>
        </div>
      </article>
    `;
  }

  function renderHealthDashboard() {
    const grid = document.getElementById("health-grid");
    const updatedEl = document.getElementById("health-updated-at");
    if (!state.health || !state.health.sources) {
      updatedEl.textContent = "হেলথ তথ্য লোড করা যায়নি।";
      grid.innerHTML = "";
      return;
    }

    const entries = Object.values(state.health.sources);
    const healthyCount = entries.filter((e) => e.status === "healthy").length;
    updatedEl.textContent =
      `সর্বশেষ হালনাগাদ: ${formatFullDate(state.health.updated_at)} • ` +
      `সচল সোর্স: ${formatNumber(healthyCount)}/${formatNumber(entries.length)} • ` +
      `মোট সক্রিয় লেখা: ${formatNumber(state.health.total_active_articles || 0)}`;

    grid.innerHTML = entries
      .map((h) => {
        const statusLabel =
          h.status === "healthy"
            ? "সচল (Healthy)"
            : h.status === "disabled"
            ? "নিষ্ক্রিয় / ব্লকড"
            : "ত্রুটিযুক্ত";
        const lastOk = h.last_success_at ? formatFullDate(h.last_success_at) : "কখনো নয়";
        return `
          <div class="health-card">
            <div class="health-card-top">
              <strong>${escapeHtml(h.name_bn)} (${escapeHtml(h.name_en)})</strong>
              <span class="status-pill status-${escapeHtml(h.status)}">${escapeHtml(statusLabel)}</span>
            </div>
            <p class="health-meta">পদ্ধতি: <code>${escapeHtml((h.fetch_method || "").toUpperCase())}</code> • সংরক্ষিত লেখা: ${formatNumber(h.stored_article_count || 0)}টি</p>
            <p class="health-meta">সর্বশেষ সফল সংগ্রহ: ${escapeHtml(lastOk)}</p>
            ${
              h.last_error
                ? `<div class="health-error"><strong>নোট:</strong> ${escapeHtml(h.last_error)}</div>`
                : ""
            }
          </div>
        `;
      })
      .join("");
  }

  async function openReaderById(articleId, updateHash = true) {
    let art = state.articleMap.get(articleId) || state.bookmarks[articleId];
    if (!art && !state.allLoaded) {
      await ensureAllChunksLoaded();
      art = state.articleMap.get(articleId);
    }
    if (!art) {
      showToast("নির্দিষ্ট লেখাটি খুঁজে পাওয়া যায়নি।");
      return;
    }

    state.activeReaderId = art.id;
    if (updateHash && window.location.hash !== `#/read/${art.id}`) {
      history.pushState(null, "", `#/read/${art.id}`);
    }

    const src = getSourceDisplay(art.source, art.language);
    const srcEl = document.getElementById("reader-source-badge");
    srcEl.href = src.website;
    srcEl.innerHTML = `<img src="${escapeHtml(src.logo)}" alt="" /> <span>${escapeHtml(src.name)}</span>`;

    const catEl = document.getElementById("reader-category-badge");
    catEl.textContent = CATEGORY_LABELS[art.category] || "মতামত";
    catEl.className = `category-badge ${art.category === "editorial" ? "cat-editorial" : ""}`;

    document.getElementById("reader-title").textContent = art.title;

    const authorBtn = document.getElementById("reader-author-btn");
    authorBtn.textContent = art.author || src.name;
    authorBtn.onclick = () => {
      closeReader(false);
      filterByAuthor(art.author);
    };

    document.getElementById("reader-time").textContent = formatFullDate(art.published_at);

    const rtSep = document.getElementById("reader-readtime-sep");
    const rtEl = document.getElementById("reader-readtime");
    if (art.reading_time_min > 0) {
      rtSep.classList.remove("hidden");
      rtEl.classList.remove("hidden");
      rtEl.textContent = `মূল লেখা ~${formatNumber(art.reading_time_min)} মিনিট পাঠযোগ্য`;
    } else {
      rtSep.classList.add("hidden");
      rtEl.classList.add("hidden");
    }

    const hasFullSummary = Boolean(art.summary && art.summary.trim());
    const summaryText = hasFullSummary ? art.summary : (art.snippet || "সারাংশ উপলব্ধ নেই।");
    const wc = countWordsSimple(summaryText);
    document.getElementById("reader-summary-text").textContent = summaryText;
    const methodTitle = hasFullSummary
      ? METHOD_LABELS[art.summary_method] || "সারাংশ"
      : "সংক্ষিপ্ত অংশ";
    document.getElementById("reader-summary-method").textContent =
      wc > 0 ? `${methodTitle} • ${formatNumber(wc)} শব্দ` : methodTitle;

    // Render clickable tags
    const tagsRow = document.getElementById("reader-tags-row");
    const tags = Array.isArray(art.tags) ? art.tags.filter(Boolean) : [];
    if (tags.length > 0) {
      tagsRow.classList.remove("hidden");
      tagsRow.innerHTML = tags
        .map(
          (t) =>
            `<button type="button" class="reader-tag-chip" data-tag="${escapeHtml(t)}">#${escapeHtml(t)}</button>`
        )
        .join("");
    } else {
      tagsRow.classList.add("hidden");
      tagsRow.innerHTML = "";
    }

    const origLink = document.getElementById("reader-original-link");
    origLink.href = art.url;
    origLink.textContent = `পূর্ণ লেখা মূল সাইটে পড়ুন (${src.name}) →`;

    syncReaderBookmarkButton();
    syncReaderPrevNext();

    document.getElementById("reader-backdrop").classList.remove("hidden");
    const sheet = document.getElementById("reader-sheet");
    sheet.classList.remove("hidden");
    document.getElementById("reader-scroll-container").scrollTop = 0;
    document.body.style.overflow = "hidden";
  }

  function closeReader(updateHash = true) {
    if (!state.activeReaderId) return;
    state.activeReaderId = null;
    document.getElementById("reader-backdrop").classList.add("hidden");
    document.getElementById("reader-sheet").classList.add("hidden");
    document.body.style.overflow = "";
    if (updateHash && window.location.hash.startsWith("#/read/")) {
      history.pushState(null, "", "#/");
    }
  }

  function syncReaderBookmarkButton() {
    if (!state.activeReaderId) return;
    const btn = document.getElementById("reader-bookmark-btn");
    const saved = Boolean(state.bookmarks[state.activeReaderId]);
    btn.textContent = saved ? "★ সংরক্ষিত" : "☆ বুকমার্ক";
  }

  function syncReaderPrevNext() {
    const list = state.filteredList.length > 0 ? state.filteredList : state.articles;
    const idx = list.findIndex((a) => a.id === state.activeReaderId);
    const prevBtn = document.getElementById("reader-prev-btn");
    const nextBtn = document.getElementById("reader-next-btn");
    const posEl = document.getElementById("reader-pos-indicator");

    if (idx === -1) {
      prevBtn.disabled = true;
      nextBtn.disabled = true;
      posEl.textContent = "";
      return;
    }

    prevBtn.disabled = idx <= 0;
    nextBtn.disabled = idx >= list.length - 1;
    posEl.textContent = `${formatNumber(idx + 1)} / ${formatNumber(list.length)}`;

    prevBtn.onclick = () => idx > 0 && openReaderById(list[idx - 1].id);
    nextBtn.onclick = () => idx < list.length - 1 && openReaderById(list[idx + 1].id);
  }

  function toggleBookmark(articleId) {
    const existing = state.bookmarks[articleId];
    if (existing) {
      delete state.bookmarks[articleId];
      showToast("বুকমার্ক থেকে সরানো হয়েছে");
    } else {
      const art = state.articleMap.get(articleId);
      if (art) {
        state.bookmarks[articleId] = art;
        showToast("‘পরে পড়ব’ তালিকায় সংরক্ষিত হয়েছে");
      }
    }
    saveBookmarks();
    renderFeed();
    syncReaderBookmarkButton();
  }

  function updateBookmarkBadge() {
    const count = Object.keys(state.bookmarks).length;
    document.getElementById("bookmark-count").textContent = formatNumber(count);
  }

  async function filterByAuthor(authorName) {
    if (!authorName) return;
    await ensureAllChunksLoaded();
    state.view = "feed";
    state.selectedAuthor = authorName.trim();
    history.pushState(null, "", `#/author/${encodeURIComponent(state.selectedAuthor)}`);
    renderFeed();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function applySiteTheme(theme) {
    state.siteTheme = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", state.siteTheme);
    localStorage.setItem(STORAGE_KEYS.theme, state.siteTheme);
    document.getElementById("theme-icon").textContent = state.siteTheme === "dark" ? "☀" : "☾";
  }

  function applyReaderTheme(rtheme) {
    state.readerTheme = ["light", "sepia", "dark"].includes(rtheme) ? rtheme : "light";
    document.getElementById("reader-sheet").setAttribute("data-reader-theme", state.readerTheme);
    localStorage.setItem(STORAGE_KEYS.readerTheme, state.readerTheme);
    document.querySelectorAll(".theme-dot").forEach((b) => {
      b.classList.toggle("active", b.dataset.rtheme === state.readerTheme);
    });
  }

  function applyReaderFontSize(rem) {
    const clamped = Math.min(1.55, Math.max(0.95, Number(rem.toFixed(2))));
    state.readerFontRem = clamped;
    document.documentElement.style.setProperty("--reader-font-size", `${clamped}rem`);
    localStorage.setItem(STORAGE_KEYS.readerFontRem, String(clamped));
  }

  function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.remove("hidden");
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(() => toast.classList.add("hidden"), 2300);
  }

  async function handleHashRoute() {
    const hash = window.location.hash || "#/";
    if (hash.startsWith("#/read/")) {
      const id = decodeURIComponent(hash.slice("#/read/".length)).trim();
      if (id) await openReaderById(id, false);
      return;
    }

    closeReader(false);

    if (hash.startsWith("#/author/")) {
      const author = decodeURIComponent(hash.slice("#/author/".length)).trim();
      await ensureAllChunksLoaded();
      state.view = "feed";
      state.selectedAuthor = author;
      renderFeed();
    } else if (hash === "#/authors") {
      await ensureAllChunksLoaded();
      state.view = "authors";
      renderFeed();
    } else if (hash === "#/editorials") {
      await ensureAllChunksLoaded();
      state.view = "editorials";
      renderFeed();
    } else if (hash === "#/bookmarks") {
      state.view = "bookmarks";
      renderFeed();
    } else if (hash === "#/health") {
      state.view = "health";
      renderFeed();
    } else {
      if (state.selectedAuthor) state.selectedAuthor = "";
      if (state.view === "health" || state.view === "authors") state.view = "feed";
      renderFeed();
    }
  }

  function bindEvents() {
    document.getElementById("theme-toggle").addEventListener("click", () => {
      applySiteTheme(state.siteTheme === "dark" ? "light" : "dark");
    });

    const numBtn = document.getElementById("numeral-toggle");
    const syncNumBtn = () => {
      numBtn.textContent = state.numeralMode === "bn" ? "সংখ্যা: বাংলা" : "Num: 123";
    };
    syncNumBtn();
    numBtn.addEventListener("click", () => {
      state.numeralMode = state.numeralMode === "bn" ? "en" : "bn";
      localStorage.setItem(STORAGE_KEYS.numerals, state.numeralMode);
      syncNumBtn();
      updateBookmarkBadge();
      renderSourcePills();
      renderFeed();
      if (state.activeReaderId) openReaderById(state.activeReaderId, false);
    });

    document.querySelectorAll(".nav-tab").forEach((tab) => {
      tab.addEventListener("click", async () => {
        const v = tab.dataset.view;
        state.view = v;
        if (v === "editorials") {
          await ensureAllChunksLoaded();
          history.pushState(null, "", "#/editorials");
        } else if (v === "authors") {
          await ensureAllChunksLoaded();
          history.pushState(null, "", "#/authors");
        } else if (v === "bookmarks") {
          history.pushState(null, "", "#/bookmarks");
        } else if (v === "health") {
          history.pushState(null, "", "#/health");
        } else {
          state.selectedAuthor = "";
          history.pushState(null, "", "#/");
        }
        renderFeed();
      });
    });

    const searchInput = document.getElementById("search-input");
    const clearSearchBtn = document.getElementById("clear-search-btn");
    let searchDebounce = null;
    searchInput.addEventListener("input", () => {
      clearSearchBtn.classList.toggle("hidden", !searchInput.value);
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(async () => {
        state.searchQuery = searchInput.value;
        if (state.searchQuery.trim().length >= 2) {
          await ensureAllChunksLoaded();
        }
        renderFeed();
      }, 180);
    });

    clearSearchBtn.addEventListener("click", () => {
      searchInput.value = "";
      state.searchQuery = "";
      clearSearchBtn.classList.add("hidden");
      renderFeed();
    });

    document.getElementById("author-search-input").addEventListener("input", (e) => {
      state.authorSearchQuery = e.target.value;
      renderAuthorsDirectory();
    });

    document.getElementById("authors-grid").addEventListener("click", (e) => {
      const card = e.target.closest("[data-author-card]");
      if (!card) return;
      filterByAuthor(card.dataset.authorCard);
    });

    document.getElementById("all-authors-btn").addEventListener("click", async () => {
      await ensureAllChunksLoaded();
      state.selectedAuthor = "";
      state.view = "authors";
      history.pushState(null, "", "#/authors");
      renderFeed();
    });

    document.getElementById("language-filter").addEventListener("change", async (e) => {
      state.selectedLanguage = e.target.value;
      if (state.selectedLanguage !== "all") await ensureAllChunksLoaded();
      renderSourcePills();
      renderFeed();
    });

    document.getElementById("date-filter").addEventListener("change", async (e) => {
      state.dateRange = e.target.value;
      document
        .getElementById("custom-date-row")
        .classList.toggle("hidden", state.dateRange !== "custom");
      if (state.dateRange !== "all") await ensureAllChunksLoaded();
      renderFeed();
    });

    document.getElementById("date-from").addEventListener("change", (e) => {
      state.dateFrom = e.target.value;
      renderFeed();
    });
    document.getElementById("date-to").addEventListener("change", (e) => {
      state.dateTo = e.target.value;
      renderFeed();
    });

    document.getElementById("category-pills").addEventListener("click", async (e) => {
      const btn = e.target.closest(".filter-pill");
      if (!btn) return;
      state.selectedCategory = btn.dataset.category;
      document.querySelectorAll("#category-pills .filter-pill").forEach((p) => {
        p.classList.toggle("active", p.dataset.category === state.selectedCategory);
      });
      if (state.selectedCategory !== "all") await ensureAllChunksLoaded();
      renderFeed();
    });

    document.getElementById("source-pills").addEventListener("click", async (e) => {
      const btn = e.target.closest(".filter-pill");
      if (!btn) return;
      const sid = btn.dataset.sourceId;
      if (state.selectedSources.has(sid)) {
        state.selectedSources.delete(sid);
      } else {
        state.selectedSources.add(sid);
      }
      await ensureAllChunksLoaded();
      renderSourcePills();
      renderFeed();
    });

    document.getElementById("toggle-all-sources-btn").addEventListener("click", () => {
      state.showAllSourcePills = !state.showAllSourcePills;
      renderSourcePills();
    });

    document.getElementById("clear-author-btn").addEventListener("click", () => {
      state.selectedAuthor = "";
      history.pushState(null, "", "#/");
      renderFeed();
    });

    document.getElementById("reset-filters-btn").addEventListener("click", () => {
      state.searchQuery = "";
      searchInput.value = "";
      clearSearchBtn.classList.add("hidden");
      state.selectedSources.clear();
      state.selectedCategory = "all";
      state.selectedLanguage = "all";
      state.dateRange = "all";
      state.dateFrom = "";
      state.dateTo = "";
      state.selectedAuthor = "";
      document.getElementById("language-filter").value = "all";
      document.getElementById("date-filter").value = "all";
      document.getElementById("custom-date-row").classList.add("hidden");
      document.querySelectorAll("#category-pills .filter-pill").forEach((p) => {
        p.classList.toggle("active", p.dataset.category === "all");
      });
      renderSourcePills();
      if (window.location.hash.startsWith("#/author/")) history.pushState(null, "", "#/");
      renderFeed();
    });

    document.getElementById("articles-grid").addEventListener("click", (e) => {
      const actionEl = e.target.closest("[data-action]");
      if (!actionEl) return;
      const action = actionEl.dataset.action;
      if (action === "open-reader") {
        openReaderById(actionEl.dataset.id);
      } else if (action === "bookmark") {
        toggleBookmark(actionEl.dataset.id);
      } else if (action === "filter-author") {
        filterByAuthor(actionEl.dataset.author);
      }
    });

    document.getElementById("reader-tags-row").addEventListener("click", async (e) => {
      const chip = e.target.closest("[data-tag]");
      if (!chip) return;
      const tag = chip.dataset.tag;
      closeReader(false);
      await ensureAllChunksLoaded();
      state.view = "feed";
      state.searchQuery = tag;
      searchInput.value = tag;
      clearSearchBtn.classList.remove("hidden");
      history.pushState(null, "", "#/");
      renderFeed();
    });

    document.getElementById("load-more-btn").addEventListener("click", async () => {
      if (await loadNextChunk()) renderFeed();
    });

    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(
        async (entries) => {
          if (entries[0].isIntersecting && state.view === "feed" && !state.allLoaded) {
            if (await loadNextChunk()) renderFeed();
          }
        },
        { rootMargin: "280px" }
      );
      observer.observe(document.getElementById("scroll-sentinel"));
    }

    document.getElementById("reader-close-btn").addEventListener("click", () => closeReader());
    document.getElementById("reader-backdrop").addEventListener("click", () => closeReader());
    document.getElementById("font-dec-btn").addEventListener("click", () =>
      applyReaderFontSize(state.readerFontRem - 0.08)
    );
    document.getElementById("font-inc-btn").addEventListener("click", () =>
      applyReaderFontSize(state.readerFontRem + 0.08)
    );

    document.querySelectorAll(".theme-dot").forEach((btn) => {
      btn.addEventListener("click", () => applyReaderTheme(btn.dataset.rtheme));
    });

    document.getElementById("reader-bookmark-btn").addEventListener("click", () => {
      if (state.activeReaderId) toggleBookmark(state.activeReaderId);
    });

    document.getElementById("reader-share-btn").addEventListener("click", async () => {
      if (!state.activeReaderId) return;
      const art = state.articleMap.get(state.activeReaderId) || state.bookmarks[state.activeReaderId];
      const shareUrl = `${window.location.origin}${window.location.pathname}#/read/${state.activeReaderId}`;
      if (navigator.share && art) {
        try {
          await navigator.share({ title: art.title, text: art.snippet, url: shareUrl });
          return;
        } catch {
          // Fall back to clipboard
        }
      }
      try {
        await navigator.clipboard.writeText(shareUrl);
        showToast("পাঠক মোডের লিংক কপি করা হয়েছে");
      } catch {
        showToast(shareUrl);
      }
    });

    window.addEventListener("keydown", (e) => {
      if (!state.activeReaderId) return;
      if (e.key === "Escape") {
        closeReader();
      } else if (e.key === "ArrowLeft") {
        document.getElementById("reader-prev-btn").click();
      } else if (e.key === "ArrowRight") {
        document.getElementById("reader-next-btn").click();
      }
    });

    let touchStartX = 0;
    let touchStartY = 0;
    const readerSheet = document.getElementById("reader-sheet");
    readerSheet.addEventListener(
      "touchstart",
      (e) => {
        touchStartX = e.changedTouches[0].screenX;
        touchStartY = e.changedTouches[0].screenY;
      },
      { passive: true }
    );
    readerSheet.addEventListener(
      "touchend",
      (e) => {
        if (!state.activeReaderId) return;
        const dx = e.changedTouches[0].screenX - touchStartX;
        const dy = e.changedTouches[0].screenY - touchStartY;
        if (Math.abs(dx) > 65 && Math.abs(dx) > Math.abs(dy) * 1.6) {
          if (dx > 0) {
            document.getElementById("reader-prev-btn").click();
          } else {
            document.getElementById("reader-next-btn").click();
          }
        }
      },
      { passive: true }
    );

    window.addEventListener("hashchange", handleHashRoute);
  }

  async function init() {
    applySiteTheme(state.siteTheme);
    applyReaderTheme(state.readerTheme);
    applyReaderFontSize(state.readerFontRem);
    updateBookmarkBadge();
    bindEvents();

    const isLocalhost =
      window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

    if ("serviceWorker" in navigator && window.location.protocol.startsWith("http")) {
      if (isLocalhost) {
        navigator.serviceWorker.getRegistrations().then((regs) => {
          regs.forEach((r) => r.unregister());
        });
      } else {
        navigator.serviceWorker.register("./sw.js").catch(() => {});
      }
    }

    try {
      await resolveDataBase();
      const [sources, health] = await Promise.all([
        fetchJson("sources.json").catch(() => []),
        fetchJson("health.json").catch(() => null),
      ]);
      state.sources = sources;
      state.sourcesMap = new Map(sources.map((s) => [s.id, s]));
      state.health = health;

      renderSourcePills();
      await loadNextChunk();
      await handleHashRoute();
    } catch (err) {
      console.error(err);
      document.getElementById("results-summary").textContent = "ডেটা লোড করতে সমস্যা হয়েছে।";
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();

import { create } from 'zustand';
import toast from 'react-hot-toast';
import * as api from '../utils/api';
import {
  getVideoCategory,
  buildCategoryIndex,
  getDescendantIds,
  generateId,
  SEED_CATEGORIES,
  UNSORTED_CATEGORIES,
} from '../utils/formatters';

/** Debounce helper */
function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/** Mulberry32 seeded PRNG — deterministic shuffle that stays stable across re-filters. */
function mulberry32(seed) {
  let a = seed;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Fisher-Yates shuffle using a seeded RNG so the order only changes when the seed does. */
function seededShuffle(arr, seed) {
  const rand = mulberry32(seed);
  const result = arr.slice();
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}

// Videos watched within this window are pushed to the back of the random shuffle.
const RECENTLY_WATCHED_MS = 14 * 24 * 60 * 60 * 1000;

// Debounced save functions — persist to disk via API
const debouncedSaveCategories = debounce((data) => api.saveCategories(data).catch(console.error), 400);
const debouncedSaveCategorySchema = debounce((data) => api.saveCategorySchema(data).catch(console.error), 400);
const debouncedSaveBlacklist = debounce((data) => api.saveBlacklist(data).catch(console.error), 400);
const debouncedSavePlaylists = debounce((data) => api.savePlaylists(data).catch(console.error), 400);
const debouncedSaveTags = debounce((data) => api.saveTags(data).catch(console.error), 400);
const debouncedSaveHistory = debounce((data) => api.saveHistory(data).catch(console.error), 400);

const useVideoStore = create((set, get) => ({
  // ── Data ──────────────────────────────────────────────────────────
  videos: [],
  categories: {},
  categoryTree: [],          // flat array of { id, name, color, icon, parentId, sortOrder }
  blacklist: [],
  playlists: {},
  tags: {},
  watchHistory: {},
  isLoading: true,
  error: null,

  // ── UI State ──────────────────────────────────────────────────────
  pickerTarget: null,        // { mode: 'single', viewkey } | { mode: 'bulk' } | null
  activeTab: 'all',          // 'all' | 'none' | 'recent' | 'blacklist' | categoryId
  activePlaylist: null,      // playlist name string | null
  activeTag: null,           // tag string | null
  durationFilter: 'all',     // 'all' | 'under5' | '5to15' | '15to30' | 'over30'
  watchFilter: 'all',        // 'all' | 'unwatched' | 'watched'
  searchQuery: '',
  advancedSearch: {
    minViews: '',
    minDuration: '',
    regex: '',
  },
  sortMode: 'random',
  shuffleSeed: Date.now(),
  viewMode: 'grid',          // 'grid' (comfortable) | 'compact' | 'list' (dense table)
  isBulkMode: false,
  selectedVideos: new Set(),
  isTheaterMode: false,
  isSidebarCollapsed: false,
  focusedIndex: -1,          // Keyboard navigation index
  inspectorVideo: null,      // Video currently shown in inspector drawer

  // ── Player State ──────────────────────────────────────────────────
  currentVideo: null,
  queue: [],
  isPlaying: false,
  playerMode: 'idle',        // 'idle' | 'native' | 'iframe'
  streams: [],
  activeStreamIdx: 0,

  // ── Derived: filtered + sorted videos ─────────────────────────────
  filteredVideos: [],

  // ── Init: Load all data from server ───────────────────────────────
  init: async () => {
    set({ isLoading: true, error: null });
    try {
      const [videos, categories, categoryTree, blacklist, playlists, tags, history] = await Promise.all([
        api.fetchVideos(),
        api.fetchCategories(),
        api.fetchCategorySchema().catch(() => []),
        api.fetchBlacklist(),
        api.fetchPlaylists().catch(() => ({})),
        api.fetchTags().catch(() => ({})),
        api.fetchHistory().catch(() => ({})),
      ]);

      // Auto-seed the tree on first load so categories-schema.json gets created
      // with the 8 legacy category ids/colors as top-level nodes.
      let tree = categoryTree;
      if (!tree || tree.length === 0) {
        tree = SEED_CATEGORIES;
        debouncedSaveCategorySchema(tree);
      }

      set({
        videos: videos || [],
        categories: categories || {},
        categoryTree: tree || [],
        blacklist: blacklist || [],
        playlists: playlists || {},
        tags: tags || {},
        watchHistory: history || {},
        isLoading: false,
      });
      get().refilter();
    } catch (err) {
      set({ error: err.message, isLoading: false });
      console.error('Failed to load data:', err);
    }
  },

  // ── Filtering + Sorting ───────────────────────────────────────────
  refilter: () => {
    const {
      videos,
      categories,
      blacklist,
      activeTab,
      activePlaylist,
      activeTag,
      durationFilter,
      watchFilter,
      searchQuery,
      advancedSearch,
      sortMode,
      shuffleSeed,
      watchHistory,
      categoryTree,
      playlists,
      tags,
    } = get();

    const { byId, childrenOf } = buildCategoryIndex(categoryTree);
    const blacklistSet = new Set(blacklist);
    const query = searchQuery.toLowerCase().trim();
    const queryTokens = query ? query.split(/\s+/).filter(Boolean) : [];

    let regexObj = null;
    if (advancedSearch.regex) {
      try {
        regexObj = new RegExp(advancedSearch.regex, 'i');
      } catch {
        // invalid regex, ignore
      }
    }

    // Selecting a parent category includes all of its descendants' videos.
    const isCategoryTab = activeTab !== 'all' && activeTab !== 'none' && activeTab !== 'recent' && activeTab !== 'blacklist';
    const activeCatSet = isCategoryTab ? getDescendantIds(activeTab, childrenOf) : null;

    // "All Videos" hides the scraped recommended/related feeds — they are still
    // reachable from their own sidebar tabs. Includes any sub-categories of them.
    const hiddenFromAll = new Set([
      ...getDescendantIds('recommended', childrenOf),
      ...getDescendantIds('related', childrenOf),
    ]);

    let filtered = videos.filter((vid) => {
      const isBlacklisted = blacklistSet.has(vid.viewkey);

      // Handle Blacklist tab view
      if (activeTab === 'blacklist') {
        if (!isBlacklisted) return false;
      } else {
        if (isBlacklisted) return false;
      }

      // Handle Tab filtering
      if (activeTab === 'all') {
        // All non-blacklisted included, except the recommended/related feeds.
        if (hiddenFromAll.has(getVideoCategory(vid, categories))) return false;
      } else if (activeTab === 'none') {
        const rawCat = getVideoCategory(vid, categories);
        const cat = byId.has(rawCat) ? rawCat : 'none';
        if (cat !== 'none') return false;
      } else if (activeTab === 'recent') {
        const entry = watchHistory[vid.viewkey];
        if (!entry || !entry.lastWatched) return false;
      } else if (activeTab === 'blacklist') {
        // Handled above
      } else if (activeCatSet) {
        const rawCat = getVideoCategory(vid, categories);
        const cat = byId.has(rawCat) ? rawCat : 'none';
        if (!activeCatSet.has(cat)) return false;
      }

      // Handle Playlist filter
      if (activePlaylist) {
        const pList = playlists[activePlaylist] || [];
        if (!pList.includes(vid.viewkey)) return false;
      }

      // Handle Tag filter
      if (activeTag) {
        const vTags = tags[vid.viewkey] || [];
        if (!vTags.includes(activeTag)) return false;
      }

      // Handle Duration filter
      if (durationFilter !== 'all') {
        const d = vid.rawDuration || 0;
        if (durationFilter === 'under5' && d >= 300) return false;
        if (durationFilter === '5to15' && (d < 300 || d >= 900)) return false;
        if (durationFilter === '15to30' && (d < 900 || d >= 1800)) return false;
        if (durationFilter === 'over30' && d < 1800) return false;
      }

      // Handle Watch status filter
      if (watchFilter !== 'all') {
        const watched = watchHistory[vid.viewkey]?.count > 0;
        if (watchFilter === 'watched' && !watched) return false;
        if (watchFilter === 'unwatched' && watched) return false;
      }

      // Search Query (Multi-token match)
      if (queryTokens.length > 0) {
        const text = vid.searchText || vid.title.toLowerCase();
        for (const token of queryTokens) {
          if (!text.includes(token)) return false;
        }
      }

      // Advanced Regex
      if (regexObj && !regexObj.test(vid.title)) {
        return false;
      }

      // Advanced Views & Duration
      if (advancedSearch.minViews && (vid.rawViews || 0) < parseInt(advancedSearch.minViews, 10)) {
        return false;
      }
      if (advancedSearch.minDuration && (vid.rawDuration || 0) < (parseInt(advancedSearch.minDuration, 10) * 60)) {
        return false;
      }

      return true;
    });

    // Sorting
    switch (sortMode) {
      case 'title-az':
        filtered.sort((a, b) => a.title.localeCompare(b.title));
        break;
      case 'views-desc':
        filtered.sort((a, b) => (b.rawViews || 0) - (a.rawViews || 0));
        break;
      case 'duration-desc':
        filtered.sort((a, b) => (b.rawDuration || 0) - (a.rawDuration || 0));
        break;
      case 'newest':
        filtered.sort((a, b) => (a.idx ?? 0) - (b.idx ?? 0));
        break;
      default: {
        // 'random' — seeded shuffle with recently-watched deprioritization
        if (activeTab === 'recent') {
          filtered.sort((a, b) => {
            const timeA = watchHistory[a.viewkey]?.lastWatched || 0;
            const timeB = watchHistory[b.viewkey]?.lastWatched || 0;
            return timeB - timeA;
          });
        } else {
          const now = Date.now();
          const isRecentlyWatched = (vid) => {
            const entry = watchHistory[vid.viewkey];
            return entry && (now - entry.lastWatched) < RECENTLY_WATCHED_MS;
          };
          const fresh = filtered.filter((v) => !isRecentlyWatched(v));
          const recent = filtered.filter(isRecentlyWatched);
          filtered = [...seededShuffle(fresh, shuffleSeed), ...seededShuffle(recent, shuffleSeed)];
        }
      }
    }

    set({ filteredVideos: filtered, focusedIndex: filtered.length > 0 ? 0 : -1 });
  },

  // ── Tab & Filter Actions ──────────────────────────────────────────
  setTab: (tab) => {
    set({
      activeTab: tab,
      activePlaylist: null,
      activeTag: null,
      selectedVideos: new Set(),
    });
    get().refilter();
  },

  setActivePlaylist: (playlistName) => {
    set((state) => ({
      activePlaylist: state.activePlaylist === playlistName ? null : playlistName,
      activeTag: null,
    }));
    get().refilter();
  },

  setActiveTag: (tagName) => {
    set((state) => ({
      activeTag: state.activeTag === tagName ? null : tagName,
      activePlaylist: null,
    }));
    get().refilter();
  },

  setDurationFilter: (duration) => {
    set({ durationFilter: duration });
    get().refilter();
  },

  setWatchFilter: (watch) => {
    set({ watchFilter: watch });
    get().refilter();
  },

  clearAllFilters: () => {
    set({
      searchQuery: '',
      activeTag: null,
      activePlaylist: null,
      durationFilter: 'all',
      watchFilter: 'all',
      advancedSearch: { minViews: '', minDuration: '', regex: '' },
    });
    get().refilter();
  },

  // ── Search ────────────────────────────────────────────────────────
  setSearchQuery: (q) => {
    set({ searchQuery: q });
    get().refilter();
  },

  setAdvancedSearch: (filters) => {
    set((state) => ({ advancedSearch: { ...state.advancedSearch, ...filters } }));
    get().refilter();
  },

  // ── Sort ──────────────────────────────────────────────────────────
  setSortMode: (mode) => {
    if (mode === 'random') {
      set({ sortMode: mode, shuffleSeed: Date.now() });
    } else {
      set({ sortMode: mode });
    }
    get().refilter();
  },

  reshuffle: () => {
    set({ shuffleSeed: Date.now() });
    get().refilter();
  },

  // ── View Mode ─────────────────────────────────────────────────────
  setViewMode: (mode) => set({ viewMode: mode }),

  // ── Sidebar & Layout ──────────────────────────────────────────────
  toggleSidebar: () => set((s) => ({ isSidebarCollapsed: !s.isSidebarCollapsed })),
  toggleTheaterMode: () => set((s) => ({ isTheaterMode: !s.isTheaterMode })),

  // ── Keyboard Navigation ───────────────────────────────────────────
  setFocusedIndex: (idx) => set({ focusedIndex: idx }),

  navigateFocus: (delta) => {
    const { filteredVideos, focusedIndex } = get();
    if (filteredVideos.length === 0) return;
    const next = Math.max(0, Math.min(filteredVideos.length - 1, (focusedIndex === -1 ? 0 : focusedIndex) + delta));
    set({ focusedIndex: next });
  },

  // ── Inspector Drawer ──────────────────────────────────────────────
  openInspector: (video) => set({ inspectorVideo: video }),
  closeInspector: () => set({ inspectorVideo: null }),

  // ── Copy Link Helper ──────────────────────────────────────────────
  copyVideoLink: async (video) => {
    try {
      await navigator.clipboard.writeText(video.url);
      toast.success('Link copied to clipboard!');
    } catch {
      toast.error('Failed to copy link');
    }
  },

  // ── Categorize ────────────────────────────────────────────────────
  setCategory: (viewkey, cat) => {
    set((state) => {
      const next = { ...state.categories };
      if (cat === 'none') delete next[viewkey];
      else next[viewkey] = cat;
      debouncedSaveCategories(next);
      return { categories: next };
    });
    get().refilter();
  },

  bulkSetCategory: (cat) => {
    set((state) => {
      const next = { ...state.categories };
      for (const vk of state.selectedVideos) {
        if (cat === 'none') delete next[vk];
        else next[vk] = cat;
      }
      debouncedSaveCategories(next);
      return { categories: next, selectedVideos: new Set(), isBulkMode: false };
    });
    get().refilter();
  },

  // ── Blacklist & Restore ───────────────────────────────────────────
  deleteVideo: (viewkey) => {
    set((state) => {
      if (state.blacklist.includes(viewkey)) return state;
      const next = [...state.blacklist, viewkey];
      debouncedSaveBlacklist(next);
      return { blacklist: next };
    });
    get().refilter();
  },

  restoreVideo: (viewkey) => {
    set((state) => {
      const next = state.blacklist.filter((vk) => vk !== viewkey);
      debouncedSaveBlacklist(next);
      return { blacklist: next };
    });
    toast.success('Video restored from blacklist');
    get().refilter();
  },

  // Applied after a successful /api/refresh-thumbnail call, so the freshly
  // re-scraped preview URL is used everywhere without a full data reload.
  setVideoThumbnail: (viewkey, remoteThumbnail) => {
    set((state) => ({
      videos: state.videos.map((v) => (
        v.viewkey === viewkey ? { ...v, remoteThumbnail } : v
      )),
    }));
    get().refilter();
  },

  toggleBlacklist: (viewkey) => {
    const { blacklist } = get();
    if (blacklist.includes(viewkey)) {
      get().restoreVideo(viewkey);
    } else {
      get().deleteVideo(viewkey);
      toast.success('Moved to blacklist');
    }
  },

  bulkDelete: () => {
    set((state) => {
      const next = Array.from(new Set([...state.blacklist, ...state.selectedVideos]));
      debouncedSaveBlacklist(next);
      return { blacklist: next, selectedVideos: new Set(), isBulkMode: false };
    });
    get().refilter();
  },

  clearBlacklist: () => {
    set({ blacklist: [] });
    debouncedSaveBlacklist([]);
    get().refilter();
  },

  // ── Selection (Bulk Mode) ─────────────────────────────────────────
  toggleBulkMode: () => set((s) => ({
    isBulkMode: !s.isBulkMode,
    selectedVideos: new Set(),
  })),

  toggleSelection: (viewkey) => set((state) => {
    const next = new Set(state.selectedVideos);
    if (next.has(viewkey)) next.delete(viewkey);
    else next.add(viewkey);
    return { selectedVideos: next };
  }),

  selectAll: () => set((state) => ({
    selectedVideos: new Set(state.filteredVideos.map((v) => v.viewkey)),
  })),

  clearSelection: () => set({ selectedVideos: new Set() }),

  // ── Player ────────────────────────────────────────────────────────
  playVideo: (video, opts = {}) => {
    const { currentVideo, categories } = get();

    if (
      !opts.force &&
      currentVideo &&
      currentVideo.viewkey !== video.viewkey &&
      UNSORTED_CATEGORIES.has(getVideoCategory(currentVideo, categories))
    ) {
      get().openPicker({ mode: 'auto', viewkey: currentVideo.viewkey, pendingVideo: video });
      return;
    }

    set({
      currentVideo: video,
      isPlaying: true,
      playerMode: 'idle',
      streams: [],
      activeStreamIdx: 0,
    });
    get().recordWatch(video.viewkey);
  },

  stopPlayer: () => set({
    currentVideo: null,
    isPlaying: false,
    playerMode: 'idle',
    streams: [],
  }),

  setPlayerMode: (mode) => set({ playerMode: mode }),
  setStreams: (streams, activeIdx = 0) => set({ streams, activeStreamIdx: activeIdx }),
  setActiveStream: (idx) => set({ activeStreamIdx: idx }),

  playNext: () => {
    const { queue, currentVideo, filteredVideos } = get();
    if (queue.length > 0) {
      const next = queue[0];
      set((s) => ({ queue: s.queue.slice(1) }));
      get().playVideo(next);
      return;
    }
    if (currentVideo) {
      const idx = filteredVideos.findIndex((v) => v.viewkey === currentVideo.viewkey);
      if (idx >= 0 && idx < filteredVideos.length - 1) {
        get().playVideo(filteredVideos[idx + 1]);
      }
    }
  },

  // ── Queue ─────────────────────────────────────────────────────────
  addToQueue: (video) => {
    set((state) => {
      if (state.queue.some((v) => v.viewkey === video.viewkey)) return state;
      return { queue: [...state.queue, video] };
    });
    toast.success('Added to queue');
  },

  removeFromQueue: (viewkey) => set((state) => ({
    queue: state.queue.filter((v) => v.viewkey !== viewkey),
  })),

  playFromQueue: (viewkey) => {
    const { queue } = get();
    const vid = queue.find((v) => v.viewkey === viewkey);
    if (vid) {
      set((s) => ({ queue: s.queue.filter((v) => v.viewkey !== viewkey) }));
      get().playVideo(vid);
    }
  },

  clearQueue: () => set({ queue: [] }),

  // ── Watch History ─────────────────────────────────────────────────
  recordWatch: (viewkey) => {
    set((state) => {
      const prev = state.watchHistory[viewkey] || { count: 0 };
      const next = {
        ...state.watchHistory,
        [viewkey]: {
          lastWatched: Date.now(),
          count: (prev.count || 0) + 1,
        },
      };
      debouncedSaveHistory(next);
      return { watchHistory: next };
    });
  },

  // ── Playlists ─────────────────────────────────────────────────────
  createPlaylist: (name) => {
    set((state) => {
      const next = { ...state.playlists, [name]: [] };
      debouncedSavePlaylists(next);
      return { playlists: next };
    });
  },

  deletePlaylist: (name) => {
    set((state) => {
      const next = { ...state.playlists };
      delete next[name];
      debouncedSavePlaylists(next);
      return { playlists: next };
    });
  },

  addToPlaylist: (name, viewkey) => {
    set((state) => {
      const list = state.playlists[name] || [];
      if (list.includes(viewkey)) return state;
      const next = { ...state.playlists, [name]: [...list, viewkey] };
      debouncedSavePlaylists(next);
      return { playlists: next };
    });
  },

  removeFromPlaylist: (name, viewkey) => {
    set((state) => {
      const list = (state.playlists[name] || []).filter((v) => v !== viewkey);
      const next = { ...state.playlists, [name]: list };
      debouncedSavePlaylists(next);
      return { playlists: next };
    });
  },

  // ── Tags ──────────────────────────────────────────────────────────
  addTag: (viewkey, tag) => {
    set((state) => {
      const current = state.tags[viewkey] || [];
      if (current.includes(tag)) return state;
      const next = { ...state.tags, [viewkey]: [...current, tag] };
      debouncedSaveTags(next);
      return { tags: next };
    });
  },

  removeTag: (viewkey, tag) => {
    set((state) => {
      const current = (state.tags[viewkey] || []).filter((t) => t !== tag);
      const next = { ...state.tags };
      if (current.length === 0) delete next[viewkey];
      else next[viewkey] = current;
      debouncedSaveTags(next);
      return { tags: next };
    });
  },

  // ── Category Counts & Metadata ────────────────────────────────────
  getCategoryCounts: () => {
    const { videos, categories, blacklist, categoryTree, watchHistory } = get();
    const { byId, childrenOf } = buildCategoryIndex(categoryTree);
    const blacklistSet = new Set(blacklist);

    let allCount = 0;
    let recentCount = 0;
    const direct = { none: 0 };
    for (const n of categoryTree) direct[n.id] = 0;

    for (const vid of videos) {
      if (blacklistSet.has(vid.viewkey)) continue;
      allCount++;

      if (watchHistory[vid.viewkey]?.lastWatched) {
        recentCount++;
      }

      const rawCat = getVideoCategory(vid, categories);
      const cat = byId.has(rawCat) ? rawCat : 'none';
      direct[cat] = (direct[cat] || 0) + 1;
    }

    const total = {
      all: allCount,
      none: direct.none || 0,
      recent: recentCount,
      blacklist: blacklist.length,
      ...direct,
    };

    const memo = new Set();
    const compute = (id) => {
      if (memo.has(id)) return total[id];
      let sum = direct[id] || 0;
      for (const child of childrenOf.get(id) || []) sum += compute(child.id);
      total[id] = sum;
      memo.add(id);
      return sum;
    };
    for (const n of categoryTree) compute(n.id);
    return total;
  },

  getCategoryColor: (id) => {
    const node = get().categoryTree.find((n) => n.id === id);
    return node?.color || 'transparent';
  },

  // ── Category tree CRUD ──────────────────────────────────────────────
  createCategory: ({ name, color, icon = null, parentId = null }) => {
    set((state) => {
      const id = generateId();
      const siblings = state.categoryTree.filter((n) => n.parentId === parentId);
      const sortOrder = siblings.length;
      const next = [...state.categoryTree, { id, name, color, icon, parentId, sortOrder }];
      debouncedSaveCategorySchema(next);
      return { categoryTree: next };
    });
  },

  renameCategory: (id, name) => {
    set((state) => {
      const next = state.categoryTree.map((n) => (n.id === id ? { ...n, name } : n));
      debouncedSaveCategorySchema(next);
      return { categoryTree: next };
    });
  },

  setCategoryColor: (id, color) => {
    set((state) => {
      const next = state.categoryTree.map((n) => (n.id === id ? { ...n, color } : n));
      debouncedSaveCategorySchema(next);
      return { categoryTree: next };
    });
  },

  moveCategory: (id, newParentId) => {
    set((state) => {
      const { childrenOf } = buildCategoryIndex(state.categoryTree);
      const descendants = getDescendantIds(id, childrenOf);
      if (newParentId === id || descendants.has(newParentId)) {
        toast.error("Can't move a category into itself or its own subcategory");
        return state;
      }
      const siblings = state.categoryTree.filter((n) => n.parentId === newParentId && n.id !== id);
      const next = state.categoryTree.map((n) =>
        n.id === id ? { ...n, parentId: newParentId, sortOrder: siblings.length } : n
      );
      debouncedSaveCategorySchema(next);
      return { categoryTree: next };
    });
    get().refilter();
  },

  reorderCategory: (id, parentId, newIndex) => {
    set((state) => {
      const moved = state.categoryTree.find((n) => n.id === id);
      if (!moved) return state;
      const siblings = state.categoryTree
        .filter((n) => n.parentId === parentId && n.id !== id)
        .sort((a, b) => a.sortOrder - b.sortOrder);
      siblings.splice(newIndex, 0, moved);
      const reindexed = new Map(siblings.map((n, i) => [n.id, i]));
      const next = state.categoryTree.map((n) =>
        reindexed.has(n.id) ? { ...n, sortOrder: reindexed.get(n.id), parentId } : n
      );
      debouncedSaveCategorySchema(next);
      return { categoryTree: next };
    });
  },

  deleteCategory: (id) => {
    set((state) => {
      const target = state.categoryTree.find((n) => n.id === id);
      if (!target) return state;
      const parentId = target.parentId;

      const nextTree = state.categoryTree
        .filter((n) => n.id !== id)
        .map((n) => (n.parentId === id ? { ...n, parentId } : n));

      const nextCategories = { ...state.categories };
      for (const [vk, cat] of Object.entries(nextCategories)) {
        if (cat === id) {
          if (parentId) nextCategories[vk] = parentId;
          else delete nextCategories[vk];
        }
      }

      debouncedSaveCategorySchema(nextTree);
      debouncedSaveCategories(nextCategories);

      return {
        categoryTree: nextTree,
        categories: nextCategories,
        activeTab: state.activeTab === id ? (parentId || 'none') : state.activeTab,
      };
    });
    get().refilter();
  },

  // ── Category picker modal target ──────────────────────────────────
  openPicker: (target) => set({ pickerTarget: target }),
  closePicker: () => set({ pickerTarget: null }),
}));

export default useVideoStore;

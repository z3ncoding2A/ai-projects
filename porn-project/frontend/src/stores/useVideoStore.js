import { create } from 'zustand';
import * as api from '../utils/api';
import { getVideoCategory, ASSIGNED_CATEGORIES } from '../utils/formatters';

/** Debounce helper */
function debounce(fn, ms) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

// Debounced save functions — persist to disk via API
const debouncedSaveCategories = debounce((data) => api.saveCategories(data).catch(console.error), 400);
const debouncedSaveBlacklist = debounce((data) => api.saveBlacklist(data).catch(console.error), 400);
const debouncedSavePlaylists = debounce((data) => api.savePlaylists(data).catch(console.error), 400);
const debouncedSaveTags = debounce((data) => api.saveTags(data).catch(console.error), 400);
const debouncedSaveHistory = debounce((data) => api.saveHistory(data).catch(console.error), 400);

const useVideoStore = create((set, get) => ({
  // ── Data ──────────────────────────────────────────────────────────
  videos: [],
  categories: {},
  blacklist: [],
  playlists: {},
  tags: {},
  watchHistory: {},
  isLoading: true,
  error: null,

  // ── UI State ──────────────────────────────────────────────────────
  activeTab: 'none',
  searchQuery: '',
  advancedSearch: {
    minViews: '',
    minDuration: '',
    regex: '',
  },
  sortMode: 'newest',
  viewMode: 'grid',       // 'grid' | 'list'
  isBulkMode: false,
  selectedVideos: new Set(),
  isTheaterMode: false,
  isSidebarCollapsed: false,

  // ── Player State ──────────────────────────────────────────────────
  currentVideo: null,
  queue: [],
  isPlaying: false,
  playerMode: 'idle',     // 'idle' | 'native' | 'iframe'
  streams: [],
  activeStreamIdx: 0,

  // ── Derived: filtered + sorted videos ─────────────────────────────
  filteredVideos: [],

  // ── Init: Load all data from server ───────────────────────────────
  init: async () => {
    set({ isLoading: true, error: null });
    try {
      const [videos, categories, blacklist, playlists, tags, history] = await Promise.all([
        api.fetchVideos(),
        api.fetchCategories(),
        api.fetchBlacklist(),
        api.fetchPlaylists().catch(() => ({})),
        api.fetchTags().catch(() => ({})),
        api.fetchHistory().catch(() => ({})),
      ]);
      set({
        videos,
        categories,
        blacklist,
        playlists,
        tags,
        watchHistory: history,
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
    const { videos, categories, blacklist, activeTab, searchQuery, advancedSearch, sortMode } = get();
    const blacklistSet = new Set(blacklist);
    const query = searchQuery.toLowerCase().trim();

    let regexObj = null;
    if (advancedSearch.regex) {
      try {
        regexObj = new RegExp(advancedSearch.regex, 'i');
      } catch (e) {
        // invalid regex, ignore
      }
    }

    let filtered = videos.filter((vid) => {
      if (blacklistSet.has(vid.viewkey)) return false;
      const cat = getVideoCategory(vid, categories);
      const matchTab = activeTab === 'none'
        ? !ASSIGNED_CATEGORIES.includes(cat)
        : cat === activeTab;
      
      let matchQuery = !query || vid.searchText.includes(query);
      if (matchQuery && regexObj) {
        matchQuery = regexObj.test(vid.title);
      }
      
      const matchViews = !advancedSearch.minViews || vid.rawViews >= parseInt(advancedSearch.minViews, 10);
      const matchDuration = !advancedSearch.minDuration || vid.rawDuration >= (parseInt(advancedSearch.minDuration, 10) * 60);

      return matchTab && matchQuery && matchViews && matchDuration;
    });

    // Sort
    switch (sortMode) {
      case 'title-az':
        filtered.sort((a, b) => a.title.localeCompare(b.title));
        break;
      case 'views-desc':
        filtered.sort((a, b) => b.rawViews - a.rawViews);
        break;
      case 'duration-desc':
        filtered.sort((a, b) => b.rawDuration - a.rawDuration);
        break;
      default: // 'newest' — by original scrape index (lower = newer for most recent)
        filtered.sort((a, b) => a.idx - b.idx);
    }

    set({ filteredVideos: filtered });
  },

  // ── Tab ───────────────────────────────────────────────────────────
  setTab: (tab) => {
    set({ activeTab: tab, selectedVideos: new Set() });
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
    set({ sortMode: mode });
    get().refilter();
  },

  // ── View Mode ─────────────────────────────────────────────────────
  setViewMode: (mode) => set({ viewMode: mode }),

  // ── Sidebar ───────────────────────────────────────────────────────
  toggleSidebar: () => set((s) => ({ isSidebarCollapsed: !s.isSidebarCollapsed })),

  // ── Theater Mode ──────────────────────────────────────────────────
  toggleTheaterMode: () => set((s) => ({ isTheaterMode: !s.isTheaterMode })),

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

  // ── Bulk categorize ───────────────────────────────────────────────
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

  // ── Blacklist ─────────────────────────────────────────────────────
  deleteVideo: (viewkey) => {
    set((state) => {
      const next = [...state.blacklist, viewkey];
      debouncedSaveBlacklist(next);
      return { blacklist: next };
    });
    get().refilter();
  },

  bulkDelete: () => {
    set((state) => {
      const next = [...state.blacklist, ...state.selectedVideos];
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
  playVideo: (video) => {
    set({
      currentVideo: video,
      isPlaying: true,
      playerMode: 'idle',
      streams: [],
      activeStreamIdx: 0,
    });
    // Record in watch history
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

  // ── Play Next ─────────────────────────────────────────────────────
  playNext: () => {
    const { queue, currentVideo, filteredVideos } = get();
    if (queue.length > 0) {
      const next = queue[0];
      set((s) => ({ queue: s.queue.slice(1) }));
      get().playVideo(next);
      return;
    }
    // Find current in filtered list and play next
    if (currentVideo) {
      const idx = filteredVideos.findIndex((v) => v.viewkey === currentVideo.viewkey);
      if (idx >= 0 && idx < filteredVideos.length - 1) {
        get().playVideo(filteredVideos[idx + 1]);
      }
    }
  },

  // ── Queue ─────────────────────────────────────────────────────────
  addToQueue: (video) => set((state) => {
    if (state.queue.some((v) => v.viewkey === video.viewkey)) return state;
    return { queue: [...state.queue, video] };
  }),

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

  // ── Category Counts (for sidebar badges) ──────────────────────────
  getCategoryCounts: () => {
    const { videos, categories, blacklist } = get();
    const blacklistSet = new Set(blacklist);
    const counts = { none: 0, public: 0, pending: 0, least: 0, average: 0, most: 0, explode: 0 };
    for (const vid of videos) {
      if (blacklistSet.has(vid.viewkey)) continue;
      const cat = getVideoCategory(vid, categories);
      if (ASSIGNED_CATEGORIES.includes(cat)) counts[cat]++;
      else counts.none++;
    }
    return counts;
  },
}));

export default useVideoStore;

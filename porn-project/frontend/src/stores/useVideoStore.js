import { create } from 'zustand';
import toast from 'react-hot-toast';
import * as api from '../utils/api';
import {
  getVideoCategory,
  buildCategoryIndex,
  getDescendantIds,
  generateId,
  SEED_CATEGORIES,
} from '../utils/formatters';

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
        videos,
        categories,
        categoryTree: tree,
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
    const { videos, categories, blacklist, activeTab, searchQuery, advancedSearch, sortMode, categoryTree } = get();
    const { byId, childrenOf } = buildCategoryIndex(categoryTree);
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

    // Selecting a parent category includes all of its descendants' videos.
    const activeSet = activeTab !== 'none' ? getDescendantIds(activeTab, childrenOf) : null;

    let filtered = videos.filter((vid) => {
      if (blacklistSet.has(vid.viewkey)) return false;
      const rawCat = getVideoCategory(vid, categories);
      // Dangling ids (deleted category, stale legacy value) fold into Uncategorized.
      const cat = byId.has(rawCat) ? rawCat : 'none';
      const matchTab = activeTab === 'none' ? cat === 'none' : activeSet.has(cat);

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

  // ── Category Counts (for sidebar badges, bottom-up aggregated) ─────
  getCategoryCounts: () => {
    const { videos, categories, blacklist, categoryTree } = get();
    const { byId, childrenOf } = buildCategoryIndex(categoryTree);
    const blacklistSet = new Set(blacklist);

    const direct = { none: 0 };
    for (const n of categoryTree) direct[n.id] = 0;
    for (const vid of videos) {
      if (blacklistSet.has(vid.viewkey)) continue;
      const rawCat = getVideoCategory(vid, categories);
      const cat = byId.has(rawCat) ? rawCat : 'none';
      direct[cat] = (direct[cat] || 0) + 1;
    }

    // total[n] = direct[n] + sum(total[child]) — so a parent's badge includes its subtree.
    const total = { ...direct };
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

  // ── Category color lookup (tree-derived, replaces static CATEGORY_COLORS) ──
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

  // Reparent a node. Rejects moving a node into itself or one of its own descendants.
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

  // Recompute sortOrder for a sibling group after a drag reorder.
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

  // Splice-delete: videos + child nodes are promoted to the deleted node's parent
  // (or unassigned/top-level if it had none). Not a cascade delete.
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

  // ── Category picker modal target (VideoCard + TopBar both open this) ──
  openPicker: (target) => set({ pickerTarget: target }),
  closePicker: () => set({ pickerTarget: null }),
}));

export default useVideoStore;

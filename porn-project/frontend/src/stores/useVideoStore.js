import { create } from 'zustand';
import * as api from '../utils/api';
import { getVideoCategory, ASSIGNED_CATEGORIES } from '../utils/formatters';
import * as fsSync from '../utils/fsSync';

/**
 * Debounce helper. Exposes `.flush()` so a pending call can be forced through
 * immediately (used on tab close/hide — see the flushAllPendingSaves() below,
 * added after review found that closing the tab within the debounce window
 * silently dropped the last edit).
 */
function debounce(fn, ms) {
  let timer;
  let pending = null; // last args passed while a call is pending
  const wrapped = (...args) => {
    clearTimeout(timer);
    pending = args;
    timer = setTimeout(() => {
      pending = null;
      fn(...args);
    }, ms);
  };
  wrapped.flush = () => {
    if (pending === null) return;
    clearTimeout(timer);
    const args = pending;
    pending = null;
    fn(...args);
  };
  return wrapped;
}

// Debounced save functions — persist to disk via API
const debouncedSaveCategories = debounce((data) => api.saveCategories(data).catch(console.error), 400);
const debouncedSaveBlacklist = debounce((data) => api.saveBlacklist(data).catch(console.error), 400);
const debouncedSavePlaylists = debounce((data) => api.savePlaylists(data).catch(console.error), 400);
const debouncedSaveTags = debounce((data) => api.saveTags(data).catch(console.error), 400);
const debouncedSaveHistory = debounce((data) => api.saveHistory(data).catch(console.error), 400);
const debouncedSaveFilterPresets = debounce((data) => api.saveFilterPresets(data).catch(console.error), 400);

// Holds the live FileSystemDirectoryHandle — not serializable, so it lives
// outside Zustand state. Only the sync *status* (a string) is stored.
let fsDirHandle = null;

// Guards against a background tryReconnectFolder() clobbering a manual
// connectFolder() the user triggered while the reconnect was still resolving
// (both write fsDirHandle/fsSyncStatus with no lock otherwise).
let connectGeneration = 0;

// Flush every debounced save immediately — best-effort insurance against the
// tab closing/hiding inside the ~400ms debounce window. Registered once,
// below, on 'pagehide' and 'visibilitychange'.
function flushAllPendingSaves() {
  debouncedSaveCategories.flush();
  debouncedSaveBlacklist.flush();
  debouncedSavePlaylists.flush();
  debouncedSaveTags.flush();
  debouncedSaveHistory.flush();
  debouncedSaveFilterPresets.flush();
  // useVideoStore is declared further down this module, but this function
  // isn't called until a real 'pagehide'/'visibilitychange' event fires —
  // long after the module has finished evaluating — so the reference below
  // is always resolved by call time.
  useVideoStore.getState()._syncToDisk.flush();
}
if (typeof window !== 'undefined') {
  window.addEventListener('pagehide', flushAllPendingSaves);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flushAllPendingSaves();
  });
}

// Sort order depends only on `videos` + `sortMode` — never on category,
// blacklist, tags, or the search query. refilter() previously filtered first
// and then re-sorted the resulting subset from scratch on every call
// (every keystroke, tab switch, tag click, etc.), which is wasted work: the
// same ~8,000-item sort was being recomputed even when only the search query
// changed. Sorting once per (videos, sortMode) pair and filtering the
// already-ordered array afterward preserves order for free (Array#filter
// doesn't reorder), so the sort itself only reruns when sortMode changes.
let sortCacheVideosRef = null;
let sortCacheBySortMode = {};

function getSortedVideos(videos, sortMode) {
  if (sortCacheVideosRef !== videos) {
    sortCacheVideosRef = videos;
    sortCacheBySortMode = {};
  }
  if (sortCacheBySortMode[sortMode]) return sortCacheBySortMode[sortMode];

  const sorted = [...videos];
  switch (sortMode) {
    case 'title-az':
      sorted.sort((a, b) => a.title.localeCompare(b.title));
      break;
    case 'views-desc':
      sorted.sort((a, b) => b.rawViews - a.rawViews);
      break;
    case 'duration-desc':
      sorted.sort((a, b) => b.rawDuration - a.rawDuration);
      break;
    case 'date-added-desc':
      // Falls back to scrape idx for videos without a firstSeen date (pre-migration data)
      sorted.sort((a, b) => (b.firstSeen || '').localeCompare(a.firstSeen || '') || b.idx - a.idx);
      break;
    default: // 'newest' — by original scrape index (lower = newer for most recent)
      sorted.sort((a, b) => a.idx - b.idx);
  }
  sortCacheBySortMode[sortMode] = sorted;
  return sorted;
}

const useVideoStore = create((set, get) => ({
  // ── Data ──────────────────────────────────────────────────────────
  videos: [],
  categories: {},
  blacklist: [],
  playlists: {},
  tags: {},
  watchHistory: {},
  filterPresets: {}, // name -> { searchQuery, minViews, minDuration, regex }
  isLoading: true,
  error: null,

  // ── UI State ──────────────────────────────────────────────────────
  activeTab: 'none',
  activePlaylist: null,   // playlist name being browsed, or null
  activeTagFilter: null,  // tag being browsed, or null
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

  // ── Folder Sync (File System Access API) ───────────────────────────
  // 'unsupported' | 'disconnected' | 'needs-reauth' | 'connected' | 'saving' | 'error'
  fsSyncStatus: fsSync.isSupported() ? 'disconnected' : 'unsupported',
  fsSyncMessage: '',

  // ── Player State ──────────────────────────────────────────────────
  currentVideo: null,
  queue: [],
  isPlaying: false,
  playerMode: 'idle',     // 'idle' | 'native' | 'iframe'
  streams: [],
  activeStreamIdx: 0,
  // Bumped on every _playVideoNow, including re-selecting the video that's
  // already playing. The PlayerPanel load effect keys on this so a re-click
  // genuinely retries loading instead of resetting to a blank idle player.
  loadNonce: 0,

  // ── Derived: filtered + sorted videos ─────────────────────────────
  filteredVideos: [],

  // ── Init: Load all data from server ───────────────────────────────
  init: async () => {
    set({ isLoading: true, error: null });
    try {
      const [videos, categories, blacklist, playlists, tags, history, filterPresets] = await Promise.all([
        api.fetchVideos(),
        api.fetchCategories(),
        api.fetchBlacklist(),
        api.fetchPlaylists().catch(() => ({})),
        api.fetchTags().catch(() => ({})),
        api.fetchHistory().catch(() => ({})),
        api.fetchFilterPresets().catch(() => ({})),
      ]);
      set({
        videos,
        categories,
        blacklist,
        playlists,
        tags,
        watchHistory: history,
        filterPresets,
        isLoading: false,
      });
      get().refilter();
      get().tryReconnectFolder();
    } catch (err) {
      set({ error: err.message, isLoading: false });
      console.error('Failed to load data:', err);
    }
  },

  // ── Folder Sync ───────────────────────────────────────────────────
  // Reattach to a previously connected folder (if permission survived) and,
  // per the legacy template's behavior, let disk contents win on reconnect.
  //
  // Both this and connectFolder() write the module-level fsDirHandle/status
  // with no lock, and this one runs unawaited from init() — if the user
  // clicks "Connect Folder" manually while this is still resolving (it makes
  // no UI prompt itself, so nothing blocks that), whichever finishes last
  // would silently win and could revert a freshly-picked folder. connectGeneration
  // guards against that: each call captures the generation counter at start
  // and bails before applying its result if a newer attempt has started since.
  tryReconnectFolder: async () => {
    const myGeneration = ++connectGeneration;
    try {
      const result = await fsSync.reconnectFolder();
      if (!result || myGeneration !== connectGeneration) return;
      if (result.needsReauth) {
        fsDirHandle = result.dirHandle;
        set({ fsSyncStatus: 'needs-reauth', fsSyncMessage: 'Click Connect Folder to re-authorize' });
        return;
      }
      fsDirHandle = result.dirHandle;
      const { categories, blacklist } = await fsSync.loadFromDisk(fsDirHandle);
      if (myGeneration !== connectGeneration) return; // superseded while awaiting the disk read
      set((state) => ({
        categories: categories ?? state.categories,
        blacklist: blacklist ?? state.blacklist,
        fsSyncStatus: 'connected',
        fsSyncMessage: 'Connected — loaded from disk',
      }));
      get().refilter();
    } catch (e) {
      console.warn('Folder reconnect failed:', e);
    }
  },

  connectFolder: async () => {
    const myGeneration = ++connectGeneration;
    try {
      const handle = await fsSync.connectFolder();
      if (myGeneration !== connectGeneration) return; // a newer attempt started while the picker was open
      fsDirHandle = handle;
      set({ fsSyncStatus: 'connected', fsSyncMessage: 'Connected — auto-saving' });
      // Push current in-memory state to the newly connected folder immediately.
      const { categories, blacklist } = get();
      await fsSync.saveToDisk(fsDirHandle, categories, blacklist);
    } catch (e) {
      if (e.name !== 'AbortError' && myGeneration === connectGeneration) {
        set({ fsSyncStatus: 'error', fsSyncMessage: e.message });
      }
    }
  },

  // Fire-and-forget: writes current categories/blacklist to the connected
  // folder, if any. Called alongside every categorize/blacklist mutation.
  _syncToDisk: debounce(async (categories, blacklist) => {
    if (!fsDirHandle) return;
    set({ fsSyncStatus: 'saving', fsSyncMessage: 'Saving...' });
    try {
      await fsSync.saveToDisk(fsDirHandle, categories, blacklist);
      set({ fsSyncStatus: 'connected', fsSyncMessage: `Saved — ${new Date().toLocaleTimeString()}` });
    } catch (e) {
      set({ fsSyncStatus: 'error', fsSyncMessage: e.message });
    }
  }, 300),

  // ── Filtering + Sorting ───────────────────────────────────────────
  refilter: () => {
    const {
      videos, categories, blacklist, activeTab, activePlaylist, activeTagFilter,
      playlists, tags, searchQuery, advancedSearch, sortMode,
    } = get();
    const blacklistSet = new Set(blacklist);
    const query = searchQuery.toLowerCase().trim();
    const playlistSet = activePlaylist ? new Set(playlists[activePlaylist] || []) : null;

    let regexObj = null;
    if (advancedSearch.regex) {
      try {
        regexObj = new RegExp(advancedSearch.regex, 'i');
      } catch (e) {
        // invalid regex, ignore
      }
    }

    // Sort once (cached per sortMode) *before* filtering — Array#filter
    // preserves order, so the already-sorted array stays sorted afterward
    // with no extra work. See getSortedVideos() above for why this is safe.
    const sortedVideos = getSortedVideos(videos, sortMode);

    let filtered = sortedVideos.filter((vid) => {
      if (blacklistSet.has(vid.viewkey)) return false;

      // Playlist / tag browsing takes over from the normal category-tab scope
      // — browsing "everything tagged X" shouldn't be limited to one tab.
      let matchScope;
      if (playlistSet) {
        matchScope = playlistSet.has(vid.viewkey);
      } else if (activeTagFilter) {
        matchScope = (tags[vid.viewkey] || []).includes(activeTagFilter);
      } else {
        const cat = getVideoCategory(vid, categories);
        matchScope = activeTab === 'none'
          ? !ASSIGNED_CATEGORIES.includes(cat)
          : cat === activeTab;
      }

      let matchQuery = !query || vid.searchText.includes(query);
      if (matchQuery && regexObj) {
        matchQuery = regexObj.test(vid.title);
      }

      const matchViews = !advancedSearch.minViews || vid.rawViews >= parseInt(advancedSearch.minViews, 10);
      const matchDuration = !advancedSearch.minDuration || vid.rawDuration >= (parseInt(advancedSearch.minDuration, 10) * 60);

      return matchScope && matchQuery && matchViews && matchDuration;
    });

    set({ filteredVideos: filtered });
  },

  // ── Tab ───────────────────────────────────────────────────────────
  setTab: (tab) => {
    set({ activeTab: tab, activePlaylist: null, activeTagFilter: null, selectedVideos: new Set() });
    get().refilter();
  },

  // ── Playlist / Tag browsing ─────────────────────────────────────────
  // Both act as an alternative to the category tab, not a combination of it —
  // selecting one clears the other and clears the tab selection.
  setActivePlaylist: (name) => {
    set((state) => ({
      activePlaylist: state.activePlaylist === name ? null : name, // click again to exit
      activeTagFilter: null,
      selectedVideos: new Set(),
    }));
    get().refilter();
  },

  setActiveTagFilter: (tag) => {
    set((state) => ({
      activeTagFilter: state.activeTagFilter === tag ? null : tag,
      activePlaylist: null,
      selectedVideos: new Set(),
    }));
    get().refilter();
  },

  // ── Tag Counts (for sidebar) ────────────────────────────────────────
  getTagCounts: () => {
    const { tags, blacklist } = get();
    const blacklistSet = new Set(blacklist);
    const counts = {};
    for (const [viewkey, tagList] of Object.entries(tags)) {
      if (blacklistSet.has(viewkey)) continue;
      for (const t of tagList) counts[t] = (counts[t] || 0) + 1;
    }
    return counts;
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

  // ── Saved Filter Presets ─────────────────────────────────────────────
  // Bundles searchQuery + advancedSearch into a named, persisted preset so a
  // useful combination (e.g. a regex + min-views filter) doesn't have to be
  // re-entered after every reload.
  saveFilterPreset: (name) => {
    const { searchQuery, advancedSearch } = get();
    set((state) => {
      const next = { ...state.filterPresets, [name]: { searchQuery, ...advancedSearch } };
      debouncedSaveFilterPresets(next);
      return { filterPresets: next };
    });
  },

  applyFilterPreset: (name) => {
    const preset = get().filterPresets[name];
    if (!preset) return;
    const { searchQuery = '', ...advancedSearch } = preset;
    set({ searchQuery, advancedSearch: { minViews: '', minDuration: '', regex: '', ...advancedSearch } });
    get().refilter();
  },

  deleteFilterPreset: (name) => {
    set((state) => {
      const next = { ...state.filterPresets };
      delete next[name];
      debouncedSaveFilterPresets(next);
      return { filterPresets: next };
    });
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
      get()._syncToDisk(next, get().blacklist);
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
      get()._syncToDisk(next, get().blacklist);
      return { categories: next, selectedVideos: new Set(), isBulkMode: false };
    });
    get().refilter();
  },

  // ── Blacklist ─────────────────────────────────────────────────────
  deleteVideo: (viewkey) => {
    set((state) => {
      const next = [...state.blacklist, viewkey];
      debouncedSaveBlacklist(next);
      get()._syncToDisk(get().categories, next);
      return { blacklist: next };
    });
    get().refilter();
  },

  bulkDelete: () => {
    set((state) => {
      const next = [...state.blacklist, ...state.selectedVideos];
      debouncedSaveBlacklist(next);
      get()._syncToDisk(get().categories, next);
      return { blacklist: next, selectedVideos: new Set(), isBulkMode: false };
    });
    get().refilter();
  },

  // Blacklist an arbitrary list of viewkeys in one shot (one save instead of
  // N) — used by the duplicate-detection review flow.
  blacklistMany: (viewkeys) => {
    set((state) => {
      const next = Array.from(new Set([...state.blacklist, ...viewkeys]));
      debouncedSaveBlacklist(next);
      get()._syncToDisk(get().categories, next);
      return { blacklist: next };
    });
    get().refilter();
  },

  clearBlacklist: () => {
    set({ blacklist: [] });
    debouncedSaveBlacklist([]);
    get()._syncToDisk(get().categories, []);
    get().refilter();
  },

  // Un-blacklist a single video.
  restoreVideo: (viewkey) => {
    set((state) => {
      const next = state.blacklist.filter((vk) => vk !== viewkey);
      debouncedSaveBlacklist(next);
      get()._syncToDisk(get().categories, next);
      return { blacklist: next };
    });
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
  // videoAwaitingCategory / pendingNextVideo implement a hard categorization
  // gate: leaving a video that has no category assigned (and isn't
  // related/recommended — those describe how a video was discovered, not a
  // curation choice, so they're exempt) blocks the switch until the user
  // picks one. playNext/playFromQueue/playAll/shufflePlay all call playVideo
  // internally, so gating it here covers every path a switch can happen
  // through — card clicks, queue, auto-advance-on-end, and shuffle alike.
  videoAwaitingCategory: null,
  pendingNextVideo: null,

  playVideo: (video) => {
    const { currentVideo, categories } = get();
    if (currentVideo && currentVideo.viewkey !== video.viewkey) {
      const cat = getVideoCategory(currentVideo, categories);
      if (cat === 'none') {
        set({ videoAwaitingCategory: currentVideo, pendingNextVideo: video });
        return; // block the switch until resolveForcedCategory() is called
      }
    }
    get()._playVideoNow(video);
  },

  // Actually performs the switch — separated from playVideo so the gate
  // above and resolveForcedCategory() below can both reach it.
  _playVideoNow: (video) => {
    set((state) => ({
      currentVideo: video,
      isPlaying: true,
      playerMode: 'idle',
      streams: [],
      activeStreamIdx: 0,
      loadNonce: state.loadNonce + 1,
    }));
    // Record in watch history
    get().recordWatch(video.viewkey);
  },

  // Called from the forced-categorization modal. Applies the chosen category
  // to the video that was left, clears the gate, and lets the switch that was
  // waiting on it proceed.
  resolveForcedCategory: (cat) => {
    const { videoAwaitingCategory, pendingNextVideo } = get();
    if (videoAwaitingCategory) {
      get().setCategory(videoAwaitingCategory.viewkey, cat);
    }
    set({ videoAwaitingCategory: null, pendingNextVideo: null });
    if (pendingNextVideo) get()._playVideoNow(pendingNextVideo);
  },

  // Dismiss the gate without categorizing and without switching — for when the
  // switch was an accident (e.g. clicked the wrong video). Stays on the current
  // video and drops the pending switch entirely.
  cancelForcedCategory: () => set({ videoAwaitingCategory: null, pendingNextVideo: null }),

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

  // Plays the first video in a list immediately and queues the rest —
  // used for "Play All" on a playlist/tag/tab's currently filtered videos.
  playAll: (videoList) => {
    if (videoList.length === 0) return;
    const [first, ...rest] = videoList;
    get().playVideo(first);
    set({ queue: rest });
  },

  // Shuffle/radio mode: picks `count` random videos from whatever's currently
  // filtered (respects the active tab/playlist/tag/search/advanced-search
  // scope) and plays them via playAll. Fisher-Yates on a copy — never
  // mutates filteredVideos itself.
  shufflePlay: (count = 20) => {
    const list = get().filteredVideos;
    if (list.length === 0) return;
    const shuffled = [...list];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    get().playAll(shuffled.slice(0, count));
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
          ...prev, // preserve lastPosition across replays — starting a video
                    // you've already resumed shouldn't wipe the saved spot
          lastWatched: Date.now(),
          count: (prev.count || 0) + 1,
        },
      };
      debouncedSaveHistory(next);
      return { watchHistory: next };
    });
  },

  // Called periodically (throttled) while the native player plays, and once
  // more on pause/unmount, so playback can resume near where it left off.
  updatePlaybackPosition: (viewkey, seconds) => {
    set((state) => {
      const prev = state.watchHistory[viewkey];
      if (!prev) return state; // only track position for videos already in history
      const next = { ...state.watchHistory, [viewkey]: { ...prev, lastPosition: seconds } };
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

  // ── Backup Export / Import ──────────────────────────────────────────
  // Bundles everything a user might have manually curated (categories, tags,
  // playlists, watch history, blacklist) into one downloadable JSON file.
  exportBackup: () => {
    const { categories, tags, playlists, watchHistory, blacklist } = get();
    const backup = {
      exportedAt: new Date().toISOString(),
      categories,
      tags,
      playlists,
      history: watchHistory,
      blacklist,
    };
    const blob = new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `z3ncoding_backup_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  },

  // Restores from a previously exported backup. Merges into current state
  // rather than overwriting it — an older backup shouldn't be able to erase
  // categorization, tags, playlists, or watch progress made since it was
  // taken. Current values win on conflicts for categories/tags/playlists
  // (existing entries are assumed intentional and newer); watchHistory picks
  // whichever side has the more recent lastWatched per video, since count
  // and resume position should only move forward. Persisted via the normal
  // API + disk-sync paths, same as any other edit.
  importBackup: async (fileText) => {
    let backup;
    try {
      backup = JSON.parse(fileText);
    } catch (e) {
      throw new Error('Invalid backup file: not valid JSON');
    }

    const state = get();
    const updates = {};

    if (backup.categories && typeof backup.categories === 'object') {
      updates.categories = { ...backup.categories, ...state.categories };
      debouncedSaveCategories(updates.categories);
    }
    if (backup.tags && typeof backup.tags === 'object') {
      updates.tags = { ...backup.tags, ...state.tags };
      debouncedSaveTags(updates.tags);
    }
    if (backup.playlists && typeof backup.playlists === 'object') {
      updates.playlists = { ...backup.playlists, ...state.playlists };
      debouncedSavePlaylists(updates.playlists);
    }
    if (backup.history && typeof backup.history === 'object') {
      const merged = { ...backup.history };
      for (const [viewkey, currentEntry] of Object.entries(state.watchHistory)) {
        const backupEntry = merged[viewkey];
        if (!backupEntry || (currentEntry.lastWatched || 0) >= (backupEntry.lastWatched || 0)) {
          merged[viewkey] = currentEntry;
        }
      }
      updates.watchHistory = merged;
      debouncedSaveHistory(merged);
    }
    if (Array.isArray(backup.blacklist)) {
      // Merge rather than overwrite blacklist — restoring an older backup
      // shouldn't un-delete videos blacklisted since that backup was made.
      const merged = Array.from(new Set([...state.blacklist, ...backup.blacklist]));
      updates.blacklist = merged;
      debouncedSaveBlacklist(merged);
    }

    set(updates);
    if (updates.categories || updates.blacklist) {
      get()._syncToDisk(get().categories, get().blacklist);
    }
    get().refilter();
  },

  // ── Category Counts (for sidebar badges) ──────────────────────────
  getCategoryCounts: () => {
    const { videos, categories, blacklist } = get();
    const blacklistSet = new Set(blacklist);
    const counts = { none: 0, public: 0, pending: 0, least: 0, average: 0, most: 0, explode: 0, related: 0, recommended: 0 };
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

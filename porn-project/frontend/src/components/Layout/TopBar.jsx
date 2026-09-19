import { useRef, useCallback, useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import useVideoStore from '../../stores/useVideoStore';

export default function TopBar() {
  const searchQuery = useVideoStore((s) => s.searchQuery);
  const setSearchQuery = useVideoStore((s) => s.setSearchQuery);
  const sortMode = useVideoStore((s) => s.sortMode);
  const setSortMode = useVideoStore((s) => s.setSortMode);
  const viewMode = useVideoStore((s) => s.viewMode);
  const setViewMode = useVideoStore((s) => s.setViewMode);
  const isBulkMode = useVideoStore((s) => s.isBulkMode);
  const toggleBulkMode = useVideoStore((s) => s.toggleBulkMode);
  const selectedVideos = useVideoStore((s) => s.selectedVideos);
  const openPicker = useVideoStore((s) => s.openPicker);
  const bulkDelete = useVideoStore((s) => s.bulkDelete);
  const selectAll = useVideoStore((s) => s.selectAll);
  const clearSelection = useVideoStore((s) => s.clearSelection);
  const filteredCount = useVideoStore((s) => s.filteredVideos.length);
  const totalCount = useVideoStore((s) => s.videos.length);
  const reshuffle = useVideoStore((s) => s.reshuffle);
  const exportBackup = useVideoStore((s) => s.exportBackup);
  const importBackup = useVideoStore((s) => s.importBackup);
  const activePlaylist = useVideoStore((s) => s.activePlaylist);
  const activeTag = useVideoStore((s) => s.activeTag);
  const filteredVideos = useVideoStore((s) => s.filteredVideos);
  const playAll = useVideoStore((s) => s.playAll);
  const shufflePlay = useVideoStore((s) => s.shufflePlay);

  const searchRef = useRef(null);
  const debounceRef = useRef(null);
  const importInputRef = useRef(null);
  const moreMenuRef = useRef(null);
  const [showMoreMenu, setShowMoreMenu] = useState(false);

  // The search box needs to be a controlled input (not defaultValue) so that
  // applying a saved filter preset — which sets searchQuery in the store from
  // outside this component — is reflected in the visible text. lastSentRef
  // distinguishes "the store changed because we just typed" (already in sync,
  // don't fight the debounce) from "the store changed some other way"
  // (a preset was applied — pull the new value in).
  const [localQuery, setLocalQuery] = useState(searchQuery);
  const lastSentRef = useRef(searchQuery);

  useEffect(() => {
    if (searchQuery !== lastSentRef.current) {
      // An external change (e.g. applying a saved preset) landed. Cancel any
      // in-flight typing debounce — otherwise it still holds whatever the
      // user typed *before* the preset was applied, and would fire ~200ms
      // later and silently overwrite the preset's query back to the stale one.
      clearTimeout(debounceRef.current);
      setLocalQuery(searchQuery);
      lastSentRef.current = searchQuery;
    }
  }, [searchQuery]);

  // Close the overflow menu on any outside click
  useEffect(() => {
    if (!showMoreMenu) return;
    const onClick = (e) => {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target)) {
        setShowMoreMenu(false);
      }
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [showMoreMenu]);

  const handleImportFile = useCallback((e) => {
    const file = e.target.files[0];
    e.target.value = ''; // allow re-selecting the same file later
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (evt) => {
      try {
        await importBackup(evt.target.result);
        toast.success('Backup imported');
      } catch (err) {
        toast.error(err.message || 'Invalid backup file');
      }
    };
    reader.readAsText(file);
  }, [importBackup]);

  const handleSearch = useCallback((e) => {
    const val = e.target.value;
    setLocalQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      lastSentRef.current = val;
      setSearchQuery(val);
    }, 200);
  }, [setSearchQuery]);

  const handleClearSearch = useCallback(() => {
    clearTimeout(debounceRef.current);
    setLocalQuery('');
    lastSentRef.current = '';
    setSearchQuery('');
    searchRef.current?.focus();
  }, [setSearchQuery]);

  return (
    <header className="topbar">
      {/* Omni-search input */}
      <div className="search-wrapper">
        <span className="search-icon">🔍</span>
        <input
          ref={searchRef}
          className="search-input"
          type="text"
          placeholder="Omni-search titles, tags... (Press /)"
          value={localQuery}
          onChange={handleSearch}
          autoComplete="off"
          spellCheck="false"
        />
        {searchQuery ? (
          <button className="search-clear-btn" onClick={handleClearSearch} title="Clear search">
            ✕
          </button>
        ) : (
          <span className="search-shortcut">/</span>
        )}
      </div>

      {/* Controls: Sort, Density, Bulk, Count */}
      <div className="topbar-controls">
        {/* Quick Sort Dropdown */}
        <div className="topbar-sort-group">
          <select
            className="topbar-select"
            value={sortMode}
            onChange={(e) => setSortMode(e.target.value)}
          >
            <option value="random">🔀 Randomize</option>
            <option value="newest">🆕 Recently Scraped</option>
            <option value="date-added-desc">🗓 Date Added</option>
            <option value="title-az">🔤 Title A-Z</option>
            <option value="views-desc">👁 Most Viewed</option>
            <option value="duration-desc">⏱ Longest Duration</option>
          </select>

          {sortMode === 'random' && (
            <button
              className="topbar-btn shuffle-btn"
              onClick={reshuffle}
              title="Reshuffle library order"
            >
              🔀
            </button>
          )}
        </div>

        <div className="topbar-divider" />

        {/* 3 View Density Modes */}
        <div className="density-toggle-group">
          <button
            className={`topbar-btn${viewMode === 'grid' ? ' active' : ''}`}
            onClick={() => setViewMode('grid')}
            title="Comfortable Grid (Standard)"
          >
            ▦
          </button>
          <button
            className={`topbar-btn${viewMode === 'compact' ? ' active' : ''}`}
            onClick={() => setViewMode('compact')}
            title="Compact Grid"
          >
            ☷
          </button>
          <button
            className={`topbar-btn${viewMode === 'list' ? ' active' : ''}`}
            onClick={() => setViewMode('list')}
            title="Dense Table / List View"
          >
            ☰
          </button>
        </div>

        <div className="topbar-divider" />

        {(activePlaylist || activeTag) && filteredVideos.length > 0 && (
          <button
            className="topbar-btn"
            onClick={() => playAll(filteredVideos)}
            title={`Play all ${filteredVideos.length} videos, starting now`}
          >
            ▶ Play All
          </button>
        )}

        {filteredVideos.length > 0 && (
          <button
            className="topbar-btn"
            onClick={() => shufflePlay()}
            title={`Shuffle-play up to 20 random videos from the current ${filteredVideos.length.toLocaleString()}`}
          >
            🔀 Shuffle
          </button>
        )}

        <div className="topbar-divider" />

        {/* Advanced Search modal trigger */}
        <button
          className="topbar-btn"
          onClick={() => {
            const el = document.getElementById('advanced-search-trigger');
            if (el) el.click();
          }}
          title="Advanced Filter & Regex Search"
        >
          ⚙ Adv
        </button>

        {/* Bulk Selection mode */}
        <button
          className={`topbar-btn${isBulkMode ? ' active' : ''}`}
          onClick={toggleBulkMode}
          title="Toggle Multi-Select Mode"
        >
          {isBulkMode ? `✓ ${selectedVideos.size} selected` : '☑ Select'}
        </button>

        {isBulkMode && selectedVideos.size > 0 && (
          <>
            <button
              className="topbar-btn action-btn"
              onClick={() => openPicker({ mode: 'bulk' })}
            >
              🏷 Categorize ({selectedVideos.size})
            </button>
            <button
              className="topbar-btn action-btn danger"
              onClick={bulkDelete}
            >
              🗑 Delete ({selectedVideos.size})
            </button>
          </>
        )}

        {isBulkMode && (
          <div className="bulk-quick-actions">
            <button className="topbar-btn-mini" onClick={selectAll}>All</button>
            <button className="topbar-btn-mini" onClick={clearSelection}>None</button>
          </div>
        )}

        <div className="topbar-more" ref={moreMenuRef} style={{ position: 'relative' }}>
          <button className="topbar-btn" onClick={() => setShowMoreMenu((v) => !v)} title="More">
            ⋯
          </button>
          {showMoreMenu && (
            <div className="topbar-more-menu">
              <button
                className="topbar-more-item"
                onClick={() => { exportBackup(); setShowMoreMenu(false); }}
              >
                📤 Export Backup
              </button>
              <button
                className="topbar-more-item"
                onClick={() => { importInputRef.current?.click(); setShowMoreMenu(false); }}
              >
                📥 Import Backup
              </button>
            </div>
          )}
        </div>
        <input
          ref={importInputRef}
          type="file"
          accept="application/json"
          style={{ display: 'none' }}
          onChange={handleImportFile}
        />

        <div className="topbar-divider" />

        {/* Stats Counter */}
        <div className="video-count" title="Filtered / Total Videos">
          <span className="count-active">{filteredCount.toLocaleString()}</span>
          <span className="count-sep">/</span>
          <span className="count-total">{totalCount.toLocaleString()}</span>
        </div>
      </div>
    </header>
  );
}

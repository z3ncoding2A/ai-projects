import { useRef, useCallback } from 'react';
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

  const searchRef = useRef(null);
  const debounceRef = useRef(null);

  const handleSearch = useCallback((e) => {
    const val = e.target.value;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearchQuery(val), 150);
  }, [setSearchQuery]);

  const handleClearSearch = useCallback(() => {
    if (searchRef.current) {
      searchRef.current.value = '';
      searchRef.current.focus();
    }
    setSearchQuery('');
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
          defaultValue={searchQuery}
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

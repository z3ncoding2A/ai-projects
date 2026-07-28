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

  const searchRef = useRef(null);
  const debounceRef = useRef(null);

  const handleSearch = useCallback((e) => {
    const val = e.target.value;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setSearchQuery(val), 200);
  }, [setSearchQuery]);

  return (
    <header className="topbar">
      {/* Search */}
      <div className="search-wrapper">
        <span className="search-icon">🔍</span>
        <input
          ref={searchRef}
          className="search-input"
          type="text"
          placeholder="Search videos..."
          defaultValue={searchQuery}
          onChange={handleSearch}
          autoComplete="off"
        />
        <span className="search-shortcut">/</span>
      </div>

      {/* Sort */}
      <div className="topbar-controls">
        <select
          className="topbar-select"
          value={sortMode}
          onChange={(e) => setSortMode(e.target.value)}
        >
          <option value="newest">Recently Scraped</option>
          <option value="title-az">Title A-Z</option>
          <option value="views-desc">Most Viewed</option>
          <option value="duration-desc">Longest</option>
        </select>

        {/* View toggle */}
        <button
          className={`topbar-btn${viewMode === 'grid' ? ' active' : ''}`}
          onClick={() => setViewMode('grid')}
          title="Grid view"
        >
          ▦
        </button>
        <button
          className={`topbar-btn${viewMode === 'list' ? ' active' : ''}`}
          onClick={() => setViewMode('list')}
          title="List view"
        >
          ☰
        </button>

        <div className="topbar-divider" />

        <button
          className="topbar-btn"
          onClick={() => {
            const el = document.getElementById('advanced-search-trigger');
            if (el) el.click();
          }}
          title="Advanced Search"
        >
          ⚙ Adv
        </button>

        {/* Bulk mode */}
        <button
          className={`topbar-btn${isBulkMode ? ' active' : ''}`}
          onClick={toggleBulkMode}
        >
          {isBulkMode ? `✓ ${selectedVideos.size} selected` : '☑ Select'}
        </button>

        {isBulkMode && selectedVideos.size > 0 && (
          <>
            <button className="topbar-btn" onClick={() => openPicker({ mode: 'bulk' })}>
              🏷 Bulk Categorize
            </button>
            <button className="topbar-btn" onClick={bulkDelete} style={{ color: '#e74c3c' }}>
              🗑 Delete
            </button>
          </>
        )}

        {isBulkMode && (
          <>
            <button className="topbar-btn" onClick={selectAll}>All</button>
            <button className="topbar-btn" onClick={clearSelection}>None</button>
          </>
        )}

        <div className="topbar-divider" />

        {/* Count */}
        <div className="video-count">
          <b>{filteredCount}</b> / {totalCount}
        </div>
      </div>
    </header>
  );
}

import { useMemo } from 'react';
import useVideoStore from '../../stores/useVideoStore';

export default function FilterBar() {
  const durationFilter = useVideoStore((s) => s.durationFilter);
  const setDurationFilter = useVideoStore((s) => s.setDurationFilter);
  const watchFilter = useVideoStore((s) => s.watchFilter);
  const setWatchFilter = useVideoStore((s) => s.setWatchFilter);
  const activeTag = useVideoStore((s) => s.activeTag);
  const setActiveTag = useVideoStore((s) => s.setActiveTag);
  const activePlaylist = useVideoStore((s) => s.activePlaylist);
  const setActivePlaylist = useVideoStore((s) => s.setActivePlaylist);
  const searchQuery = useVideoStore((s) => s.searchQuery);
  const clearAllFilters = useVideoStore((s) => s.clearAllFilters);
  const categoryTree = useVideoStore((s) => s.categoryTree);
  const activeTab = useVideoStore((s) => s.activeTab);
  const setTab = useVideoStore((s) => s.setTab);
  const getCategoryCounts = useVideoStore((s) => s.getCategoryCounts);
  const categories = useVideoStore((s) => s.categories);
  const blacklist = useVideoStore((s) => s.blacklist);

  const counts = useMemo(
    () => getCategoryCounts(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [categoryTree, categories, blacklist, getCategoryCounts]
  );

  const hasActiveFilters =
    durationFilter !== 'all' ||
    watchFilter !== 'all' ||
    Boolean(activeTag) ||
    Boolean(activePlaylist) ||
    Boolean(searchQuery);

  return (
    <div className="filter-bar">
      {/* Quick Category Chips Bar */}
      <div className="filter-chips-row">
        <div className="filter-group-label">Category:</div>
        <div className="filter-chips-scroll">
          <button
            className={`filter-chip${activeTab === 'all' ? ' active' : ''}`}
            onClick={() => setTab('all')}
          >
            All <span className="chip-count">{counts.all || 0}</span>
          </button>
          <button
            className={`filter-chip${activeTab === 'none' ? ' active' : ''}`}
            onClick={() => setTab('none')}
          >
            Uncategorized <span className="chip-count">{counts.none || 0}</span>
          </button>
          {categoryTree.map((cat) => (
            <button
              key={cat.id}
              className={`filter-chip${activeTab === cat.id ? ' active' : ''}`}
              onClick={() => setTab(cat.id)}
              style={activeTab === cat.id && cat.color ? { borderColor: cat.color, color: '#fff' } : {}}
            >
              {cat.icon && <span className="chip-icon">{cat.icon}</span>}
              {cat.name}
              <span className="chip-count">{counts[cat.id] || 0}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Facet Controls: Duration & Watch Status */}
      <div className="filter-facets-row">
        {/* Duration */}
        <div className="facet-group">
          <span className="facet-label">Duration:</span>
          <div className="facet-pills">
            <button
              className={`facet-pill${durationFilter === 'all' ? ' active' : ''}`}
              onClick={() => setDurationFilter('all')}
            >
              All
            </button>
            <button
              className={`facet-pill${durationFilter === 'under5' ? ' active' : ''}`}
              onClick={() => setDurationFilter('under5')}
            >
              &lt; 5m
            </button>
            <button
              className={`facet-pill${durationFilter === '5to15' ? ' active' : ''}`}
              onClick={() => setDurationFilter('5to15')}
            >
              5–15m
            </button>
            <button
              className={`facet-pill${durationFilter === '15to30' ? ' active' : ''}`}
              onClick={() => setDurationFilter('15to30')}
            >
              15–30m
            </button>
            <button
              className={`facet-pill${durationFilter === 'over30' ? ' active' : ''}`}
              onClick={() => setDurationFilter('over30')}
            >
              30m+
            </button>
          </div>
        </div>

        {/* Watch Status */}
        <div className="facet-group">
          <span className="facet-label">Status:</span>
          <div className="facet-pills">
            <button
              className={`facet-pill${watchFilter === 'all' ? ' active' : ''}`}
              onClick={() => setWatchFilter('all')}
            >
              All
            </button>
            <button
              className={`facet-pill${watchFilter === 'unwatched' ? ' active' : ''}`}
              onClick={() => setWatchFilter('unwatched')}
            >
              Unwatched
            </button>
            <button
              className={`facet-pill${watchFilter === 'watched' ? ' active' : ''}`}
              onClick={() => setWatchFilter('watched')}
            >
              Watched
            </button>
          </div>
        </div>

        {/* Active Tag / Playlist indicators */}
        {activeTag && (
          <div className="facet-active-badge">
            <span>Tag: #{activeTag}</span>
            <button onClick={() => setActiveTag(null)} title="Clear tag filter">✕</button>
          </div>
        )}

        {activePlaylist && (
          <div className="facet-active-badge">
            <span>Playlist: {activePlaylist}</span>
            <button onClick={() => setActivePlaylist(null)} title="Clear playlist filter">✕</button>
          </div>
        )}

        {/* Clear All Filters */}
        {hasActiveFilters && (
          <button className="clear-filters-btn" onClick={clearAllFilters} title="Reset all active filters">
            Reset Filters ↺
          </button>
        )}
      </div>
    </div>
  );
}

import { useMemo } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import { CATEGORY_COLORS } from '../../utils/formatters';

const NAV_ITEMS = [
  { key: 'related', icon: '🔗', label: 'Related',      color: CATEGORY_COLORS.related },
  { key: 'recommended', icon: '⭐', label: 'Recommended', color: CATEGORY_COLORS.recommended },
  { key: 'none',    icon: '📚', label: 'Main Collection' },
  { key: 'public',  icon: '🌍', label: 'Public',       color: CATEGORY_COLORS.public },
  { key: 'pending', icon: '⏳', label: 'Pending',      color: CATEGORY_COLORS.pending },
  { key: 'least',   icon: '👎', label: 'Least Liked',  color: CATEGORY_COLORS.least },
  { key: 'average', icon: '👍', label: 'Average',      color: CATEGORY_COLORS.average },
  { key: 'most',    icon: '🔥', label: 'Most Liked',   color: CATEGORY_COLORS.most },
  { key: 'explode', icon: '💥', label: 'EXPLODE!!!',   color: CATEGORY_COLORS.explode },
];

export default function Sidebar() {
  const activeTab = useVideoStore((s) => s.activeTab);
  const setTab = useVideoStore((s) => s.setTab);
  const collapsed = useVideoStore((s) => s.isSidebarCollapsed);
  const toggleSidebar = useVideoStore((s) => s.toggleSidebar);
  const playlists = useVideoStore((s) => s.playlists);
  const getCategoryCounts = useVideoStore((s) => s.getCategoryCounts);
  const fsSyncStatus = useVideoStore((s) => s.fsSyncStatus);
  const fsSyncMessage = useVideoStore((s) => s.fsSyncMessage);
  const connectFolder = useVideoStore((s) => s.connectFolder);
  const activePlaylist = useVideoStore((s) => s.activePlaylist);
  const setActivePlaylist = useVideoStore((s) => s.setActivePlaylist);
  const activeTagFilter = useVideoStore((s) => s.activeTagFilter);
  const setActiveTagFilter = useVideoStore((s) => s.setActiveTagFilter);
  const getTagCounts = useVideoStore((s) => s.getTagCounts);

  // getCategoryCounts / getTagCounts read live state via get() when called, but
  // they're stable Zustand fn references — so memoizing on the fn alone runs
  // them exactly once (before videos finish loading → all zeros) and never
  // again. Subscribe to the underlying data and key the memos off it so the
  // counts recompute whenever videos / categories / blacklist / tags change.
  const videos = useVideoStore((s) => s.videos);
  const categories = useVideoStore((s) => s.categories);
  const blacklist = useVideoStore((s) => s.blacklist);
  const tags = useVideoStore((s) => s.tags);

  const counts = useMemo(() => getCategoryCounts(), [getCategoryCounts, videos, categories, blacklist]);
  const tagCounts = useMemo(() => getTagCounts(), [getTagCounts, tags, blacklist]);
  const sortedTags = useMemo(
    () => Object.entries(tagCounts).sort((a, b) => b[1] - a[1]),
    [tagCounts]
  );

  const syncLabel = {
    unsupported: 'Folder sync unsupported',
    disconnected: 'Not connected',
    'needs-reauth': 'Click to re-authorize',
    connected: fsSyncMessage || 'Connected',
    saving: 'Saving...',
    error: fsSyncMessage || 'Sync error',
  }[fsSyncStatus];

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      {/* Header */}
      <div className="sidebar-header">
        {!collapsed && (
          <div className="sidebar-brand">
            z3ncoding <span>Library</span>
          </div>
        )}
        <button
          className="sidebar-collapse-btn"
          onClick={toggleSidebar}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={collapsed ? { margin: '0 auto' } : { marginLeft: 'auto' }}
        >
          {collapsed ? '▶' : '◀'}
        </button>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {!collapsed && <div className="sidebar-section-title">Categories</div>}

        {NAV_ITEMS.map((item) => (
          <div
            key={item.key}
            className={`sidebar-item${!activePlaylist && !activeTagFilter && activeTab === item.key ? ' active' : ''}`}
            onClick={() => setTab(item.key)}
            title={collapsed ? item.label : undefined}
          >
            {item.color ? (
              <div className="sidebar-item-dot" style={{ background: item.color }} />
            ) : (
              <span className="sidebar-item-icon">{item.icon}</span>
            )}
            {!collapsed && (
              <>
                <span className="sidebar-item-label">{item.label}</span>
                <span className="sidebar-item-count">{counts[item.key] || 0}</span>
              </>
            )}
          </div>
        ))}

        {/* Playlists section */}
        {Object.keys(playlists).length > 0 && !collapsed && (
          <>
            <div className="sidebar-section-title" style={{ marginTop: 8 }}>Playlists</div>
            {Object.entries(playlists).map(([name, items]) => (
              <div
                key={name}
                className={`sidebar-item${activePlaylist === name ? ' active' : ''}`}
                onClick={() => setActivePlaylist(name)}
                title={`${items.length} videos — click to browse, click again to exit`}
              >
                <span className="sidebar-item-icon">🎵</span>
                <span className="sidebar-item-label">{name}</span>
                <span className="sidebar-item-count">{items.length}</span>
              </div>
            ))}
          </>
        )}

        {/* Tags section */}
        {sortedTags.length > 0 && !collapsed && (
          <>
            <div className="sidebar-section-title" style={{ marginTop: 8 }}>Tags</div>
            {sortedTags.map(([tag, count]) => (
              <div
                key={tag}
                className={`sidebar-item${activeTagFilter === tag ? ' active' : ''}`}
                onClick={() => setActiveTagFilter(tag)}
                title="Click to browse, click again to exit"
              >
                <span className="sidebar-item-icon">#</span>
                <span className="sidebar-item-label">{tag}</span>
                <span className="sidebar-item-count">{count}</span>
              </div>
            ))}
          </>
        )}
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="sidebar-footer">
          <div
            className="sidebar-item"
            onClick={() => {
              const el = document.getElementById('stats-trigger');
              if (el) el.click();
            }}
          >
            <span className="sidebar-item-icon">📊</span>
            <span className="sidebar-item-label">Stats</span>
          </div>

          <div
            className="sidebar-item"
            onClick={() => {
              const el = document.getElementById('blacklist-trigger');
              if (el) el.click();
            }}
          >
            <span className="sidebar-item-icon">🚫</span>
            <span className="sidebar-item-label">Blacklist</span>
          </div>

          <div
            className="sidebar-item"
            onClick={() => {
              const el = document.getElementById('duplicates-trigger');
              if (el) el.click();
            }}
          >
            <span className="sidebar-item-icon">🧬</span>
            <span className="sidebar-item-label">Find Duplicates</span>
          </div>

          {fsSyncStatus !== 'unsupported' && (
            <div
              className={`sidebar-item sync-chip sync-${fsSyncStatus}`}
              onClick={connectFolder}
              title={syncLabel}
            >
              <span className="sidebar-item-icon">
                {fsSyncStatus === 'connected' ? '✓' : fsSyncStatus === 'saving' ? '💾' : '📁'}
              </span>
              <span className="sidebar-item-label">
                {fsSyncStatus === 'connected' || fsSyncStatus === 'saving' ? syncLabel : 'Connect Folder'}
              </span>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}

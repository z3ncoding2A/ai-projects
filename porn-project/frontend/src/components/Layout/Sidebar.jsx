import { useMemo } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import { CATEGORY_COLORS, CATEGORY_LABELS } from '../../utils/formatters';

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

  const counts = useMemo(() => getCategoryCounts(), [getCategoryCounts]);

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
            className={`sidebar-item${activeTab === item.key ? ' active' : ''}`}
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
                className="sidebar-item"
                onClick={() => {/* TODO: playlist view */}}
                title={`${items.length} videos`}
              >
                <span className="sidebar-item-icon">🎵</span>
                <span className="sidebar-item-label">{name}</span>
                <span className="sidebar-item-count">{items.length}</span>
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
        </div>
      )}
    </aside>
  );
}

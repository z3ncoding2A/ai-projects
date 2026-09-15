import { useMemo, useState } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import CategoryTreeList from '../Features/CategoryTreeList';
import CategoryFormModal from '../Features/CategoryFormModal';
import CategoryDeleteConfirm from '../Features/CategoryDeleteConfirm';

export default function Sidebar() {
  const activeTab = useVideoStore((s) => s.activeTab);
  const setTab = useVideoStore((s) => s.setTab);
  const collapsed = useVideoStore((s) => s.isSidebarCollapsed);
  const toggleSidebar = useVideoStore((s) => s.toggleSidebar);
  const playlists = useVideoStore((s) => s.playlists);
  const activePlaylist = useVideoStore((s) => s.activePlaylist);
  const setActivePlaylist = useVideoStore((s) => s.setActivePlaylist);
  const tags = useVideoStore((s) => s.tags);
  const activeTag = useVideoStore((s) => s.activeTag);
  const setActiveTag = useVideoStore((s) => s.setActiveTag);
  const getCategoryCounts = useVideoStore((s) => s.getCategoryCounts);
  const categoryTree = useVideoStore((s) => s.categoryTree);
  const categories = useVideoStore((s) => s.categories);
  const blacklist = useVideoStore((s) => s.blacklist);
  const moveCategory = useVideoStore((s) => s.moveCategory);

  const counts = useMemo(
    () => getCategoryCounts(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [categoryTree, categories, blacklist, getCategoryCounts]
  );

  // Aggregate tags with frequency counts
  const tagCounts = useMemo(() => {
    const map = {};
    for (const tagList of Object.values(tags)) {
      if (Array.isArray(tagList)) {
        for (const t of tagList) {
          map[t] = (map[t] || 0) + 1;
        }
      }
    }
    return Object.entries(map).sort((a, b) => b[1] - a[1]);
  }, [tags]);

  const [collapsedIds, setCollapsedIds] = useState(() => new Set());
  const [showTagsSection, setShowTagsSection] = useState(true);
  const [formModal, setFormModal] = useState(null);   // { mode: 'create'|'rename', parentId?, node? }
  const [deleteTarget, setDeleteTarget] = useState(null); // node

  const toggleExpand = (id) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const renderActions = (node) => (
    <>
      <button
        className="cat-tree-action-btn"
        title="Add subcategory"
        onClick={(e) => { e.stopPropagation(); setFormModal({ mode: 'create', parentId: node.id }); }}
      >
        +
      </button>
      <button
        className="cat-tree-action-btn"
        title="Rename"
        onClick={(e) => { e.stopPropagation(); setFormModal({ mode: 'rename', node }); }}
      >
        ✎
      </button>
      <button
        className="cat-tree-action-btn danger"
        title="Delete"
        onClick={(e) => { e.stopPropagation(); setDeleteTarget(node); }}
      >
        🗑
      </button>
    </>
  );

  return (
    <aside className={`sidebar${collapsed ? ' collapsed' : ''}`}>
      {/* Header */}
      <div className="sidebar-header">
        {!collapsed && (
          <div className="sidebar-brand">
            <span className="brand-logo">⚡</span>
            <div className="brand-text">
              z3ncoding <span>Workstation</span>
            </div>
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
        {/* Core Library Views */}
        {!collapsed && <div className="sidebar-section-title">Library</div>}

        {/* All Videos */}
        <div
          className={`sidebar-item${activeTab === 'all' && !activePlaylist && !activeTag ? ' active' : ''}`}
          onClick={() => setTab('all')}
          title={collapsed ? 'All Videos' : undefined}
        >
          <span className="sidebar-item-icon">🎬</span>
          {!collapsed && (
            <>
              <span className="sidebar-item-label">All Videos</span>
              <span className="sidebar-item-count">{counts.all || 0}</span>
            </>
          )}
        </div>

        {/* Uncategorized */}
        <div
          className={`sidebar-item${activeTab === 'none' && !activePlaylist && !activeTag ? ' active' : ''}`}
          onClick={() => setTab('none')}
          title={collapsed ? 'Uncategorized' : undefined}
        >
          <span className="sidebar-item-icon">📚</span>
          {!collapsed && (
            <>
              <span className="sidebar-item-label">Uncategorized</span>
              <span className="sidebar-item-count">{counts.none || 0}</span>
            </>
          )}
        </div>

        {/* Recently Watched */}
        <div
          className={`sidebar-item${activeTab === 'recent' && !activePlaylist && !activeTag ? ' active' : ''}`}
          onClick={() => setTab('recent')}
          title={collapsed ? 'Recently Watched' : undefined}
        >
          <span className="sidebar-item-icon">⏱</span>
          {!collapsed && (
            <>
              <span className="sidebar-item-label">Recently Watched</span>
              <span className="sidebar-item-count">{counts.recent || 0}</span>
            </>
          )}
        </div>

        {/* Blacklist / Trash */}
        <div
          className={`sidebar-item${activeTab === 'blacklist' && !activePlaylist && !activeTag ? ' active' : ''}`}
          onClick={() => setTab('blacklist')}
          title={collapsed ? 'Blacklisted' : undefined}
        >
          <span className="sidebar-item-icon">🚫</span>
          {!collapsed && (
            <>
              <span className="sidebar-item-label">Blacklist / Trash</span>
              <span className="sidebar-item-count">{counts.blacklist || 0}</span>
            </>
          )}
        </div>

        {/* Categories Section */}
        {!collapsed && (
          <>
            <div className="sidebar-section-title" style={{ display: 'flex', alignItems: 'center', marginTop: 14 }}>
              <span>Categories</span>
              <button
                className="cat-tree-action-btn"
                style={{ marginLeft: 'auto' }}
                title="New top-level category"
                onClick={() => setFormModal({ mode: 'create', parentId: null })}
              >
                +
              </button>
            </div>

            <CategoryTreeList
              tree={categoryTree}
              counts={counts}
              activeId={activeTab}
              onSelect={(node) => setTab(node.id)}
              collapsedIds={collapsedIds}
              onToggleExpand={toggleExpand}
              renderActions={renderActions}
              draggable
              onReparent={moveCategory}
            />
          </>
        )}

        {/* Playlists section */}
        {Object.keys(playlists).length > 0 && !collapsed && (
          <>
            <div className="sidebar-section-title" style={{ marginTop: 14 }}>Playlists</div>
            {Object.entries(playlists).map(([name, items]) => (
              <div
                key={name}
                className={`sidebar-item${activePlaylist === name ? ' active' : ''}`}
                onClick={() => setActivePlaylist(name)}
                title={`${items.length} videos`}
              >
                <span className="sidebar-item-icon">🎵</span>
                <span className="sidebar-item-label">{name}</span>
                <span className="sidebar-item-count">{items.length}</span>
              </div>
            ))}
          </>
        )}

        {/* Tags section */}
        {tagCounts.length > 0 && !collapsed && (
          <>
            <div
              className="sidebar-section-title clickable"
              style={{ display: 'flex', alignItems: 'center', marginTop: 14, cursor: 'pointer' }}
              onClick={() => setShowTagsSection(!showTagsSection)}
            >
              <span>Tags ({tagCounts.length})</span>
              <span style={{ marginLeft: 'auto', fontSize: '0.7rem' }}>
                {showTagsSection ? '▾' : '▸'}
              </span>
            </div>
            {showTagsSection && (
              <div className="sidebar-tags-cloud">
                {tagCounts.slice(0, 15).map(([tag, count]) => (
                  <button
                    key={tag}
                    className={`sidebar-tag-chip${activeTag === tag ? ' active' : ''}`}
                    onClick={() => setActiveTag(tag)}
                  >
                    #{tag} <span className="tag-count">{count}</span>
                  </button>
                ))}
              </div>
            )}
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
            <span className="sidebar-item-label">Analytics & Stats</span>
          </div>
        </div>
      )}

      {formModal && (
        <CategoryFormModal
          mode={formModal.mode}
          parentId={formModal.parentId ?? null}
          node={formModal.node}
          onClose={() => setFormModal(null)}
        />
      )}
      {deleteTarget && (
        <CategoryDeleteConfirm node={deleteTarget} onClose={() => setDeleteTarget(null)} />
      )}
    </aside>
  );
}

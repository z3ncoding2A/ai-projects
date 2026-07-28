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
  const getCategoryCounts = useVideoStore((s) => s.getCategoryCounts);
  const categoryTree = useVideoStore((s) => s.categoryTree);
  const categories = useVideoStore((s) => s.categories);
  const blacklist = useVideoStore((s) => s.blacklist);
  const moveCategory = useVideoStore((s) => s.moveCategory);

  const counts = useMemo(() => getCategoryCounts(), [categoryTree, categories, blacklist]);

  const [collapsedIds, setCollapsedIds] = useState(() => new Set());
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
        {!collapsed && (
          <div className="sidebar-section-title" style={{ display: 'flex', alignItems: 'center' }}>
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
        )}

        {/* Main Collection ("Uncategorized") — pinned above the tree */}
        <div
          className={`sidebar-item${activeTab === 'none' ? ' active' : ''}`}
          onClick={() => setTab('none')}
          title={collapsed ? 'Main Collection' : undefined}
        >
          <span className="sidebar-item-icon">📚</span>
          {!collapsed && (
            <>
              <span className="sidebar-item-label">Main Collection</span>
              <span className="sidebar-item-count">{counts.none || 0}</span>
            </>
          )}
        </div>

        {!collapsed && (
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
        )}

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

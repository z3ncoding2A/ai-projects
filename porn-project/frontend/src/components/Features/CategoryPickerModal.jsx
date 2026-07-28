import { useState } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import CategoryTreeList from './CategoryTreeList';

/**
 * Single instance mounted in App.jsx, driven by store.pickerTarget so both
 * VideoCard (single-assign) and TopBar (bulk-assign) can open it without
 * mounting a tree UI per-card (VideoCard is memo'd + virtualized).
 */
export default function CategoryPickerModal() {
  const pickerTarget = useVideoStore((s) => s.pickerTarget);
  const closePicker = useVideoStore((s) => s.closePicker);
  const categoryTree = useVideoStore((s) => s.categoryTree);
  const getCategoryCounts = useVideoStore((s) => s.getCategoryCounts);
  const setCategory = useVideoStore((s) => s.setCategory);
  const bulkSetCategory = useVideoStore((s) => s.bulkSetCategory);
  const selectedCount = useVideoStore((s) => s.selectedVideos.size);

  const [query, setQuery] = useState('');
  const [collapsedIds, setCollapsedIds] = useState(() => new Set());

  if (!pickerTarget) return null;

  const counts = getCategoryCounts();
  const isBulk = pickerTarget.mode === 'bulk';

  const handleSelect = (id) => {
    if (isBulk) bulkSetCategory(id);
    else setCategory(pickerTarget.viewkey, id);
    closePicker();
  };

  const toggleExpand = (id) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="modal-overlay" onClick={closePicker}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420, maxHeight: '70vh' }}>
        <h2>🏷 {isBulk ? `Categorize ${selectedCount} video${selectedCount === 1 ? '' : 's'}` : 'Categorize'}</h2>

        <input
          type="text"
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search categories..."
          style={{ width: '100%', padding: 8, borderRadius: 6, background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'white', marginBottom: 12 }}
        />

        <div
          className="sidebar-item cat-tree-row"
          style={{ paddingLeft: 12, marginBottom: 4 }}
          onClick={() => handleSelect('none')}
        >
          <span className="cat-tree-caret cat-tree-caret-spacer" />
          <div className="sidebar-item-dot" style={{ background: 'var(--text-muted)' }} />
          <span className="sidebar-item-label">None / Uncategorized</span>
          <span className="sidebar-item-count">{counts.none || 0}</span>
        </div>

        <div style={{ maxHeight: '40vh', overflowY: 'auto' }}>
          <CategoryTreeList
            tree={categoryTree}
            counts={counts}
            onSelect={(node) => handleSelect(node.id)}
            collapsedIds={collapsedIds}
            onToggleExpand={toggleExpand}
            filterQuery={query}
          />
        </div>

        <div className="modal-footer">
          <button className="modal-btn" onClick={closePicker}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

import { useMemo, useState } from 'react';
import { buildCategoryIndex } from '../../utils/formatters';

/**
 * Recursive, presentational category tree renderer shared by the Sidebar nav
 * and the CategoryPickerModal. Callers own selection/expansion state so the
 * same component can serve a "navigate & filter" UI and a "pick one" UI.
 *
 * Props:
 *  - tree: flat node[] ({ id, name, color, icon, parentId, sortOrder })
 *  - counts: { [id]: number } — aggregated video counts (optional)
 *  - activeId: currently selected/highlighted id (optional)
 *  - onSelect(node): row click handler
 *  - collapsedIds: Set<id> (controlled by caller) — nodes NOT in this set
 *    render expanded by default, so newly-created categories (which the
 *    caller never explicitly collapsed) show their children immediately.
 *  - onToggleExpand(id): caret click handler
 *  - renderActions(node): optional JSX for per-row hover icons (add/rename/delete)
 *  - draggable: enable native HTML5 drag-to-reparent
 *  - onReparent(id, newParentId): called on a valid drop
 *  - filterQuery: optional search string — hides non-matching branches, auto-expands matches
 */
export default function CategoryTreeList({
  tree,
  counts = {},
  activeId,
  onSelect,
  collapsedIds,
  onToggleExpand,
  renderActions,
  draggable = false,
  onReparent,
  filterQuery = '',
}) {
  const { childrenOf } = useMemo(() => buildCategoryIndex(tree), [tree]);
  const [dragOverId, setDragOverId] = useState(null);

  const query = filterQuery.trim().toLowerCase();
  const visibility = useMemo(() => {
    if (!query) return null;
    const matches = new Set(tree.filter((n) => n.name.toLowerCase().includes(query)).map((n) => n.id));
    const byId = new Map(tree.map((n) => [n.id, n]));
    const visible = new Set(matches);
    // include ancestors of every match so the branch stays connected
    for (const id of matches) {
      let cur = byId.get(id);
      while (cur && cur.parentId) {
        visible.add(cur.parentId);
        cur = byId.get(cur.parentId);
      }
    }
    // include descendants of every match too
    const stack = [...matches];
    while (stack.length) {
      const cur = stack.pop();
      for (const child of childrenOf.get(cur) || []) {
        if (!visible.has(child.id)) {
          visible.add(child.id);
          stack.push(child.id);
        }
      }
    }
    return visible;
  }, [query, tree, childrenOf]);

  const isExpanded = (id) => (query ? true : !collapsedIds.has(id));

  const renderNode = (node, depth) => {
    if (visibility && !visibility.has(node.id)) return null;
    const children = childrenOf.get(node.id) || [];
    const hasChildren = children.length > 0;
    const expanded = isExpanded(node.id);

    return (
      <div key={node.id} className="cat-tree-node">
        <div
          className={`sidebar-item cat-tree-row${activeId === node.id ? ' active' : ''}${dragOverId === node.id ? ' drop-target' : ''}`}
          style={{ paddingLeft: 12 + depth * 16 }}
          onClick={() => onSelect?.(node)}
          draggable={draggable}
          onDragStart={(e) => {
            e.stopPropagation();
            e.dataTransfer.setData('text/category-id', node.id);
          }}
          onDragOver={(e) => {
            if (!draggable) return;
            e.preventDefault();
            e.stopPropagation();
            setDragOverId(node.id);
          }}
          onDragLeave={() => setDragOverId((cur) => (cur === node.id ? null : cur))}
          onDrop={(e) => {
            if (!draggable) return;
            e.preventDefault();
            e.stopPropagation();
            setDragOverId(null);
            const draggedId = e.dataTransfer.getData('text/category-id');
            if (draggedId && draggedId !== node.id) onReparent?.(draggedId, node.id);
          }}
        >
          {hasChildren ? (
            <span
              className="cat-tree-caret"
              onClick={(e) => {
                e.stopPropagation();
                onToggleExpand?.(node.id);
              }}
            >
              {expanded ? '▾' : '▸'}
            </span>
          ) : (
            <span className="cat-tree-caret cat-tree-caret-spacer" />
          )}
          <div className="sidebar-item-dot" style={{ background: node.color }} />
          {node.icon && <span className="sidebar-item-icon cat-tree-icon">{node.icon}</span>}
          <span className="sidebar-item-label">{node.name}</span>
          <span className="sidebar-item-count">{counts[node.id] || 0}</span>
          {renderActions && <div className="cat-tree-actions">{renderActions(node)}</div>}
        </div>
        {hasChildren && expanded && (
          <div className="cat-tree-children">
            {children.map((child) => renderNode(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const roots = (childrenOf.get(null) || []);

  return (
    <div
      className="cat-tree-root"
      onDragOver={(e) => { if (draggable) e.preventDefault(); }}
      onDrop={(e) => {
        if (!draggable) return;
        e.preventDefault();
        const draggedId = e.dataTransfer.getData('text/category-id');
        if (draggedId) onReparent?.(draggedId, null); // drop on empty space → top-level
      }}
    >
      {roots.map((node) => renderNode(node, 0))}
    </div>
  );
}

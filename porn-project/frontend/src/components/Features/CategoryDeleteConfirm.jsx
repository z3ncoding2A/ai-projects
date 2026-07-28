import { useMemo } from 'react';
import useVideoStore from '../../stores/useVideoStore';

/**
 * Confirms a category deletion, showing exactly what will move before it happens.
 * Delete is a "splice": direct videos + direct child categories are promoted to
 * the deleted node's parent (or unassigned/top-level if it had none) — see
 * deleteCategory in useVideoStore.
 */
export default function CategoryDeleteConfirm({ node, onClose }) {
  const categories = useVideoStore((s) => s.categories);
  const categoryTree = useVideoStore((s) => s.categoryTree);
  const deleteCategory = useVideoStore((s) => s.deleteCategory);

  const { videoCount, childCount, parentName } = useMemo(() => {
    const videoCount = Object.values(categories).filter((c) => c === node.id).length;
    const children = categoryTree.filter((n) => n.parentId === node.id);
    const parent = categoryTree.find((n) => n.id === node.parentId);
    return { videoCount, childCount: children.length, parentName: parent?.name || 'Uncategorized' };
  }, [categories, categoryTree, node]);

  const handleConfirm = () => {
    deleteCategory(node.id);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420 }}>
        <h2>🗑 Delete "{node.name}"?</h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          {videoCount === 0 && childCount === 0 ? (
            <>This category is empty and can be deleted safely.</>
          ) : (
            <>
              This will move <b>{videoCount}</b> video{videoCount === 1 ? '' : 's'} and{' '}
              <b>{childCount}</b> subcategor{childCount === 1 ? 'y' : 'ies'} to{' '}
              <b>"{parentName}"</b>. Nothing is deleted except the category itself.
            </>
          )}
        </p>
        <div className="modal-footer">
          <button className="modal-btn" onClick={onClose}>Cancel</button>
          <button className="modal-btn danger" onClick={handleConfirm}>Delete Category</button>
        </div>
      </div>
    </div>
  );
}

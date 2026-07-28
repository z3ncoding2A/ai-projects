import { useState } from 'react';
import useVideoStore from '../../stores/useVideoStore';

const RANDOM_COLORS = ['#e11d48', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899'];

/**
 * Create-or-rename modal for a single category node.
 * mode: 'create' — parentId is fixed (pre-filled from the "+" that opened it, null = top-level)
 * mode: 'rename' — node is the existing node being edited (name + color only)
 */
export default function CategoryFormModal({ mode, parentId = null, node, onClose }) {
  const createCategory = useVideoStore((s) => s.createCategory);
  const renameCategory = useVideoStore((s) => s.renameCategory);
  const setCategoryColor = useVideoStore((s) => s.setCategoryColor);

  const [name, setName] = useState(node?.name || '');
  const [color, setColor] = useState(node?.color || RANDOM_COLORS[Math.floor(Math.random() * RANDOM_COLORS.length)]);
  const [icon, setIcon] = useState(node?.icon || '');

  const isRename = mode === 'rename';

  const handleSubmit = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    if (isRename) {
      renameCategory(node.id, trimmed);
      setCategoryColor(node.id, color);
    } else {
      createCategory({ name: trimmed, color, icon: icon.trim() || null, parentId });
    }
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 380 }}>
        <h2>{isRename ? '✎ Rename Category' : parentId ? '+ New Subcategory' : '+ New Category'}</h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 20 }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
              Name
            </label>
            <input
              type="text"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSubmit(); }}
              placeholder="e.g. Amateur"
              style={{ width: '100%', padding: 8, borderRadius: 6, background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'white' }}
            />
          </div>

          <div style={{ display: 'flex', gap: 14, alignItems: 'flex-end' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                Color
              </label>
              <input
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                style={{ width: 48, height: 34, padding: 0, border: '1px solid var(--border)', borderRadius: 6, background: 'transparent', cursor: 'pointer' }}
              />
            </div>
            {!isRename && (
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 4 }}>
                  Icon (optional emoji)
                </label>
                <input
                  type="text"
                  value={icon}
                  onChange={(e) => setIcon(e.target.value.slice(0, 2))}
                  placeholder="🎬"
                  style={{ width: '100%', padding: 8, borderRadius: 6, background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'white' }}
                />
              </div>
            )}
          </div>

          {!isRename && parentId && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Creating as a subcategory.
            </div>
          )}
        </div>

        <div className="modal-footer">
          <button className="modal-btn" onClick={onClose}>Cancel</button>
          <button className="modal-btn primary" onClick={handleSubmit} disabled={!name.trim()}>
            {isRename ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
}

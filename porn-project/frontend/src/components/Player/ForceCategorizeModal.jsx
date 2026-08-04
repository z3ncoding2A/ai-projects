import { useEffect } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import { CATEGORY_LABELS, CATEGORY_COLORS } from '../../utils/formatters';

// The six real curation buckets. related/recommended are deliberately
// excluded — this modal only ever appears for a video whose effective
// category is 'none', which by construction can't include related/
// recommended videos (they always carry a baked-in category), so offering
// them here would be nonsensical.
const CURATION_CATEGORIES = ['public', 'pending', 'least', 'average', 'most', 'explode'];

/**
 * Blocks switching away from an uncategorized video until the user picks a
 * category for it. Deliberately has no close button and no backdrop-click
 * dismissal — the whole point is that it can't be skipped.
 */
export default function ForceCategorizeModal() {
  const video = useVideoStore((s) => s.videoAwaitingCategory);
  const resolveForcedCategory = useVideoStore((s) => s.resolveForcedCategory);
  const cancelForcedCategory = useVideoStore((s) => s.cancelForcedCategory);

  // Esc cancels the switch entirely (stays on the current video, applies no
  // category) — an escape hatch for when the wrong video was clicked.
  useEffect(() => {
    if (!video) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        cancelForcedCategory();
      }
    };
    // Capture phase so this fires before any other Esc handler (e.g. one that
    // might close the player) can act on the same keypress.
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [video, cancelForcedCategory]);

  if (!video) return null;

  return (
    <div className="modal-overlay" style={{ zIndex: 1000 }}>
      <div className="modal" style={{ maxWidth: 420 }}>
        <h2>🏷️ Categorize Before Continuing</h2>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
          Pick a category for this video before moving on — or press <b>Esc</b> to
          stay on this one.
        </p>

        <div style={{ display: 'flex', gap: 10, marginBottom: 20, alignItems: 'center' }}>
          <img
            src={video.thumbnail}
            alt=""
            style={{ width: 100, height: 56, objectFit: 'cover', borderRadius: 6, flexShrink: 0 }}
          />
          <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {video.title}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {CURATION_CATEGORIES.map((cat) => (
            <button
              key={cat}
              className="modal-btn"
              style={{
                borderColor: CATEGORY_COLORS[cat],
                color: CATEGORY_COLORS[cat],
                fontWeight: 600,
              }}
              onClick={() => resolveForcedCategory(cat)}
            >
              {CATEGORY_LABELS[cat]}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

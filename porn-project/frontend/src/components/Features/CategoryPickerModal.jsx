import { useState } from 'react';
import toast from 'react-hot-toast';
import useVideoStore from '../../stores/useVideoStore';
import CategoryTreeList from './CategoryTreeList';
import { suggestCategories } from '../../utils/api';

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
  const deleteVideo = useVideoStore((s) => s.deleteVideo);
  const playVideo = useVideoStore((s) => s.playVideo);
  const selectedVideos = useVideoStore((s) => s.selectedVideos);
  const selectedCount = selectedVideos.size;
  const videos = useVideoStore((s) => s.videos);

  const [query, setQuery] = useState('');
  const [collapsedIds, setCollapsedIds] = useState(() => new Set());
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState(null); // { categoryId, unanimous } | null

  if (!pickerTarget) return null;

  const counts = getCategoryCounts();
  const isBulk = pickerTarget.mode === 'bulk';
  const isAuto = pickerTarget.mode === 'auto';

  const resumePending = () => {
    if (isAuto && pickerTarget.pendingVideo) {
      playVideo(pickerTarget.pendingVideo, { force: true });
    }
  };

  const handleClose = () => {
    setSuggestion(null);
    closePicker();
  };

  const handleSelect = (id) => {
    if (isBulk) bulkSetCategory(id);
    else setCategory(pickerTarget.viewkey, id);
    setSuggestion(null);
    closePicker();
    resumePending();
  };

  const handleBlacklist = () => {
    deleteVideo(pickerTarget.viewkey);
    setSuggestion(null);
    closePicker();
    resumePending();
  };

  const handleSkip = () => {
    setSuggestion(null);
    closePicker();
    resumePending();
  };

  const autoVideo = isAuto ? videos.find((v) => v.viewkey === pickerTarget.viewkey) : null;

  const toggleExpand = (id) => {
    setCollapsedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // The videos Claude should categorize: the single/auto target, or every
  // selected video in bulk mode. Titles come from the already-loaded
  // `videos` list - no extra fetch needed.
  const targetVideos = isBulk
    ? videos.filter((v) => selectedVideos.has(v.viewkey))
    : videos.filter((v) => v.viewkey === pickerTarget.viewkey);

  const handleAskClaude = async () => {
    if (targetVideos.length === 0) return;
    setSuggesting(true);
    setSuggestion(null);
    try {
      const items = targetVideos.map((v) => ({ viewkey: v.viewkey, title: v.title }));
      const results = await suggestCategories(items);
      const ids = results.map((r) => r.category_id);
      const unanimous = ids.every((id) => id === ids[0]);
      if (unanimous) {
        setSuggestion({ categoryId: ids[0], unanimous: true });
      } else {
        // Disagreement across a bulk selection - don't claim a single answer.
        setSuggestion({ categoryId: null, unanimous: false });
        toast(`Claude split the suggestions across ${new Set(ids).size} categories - pick one below.`, { icon: '🤔' });
      }
    } catch (e) {
      toast.error(`Claude couldn't suggest a category: ${e.message}`);
    } finally {
      setSuggesting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={isAuto ? handleSkip : handleClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 420, maxHeight: '70vh' }}>
        <h2>
          🏷 {isBulk
            ? `Categorize ${selectedCount} video${selectedCount === 1 ? '' : 's'}`
            : isAuto
              ? 'Categorize before continuing'
              : 'Categorize'}
        </h2>
        {isAuto && autoVideo && (
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: -8, marginBottom: 12 }}>
            {autoVideo.title}
          </p>
        )}

        <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search categories..."
            style={{ flex: 1, padding: 8, borderRadius: 6, background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'white' }}
          />
          <button
            className="modal-btn"
            onClick={handleAskClaude}
            disabled={suggesting || targetVideos.length === 0}
            title="Suggest a category from the video title(s)"
            style={{ whiteSpace: 'nowrap' }}
          >
            {suggesting ? '✨ Thinking…' : '✨ Ask Claude'}
          </button>
        </div>

        {suggestion?.unanimous && (
          <div
            className="sidebar-item cat-tree-row"
            style={{
              marginBottom: 12,
              padding: '8px 12px',
              borderRadius: 6,
              background: 'var(--bg-surface)',
              border: '1px solid var(--accent, #7c3aed)',
              cursor: 'pointer',
            }}
            onClick={() => handleSelect(suggestion.categoryId)}
          >
            <span style={{ fontSize: '0.85rem' }}>
              ✨ Suggested: <strong>{categoryTree.find((c) => c.id === suggestion.categoryId)?.name || suggestion.categoryId}</strong>
              {' '}— click to apply
            </span>
          </div>
        )}

        {!isAuto && (
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
        )}

        <div style={{ maxHeight: '40vh', overflowY: 'auto' }}>
          <CategoryTreeList
            tree={categoryTree}
            counts={counts}
            activeId={suggestion?.categoryId}
            onSelect={(node) => handleSelect(node.id)}
            collapsedIds={collapsedIds}
            onToggleExpand={toggleExpand}
            filterQuery={query}
          />
        </div>

        <div className="modal-footer">
          {isAuto && (
            <button
              className="modal-btn"
              style={{ color: 'var(--danger, #e5484d)', marginRight: 'auto' }}
              onClick={handleBlacklist}
            >
              🗑 Blacklist / Remove
            </button>
          )}
          <button className="modal-btn" onClick={isAuto ? handleSkip : handleClose}>
            {isAuto ? 'Skip' : 'Cancel'}
          </button>
        </div>
      </div>
    </div>
  );
}

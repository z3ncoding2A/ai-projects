import { useState, useCallback } from 'react';
import toast from 'react-hot-toast';
import useVideoStore from '../../stores/useVideoStore';
import { findDuplicateGroups } from '../../utils/duplicateDetection';
import { formatDuration, formatViews } from '../../utils/formatters';

export default function DuplicatesModal({ onClose }) {
  const videos = useVideoStore((s) => s.videos);
  const blacklist = useVideoStore((s) => s.blacklist);
  const blacklistMany = useVideoStore((s) => s.blacklistMany);

  const [groups, setGroups] = useState(null); // null = not scanned yet
  const [scanning, setScanning] = useState(false);
  // viewkey -> bool, which candidates are checked for removal
  const [checked, setChecked] = useState({});

  const runScan = useCallback(() => {
    setScanning(true);
    // Let the loading state paint before the ~0.5s synchronous scan blocks the thread.
    setTimeout(() => {
      const blacklistSet = new Set(blacklist);
      const active = videos.filter((v) => !blacklistSet.has(v.viewkey));
      const found = findDuplicateGroups(active);

      // Default suggestion: keep the highest-viewed video in each group,
      // pre-check the rest for removal. Purely a starting point — nothing
      // is blacklisted until the user reviews and confirms.
      const defaultChecked = {};
      for (const group of found) {
        const sorted = [...group].sort((a, b) => (b.rawViews || 0) - (a.rawViews || 0));
        for (let i = 1; i < sorted.length; i++) defaultChecked[sorted[i].viewkey] = true;
      }

      setGroups(found);
      setChecked(defaultChecked);
      setScanning(false);
    }, 50);
  }, [videos, blacklist]);

  const toggleCheck = (viewkey) => {
    setChecked((prev) => ({ ...prev, [viewkey]: !prev[viewkey] }));
  };

  const checkedCount = Object.values(checked).filter(Boolean).length;

  const applyRemoval = () => {
    const toRemove = Object.entries(checked).filter(([, v]) => v).map(([vk]) => vk);
    if (toRemove.length === 0) return;
    blacklistMany(toRemove);
    toast.success(`Blacklisted ${toRemove.length} duplicate${toRemove.length === 1 ? '' : 's'}`);
    // Drop removed videos from the visible groups so the list reflects the change.
    setGroups((prev) => prev
      .map((g) => g.filter((v) => !toRemove.includes(v.viewkey)))
      .filter((g) => g.length >= 2));
    setChecked({});
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 560 }}>
        <h2>🧬 Find Duplicates</h2>

        {groups === null && (
          <div style={{ textAlign: 'center', padding: '24px 0' }}>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: 16 }}>
              Scans your active library for videos that are likely duplicates — same
              approximate duration and very similar titles — since videos get scraped from
              your profile, related, and recommended crawls and can end up in more than once.
              This is a heuristic: review before removing anything, especially numbered
              parts of a series, which can look similar by title alone.
            </p>
            <button className="modal-btn primary" onClick={runScan} disabled={scanning}>
              {scanning ? 'Scanning...' : `Scan ${videos.length.toLocaleString()} videos`}
            </button>
          </div>
        )}

        {groups !== null && groups.length === 0 && (
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '20px 0' }}>
            No likely duplicates found.
          </p>
        )}

        {groups !== null && groups.length > 0 && (
          <>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', marginBottom: 12 }}>
              {groups.length} group{groups.length === 1 ? '' : 's'} found. The highest-viewed
              video in each group is left unchecked (kept) by default — review before applying.
            </p>
            <div style={{ maxHeight: 380, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {groups.map((group, i) => (
                <div key={i} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 8 }}>
                  {group.map((v) => (
                    <label
                      key={v.viewkey}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 8, padding: '4px 4px',
                        fontSize: '0.78rem', cursor: 'pointer', color: 'var(--text-secondary)',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={!!checked[v.viewkey]}
                        onChange={() => toggleCheck(v.viewkey)}
                      />
                      <img src={v.thumbnail} alt="" style={{ width: 60, height: 34, objectFit: 'cover', borderRadius: 4, flexShrink: 0 }} />
                      <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={v.title}>
                        {v.title}
                      </span>
                      <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{formatDuration(v.rawDuration)}</span>
                      <span style={{ color: 'var(--text-muted)', flexShrink: 0, width: 70, textAlign: 'right' }}>{formatViews(v.rawViews)}</span>
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </>
        )}

        <div className="modal-footer" style={{ justifyContent: 'space-between', marginTop: 16 }}>
          <button className="modal-btn" onClick={onClose}>Close</button>
          {groups !== null && groups.length > 0 && (
            <button className="modal-btn danger" disabled={checkedCount === 0} onClick={applyRemoval}>
              Blacklist {checkedCount} Selected
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

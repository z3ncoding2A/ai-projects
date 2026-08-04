import { useMemo, useState } from 'react';
import useVideoStore from '../../stores/useVideoStore';

export default function BlacklistModal({ onClose }) {
  const blacklist = useVideoStore((s) => s.blacklist);
  const videos = useVideoStore((s) => s.videos);
  const restoreVideo = useVideoStore((s) => s.restoreVideo);
  const clearBlacklist = useVideoStore((s) => s.clearBlacklist);

  const [query, setQuery] = useState('');

  // viewkey -> title lookup, so blacklisted entries show something readable
  // instead of a bare viewkey (titles aren't guaranteed to still be in `videos`
  // if a video was blacklisted before its last scrape, hence the fallback).
  const titleByViewkey = useMemo(() => {
    const map = {};
    for (const v of videos) map[v.viewkey] = v.title;
    return map;
  }, [videos]);

  const entries = useMemo(() => {
    const q = query.toLowerCase().trim();
    return blacklist
      .map((vk) => ({ viewkey: vk, title: titleByViewkey[vk] || null }))
      .filter((e) => !q || e.viewkey.toLowerCase().includes(q) || (e.title || '').toLowerCase().includes(q));
  }, [blacklist, titleByViewkey, query]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <h2>🚫 Blacklist ({blacklist.length})</h2>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search blacklisted videos..."
          style={{
            width: '100%', padding: '8px', borderRadius: '6px',
            background: 'var(--bg-surface)', border: '1px solid var(--border)',
            color: 'white', marginBottom: '12px',
          }}
        />

        <div style={{ maxHeight: 320, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {entries.length === 0 && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', padding: '20px 0' }}>
              {blacklist.length === 0 ? 'Nothing blacklisted.' : 'No matches.'}
            </p>
          )}
          {entries.map((e) => (
            <div
              key={e.viewkey}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                gap: '8px', padding: '6px 8px', borderRadius: '6px',
                background: 'var(--bg-surface)', fontSize: '0.82rem',
              }}
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={e.title || e.viewkey}>
                {e.title || <em style={{ color: 'var(--text-muted)' }}>{e.viewkey}</em>}
              </span>
              <button className="modal-btn" style={{ flexShrink: 0, padding: '4px 10px' }} onClick={() => restoreVideo(e.viewkey)}>
                Restore
              </button>
            </div>
          ))}
        </div>

        <div className="modal-footer" style={{ justifyContent: 'space-between', marginTop: '16px' }}>
          <button
            className="modal-btn danger"
            disabled={blacklist.length === 0}
            onClick={() => {
              if (confirm(`Restore all ${blacklist.length} blacklisted videos?`)) clearBlacklist();
            }}
          >
            Clear All
          </button>
          <button className="modal-btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

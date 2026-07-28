import { useMemo } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import { getVideoCategory, formatDuration } from '../../utils/formatters';

export default function StatsPanel({ onClose }) {
  const videos = useVideoStore((s) => s.videos);
  const categories = useVideoStore((s) => s.categories);
  const categoryTree = useVideoStore((s) => s.categoryTree);
  const blacklist = useVideoStore((s) => s.blacklist);
  const watchHistory = useVideoStore((s) => s.watchHistory);

  const catById = useMemo(() => new Map(categoryTree.map((n) => [n.id, n])), [categoryTree]);

  const stats = useMemo(() => {
    const blacklistSet = new Set(blacklist);
    const catCounts = {};
    let totalDuration = 0;
    let totalViews = 0;
    let activeCount = 0;

    for (const vid of videos) {
      if (blacklistSet.has(vid.viewkey)) continue;
      activeCount++;
      const cat = getVideoCategory(vid, categories);
      catCounts[cat] = (catCounts[cat] || 0) + 1;
      totalDuration += vid.rawDuration || 0;
      totalViews += vid.rawViews || 0;
    }

    const watchCount = Object.keys(watchHistory).length;
    const totalWatches = Object.values(watchHistory).reduce((sum, h) => sum + (h.count || 0), 0);

    // Most watched
    const mostWatched = Object.entries(watchHistory)
      .sort(([, a], [, b]) => (b.count || 0) - (a.count || 0))
      .slice(0, 5)
      .map(([viewkey, h]) => {
        const vid = videos.find((v) => v.viewkey === viewkey);
        return { viewkey, title: vid?.title || viewkey, count: h.count || 0 };
      });

    return {
      activeCount,
      blacklisted: blacklist.length,
      totalDuration,
      totalViews,
      catCounts,
      watchCount,
      totalWatches,
      mostWatched,
    };
  }, [videos, categories, blacklist, watchHistory]);

  const catEntries = Object.entries(stats.catCounts).sort(([, a], [, b]) => b - a);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 600 }}>
        <h2>📊 Library Statistics</h2>

        {/* Summary cards */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.activeCount.toLocaleString()}</div>
            <div className="stat-label">Active Videos</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{formatDuration(stats.totalDuration)}</div>
            <div className="stat-label">Total Duration</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.watchCount}</div>
            <div className="stat-label">Unique Watched</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.totalWatches}</div>
            <div className="stat-label">Total Plays</div>
          </div>
        </div>

        {/* Category breakdown */}
        <h3 style={{ fontSize: '0.9rem', marginBottom: 12, color: 'var(--text-secondary)' }}>
          Category Breakdown
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
          {catEntries.map(([cat, count]) => {
            const pct = stats.activeCount > 0 ? (count / stats.activeCount) * 100 : 0;
            const node = catById.get(cat);
            const color = node?.color || 'var(--text-muted)';
            const label = cat === 'none' ? 'Uncategorized' : (node?.name || cat);
            return (
              <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 10, height: 10, borderRadius: '50%',
                  background: color, flexShrink: 0,
                }} />
                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', width: 100 }}>
                  {label}
                </span>
                <div style={{
                  flex: 1, height: 6, background: 'var(--bg-surface)',
                  borderRadius: 3, overflow: 'hidden',
                }}>
                  <div style={{
                    width: `${pct}%`, height: '100%',
                    background: color, borderRadius: 3,
                    transition: 'width 0.5s ease',
                  }} />
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', width: 60, textAlign: 'right' }}>
                  {count} ({pct.toFixed(1)}%)
                </span>
              </div>
            );
          })}
        </div>

        {/* Most watched */}
        {stats.mostWatched.length > 0 && (
          <>
            <h3 style={{ fontSize: '0.9rem', marginBottom: 8, color: 'var(--text-secondary)' }}>
              Most Watched
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {stats.mostWatched.map((item, i) => (
                <div key={item.viewkey} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  fontSize: '0.78rem', color: 'var(--text-secondary)',
                  padding: '4px 0',
                }}>
                  <span style={{ color: 'var(--text-muted)', width: 20 }}>#{i + 1}</span>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {item.title}
                  </span>
                  <span style={{ color: 'var(--accent)', fontWeight: 600 }}>
                    {item.count}×
                  </span>
                </div>
              ))}
            </div>
          </>
        )}

        <div className="modal-footer">
          <button className="modal-btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

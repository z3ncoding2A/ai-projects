import { useMemo } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import { getVideoCategory, formatDuration } from '../../utils/formatters';

/** Shared renderer for the category-breakdown-style bar lists (count / duration / watch time). */
function CategoryBarList({ entries, formatValue, catById }) {
  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 20 }}>
      {entries.map(([cat, value]) => {
        const pct = total > 0 ? (value / total) * 100 : 0;
        const node = catById.get(cat);
        const color = node?.color || 'var(--text-muted)';
        const label = cat === 'none' ? 'Uncategorized' : (node?.name || cat);
        return (
          <div key={cat} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: color, flexShrink: 0 }} />
            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', width: 100 }}>
              {label}
            </span>
            <div style={{ flex: 1, height: 6, background: 'var(--bg-surface)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.5s ease' }} />
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', width: 70, textAlign: 'right' }}>
              {formatValue(value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

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

    // Duration by category — total content-hours per bucket.
    const durationByCategory = {};
    for (const vid of videos) {
      if (blacklistSet.has(vid.viewkey)) continue;
      const cat = getVideoCategory(vid, categories);
      durationByCategory[cat] = (durationByCategory[cat] || 0) + (vid.rawDuration || 0);
    }

    // Watch time by category — approximated as duration × play count, since
    // watchHistory tracks play counts and a resume position but not a full
    // per-session watch log. A video played 3 times counts as 3× its runtime;
    // this over-counts partial/abandoned plays and under-counts re-watches
    // of only part of a video, but it's the best signal the data supports.
    const videosByViewkey = new Map(videos.map((v) => [v.viewkey, v]));
    const watchTimeByCategory = {};
    for (const [viewkey, h] of Object.entries(watchHistory)) {
      const vid = videosByViewkey.get(viewkey);
      if (!vid || blacklistSet.has(viewkey)) continue;
      const cat = getVideoCategory(vid, categories);
      watchTimeByCategory[cat] = (watchTimeByCategory[cat] || 0) + (vid.rawDuration || 0) * (h.count || 1);
    }

    // Recent activity — videos by their most recent watch date, last 14 days.
    // watchHistory only keeps the single latest lastWatched per video (not a
    // full watch log), so this reflects "last touched," not every session.
    const DAYS = 14;
    const dayBuckets = [];
    const now = new Date();
    for (let i = DAYS - 1; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      dayBuckets.push({ key: d.toISOString().slice(0, 10), count: 0 });
    }
    const bucketByKey = new Map(dayBuckets.map((b) => [b.key, b]));
    for (const h of Object.values(watchHistory)) {
      if (!h.lastWatched) continue;
      const key = new Date(h.lastWatched).toISOString().slice(0, 10);
      const bucket = bucketByKey.get(key);
      if (bucket) bucket.count++;
    }

    return {
      activeCount,
      blacklisted: blacklist.length,
      totalDuration,
      totalViews,
      catCounts,
      watchCount,
      totalWatches,
      mostWatched,
      durationByCategory,
      watchTimeByCategory,
      dayBuckets,
    };
  }, [videos, categories, blacklist, watchHistory]);

  const catEntries = Object.entries(stats.catCounts).sort(([, a], [, b]) => b - a);
  const durationEntries = Object.entries(stats.durationByCategory).sort(([, a], [, b]) => b - a);
  const watchTimeEntries = Object.entries(stats.watchTimeByCategory).sort(([, a], [, b]) => b - a);

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
        <CategoryBarList
          entries={catEntries}
          formatValue={(v) => `${v} (${stats.activeCount > 0 ? ((v / stats.activeCount) * 100).toFixed(1) : '0'}%)`}
          catById={catById}
        />

        {/* Duration by category */}
        {durationEntries.length > 0 && (
          <>
            <h3 style={{ fontSize: '0.9rem', marginBottom: 12, color: 'var(--text-secondary)' }}>
              Duration by Category
            </h3>
            <CategoryBarList entries={durationEntries} formatValue={formatDuration} catById={catById} />
          </>
        )}

        {/* Watch time by category */}
        {watchTimeEntries.length > 0 && (
          <>
            <h3 style={{ fontSize: '0.9rem', marginBottom: 4, color: 'var(--text-secondary)' }}>
              Watch Time by Category
            </h3>
            <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 12 }}>
              Estimated from play count × runtime — not exact watch duration.
            </p>
            <CategoryBarList entries={watchTimeEntries} formatValue={formatDuration} catById={catById} />
          </>
        )}

        {/* Recent activity */}
        {stats.dayBuckets.some((b) => b.count > 0) && (
          <>
            <h3 style={{ fontSize: '0.9rem', marginBottom: 12, color: 'var(--text-secondary)' }}>
              Recent Activity (last 14 days)
            </h3>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 60, marginBottom: 20 }}>
              {stats.dayBuckets.map((b) => {
                const maxCount = Math.max(...stats.dayBuckets.map((x) => x.count), 1);
                const height = b.count > 0 ? Math.max(4, (b.count / maxCount) * 100) : 2;
                const day = new Date(b.key + 'T00:00:00');
                return (
                  <div
                    key={b.key}
                    style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', height: '100%' }}
                    title={`${day.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}: ${b.count} video${b.count === 1 ? '' : 's'}`}
                  >
                    <div style={{
                      height: `${height}%`, background: b.count > 0 ? 'var(--accent)' : 'var(--bg-surface)',
                      borderRadius: 2, minHeight: 2,
                    }} />
                  </div>
                );
              })}
            </div>
          </>
        )}

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

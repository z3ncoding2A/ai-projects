import { useState, useEffect, useMemo } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import { getVideoCategory } from '../../utils/formatters';

export default function HeroBanner() {
  const videos = useVideoStore((s) => s.videos);
  const categories = useVideoStore((s) => s.categories);
  const playVideo = useVideoStore((s) => s.playVideo);
  const addToQueue = useVideoStore((s) => s.addToQueue);
  const activeTab = useVideoStore((s) => s.activeTab);

  // Pick featured videos from explode/most categories
  const featuredPool = useMemo(() => {
    return videos.filter((v) => {
      const cat = getVideoCategory(v, categories);
      return cat === 'explode' || cat === 'most';
    });
  }, [videos, categories]);

  const [currentIdx, setCurrentIdx] = useState(0);

  // Randomize on mount and auto-cycle
  useEffect(() => {
    if (featuredPool.length === 0) return;
    setCurrentIdx(Math.floor(Math.random() * featuredPool.length));

    const timer = setInterval(() => {
      setCurrentIdx((prev) => (prev + 1) % featuredPool.length);
    }, 15000);

    return () => clearInterval(timer);
  }, [featuredPool.length]);

  // Only show hero on main collection tab
  if (activeTab !== 'none' || featuredPool.length === 0) return null;

  const featured = featuredPool[currentIdx];
  if (!featured) return null;

  const bgImage = featured.remoteThumbnail || featured.thumbnail;

  return (
    <div className="hero-banner">
      <div
        className="hero-bg"
        style={{ backgroundImage: `url(${bgImage})` }}
      />
      <div className="hero-gradient" />

      <div className="hero-content">
        <h1 className="hero-title">{featured.title}</h1>
        <div className="hero-meta">
          {featured.duration && <span>⏱ {featured.duration}</span>}
          {featured.views && <span>👁 {featured.views}</span>}
          <span style={{ color: 'var(--cat-explode)' }}>
            ★ Featured
          </span>
        </div>
        <div className="hero-actions">
          <button className="hero-btn primary" onClick={() => playVideo(featured)}>
            ▶ Play Now
          </button>
          <button className="hero-btn secondary" onClick={() => addToQueue(featured)}>
            + Add to Queue
          </button>
        </div>
      </div>
    </div>
  );
}

import useVideoStore from '../../stores/useVideoStore';

export default function MiniPlayer() {
  const currentVideo = useVideoStore((s) => s.currentVideo);
  const isPlaying = useVideoStore((s) => s.isPlaying);
  const queue = useVideoStore((s) => s.queue);
  const playNext = useVideoStore((s) => s.playNext);
  const stopPlayer = useVideoStore((s) => s.stopPlayer);
  const isTheaterMode = useVideoStore((s) => s.isTheaterMode);
  const toggleTheaterMode = useVideoStore((s) => s.toggleTheaterMode);

  if (!currentVideo) return null;

  const handlePlayPause = () => {
    const video = document.getElementById('native-player');
    if (video) {
      video.paused ? video.play() : video.pause();
    }
  };

  return (
    <div className="miniplayer">
      <img
        className="miniplayer-thumb"
        src={currentVideo.thumbnail}
        alt=""
        onError={(e) => { e.target.style.display = 'none'; }}
      />

      <div className="miniplayer-info">
        <div className="miniplayer-title">{currentVideo.title}</div>
        <div className="miniplayer-sub">
          {currentVideo.duration} · {currentVideo.views}
          {queue.length > 0 && ` · ${queue.length} in queue`}
        </div>
      </div>

      <div className="miniplayer-controls">
        <button className="miniplayer-btn" onClick={handlePlayPause} title="Play/Pause">
          {isPlaying ? '⏸' : '▶'}
        </button>
        <button className="miniplayer-btn" onClick={playNext} title="Next">
          ⏭
        </button>
        <button className="miniplayer-btn" onClick={stopPlayer} title="Stop">
          ⏹
        </button>
        <button
          className={`miniplayer-btn${isTheaterMode ? ' active' : ''}`}
          onClick={toggleTheaterMode}
          title="Theater Mode (T)"
          style={isTheaterMode ? { color: 'var(--accent)' } : {}}
        >
          🎬
        </button>
        <a
          className="miniplayer-btn"
          href={currentVideo.url}
          target="_blank"
          rel="noreferrer noopener"
          title="Open on site"
          style={{ textDecoration: 'none' }}
        >
          ↗
        </a>
      </div>
    </div>
  );
}

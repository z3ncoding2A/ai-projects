import { useEffect, useRef, useState, useCallback } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import { buildEmbedUrl } from '../../utils/formatters';
import { fetchStreams } from '../../utils/api';
import VideoDetailsPanel from './VideoDetailsPanel';

export default function PlayerPanel() {
  const currentVideo = useVideoStore((s) => s.currentVideo);
  const playNext = useVideoStore((s) => s.playNext);
  const setPlayerMode = useVideoStore((s) => s.setPlayerMode);
  const playerMode = useVideoStore((s) => s.playerMode);
  const streams = useVideoStore((s) => s.streams);
  const setStreams = useVideoStore((s) => s.setStreams);
  const activeStreamIdx = useVideoStore((s) => s.activeStreamIdx);
  const setActiveStream = useVideoStore((s) => s.setActiveStream);

  const videoRef = useRef(null);
  const iframeRef = useRef(null);
  const [showQualityMenu, setShowQualityMenu] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const autoNextTimerRef = useRef(null);

  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  // Load streams when video changes
  useEffect(() => {
    if (!currentVideo) return;
    let cancelled = false;
    setLoading(true);

    (async () => {
      try {
        const data = await fetchStreams(currentVideo.url);
        if (cancelled) return;

        if (data.streams?.length > 0) {
          setStreams(data.streams, 0);
          setPlayerMode('native');
          setLoading(false);
        } else {
          throw new Error('No streams');
        }
      } catch {
        if (cancelled) return;
        // Fallback to iframe
        setPlayerMode('iframe');
        setStreams([], 0);
        setLoading(false);

        // Set auto-next timer based on duration
        if (currentVideo.rawDuration > 0) {
          clearTimeout(autoNextTimerRef.current);
          autoNextTimerRef.current = setTimeout(() => {
            playNext();
          }, (currentVideo.rawDuration + 2) * 1000);
        }
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(autoNextTimerRef.current);
    };
  }, [currentVideo?.viewkey]);

  // Set video src when stream changes
  useEffect(() => {
    if (playerMode === 'native' && streams.length > 0 && videoRef.current) {
      const stream = streams[activeStreamIdx];
      if (stream) {
        videoRef.current.src = stream.url;
        videoRef.current.play().catch(() => {});
      }
    }
  }, [playerMode, streams, activeStreamIdx]);

  const handleEnded = useCallback(() => {
    playNext();
  }, [playNext]);

  const handleQualitySelect = useCallback((idx) => {
    if (videoRef.current) {
      const currentTime = videoRef.current.currentTime;
      const wasPaused = videoRef.current.paused;

      setActiveStream(idx);

      // Wait for next render to set new src, then restore position
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.addEventListener('loadedmetadata', function onMeta() {
            videoRef.current.currentTime = currentTime;
            if (!wasPaused) videoRef.current.play();
            videoRef.current.removeEventListener('loadedmetadata', onMeta);
          });
        }
      }, 50);
    }
    setShowQualityMenu(false);
  }, [setActiveStream]);

  // No video selected
  if (!currentVideo) {
    return (
      <div className="player-area">
        <div className="player-empty-state">
          <div className="icon">▶</div>
          <p>Select a video to start playing</p>
        </div>
      </div>
    );
  }

  return (
    <div className="player-area" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {loading && (
        <div className="player-empty-state">
          <div className="icon" style={{ animation: 'spin 1s linear infinite' }}>⏳</div>
          <p>Loading streams...</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Native video player */}
      <div
        id="native-player-wrap"
        style={{
          display: playerMode === 'native' ? 'block' : 'none',
          position: 'relative',
          width: '100%',
          aspectRatio: '16/9',
          flexShrink: 0,
          background: '#000',
        }}
      >
        <video
          ref={videoRef}
          id="native-player"
          controls
          autoPlay
          onEnded={handleEnded}
          style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }}
        />

        {/* Quality button — hidden in fullscreen so native controls can auto-hide */}
        {streams.length > 1 && !isFullscreen && (
          <div style={{ position: 'absolute', bottom: 16, right: 16 }}>
            <button
              className="quality-btn"
              onClick={() => setShowQualityMenu(!showQualityMenu)}
            >
              ⚙ {streams[activeStreamIdx]?.quality || 'Quality'}
            </button>
            {showQualityMenu && (
              <div className="quality-menu">
                {streams.map((s, i) => (
                  <button
                    key={s.quality}
                    className={`quality-option${i === activeStreamIdx ? ' active' : ''}`}
                    onClick={() => handleQualitySelect(i)}
                  >
                    {s.quality}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Iframe fallback */}
      {playerMode === 'iframe' && (
        <div style={{ position: 'relative', width: '100%', aspectRatio: '16/9', flexShrink: 0 }}>
          <iframe
            ref={iframeRef}
            src={buildEmbedUrl(currentVideo.url, currentVideo.viewkey)}
            allowFullScreen
            allow="autoplay; encrypted-media; fullscreen; picture-in-picture"
            referrerPolicy="no-referrer"
            style={{ width: '100%', height: '100%', border: 'none' }}
          />
        </div>
      )}

      {/* Video Details */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        <VideoDetailsPanel video={currentVideo} />
      </div>
    </div>
  );
}

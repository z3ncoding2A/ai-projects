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
  const loadNonce = useVideoStore((s) => s.loadNonce);
  const watchHistory = useVideoStore((s) => s.watchHistory);
  const updatePlaybackPosition = useVideoStore((s) => s.updatePlaybackPosition);

  const videoRef = useRef(null);
  const iframeRef = useRef(null);
  const [showQualityMenu, setShowQualityMenu] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const autoNextTimerRef = useRef(null);
  const lastPositionSaveRef = useRef(0);
  const qualitySwitchRef = useRef(null); // { timeoutId, video, listener } for the in-flight quality switch, if any

  const clearPendingQualitySwitch = useCallback(() => {
    const pending = qualitySwitchRef.current;
    if (!pending) return;
    clearTimeout(pending.timeoutId);
    if (pending.video && pending.listener) {
      pending.video.removeEventListener('loadedmetadata', pending.listener);
    }
    qualitySwitchRef.current = null;
  }, []);

  // Cancel any pending quality-switch reseek when the video itself changes or
  // the component unmounts — otherwise a stale currentTime from the previous
  // video could get applied to whatever plays next (review finding: stale
  // closure + no cleanup in handleQualitySelect).
  useEffect(() => {
    return clearPendingQualitySwitch;
  }, [currentVideo?.viewkey, clearPendingQualitySwitch]);

  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  // Flush the resume position for whichever video was playing before this one,
  // right as we switch away from it (covers "clicked next video" and unmount —
  // onPause alone misses cases where the element's src changes without a pause
  // event, or the component unmounts entirely).
  useEffect(() => {
    return () => {
      const video = videoRef.current;
      if (video && currentVideo && video.currentTime > 0) {
        updatePlaybackPosition(currentVideo.viewkey, Math.floor(video.currentTime));
      }
    };
    // Only re-run (and thus flush) when the video itself changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentVideo?.viewkey]);

  // Switch to the Pornhub iframe embed — the fallback whenever native playback
  // isn't possible: stream extraction failed, returned nothing, OR the
  // extracted stream URL won't actually play (expired token, CORS, an HLS
  // manifest the bare <video> can't decode). Shared by the fetch catch, the
  // <video> onError, and the load watchdog below.
  const fallbackToIframe = useCallback(() => {
    setPlayerMode('iframe');
    setStreams([], 0);
    setLoading(false);
    if (currentVideo?.rawDuration > 0) {
      clearTimeout(autoNextTimerRef.current);
      autoNextTimerRef.current = setTimeout(() => {
        playNext();
      }, (currentVideo.rawDuration + 2) * 1000);
    }
  }, [currentVideo, playNext, setPlayerMode, setStreams]);

  // Load streams when the video changes (keyed on loadNonce too, so re-clicking
  // the already-playing video actually retries instead of going blank).
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
        fallbackToIframe();
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(autoNextTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentVideo?.viewkey, loadNonce]);

  // Watchdog: if native mode is selected but the <video> hasn't reached a
  // playable state within 10s (black screen stuck at 0:00 — a stalled or
  // silently-failing stream that never fires an 'error' event), give up on
  // native and drop to the iframe embed.
  useEffect(() => {
    if (playerMode !== 'native' || streams.length === 0) return;
    const video = videoRef.current;
    if (!video) return;

    let settled = false;
    const markPlayable = () => { settled = true; };
    video.addEventListener('canplay', markPlayable, { once: true });

    const watchdog = setTimeout(() => {
      // readyState >= 2 (HAVE_CURRENT_DATA) means frames are actually decoding.
      if (!settled && (videoRef.current?.readyState ?? 0) < 2) {
        fallbackToIframe();
      }
    }, 10000);

    return () => {
      clearTimeout(watchdog);
      video.removeEventListener('canplay', markPlayable);
    };
  }, [playerMode, streams, activeStreamIdx, loadNonce, fallbackToIframe]);

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

  // Resume playback: seek to the saved position once metadata (and therefore
  // duration) is available. Skips resuming into the last ~15s so a video that
  // was basically finished starts over instead of replaying the tail.
  useEffect(() => {
    const video = videoRef.current;
    if (!video || playerMode !== 'native' || !currentVideo) return;

    const saved = watchHistory[currentVideo.viewkey]?.lastPosition;
    if (!saved || saved < 5) return;

    const onLoadedMetadata = () => {
      if (saved < video.duration - 15) {
        video.currentTime = saved;
      }
    };
    video.addEventListener('loadedmetadata', onLoadedMetadata);
    return () => video.removeEventListener('loadedmetadata', onLoadedMetadata);
    // Only re-run when the video itself changes, not on every watchHistory update
    // (which would otherwise re-seek on every throttled position save).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentVideo?.viewkey, playerMode, streams]);

  // Throttled position saving while playing (~every 5s), plus a flush on pause.
  const flushPosition = useCallback(() => {
    const video = videoRef.current;
    if (!video || !currentVideo) return;
    updatePlaybackPosition(currentVideo.viewkey, Math.floor(video.currentTime));
  }, [currentVideo, updatePlaybackPosition]);

  const handleTimeUpdate = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    const now = Date.now();
    if (now - lastPositionSaveRef.current > 5000) {
      lastPositionSaveRef.current = now;
      flushPosition();
    }
  }, [flushPosition]);

  const handleEnded = useCallback(() => {
    // Fully watched — clear the resume point so it starts from 0 next time.
    if (currentVideo) updatePlaybackPosition(currentVideo.viewkey, 0);
    playNext();
  }, [playNext, currentVideo, updatePlaybackPosition]);

  const handleQualitySelect = useCallback((idx) => {
    if (videoRef.current && currentVideo) {
      const currentTime = videoRef.current.currentTime;
      const wasPaused = videoRef.current.paused;
      const targetViewkey = currentVideo.viewkey;

      // A previous quality switch (or video change) may still have a pending
      // reseek queued — cancel it so it can't fire after this one.
      clearPendingQualitySwitch();

      setActiveStream(idx);

      // Wait for next render to set new src, then restore position
      const timeoutId = setTimeout(() => {
        const video = videoRef.current;
        // Bail if the video changed during this 50ms window. Read the store
        // directly (not the `currentVideo` closed over above, which is
        // frozen to click-time) so this actually reflects what's live now.
        if (!video || useVideoStore.getState().currentVideo?.viewkey !== targetViewkey) return;

        const onMeta = () => {
          video.currentTime = currentTime;
          if (!wasPaused) video.play();
          qualitySwitchRef.current = null;
        };
        video.addEventListener('loadedmetadata', onMeta, { once: true });
        qualitySwitchRef.current = { timeoutId: null, video, listener: onMeta };
      }, 50);
      qualitySwitchRef.current = { timeoutId, video: null, listener: null };
    }
    setShowQualityMenu(false);
  }, [setActiveStream, currentVideo, clearPendingQualitySwitch]);

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
          onPause={flushPosition}
          onTimeUpdate={handleTimeUpdate}
          onError={fallbackToIframe}
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

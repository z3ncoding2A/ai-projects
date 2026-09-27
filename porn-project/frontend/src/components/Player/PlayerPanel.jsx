import { useEffect, useRef, useState, useCallback } from 'react';
import useVideoStore from '../../stores/useVideoStore';
import { buildEmbedUrl } from '../../utils/formatters';
import { fetchStreams } from '../../utils/api';
import VideoDetailsPanel from './VideoDetailsPanel';

// Streams arrive sorted highest-quality first. Default to the best stream at or
// below 1080p instead of the top entry, which can be 4K and needlessly heavy to
// stream; if every stream is above the cap, take the one closest to it (last).
const PREFERRED_MAX_HEIGHT = 1080;

function pickDefaultStreamIdx(streams) {
  const idx = streams.findIndex((s) => s.height <= PREFERRED_MAX_HEIGHT);
  return idx !== -1 ? idx : streams.length - 1;
}

// Resume from watch history, except into the last ~15s: a video that was
// basically finished starts over instead of replaying its tail. -1 means
// "start from the beginning" (also hls.js's startPosition default).
const MIN_RESUME_SECONDS = 5;
const RESUME_TAIL_SECONDS = 15;

function historyResumePosition(saved, duration) {
  if (!saved || saved < MIN_RESUME_SECONDS) return -1;
  if (duration > 0 && saved >= duration - RESUME_TAIL_SECONDS) return -1;
  return saved;
}

// hls.js has already retried internally by the time it reports an error as
// fatal, so only a couple more attempts are worth making before dropping to the
// iframe embed. The network count resets whenever a fragment buffers, so only
// back-to-back failures (e.g. signed segment URLs that have expired) use it up.
const MAX_NETWORK_RETRIES = 2;
const MAX_MEDIA_RECOVERIES = 3;

// hls.js is ~400KB and only needed once a video actually plays, so it's loaded
// on first use rather than shipped in the main bundle.
let hlsModulePromise = null;
function loadHls() {
  hlsModulePromise ??= import('hls.js')
    .then((m) => m.default)
    .catch((err) => {
      hlsModulePromise = null; // let the next video retry a failed chunk load
      throw err;
    });
  return hlsModulePromise;
}

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
  const updatePlaybackPosition = useVideoStore((s) => s.updatePlaybackPosition);
  const viewkey = currentVideo?.viewkey;
  const rawDuration = currentVideo?.rawDuration;

  const videoRef = useRef(null);
  const iframeRef = useRef(null);
  const [showQualityMenu, setShowQualityMenu] = useState(false);
  const [loading, setLoading] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const autoNextTimerRef = useRef(null);
  const lastPositionSaveRef = useRef(0);
  // Resume point queued by a quality switch, consumed by the load effect.
  // Tagged with its viewkey so a stale currentTime can't be applied to a
  // different video that started playing in the meantime.
  const pendingSeekRef = useRef(null);
  // While hls.js drives the <video>, routes element 'error' events into its
  // media-error recovery (null otherwise).
  const hlsRecoverRef = useRef(null);

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
          setStreams(data.streams, pickDefaultStreamIdx(data.streams));
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

  // Set video src when stream changes. The streams are HLS playlists, which
  // only Safari can decode from a plain src assignment — everywhere else they
  // need hls.js via Media Source Extensions, or the <video> silently never
  // becomes playable and the watchdog drops us to the iframe embed.
  //
  // This effect is also the one place the start position is decided, so no
  // other 'loadedmetadata' listener can seek over it later (e.g. when a media
  // error recovery re-attaches the MediaSource).
  useEffect(() => {
    if (playerMode !== 'native' || streams.length === 0) return;
    const video = videoRef.current;
    const stream = streams[activeStreamIdx];
    if (!video || !stream || !viewkey) return;

    // A quality switch on this same video resumes where it left off, in the
    // same paused/playing state (queued by handleQualitySelect); any other
    // load resumes from watch history. Read synchronously, before the async
    // hls.js import below.
    const pendingSeek = pendingSeekRef.current;
    pendingSeekRef.current = null;
    const qualitySwitch = pendingSeek?.viewkey === viewkey ? pendingSeek : null;
    // Read from the store rather than subscribing: history updates every ~5s
    // during playback, and depending on it would rebuild the player each time.
    const saved = useVideoStore.getState().watchHistory[viewkey]?.lastPosition;
    const startPositionFor = (duration) =>
      qualitySwitch ? qualitySwitch.currentTime : historyResumePosition(saved, duration);
    // Playback is started explicitly rather than with the autoPlay attribute,
    // which would restart a paused video as soon as the new source buffered.
    const play = () => {
      if (!qualitySwitch?.wasPaused) video.play().catch(() => {});
    };

    let cancelled = false;
    let hls = null;

    // Safari decodes HLS natively from a plain src.
    const onNativeMetadata = () => {
      const start = startPositionFor(video.duration);
      if (start > 0) video.currentTime = start;
      play();
    };
    const startNative = () => {
      video.addEventListener('loadedmetadata', onNativeMetadata, { once: true });
      video.src = stream.url;
    };

    loadHls()
      .then((Hls) => {
        if (cancelled) return;
        if (!Hls.isSupported()) {
          startNative();
          return;
        }

        hls = new Hls({ startPosition: startPositionFor(rawDuration) });
        let manifestParsed = false;
        let networkRetries = 0;
        let mediaRecoveries = 0;

        const recoverMedia = () => {
          if (mediaRecoveries >= MAX_MEDIA_RECOVERIES) {
            fallbackToIframe();
            return;
          }
          mediaRecoveries += 1;
          hls.recoverMediaError();
        };
        hlsRecoverRef.current = recoverMedia;

        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          manifestParsed = true;
          play();
        });
        hls.on(Hls.Events.FRAG_BUFFERED, () => {
          networkRetries = 0;
        });
        hls.on(Hls.Events.ERROR, (_evt, data) => {
          if (!data.fatal) return;
          if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
            recoverMedia();
          } else if (
            // startLoad() can't help before the manifest loads -- there's
            // nothing to resume loading -- so that goes straight to the iframe.
            data.type === Hls.ErrorTypes.NETWORK_ERROR &&
            manifestParsed &&
            networkRetries < MAX_NETWORK_RETRIES
          ) {
            networkRetries += 1;
            hls.startLoad();
          } else {
            fallbackToIframe();
          }
        });

        hls.loadSource(stream.url);
        hls.attachMedia(video);
      })
      .catch(() => {
        if (!cancelled) fallbackToIframe();
      });

    return () => {
      cancelled = true;
      video.removeEventListener('loadedmetadata', onNativeMetadata);
      hlsRecoverRef.current = null;
      hls?.destroy();
    };
  }, [playerMode, streams, activeStreamIdx, fallbackToIframe, viewkey, rawDuration]);

  // hls.js only logs errors raised on the <video> element itself, so a decode
  // error there has to be routed into its recovery by hand; falling straight
  // back to the iframe would pre-empt a recoverable error. Without hls.js
  // (native src) there's nothing to recover.
  const handleVideoError = useCallback(() => {
    if (hlsRecoverRef.current) hlsRecoverRef.current();
    else fallbackToIframe();
  }, [fallbackToIframe]);

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
    setShowQualityMenu(false);
    // Re-selecting the active quality doesn't re-run the load effect, so a
    // resume point queued here would linger and hijack the next reload.
    if (idx === activeStreamIdx) return;
    const video = videoRef.current;
    if (video && currentVideo) {
      // Hand the resume point to the load effect, which rebuilds the player
      // for the new stream and starts it from there.
      pendingSeekRef.current = {
        viewkey: currentVideo.viewkey,
        currentTime: video.currentTime,
        wasPaused: video.paused,
      };
      setActiveStream(idx);
    }
  }, [setActiveStream, currentVideo, activeStreamIdx]);

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
          onEnded={handleEnded}
          onPause={flushPosition}
          onTimeUpdate={handleTimeUpdate}
          onError={handleVideoError}
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

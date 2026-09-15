import { useRef, useCallback, useEffect, memo } from 'react';
import { motion } from 'framer-motion';
import useVideoStore from '../../stores/useVideoStore';
import { getVideoCategory } from '../../utils/formatters';
import { refreshThumbnail } from '../../utils/api';

const VideoCard = memo(function VideoCard({ video, isActive, isFocused, rowActive }) {
  const categories = useVideoStore((s) => s.categories);
  const categoryTree = useVideoStore((s) => s.categoryTree);
  const watchHistory = useVideoStore((s) => s.watchHistory);
  const isBulkMode = useVideoStore((s) => s.isBulkMode);
  const selectedVideos = useVideoStore((s) => s.selectedVideos);
  const viewMode = useVideoStore((s) => s.viewMode);
  const activeTab = useVideoStore((s) => s.activeTab);
  const playVideo = useVideoStore((s) => s.playVideo);
  const getCategoryColor = useVideoStore((s) => s.getCategoryColor);
  const openPicker = useVideoStore((s) => s.openPicker);
  const openInspector = useVideoStore((s) => s.openInspector);
  const deleteVideo = useVideoStore((s) => s.deleteVideo);
  const restoreVideo = useVideoStore((s) => s.restoreVideo);
  const copyVideoLink = useVideoStore((s) => s.copyVideoLink);
  const addToQueue = useVideoStore((s) => s.addToQueue);
  const toggleSelection = useVideoStore((s) => s.toggleSelection);
  const setVideoThumbnail = useVideoStore((s) => s.setVideoThumbnail);

  const previewRef = useRef(null);
  const intervalRef = useRef(null);
  const refreshedRef = useRef(false);

  const catId = getVideoCategory(video, categories);
  const catNode = categoryTree.find((n) => n.id === catId);
  const catColor = getCategoryColor(catId);
  const catName = catNode ? catNode.name : (catId === 'none' ? 'Uncategorized' : catId);
  const isSelected = selectedVideos.has(video.viewkey);
  const watched = watchHistory[video.viewkey];
  const isBlacklistTab = activeTab === 'blacklist';

  const handleClick = useCallback((e) => {
    if (
      e.target.closest('.card-actions') ||
      e.target.closest('.card-queue-btn') ||
      e.target.closest('.card-checkbox') ||
      e.target.closest('.card-quick-btn')
    ) {
      return;
    }
    if (isBulkMode) {
      toggleSelection(video.viewkey);
    } else {
      playVideo(video);
    }
  }, [isBulkMode, video, playVideo, toggleSelection]);

  const handleQueueAdd = useCallback((e) => {
    e.stopPropagation();
    addToQueue(video);
  }, [video, addToQueue]);

  const handleCheckbox = useCallback((e) => {
    e.stopPropagation();
    toggleSelection(video.viewkey);
  }, [video.viewkey, toggleSelection]);

  const handleInspector = useCallback((e) => {
    e.stopPropagation();
    openInspector(video);
  }, [video, openInspector]);

  const handleCopyLink = useCallback((e) => {
    e.stopPropagation();
    copyVideoLink(video);
  }, [video, copyVideoLink]);

  const handleBlacklistAction = useCallback((e) => {
    e.stopPropagation();
    if (isBlacklistTab) {
      restoreVideo(video.viewkey);
    } else {
      if (window.confirm('Move to blacklist?')) {
        deleteVideo(video.viewkey);
      }
    }
  }, [isBlacklistTab, video.viewkey, restoreVideo, deleteVideo]);

  // Thumbnail preview frame rotation. Pornhub serves two URL shapes in
  // remoteThumbnail: a numbered frame sequence ("...N.jpg", cycled 1-16
  // here) and a signed, time-limited CDN transform URL that expires ~24h
  // after scraping and 404s/410s once stale. Either can go bad, so failure
  // handling below is shared: a run of load errors triggers exactly one
  // on-demand backend re-scrape (/api/refresh-thumbnail), and only gives up
  // (hides the overlay, revealing the static thumb underneath) if that also
  // fails.
  const applyPreviewSrc = useCallback((src) => {
    const img = previewRef.current;
    if (!img || !src) return;

    clearInterval(intervalRef.current);

    const numMatch = src.match(/^(.+?)(\d+)(\.jpg)$/i);
    // Cyclable frames tolerate a few missing frame numbers before giving up;
    // the static/signed branch only ever attempts one image, so any failure
    // there is already the end of the road.
    const maxErrors = numMatch ? 4 : 0;
    let frame = 1;
    let errors = 0;

    const giveUp = async () => {
      clearInterval(intervalRef.current);
      if (refreshedRef.current) {
        img.style.opacity = '0';
        return;
      }
      refreshedRef.current = true;
      const fresh = await refreshThumbnail(video.viewkey);
      if (fresh) {
        setVideoThumbnail(video.viewkey, fresh);
        applyPreviewSrc(fresh);
      } else {
        img.style.opacity = '0';
      }
    };

    img.onload = () => { errors = 0; };
    img.onerror = () => {
      errors++;
      if (errors > maxErrors) giveUp();
    };

    img.style.opacity = '1';
    if (numMatch) {
      // Plain numbered CDN host — verified to need no Referer, so load direct
      // to keep row-wide hover (many cards cycling at once) off the local proxy.
      img.src = `${numMatch[1]}${frame}${numMatch[3]}`;
      intervalRef.current = setInterval(() => {
        frame = (frame % 16) + 1;
        img.src = `${numMatch[1]}${frame}${numMatch[3]}`;
      }, 450);
    } else {
      // Signed CDN transform URL — this host 403s without a Referer, which
      // the site-wide no-referrer meta tag strips from a direct <img> load.
      // Route through /api/proxy, which already attaches the right Referer.
      img.src = `/api/proxy?url=${encodeURIComponent(src)}`;
    }
  }, [video.viewkey, setVideoThumbnail]);

  const startPreview = useCallback(() => {
    const src = video.remoteThumbnail;
    if (!src || src === 'undefined' || src === 'null' || src === '') return;
    applyPreviewSrc(src);
  }, [video.remoteThumbnail, applyPreviewSrc]);

  const stopPreview = useCallback(() => {
    clearInterval(intervalRef.current);
    intervalRef.current = null;
    refreshedRef.current = false;
    const img = previewRef.current;
    if (img) {
      img.style.opacity = '0';
      img.onerror = null;
      img.onload = null;
    }
  }, []);

  // Row-wide hover (see VideoGrid) drives preview playback instead of this
  // card's own mouse events, so every card in the hovered row animates together.
  useEffect(() => {
    if (rowActive) {
      startPreview();
    } else {
      stopPreview();
    }
    return stopPreview;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rowActive]);

  const className = [
    'video-card',
    viewMode === 'compact' && 'compact-mode',
    viewMode === 'list' && 'list-mode',
    isActive && 'active',
    isFocused && 'focused',
    isSelected && 'selected',
  ].filter(Boolean).join(' ');

  // ── 1. DENSE TABLE / LIST ROW MODE ──────────────────────────────────
  if (viewMode === 'list') {
    return (
      <div
        className={className}
        onClick={handleClick}
        data-viewkey={video.viewkey}
      >
        {/* Checkbox / Index */}
        {isBulkMode ? (
          <div
            className={`card-checkbox${isSelected ? ' checked' : ''}`}
            onClick={handleCheckbox}
          >
            {isSelected ? '✓' : ''}
          </div>
        ) : (
          <span className="list-idx">{video.idx != null ? video.idx + 1 : ''}</span>
        )}

        {/* Thumbnail Snapshot */}
        <div className="list-thumb-wrap">
          <img
            src={video.thumbnail}
            alt=""
            loading="lazy"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
          {video.duration && <span className="card-duration mini">{video.duration}</span>}
        </div>

        {/* Title & Viewkey */}
        <div className="list-title-col">
          <div className="list-title" title={video.title}>{video.title}</div>
          <span className="list-sub">{video.views || '0 views'}</span>
        </div>

        {/* Category Pill */}
        <div className="list-cat-col">
          <span
            className="card-cat-pill"
            style={catColor && catColor !== 'transparent' ? { borderColor: catColor, color: '#fff' } : {}}
          >
            {catNode?.icon && <span style={{ marginRight: 4 }}>{catNode.icon}</span>}
            {catName}
          </span>
        </div>

        {/* Watch status */}
        <div className="list-status-col">
          {watched ? (
            <span className="badge-watched">👁 {watched.count}×</span>
          ) : (
            <span className="badge-unwatched">Unwatched</span>
          )}
        </div>

        {/* Actions */}
        <div className="list-actions-col" onClick={(e) => e.stopPropagation()}>
          <button
            className="card-quick-btn"
            onClick={handleInspector}
            title="Inspector (I)"
          >
            ℹ️
          </button>
          <button
            className="card-quick-btn"
            onClick={() => openPicker({ mode: 'single', viewkey: video.viewkey })}
            title="Categorize (C)"
          >
            🏷
          </button>
          <button
            className="card-quick-btn"
            onClick={handleQueueAdd}
            title="Add to queue"
          >
            +
          </button>
          <button
            className="card-quick-btn"
            onClick={handleCopyLink}
            title="Copy link"
          >
            📋
          </button>
          <button
            className={`card-quick-btn${isBlacklistTab ? ' restore' : ' del'}`}
            onClick={handleBlacklistAction}
            title={isBlacklistTab ? 'Restore video' : 'Blacklist (B)'}
          >
            {isBlacklistTab ? '✓' : '✕'}
          </button>
        </div>
      </div>
    );
  }

  // ── 2. COMPACT OR STANDARD GRID CARD MODE ────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.15 }}
      className={className}
      onClick={handleClick}
      data-viewkey={video.viewkey}
    >
      {/* Thumbnail */}
      <div className="card-thumb">
        {/* Category color strip */}
        {catColor && catColor !== 'transparent' && (
          <div className="card-cat-strip" style={{ background: catColor }} />
        )}

        {/* Bulk checkbox */}
        {isBulkMode && (
          <div
            className={`card-checkbox${isSelected ? ' checked' : ''}`}
            onClick={handleCheckbox}
          >
            {isSelected ? '✓' : ''}
          </div>
        )}

        {/* Queue button */}
        {!isBulkMode && (
          <button className="card-queue-btn" onClick={handleQueueAdd} title="Add to Queue">
            +
          </button>
        )}

        <img
          src={video.thumbnail}
          alt=""
          loading="lazy"
          onError={(e) => { e.target.style.display = 'none'; }}
        />

        {/* Preview frame overlay — src is assigned imperatively by
           applyPreviewSrc, only once a row is actually hovered, so scrolling
           the grid alone never fires a wasted request for every visible card. */}
        {video.remoteThumbnail && (
          <img
            ref={previewRef}
            className="preview-img"
            alt=""
            style={{ opacity: 0 }}
          />
        )}

        <div className="card-scrim" />

        {/* Duration badge */}
        {video.duration && <span className="card-duration">{video.duration}</span>}

        {/* Watched indicator */}
        {watched && (
          <div className="card-watched">👁 {watched.count}×</div>
        )}

        {/* Quick action bar overlay on hover */}
        {!isBulkMode && (
          <div className="card-quick-bar" onClick={(e) => e.stopPropagation()}>
            <button
              className="card-quick-btn"
              onClick={handleInspector}
              title="Inspector Sheet (I)"
            >
              ℹ️
            </button>
            <button
              className="card-quick-btn"
              onClick={() => openPicker({ mode: 'single', viewkey: video.viewkey })}
              title="Categorize (C)"
            >
              🏷
            </button>
            <button
              className="card-quick-btn"
              onClick={handleCopyLink}
              title="Copy Link"
            >
              📋
            </button>
            <button
              className={`card-quick-btn${isBlacklistTab ? ' restore' : ' del'}`}
              onClick={handleBlacklistAction}
              title={isBlacklistTab ? 'Restore Video' : 'Blacklist (B)'}
            >
              {isBlacklistTab ? '✓' : '✕'}
            </button>
          </div>
        )}

        {/* Play icon overlay */}
        <div className="card-play-overlay">
          <div className="card-play-icon">▶</div>
        </div>
      </div>

      {/* Card Info Area */}
      <div className="card-info">
        <div className="card-title" title={video.title}>{video.title}</div>
        <div className="card-meta">
          {video.views && <span className="card-views">{video.views}</span>}
          {catId !== 'none' && (
            <span
              className="card-cat-tag"
              style={catColor && catColor !== 'transparent' ? { borderColor: catColor, color: '#fff' } : {}}
            >
              {catNode?.icon || '📁'} {catName}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
});

export default VideoCard;

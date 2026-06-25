import { useRef, useCallback, memo } from 'react';
import { motion } from 'framer-motion';
import useVideoStore from '../../stores/useVideoStore';
import { CATEGORY_COLORS, CATEGORY_BUTTONS, getVideoCategory } from '../../utils/formatters';

const VideoCard = memo(function VideoCard({ video, isActive, isFocused }) {
  const categories = useVideoStore((s) => s.categories);
  const watchHistory = useVideoStore((s) => s.watchHistory);
  const isBulkMode = useVideoStore((s) => s.isBulkMode);
  const selectedVideos = useVideoStore((s) => s.selectedVideos);
  const playVideo = useVideoStore((s) => s.playVideo);
  const setCategory = useVideoStore((s) => s.setCategory);
  const deleteVideo = useVideoStore((s) => s.deleteVideo);
  const addToQueue = useVideoStore((s) => s.addToQueue);
  const toggleSelection = useVideoStore((s) => s.toggleSelection);

  const previewRef = useRef(null);
  const intervalRef = useRef(null);

  const cat = getVideoCategory(video, categories);
  const catColor = CATEGORY_COLORS[cat] || 'transparent';
  const isSelected = selectedVideos.has(video.viewkey);
  const watched = watchHistory[video.viewkey];

  const handleClick = useCallback((e) => {
    if (e.target.closest('.card-actions') || e.target.closest('.card-queue-btn') || e.target.closest('.card-checkbox')) return;
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

  // Thumbnail preview rotation
  const startPreview = useCallback(() => {
    const src = video.remoteThumbnail;
    if (!src || src === 'undefined' || src === 'null' || src === '') return;
    const img = previewRef.current;
    if (!img) return;

    const numMatch = src.match(/^(.+?)(\d+)(\.jpg)$/i);
    let frame = 1;
    let errors = 0;

    img.onerror = () => {
      errors++;
      if (errors > 4) {
        clearInterval(intervalRef.current);
        img.src = src;
        img.onerror = () => { img.style.opacity = '0'; };
        return;
      }
      frame = (frame % 16) + 1;
    };

    if (numMatch) {
      img.style.opacity = '1';
      img.src = `${numMatch[1]}${frame}${numMatch[3]}`;
      intervalRef.current = setInterval(() => {
        frame = (frame % 16) + 1;
        img.src = `${numMatch[1]}${frame}${numMatch[3]}`;
      }, 500);
    } else {
      img.style.opacity = '1';
      img.src = src;
      img.onerror = () => { img.style.opacity = '0'; };
    }
  }, [video.remoteThumbnail]);

  const stopPreview = useCallback(() => {
    clearInterval(intervalRef.current);
    intervalRef.current = null;
    const img = previewRef.current;
    if (img) {
      img.style.opacity = '0';
      img.onerror = null;
    }
  }, []);

  const className = [
    'video-card',
    isActive && 'active',
    isFocused && 'focused',
    isSelected && 'selected',
  ].filter(Boolean).join(' ');

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.2 }}
      className={className}
      onClick={handleClick}
      data-viewkey={video.viewkey}
    >
      {/* Thumbnail */}
      <div
        className="card-thumb"
        onMouseEnter={startPreview}
        onMouseLeave={stopPreview}
      >
        {/* Category strip */}
        {catColor !== 'transparent' && (
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

        {/* Preview overlay */}
        {video.remoteThumbnail && (
          <img
            ref={previewRef}
            className="preview-img"
            src={video.remoteThumbnail}
            alt=""
            style={{ opacity: 0 }}
          />
        )}

        <div className="card-scrim" />

        {video.duration && <span className="card-duration">{video.duration}</span>}

        {/* Watch indicator */}
        {watched && (
          <div className="card-watched">👁 {watched.count}×</div>
        )}

        {/* Play overlay */}
        <div className="card-play-overlay">
          <div className="card-play-icon">▶</div>
        </div>
      </div>

      {/* Info */}
      <div className="card-info">
        <div className="card-title" title={video.title}>{video.title}</div>
        <div className="card-meta">
          {video.views && <span>{video.views}</span>}
        </div>
      </div>

      {/* Category quick-actions */}
      {!isBulkMode && (
        <div className="card-actions" onClick={(e) => e.stopPropagation()}>
          {CATEGORY_BUTTONS.map((btn) => (
            <button
              key={btn.key}
              className={`cat-btn ${btn.cls}`}
              onClick={() => setCategory(video.viewkey, btn.key)}
            >
              {btn.label}
            </button>
          ))}
          <button className="cat-btn rst" onClick={() => setCategory(video.viewkey, 'none')}>↺</button>
          <button className="cat-btn del" onClick={() => {
            if (window.confirm('Move to blacklist?')) deleteVideo(video.viewkey);
          }}>✕</button>
        </div>
      )}
    </motion.div>
  );
});

export default VideoCard;

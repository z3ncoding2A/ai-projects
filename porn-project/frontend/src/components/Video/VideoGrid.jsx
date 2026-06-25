import { useRef, useCallback } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { AnimatePresence } from 'framer-motion';
import useVideoStore from '../../stores/useVideoStore';
import VideoCard from './VideoCard';

/**
 * Virtualized video grid using @tanstack/react-virtual.
 * Only renders visible rows for smooth scrolling with 2,400+ videos.
 */
export default function VideoGrid() {
  const filteredVideos = useVideoStore((s) => s.filteredVideos);
  const viewMode = useVideoStore((s) => s.viewMode);
  const currentVideo = useVideoStore((s) => s.currentVideo);
  const isLoading = useVideoStore((s) => s.isLoading);

  const containerRef = useRef(null);

  // Calculate columns based on container width
  const getColumnCount = useCallback(() => {
    if (viewMode === 'list') return 1;
    const container = containerRef.current;
    if (!container) return 4;
    const width = container.clientWidth - 32; // padding
    const minCardWidth = 220;
    return Math.max(1, Math.floor(width / (minCardWidth + 14))); // 14 = gap
  }, [viewMode]);

  const columnCount = containerRef.current ? getColumnCount() : 4;
  const rowCount = Math.ceil(filteredVideos.length / columnCount);

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => containerRef.current,
    estimateSize: () => viewMode === 'list' ? 80 : 230,
    overscan: 5,
  });

  if (isLoading) {
    return (
      <div className="video-grid-container" ref={containerRef}>
        <div className="video-grid">
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="skeleton skeleton-card" />
          ))}
        </div>
      </div>
    );
  }

  if (filteredVideos.length === 0) {
    return (
      <div className="video-grid-container" ref={containerRef}>
        <div className="empty-state">
          <div className="icon">🔍</div>
          <p>No videos found</p>
        </div>
      </div>
    );
  }

  return (
    <div className="video-grid-container" ref={containerRef}>
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const startIdx = virtualRow.index * columnCount;
          const rowVideos = filteredVideos.slice(startIdx, startIdx + columnCount);

          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <div
                className={`video-grid${viewMode === 'list' ? ' list-view' : ''}`}
                style={{ height: '100%' }}
              >
                <AnimatePresence mode="popLayout">
                  {rowVideos.map((video) => (
                    <VideoCard
                      key={video.viewkey}
                      video={video}
                      isActive={currentVideo?.viewkey === video.viewkey}
                      isFocused={false}
                    />
                  ))}
                </AnimatePresence>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

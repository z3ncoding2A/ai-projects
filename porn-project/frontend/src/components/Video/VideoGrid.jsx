import { useRef, useCallback, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { AnimatePresence } from 'framer-motion';
import useVideoStore from '../../stores/useVideoStore';
import VideoCard from './VideoCard';
import FilterBar from './FilterBar';

/**
 * Virtualized video grid with dynamic layout density (Standard, Compact, Table)
 * and seamless keyboard navigation scrolling.
 */
export default function VideoGrid() {
  const filteredVideos = useVideoStore((s) => s.filteredVideos);
  const viewMode = useVideoStore((s) => s.viewMode);
  const currentVideo = useVideoStore((s) => s.currentVideo);
  const focusedIndex = useVideoStore((s) => s.focusedIndex);
  const isLoading = useVideoStore((s) => s.isLoading);
  const clearAllFilters = useVideoStore((s) => s.clearAllFilters);

  const containerRef = useRef(null);

  // Calculate columns dynamically based on density mode & container width
  const getColumnCount = useCallback(() => {
    if (viewMode === 'list') return 1;
    const container = containerRef.current;
    if (!container) return 4;
    const width = container.clientWidth - 32; // container padding
    const minCardWidth = viewMode === 'compact' ? 165 : 225;
    const gap = viewMode === 'compact' ? 10 : 14;
    return Math.max(1, Math.floor(width / (minCardWidth + gap)));
  }, [viewMode]);

  const columnCount = containerRef.current ? getColumnCount() : (viewMode === 'list' ? 1 : 4);
  const rowCount = Math.ceil(filteredVideos.length / columnCount);

  // Estimate row height based on view mode
  const estimateRowHeight = useCallback(() => {
    if (viewMode === 'list') return 58;
    if (viewMode === 'compact') return 195;
    return 248; // standard grid
  }, [viewMode]);

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => containerRef.current,
    estimateSize: estimateRowHeight,
    overscan: 4,
  });

  // Scroll focused video into view when keyboard navigation changes focusedIndex
  useEffect(() => {
    if (focusedIndex >= 0 && focusedIndex < filteredVideos.length && columnCount > 0) {
      const targetRow = Math.floor(focusedIndex / columnCount);
      virtualizer.scrollToIndex(targetRow, { align: 'auto', behavior: 'smooth' });
    }
  }, [focusedIndex, columnCount, virtualizer, filteredVideos.length]);

  return (
    <div className="browse-container">
      {/* Top Faceted Filter Bar */}
      <FilterBar />

      {/* Main Virtualized Scroll Area */}
      <div className="video-grid-container" ref={containerRef}>
        {isLoading ? (
          <div className="video-grid">
            {Array.from({ length: 12 }).map((_, i) => (
              <div key={i} className="skeleton skeleton-card" />
            ))}
          </div>
        ) : filteredVideos.length === 0 ? (
          <div className="empty-state">
            <div className="icon">🔍</div>
            <p className="empty-title">No videos found matching your filters</p>
            <p className="empty-sub">Try changing category, search terms, or adjusting duration limits.</p>
            <button className="clear-filters-btn large" onClick={clearAllFilters}>
              Reset All Filters ↺
            </button>
          </div>
        ) : (
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
                    className={[
                      'video-grid',
                      viewMode === 'compact' && 'compact-grid',
                      viewMode === 'list' && 'list-view',
                    ].filter(Boolean).join(' ')}
                    style={{ height: '100%' }}
                  >
                    <AnimatePresence>
                      {rowVideos.map((video, idx) => {
                        const globalIdx = startIdx + idx;
                        return (
                          <VideoCard
                            key={video.viewkey}
                            video={video}
                            isActive={currentVideo?.viewkey === video.viewkey}
                            isFocused={focusedIndex === globalIdx}
                          />
                        );
                      })}
                    </AnimatePresence>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

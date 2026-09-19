import { useRef, useState, useCallback, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { AnimatePresence } from 'framer-motion';
import useVideoStore from '../../stores/useVideoStore';
import VideoCard from './VideoCard';
import FilterBar from './FilterBar';

// Fixed columns per density mode — deliberately NOT derived from container
// width. Cards flex to fill the row (grid-template-columns: repeat(N, 1fr)),
// so browser zoom and the player panel resizing the grid only change card
// size, never how many videos are visible per row.
const COLUMN_COUNTS = { grid: 4, compact: 7, list: 1 };

// Rough initial guess before the virtualizer measures real row height via
// measureElement — only affects first paint / scrollbar sizing, not layout
// correctness, since card height (aspect-ratio 16:9 thumb) depends on the
// container width available at render time.
function estimateRowHeight(viewMode, containerWidth) {
  if (viewMode === 'list') return 58;
  const columns = COLUMN_COUNTS[viewMode] ?? COLUMN_COUNTS.grid;
  const gap = viewMode === 'compact' ? 10 : 14;
  const infoHeight = viewMode === 'compact' ? 44 : 62;
  const cardWidth = (containerWidth - gap * (columns - 1)) / columns;
  return Math.round((cardWidth * 9) / 16) + infoHeight + gap;
}

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
  const [hoveredRow, setHoveredRow] = useState(-1);

  const columnCount = COLUMN_COUNTS[viewMode] ?? COLUMN_COUNTS.grid;
  const rowCount = Math.ceil(filteredVideos.length / columnCount);

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => containerRef.current,
    estimateSize: () => estimateRowHeight(viewMode, containerRef.current?.clientWidth ?? 1200),
    overscan: 4,
  });

  // Scroll focused video into view when keyboard navigation changes focusedIndex
  useEffect(() => {
    if (focusedIndex >= 0 && focusedIndex < filteredVideos.length && columnCount > 0) {
      const targetRow = Math.floor(focusedIndex / columnCount);
      virtualizer.scrollToIndex(targetRow, { align: 'auto', behavior: 'smooth' });
    }
  }, [focusedIndex, columnCount, virtualizer, filteredVideos.length]);

  const handleRowEnter = useCallback((rowIndex) => setHoveredRow(rowIndex), []);
  const handleRowLeave = useCallback(() => setHoveredRow(-1), []);

  return (
    <div className="browse-container">
      {/* Top Faceted Filter Bar */}
      <FilterBar />

      {/* Main Virtualized Scroll Area */}
      <div className="video-grid-container" ref={containerRef}>
        {isLoading ? (
          <div className="video-grid" style={{ gridTemplateColumns: `repeat(${columnCount}, 1fr)` }}>
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
                  data-index={virtualRow.index}
                  ref={virtualizer.measureElement}
                  onMouseEnter={() => handleRowEnter(virtualRow.index)}
                  onMouseLeave={handleRowLeave}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  <div
                    className={[
                      'video-grid',
                      viewMode === 'compact' && 'compact-grid',
                      viewMode === 'list' && 'list-view',
                    ].filter(Boolean).join(' ')}
                    style={viewMode !== 'list' ? { gridTemplateColumns: `repeat(${columnCount}, 1fr)` } : undefined}
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
                            rowActive={hoveredRow === virtualRow.index}
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

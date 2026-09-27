import { useRef, useState, useCallback, useEffect, useLayoutEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { AnimatePresence } from 'framer-motion';
import useVideoStore from '../../stores/useVideoStore';
import VideoCard from './VideoCard';
import FilterBar from './FilterBar';

// Columns per density mode — deliberately NOT derived from container width.
// Cards flex to fill the row (grid-template-columns: repeat(N, 1fr)), so
// browser zoom and the player panel resizing the grid only change card size,
// never how many videos are visible per row. 'grid' is user-selectable
// (gridColumns in the store, 2–5); compact and list are fixed.
function getColumnCount(viewMode, gridColumns) {
  if (viewMode === 'list') return 1;
  if (viewMode === 'compact') return 7;
  return gridColumns;
}

// Rough initial guess before the virtualizer measures real row height via
// measureElement — only affects first paint / scrollbar sizing, not layout
// correctness, since card height (aspect-ratio 16:9 thumb) depends on the
// container width available at render time.
function estimateRowHeight(viewMode, columns, containerWidth) {
  if (viewMode === 'list') return 58;
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
  const gridColumns = useVideoStore((s) => s.gridColumns);
  const currentVideo = useVideoStore((s) => s.currentVideo);
  const focusedIndex = useVideoStore((s) => s.focusedIndex);
  const isLoading = useVideoStore((s) => s.isLoading);
  const clearAllFilters = useVideoStore((s) => s.clearAllFilters);

  const containerRef = useRef(null);
  const [hoveredRow, setHoveredRow] = useState(-1);

  const columnCount = getColumnCount(viewMode, gridColumns);
  const rowCount = Math.ceil(filteredVideos.length / columnCount);

  const virtualizer = useVirtualizer({
    count: rowCount,
    getScrollElement: () => containerRef.current,
    estimateSize: () => estimateRowHeight(viewMode, columnCount, containerRef.current?.clientWidth ?? 1200),
    overscan: 4,
  });

  // First video in the top visible row, recorded as the user scrolls, so a
  // column-count change can keep it in view. Keeping the same pixel offset
  // instead would land on entirely different videos once the rows reflow.
  const anchorIdxRef = useRef(0);
  const handleScroll = useCallback(() => {
    const topRow = virtualizer.getVirtualItemForOffset(containerRef.current?.scrollTop ?? 0);
    if (topRow) anchorIdxRef.current = topRow.index * columnCount;
  }, [virtualizer, columnCount]);

  const prevColumnCountRef = useRef(columnCount);
  useLayoutEffect(() => {
    if (prevColumnCountRef.current === columnCount) return;
    prevColumnCountRef.current = columnCount;
    // Row heights cached by measureElement are keyed by row index, so they go
    // stale when the column count (and thus every row's height) changes. Drop
    // the cache first so the scroll target is computed from the new layout.
    virtualizer.measure();
    virtualizer.scrollToIndex(Math.floor(anchorIdxRef.current / columnCount), { align: 'start' });
  }, [columnCount, virtualizer]);

  // Scroll the focused video into view when keyboard navigation (or a filter
  // change) moves focusedIndex -- but not when only the column count changed:
  // mouse scrolling never updates focusedIndex, so it's usually stale (often
  // 0) by then, and the layout effect above already keeps the user's place.
  const lastFocusScrollRef = useRef(null);
  useEffect(() => {
    const last = lastFocusScrollRef.current;
    if (last && last.focusedIndex === focusedIndex && last.length === filteredVideos.length) return;
    lastFocusScrollRef.current = { focusedIndex, length: filteredVideos.length };
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
      <div className="video-grid-container" ref={containerRef} onScroll={handleScroll}>
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

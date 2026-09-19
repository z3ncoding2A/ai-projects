import { useEffect, useState, useRef } from 'react';
import useVideoStore from './stores/useVideoStore';
import useKeyboardNav from './hooks/useKeyboardNav';
import Sidebar from './components/Layout/Sidebar';
import TopBar from './components/Layout/TopBar';
import MiniPlayer from './components/Layout/MiniPlayer';
import VideoGrid from './components/Video/VideoGrid';
import PlayerPanel from './components/Player/PlayerPanel';
import QueueWidget from './components/Queue/QueueWidget';
import StatsPanel from './components/Features/StatsPanel';
import AdvancedSearchModal from './components/Features/AdvancedSearchModal';
import CategoryPickerModal from './components/Features/CategoryPickerModal';
import InspectorDrawer from './components/Features/InspectorDrawer';
import BlacklistModal from './components/Features/BlacklistModal';
import DuplicatesModal from './components/Features/DuplicatesModal';

export default function App() {
  const init = useVideoStore((s) => s.init);
  const error = useVideoStore((s) => s.error);
  const currentVideo = useVideoStore((s) => s.currentVideo);
  const isTheaterMode = useVideoStore((s) => s.isTheaterMode);
  const inspectorVideo = useVideoStore((s) => s.inspectorVideo);

  const [showStats, setShowStats] = useState(false);
  const [showAdvancedSearch, setShowAdvancedSearch] = useState(false);
  const [showBlacklist, setShowBlacklist] = useState(false);
  const [showDuplicates, setShowDuplicates] = useState(false);
  const [playerWidth, setPlayerWidth] = useState(50); // percentage
  const resizerRef = useRef(null);
  const isResizing = useRef(false);

  // Initialize data
  useEffect(() => {
    init();
  }, [init]);

  // Register keyboard nav
  useKeyboardNav();

  // Resizer logic
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isResizing.current) return;
      const pct = 100 - (e.clientX / window.innerWidth) * 100;
      const clamped = Math.max(25, Math.min(75, pct));
      setPlayerWidth(clamped);
    };

    const handleMouseUp = () => {
      if (isResizing.current) {
        isResizing.current = false;
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);

  const startResize = () => {
    isResizing.current = true;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  if (error) {
    return (
      <div className="app-root" style={{ alignItems: 'center', justifyContent: 'center' }}>
        <div className="empty-state">
          <div className="icon">⚠️</div>
          <p>Failed to load: {error}</p>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Make sure serve.py is running on port 8888
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`app-root${isTheaterMode ? ' theater-mode' : ''}`}>
      {/* Sidebar */}
      <Sidebar />

      {/* Main area */}
      <div className="app-main">
        {/* Top bar */}
        <TopBar />

        {/* Content: Browse + Player */}
        <div className="app-content">
          {/* Browse panel */}
          <div className="browse-panel">
            <VideoGrid />
          </div>

          {/* Resizer */}
          {currentVideo && (
            <div
              ref={resizerRef}
              onMouseDown={startResize}
              className="player-resizer"
              title="Drag to resize video player"
            />
          )}

          {/* Player panel */}
          {currentVideo && (
            <div
              className="player-panel"
              style={{ width: `${playerWidth}%` }}
            >
              <PlayerPanel />
            </div>
          )}
        </div>

        {/* Mini player bar */}
        <MiniPlayer />
      </div>

      {/* Queue widget */}
      <QueueWidget />

      {/* Slide-over Inspector Drawer */}
      {inspectorVideo && <InspectorDrawer />}

      {/* Hidden triggers for modals */}
      <button
        id="stats-trigger"
        style={{ display: 'none' }}
        onClick={() => setShowStats(true)}
      />
      <button
        id="advanced-search-trigger"
        style={{ display: 'none' }}
        onClick={() => setShowAdvancedSearch(true)}
      />
      <button
        id="blacklist-trigger"
        style={{ display: 'none' }}
        onClick={() => setShowBlacklist(true)}
      />
      <button
        id="duplicates-trigger"
        style={{ display: 'none' }}
        onClick={() => setShowDuplicates(true)}
      />

      {/* Modals */}
      {showStats && <StatsPanel onClose={() => setShowStats(false)} />}
      {showAdvancedSearch && <AdvancedSearchModal onClose={() => setShowAdvancedSearch(false)} />}
      <CategoryPickerModal />
      {showBlacklist && <BlacklistModal onClose={() => setShowBlacklist(false)} />}
      {showDuplicates && <DuplicatesModal onClose={() => setShowDuplicates(false)} />}
    </div>
  );
}

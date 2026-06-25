import { useEffect, useCallback } from 'react';
import useVideoStore from '../stores/useVideoStore';

/**
 * Keyboard navigation hook — ports all the keyboard shortcuts from the original template.
 */
export default function useKeyboardNav() {
  const {
    filteredVideos, playVideo, currentVideo,
    setTab, isPlaying, addToQueue, deleteVideo,
    setCategory, toggleTheaterMode,
  } = useVideoStore();

  const handleKeyDown = useCallback((e) => {
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

    // Focus search on /
    if (e.key === '/') {
      e.preventDefault();
      document.querySelector('.search-input')?.focus();
      return;
    }

    // Theater mode
    if (e.key === 't' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      toggleTheaterMode();
      return;
    }

    // Player controls (space, k, f, m, j, l)
    const video = document.querySelector('#native-player');
    if (e.key === ' ' || e.key === 'k') {
      e.preventDefault();
      if (video && video.closest('[style]')?.style.display !== 'none') {
        video.paused ? video.play() : video.pause();
      }
      return;
    }
    if (e.key === 'f') {
      e.preventDefault();
      const wrap = document.getElementById('native-player-wrap');
      if (wrap && wrap.style.display !== 'none') {
        document.fullscreenElement ? document.exitFullscreen() : wrap.requestFullscreen().catch(() => {});
      }
      return;
    }
    if (e.key === 'm') {
      e.preventDefault();
      if (video) video.muted = !video.muted;
      return;
    }
    if (e.key === 'j') {
      e.preventDefault();
      if (video) video.currentTime = Math.max(0, video.currentTime - 10);
      return;
    }
    if (e.key === 'l') {
      e.preventDefault();
      if (video) video.currentTime = Math.min(video.duration || 0, video.currentTime + 10);
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      const { isTheaterMode } = useVideoStore.getState();
      if (isTheaterMode) useVideoStore.getState().toggleTheaterMode();
      return;
    }

    // Shift+number → switch tabs
    if (e.shiftKey && e.code?.startsWith('Digit')) {
      e.preventDefault();
      const num = e.code.replace('Digit', '');
      const tabMap = { '1': 'none', '2': 'public', '3': 'pending', '4': 'least', '5': 'average', '6': 'most', '7': 'explode' };
      if (tabMap[num]) setTab(tabMap[num]);
      return;
    }
  }, [setTab, toggleTheaterMode]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown, true);
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, [handleKeyDown]);
}

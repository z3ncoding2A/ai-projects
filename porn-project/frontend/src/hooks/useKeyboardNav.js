import { useEffect, useCallback } from 'react';
import useVideoStore from '../stores/useVideoStore';

/**
 * Workstation Keyboard Navigation Hook:
 * - J / K / Arrows: Move card focus
 * - Enter: Play focused video
 * - Space / P: Toggle player play/pause
 * - I: Open Inspector Sheet
 * - C: Open Category assignment picker
 * - B: Toggle blacklist on focused video
 * - /: Jump focus to search
 * - T: Toggle theater mode
 * - F: Toggle fullscreen
 * - M: Toggle mute
 * - Esc: Close inspector / modals / exit theater
 */
export default function useKeyboardNav() {
  const navigateFocus = useVideoStore((s) => s.navigateFocus);
  const setFocusedIndex = useVideoStore((s) => s.setFocusedIndex);
  const toggleTheaterMode = useVideoStore((s) => s.toggleTheaterMode);
  const setTab = useVideoStore((s) => s.setTab);

  const handleKeyDown = useCallback((e) => {
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
      if (e.key === 'Escape') {
        document.activeElement.blur();
      }
      return;
    }

    const {
      filteredVideos,
      focusedIndex,
      playVideo,
      currentVideo,
      inspectorVideo,
      closeInspector,
      openInspector,
      openPicker,
      toggleBlacklist,
      isTheaterMode,
    } = useVideoStore.getState();

    // ── Global Search Jump ──────────────────────────────────────────
    if (e.key === '/') {
      e.preventDefault();
      document.querySelector('.search-input')?.focus();
      return;
    }

    // ── Escape Key (Close inspector, modals, or theater mode) ────────
    if (e.key === 'Escape') {
      e.preventDefault();
      if (inspectorVideo) {
        closeInspector();
        return;
      }
      if (isTheaterMode) {
        toggleTheaterMode();
        return;
      }
      return;
    }

    // ── Inspector Sheet Toggle (I) ──────────────────────────────────
    if (e.key === 'i' || e.key === 'I') {
      e.preventDefault();
      if (inspectorVideo) {
        closeInspector();
      } else {
        const target = focusedIndex >= 0 && filteredVideos[focusedIndex] ? filteredVideos[focusedIndex] : currentVideo;
        if (target) openInspector(target);
      }
      return;
    }

    // ── Category Assignment (C) ─────────────────────────────────────
    if (e.key === 'c' || e.key === 'C') {
      e.preventDefault();
      const target = focusedIndex >= 0 && filteredVideos[focusedIndex] ? filteredVideos[focusedIndex] : currentVideo;
      if (target) openPicker({ mode: 'single', viewkey: target.viewkey });
      return;
    }

    // ── Toggle Blacklist (B) ────────────────────────────────────────
    if (e.key === 'b' || e.key === 'B') {
      e.preventDefault();
      const target = focusedIndex >= 0 && filteredVideos[focusedIndex] ? filteredVideos[focusedIndex] : currentVideo;
      if (target) toggleBlacklist(target.viewkey);
      return;
    }

    // ── Enter: Play focused video ───────────────────────────────────
    if (e.key === 'Enter') {
      if (focusedIndex >= 0 && filteredVideos[focusedIndex]) {
        e.preventDefault();
        playVideo(filteredVideos[focusedIndex]);
      }
      return;
    }

    // ── Card Navigation (J / K / Arrows) ────────────────────────────
    const videoElem = document.querySelector('#native-player');
    const isPlayerFocused = videoElem && document.activeElement === videoElem;

    if (!isPlayerFocused) {
      if (e.key === 'j' || e.key === 'ArrowDown' || e.key === 'ArrowRight') {
        e.preventDefault();
        navigateFocus(1);
        return;
      }
      if (e.key === 'k' || e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
        e.preventDefault();
        navigateFocus(-1);
        return;
      }
    }

    // ── Theater mode (T) ────────────────────────────────────────────
    if (e.key === 't' && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      toggleTheaterMode();
      return;
    }

    // ── Player Controls (Space / P, F, M, L) ────────────────────────
    if (e.key === ' ' || e.key === 'p' || e.key === 'P') {
      e.preventDefault();
      if (videoElem) {
        videoElem.paused ? videoElem.play() : videoElem.pause();
      }
      return;
    }
    if (e.key === 'f' || e.key === 'F') {
      e.preventDefault();
      const wrap = document.getElementById('native-player-wrap');
      if (wrap) {
        document.fullscreenElement ? document.exitFullscreen() : wrap.requestFullscreen().catch(() => {});
      }
      return;
    }
    if (e.key === 'm' || e.key === 'M') {
      e.preventDefault();
      if (videoElem) videoElem.muted = !videoElem.muted;
      return;
    }
    if (e.key === 'l') {
      e.preventDefault();
      if (videoElem) videoElem.currentTime = Math.min(videoElem.duration || 0, videoElem.currentTime + 10);
      return;
    }

    // ── Shift+number → Quick Tab Switch ─────────────────────────────
    if (e.shiftKey && e.code?.startsWith('Digit')) {
      e.preventDefault();
      const num = e.code.replace('Digit', '');
      const tabMap = {
        '1': 'all',
        '2': 'none',
        '3': 'public',
        '4': 'pending',
        '5': 'least',
        '6': 'average',
        '7': 'most',
        '8': 'explode',
      };
      if (tabMap[num]) setTab(tabMap[num]);
      return;
    }
  }, [navigateFocus, setTab, toggleTheaterMode]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown, true);
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, [handleKeyDown]);
}

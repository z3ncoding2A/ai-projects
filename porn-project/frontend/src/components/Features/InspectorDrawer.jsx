import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import useVideoStore from '../../stores/useVideoStore';
import { getVideoCategory } from '../../utils/formatters';

export default function InspectorDrawer() {
  const video = useVideoStore((s) => s.inspectorVideo);
  const closeInspector = useVideoStore((s) => s.closeInspector);
  const categories = useVideoStore((s) => s.categories);
  const categoryTree = useVideoStore((s) => s.categoryTree);
  const setCategory = useVideoStore((s) => s.setCategory);
  const blacklist = useVideoStore((s) => s.blacklist);
  const toggleBlacklist = useVideoStore((s) => s.toggleBlacklist);
  const copyVideoLink = useVideoStore((s) => s.copyVideoLink);
  const playVideo = useVideoStore((s) => s.playVideo);
  const rawTags = useVideoStore((s) => (video ? s.tags[video.viewkey] : null));
  const tags = rawTags || [];
  const addTag = useVideoStore((s) => s.addTag);
  const removeTag = useVideoStore((s) => s.removeTag);
  const playlists = useVideoStore((s) => s.playlists);
  const createPlaylist = useVideoStore((s) => s.createPlaylist);
  const addToPlaylist = useVideoStore((s) => s.addToPlaylist);
  const removeFromPlaylist = useVideoStore((s) => s.removeFromPlaylist);
  const watchHistory = useVideoStore((s) => (video ? s.watchHistory[video.viewkey] : null));

  const [newTag, setNewTag] = useState('');
  const [newPlaylist, setNewPlaylist] = useState('');

  if (!video) return null;

  const currentCat = getVideoCategory(video, categories);
  const isBlacklisted = blacklist.includes(video.viewkey);

  const handleAddTag = (e) => {
    e.preventDefault();
    if (newTag.trim()) {
      addTag(video.viewkey, newTag.trim().toLowerCase());
      setNewTag('');
    }
  };

  const handleCreatePlaylist = (e) => {
    e.preventDefault();
    if (newPlaylist.trim()) {
      const name = newPlaylist.trim();
      createPlaylist(name);
      addToPlaylist(name, video.viewkey);
      setNewPlaylist('');
    }
  };

  return (
    <AnimatePresence>
      <div className="inspector-backdrop" onClick={closeInspector}>
        <motion.div
          className="inspector-sheet"
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="inspector-header">
            <div className="inspector-header-title">
              <span className="icon">ℹ️</span> Video Inspector
            </div>
            <button className="inspector-close-btn" onClick={closeInspector} title="Close (Esc)">
              ✕
            </button>
          </div>

          {/* Body */}
          <div className="inspector-body">
            {/* Thumbnail preview with play overlay */}
            <div className="inspector-preview" onClick={() => playVideo(video)}>
              <img src={video.thumbnail} alt="" onError={(e) => { e.target.style.display = 'none'; }} />
              <div className="inspector-play-btn" title="Play Video">▶</div>
              {video.duration && <span className="card-duration">{video.duration}</span>}
            </div>

            {/* Video Title */}
            <h3 className="inspector-video-title">{video.title}</h3>

            {/* Metadata Stats */}
            <div className="inspector-meta-row">
              <div className="inspector-meta-item">
                <span className="meta-label">Duration</span>
                <span className="meta-val">{video.duration || 'N/A'}</span>
              </div>
              <div className="inspector-meta-item">
                <span className="meta-label">Views</span>
                <span className="meta-val">{video.views || '0'}</span>
              </div>
              <div className="inspector-meta-item">
                <span className="meta-label">Watch Count</span>
                <span className="meta-val">{watchHistory?.count ? `${watchHistory.count}×` : 'Unwatched'}</span>
              </div>
            </div>

            {/* Quick Actions Row */}
            <div className="inspector-actions-grid">
              <button
                className="inspector-action-btn primary"
                onClick={() => playVideo(video)}
              >
                ▶ Play in Player
              </button>
              <button
                className="inspector-action-btn"
                onClick={() => copyVideoLink(video)}
              >
                📋 Copy Link
              </button>
              <a
                className="inspector-action-btn"
                href={video.url}
                target="_blank"
                rel="noreferrer noopener"
              >
                ↗ Open Source
              </a>
              <button
                className={`inspector-action-btn${isBlacklisted ? ' success' : ' danger'}`}
                onClick={() => toggleBlacklist(video.viewkey)}
              >
                {isBlacklisted ? '✓ Restore Video' : '🗑 Blacklist'}
              </button>
            </div>

            {/* Category Selector */}
            <div className="inspector-section">
              <label className="inspector-section-label">Category Assignment</label>
              <select
                className="inspector-select"
                value={currentCat}
                onChange={(e) => setCategory(video.viewkey, e.target.value)}
              >
                <option value="none">Uncategorized</option>
                {categoryTree.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.icon ? `${cat.icon} ` : ''}{cat.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Tags Section */}
            <div className="inspector-section">
              <label className="inspector-section-label">Tags</label>
              <div className="inspector-tags-list">
                {tags.map((tag) => (
                  <span key={tag} className="inspector-tag-pill">
                    #{tag}
                    <button
                      onClick={() => removeTag(video.viewkey, tag)}
                      title={`Remove #${tag}`}
                    >
                      ×
                    </button>
                  </span>
                ))}
                {tags.length === 0 && <span className="inspector-empty-hint">No tags assigned</span>}
              </div>
              <form onSubmit={handleAddTag} className="inspector-input-form">
                <input
                  type="text"
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  placeholder="Add a tag..."
                  className="inspector-input"
                />
                <button type="submit" className="inspector-btn-small">Add</button>
              </form>
            </div>

            {/* Playlists Section */}
            <div className="inspector-section">
              <label className="inspector-section-label">Playlists</label>
              <div className="inspector-playlists-list">
                {Object.entries(playlists).map(([name, items]) => {
                  const inList = items.includes(video.viewkey);
                  return (
                    <label key={name} className="inspector-checkbox-row">
                      <input
                        type="checkbox"
                        checked={inList}
                        onChange={() =>
                          inList
                            ? removeFromPlaylist(name, video.viewkey)
                            : addToPlaylist(name, video.viewkey)
                        }
                      />
                      <span>{name}</span>
                      <span className="count">({items.length})</span>
                    </label>
                  );
                })}
                {Object.keys(playlists).length === 0 && (
                  <span className="inspector-empty-hint">No playlists created yet</span>
                )}
              </div>
              <form onSubmit={handleCreatePlaylist} className="inspector-input-form">
                <input
                  type="text"
                  value={newPlaylist}
                  onChange={(e) => setNewPlaylist(e.target.value)}
                  placeholder="New playlist name..."
                  className="inspector-input"
                />
                <button type="submit" className="inspector-btn-small">Create</button>
              </form>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}

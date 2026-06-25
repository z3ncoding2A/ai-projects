import { useState } from 'react';
import useVideoStore from '../../stores/useVideoStore';

export default function VideoDetailsPanel({ video }) {
  const tags = useVideoStore((s) => s.tags[video.viewkey] || []);
  const addTag = useVideoStore((s) => s.addTag);
  const removeTag = useVideoStore((s) => s.removeTag);
  
  const playlists = useVideoStore((s) => s.playlists);
  const createPlaylist = useVideoStore((s) => s.createPlaylist);
  const addToPlaylist = useVideoStore((s) => s.addToPlaylist);
  const removeFromPlaylist = useVideoStore((s) => s.removeFromPlaylist);

  const [newTag, setNewTag] = useState('');
  const [newPlaylist, setNewPlaylist] = useState('');

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
    <div style={{ padding: '16px', borderTop: '1px solid var(--border)', background: 'var(--bg-card)' }}>
      {/* Title & Meta */}
      <h3 style={{ fontSize: '1rem', marginBottom: '8px', color: 'var(--text-primary)' }}>
        {video.title}
      </h3>
      <div style={{ display: 'flex', gap: '16px', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
        <span>⏱ {video.duration || 'N/A'}</span>
        <span>👁 {video.views || '0'}</span>
        <a href={video.url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none' }}>
          Open on Pornhub ↗
        </a>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Tags */}
        <div>
          <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>Tags</h4>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
            {tags.map((tag) => (
              <span key={tag} style={{
                background: 'var(--bg-surface)', padding: '4px 8px', borderRadius: '4px',
                fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '6px', border: '1px solid var(--border)'
              }}>
                #{tag}
                <button
                  onClick={() => removeTag(video.viewkey, tag)}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
                >×</button>
              </span>
            ))}
            {tags.length === 0 && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No tags added</span>}
          </div>
          <form onSubmit={handleAddTag} style={{ display: 'flex', gap: '6px' }}>
            <input
              type="text"
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              placeholder="Add tag..."
              style={{ flex: 1, padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg-deep)', color: 'var(--text-primary)', fontSize: '0.8rem' }}
            />
            <button type="submit" className="hero-btn secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>Add</button>
          </form>
        </div>

        {/* Playlists */}
        <div>
          <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>Playlists</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '8px' }}>
            {Object.entries(playlists).map(([name, items]) => {
              const inList = items.includes(video.viewkey);
              return (
                <label key={name} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.8rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={inList}
                    onChange={() => inList ? removeFromPlaylist(name, video.viewkey) : addToPlaylist(name, video.viewkey)}
                    style={{ cursor: 'pointer' }}
                  />
                  {name} <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>({items.length})</span>
                </label>
              );
            })}
            {Object.keys(playlists).length === 0 && <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>No playlists exist</span>}
          </div>
          <form onSubmit={handleCreatePlaylist} style={{ display: 'flex', gap: '6px' }}>
            <input
              type="text"
              value={newPlaylist}
              onChange={(e) => setNewPlaylist(e.target.value)}
              placeholder="New playlist..."
              style={{ flex: 1, padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--bg-deep)', color: 'var(--text-primary)', fontSize: '0.8rem' }}
            />
            <button type="submit" className="hero-btn secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>Create</button>
          </form>
        </div>
      </div>
    </div>
  );
}

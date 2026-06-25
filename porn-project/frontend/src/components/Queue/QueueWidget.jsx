import { useState } from 'react';
import useVideoStore from '../../stores/useVideoStore';

export default function QueueWidget() {
  const queue = useVideoStore((s) => s.queue);
  const removeFromQueue = useVideoStore((s) => s.removeFromQueue);
  const playFromQueue = useVideoStore((s) => s.playFromQueue);
  const clearQueue = useVideoStore((s) => s.clearQueue);
  const currentVideo = useVideoStore((s) => s.currentVideo);

  const [expanded, setExpanded] = useState(false);

  if (queue.length === 0 || !currentVideo) return null;

  return (
    <div className="queue-widget">
      <div className="queue-header" onClick={() => setExpanded(!expanded)}>
        <span>Video Queue ({queue.length})</span>
        <span style={{
          transition: 'transform 0.3s',
          transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
        }}>
          ▲
        </span>
      </div>

      {/* Collapsed: show next up */}
      {!expanded && (
        <div
          className="queue-item"
          onClick={() => setExpanded(true)}
          style={{ cursor: 'pointer' }}
        >
          <img src={queue[0].thumbnail} alt="" onError={(e) => { e.target.style.display = 'none'; }} />
          <div className="queue-item-info">
            <div className="queue-item-title">{queue[0].title}</div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
              Up Next · {queue.length} in queue
            </div>
          </div>
        </div>
      )}

      {/* Expanded: full list */}
      {expanded && (
        <div className="queue-list" style={{ maxHeight: 300 }}>
          {queue.map((vid) => (
            <div key={vid.viewkey} className="queue-item">
              <img
                src={vid.thumbnail}
                alt=""
                onClick={() => playFromQueue(vid.viewkey)}
                onError={(e) => { e.target.style.display = 'none'; }}
              />
              <div
                className="queue-item-info"
                onClick={() => playFromQueue(vid.viewkey)}
              >
                <div className="queue-item-title">{vid.title}</div>
              </div>
              <div className="queue-item-actions">
                <button
                  className="queue-action-btn play"
                  onClick={() => playFromQueue(vid.viewkey)}
                  title="Play"
                >
                  ▶
                </button>
                <button
                  className="queue-action-btn"
                  onClick={() => removeFromQueue(vid.viewkey)}
                  title="Remove"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
          <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
            <button
              className="queue-action-btn"
              onClick={clearQueue}
              style={{ width: '100%', textAlign: 'center', padding: '6px' }}
            >
              Clear Queue
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState } from 'react';
import useVideoStore from '../../stores/useVideoStore';

export default function AdvancedSearchModal({ onClose }) {
  const advancedSearch = useVideoStore((s) => s.advancedSearch);
  const setAdvancedSearch = useVideoStore((s) => s.setAdvancedSearch);

  const [minViews, setMinViews] = useState(advancedSearch.minViews);
  const [minDuration, setMinDuration] = useState(advancedSearch.minDuration);
  const [regex, setRegex] = useState(advancedSearch.regex);

  const applyFilters = () => {
    setAdvancedSearch({ minViews, minDuration, regex });
    onClose();
  };

  const clearFilters = () => {
    setAdvancedSearch({ minViews: '', minDuration: '', regex: '' });
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 400 }}>
        <h2>🔍 Advanced Search</h2>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>Minimum Views</label>
            <input 
              type="number" 
              value={minViews} 
              onChange={(e) => setMinViews(e.target.value)} 
              placeholder="e.g. 100000"
              style={{ width: '100%', padding: '8px', borderRadius: '6px', background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'white' }}
            />
          </div>
          
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>Minimum Duration (minutes)</label>
            <input 
              type="number" 
              value={minDuration} 
              onChange={(e) => setMinDuration(e.target.value)} 
              placeholder="e.g. 10"
              style={{ width: '100%', padding: '8px', borderRadius: '6px', background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'white' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>Title Regex</label>
            <input 
              type="text" 
              value={regex} 
              onChange={(e) => setRegex(e.target.value)} 
              placeholder="e.g. ^public.*"
              style={{ width: '100%', padding: '8px', borderRadius: '6px', background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'white', fontFamily: 'monospace' }}
            />
          </div>
        </div>

        <div className="modal-footer" style={{ justifyContent: 'space-between' }}>
          <button className="modal-btn danger" onClick={clearFilters}>Clear All</button>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="modal-btn" onClick={onClose}>Cancel</button>
            <button className="modal-btn primary" onClick={applyFilters}>Apply Filters</button>
          </div>
        </div>
      </div>
    </div>
  );
}

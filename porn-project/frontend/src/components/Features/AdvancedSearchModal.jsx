import { useState } from 'react';
import toast from 'react-hot-toast';
import useVideoStore from '../../stores/useVideoStore';

export default function AdvancedSearchModal({ onClose }) {
  const advancedSearch = useVideoStore((s) => s.advancedSearch);
  const setAdvancedSearch = useVideoStore((s) => s.setAdvancedSearch);
  const filterPresets = useVideoStore((s) => s.filterPresets);
  const saveFilterPreset = useVideoStore((s) => s.saveFilterPreset);
  const applyFilterPreset = useVideoStore((s) => s.applyFilterPreset);
  const deleteFilterPreset = useVideoStore((s) => s.deleteFilterPreset);

  const [minViews, setMinViews] = useState(advancedSearch.minViews);
  const [minDuration, setMinDuration] = useState(advancedSearch.minDuration);
  const [regex, setRegex] = useState(advancedSearch.regex);
  const [presetName, setPresetName] = useState('');

  const applyFilters = () => {
    setAdvancedSearch({ minViews, minDuration, regex });
    onClose();
  };

  const clearFilters = () => {
    setAdvancedSearch({ minViews: '', minDuration: '', regex: '' });
    onClose();
  };

  const handleSavePreset = () => {
    const name = presetName.trim();
    if (!name) return;
    // Save whatever is currently applied (searchQuery + the store's advancedSearch),
    // not just the not-yet-applied draft fields in this form.
    setAdvancedSearch({ minViews, minDuration, regex });
    saveFilterPreset(name);
    setPresetName('');
    toast.success(`Saved search "${name}"`);
  };

  const handleApplyPreset = (name) => {
    applyFilterPreset(name);
    const preset = filterPresets[name];
    if (preset) {
      setMinViews(preset.minViews || '');
      setMinDuration(preset.minDuration || '');
      setRegex(preset.regex || '');
    }
    onClose();
  };

  const presetNames = Object.keys(filterPresets).sort();

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

        {presetNames.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Saved Searches
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {presetNames.map((name) => (
                <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <button
                    className="modal-btn"
                    style={{ flex: 1, textAlign: 'left' }}
                    onClick={() => handleApplyPreset(name)}
                  >
                    {name}
                  </button>
                  <button
                    className="modal-btn"
                    style={{ color: '#e74c3c', padding: '6px 10px' }}
                    title="Delete saved search"
                    onClick={() => deleteFilterPreset(name)}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
          <input
            type="text"
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
            placeholder="Name this search to save it..."
            style={{ flex: 1, padding: '8px', borderRadius: '6px', background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'white' }}
          />
          <button className="modal-btn" onClick={handleSavePreset} disabled={!presetName.trim()}>
            Save
          </button>
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

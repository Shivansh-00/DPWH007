import React from 'react';
import './AnomalyPanel.css';

export default function AnomalyPanel({ anomalyMode, weatherActive, onSetAnomaly, onToggleWeather }) {
  const modes = [
    { id: 'NORMAL', label: 'Normal', icon: '🟢', class: 'normal' },
    { id: 'SLOW', label: 'Slow Traffic', icon: '🟡', class: 'slow' },
    { id: 'FAST', label: 'Fast Traffic', icon: '🟣', class: 'fast' },
    { id: 'STOP', label: 'All Stop', icon: '🔴', class: 'stop' }
  ];

  return (
    <div className="anomaly-panel">
      <div className="anomaly-title">Simulation Environment</div>
      
      <div className="anomaly-controls">
        <div className="anomaly-group">
          <span className="anomaly-label">Traffic Mode</span>
          <div className="anomaly-btns">
            {modes.map(mode => (
              <button
                key={mode.id}
                className={`anomaly-btn ${mode.class} ${anomalyMode === mode.id ? 'active' : ''}`}
                onClick={() => onSetAnomaly(mode.id)}
              >
                <span>{mode.icon}</span> {mode.label}
              </button>
            ))}
          </div>
        </div>

        <div className="anomaly-group">
          <span className="anomaly-label">Weather</span>
          <button 
            className={`weather-btn ${weatherActive ? 'active' : ''}`}
            onClick={onToggleWeather}
          >
            <span>{weatherActive ? '⛈️' : '☀️'}</span>
            {weatherActive ? 'Severe Storm Active (Click to Clear)' : 'Clear Skies (Click to Spawn Storm)'}
          </button>
        </div>
      </div>
    </div>
  );
}

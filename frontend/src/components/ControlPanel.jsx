import './ControlPanel.css';

export default function ControlPanel({ isRunning, isPaused, speed, onPause, onResume, onReset, onSpeedChange }) {
  return (
    <div className="control-panel">
      <div className="ctrl-group">
        <span className="ctrl-label">Playback</span>
        <div className="ctrl-buttons">
          {isRunning && !isPaused && (
            <button className="ctrl-btn ctrl-pause" onClick={onPause}>
              <span>⏸</span> Pause
            </button>
          )}
          {isRunning && isPaused && (
            <button className="ctrl-btn ctrl-resume" onClick={onResume}>
              <span>▶️</span> Resume
            </button>
          )}
          <button className="ctrl-btn ctrl-reset" onClick={onReset}>
            <span>🔄</span> Reset
          </button>
        </div>
      </div>

      <div className="ctrl-group">
        <span className="ctrl-label">Speed</span>
        <div className="ctrl-speed-btns">
          {[0.5, 1, 2, 5, 10, 20].map(s => (
            <button
              key={s}
              className={`ctrl-speed-btn ${speed === s ? 'active' : ''}`}
              onClick={() => onSpeedChange(s)}
            >
              {s}x
            </button>
          ))}
        </div>
      </div>

      <div className="ctrl-status">
        <span className={`status-dot ${isRunning ? (isPaused ? 'paused' : 'running') : 'stopped'}`}></span>
        <span className="status-text">
          {isRunning ? (isPaused ? 'Paused' : 'Running') : 'Stopped'}
        </span>
      </div>
    </div>
  );
}

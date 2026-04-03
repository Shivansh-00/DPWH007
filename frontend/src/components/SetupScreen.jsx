import { useState } from 'react';
import './SetupScreen.css';

const SHIP_TYPE_PRESETS = {
  Container: { avgLength: 300, avgDraft: 14, equipment: ['Cranes'] },
  'Bulk Carrier': { avgLength: 230, avgDraft: 12, equipment: ['Cranes'] },
  Tanker: { avgLength: 280, avgDraft: 16, equipment: ['Pipes'] },
  'Roll-On': { avgLength: 180, avgDraft: 8, equipment: ['Ramps'] },
  Food: { avgLength: 160, avgDraft: 10, equipment: ['Cranes', 'Refrigeration'] },
};

const SCENARIOS = [
  { id: 'mixed', name: 'Mixed Traffic', desc: 'Realistic mix of all ship types arriving at various intervals', icon: '🚢' },
  { id: 'weather_cluster', name: 'Weather Cluster', desc: 'Storm causes ships to slow down, then arrive simultaneously', icon: '🌊' },
  { id: 'port_congestion', name: 'Port Congestion', desc: 'All berths occupied — tests deadlock handling', icon: '⚓' },
  { id: 'emergency', name: 'Emergency Override', desc: 'Tanker breakdown forces priority reshuffling', icon: '🚨' },
];

const POLICIES = [
  { id: 'SCORING', name: 'Dynamic Scoring', desc: 'Weighted multi-factor priority' },
  { id: 'FCFS', name: 'First Come First Serve', desc: 'Simple arrival order' },
  { id: 'PRIORITY_ONLY', name: 'Cargo Priority Only', desc: 'Fixed type-based priority' },
];

export default function SetupScreen({ onStart }) {
  const [berthCount, setBerthCount] = useState(6);
  const [shipCount, setShipCount] = useState(15);
  const [scenario, setScenario] = useState('mixed');
  const [policy, setPolicy] = useState('SCORING');
  const [speed, setSpeed] = useState(1);
  const [seed, setSeed] = useState(42);
  const [stormIntensity, setStormIntensity] = useState(0.8);
  const [congestionLevel, setCongestionLevel] = useState(0.9);
  const [isLaunching, setIsLaunching] = useState(false);

  const handleStart = () => {
    setIsLaunching(true);
    setTimeout(() => {
      onStart({
        berth_count: berthCount,
        ship_count: shipCount,
        scenario,
        policy_mode: policy,
        playback_speed: speed,
        seed,
        storm_intensity: stormIntensity,
        congestion_level: congestionLevel,
      });
    }, 800);
  };

  return (
    <div className="setup-screen">
      <div className="setup-bg-ocean">
        <div className="wave wave-1"></div>
        <div className="wave wave-2"></div>
        <div className="wave wave-3"></div>
      </div>

      <div className={`setup-container ${isLaunching ? 'launching' : ''}`}>
        <header className="setup-header">
          <div className="setup-logo">
            <span className="logo-icon">⚓</span>
            <div>
              <h1>Smart Docking System</h1>
              <p className="subtitle">Decision Intelligence Engine</p>
            </div>
          </div>
        </header>

        <div className="setup-grid">
          {/* Scenario Selection */}
          <section className="setup-section scenario-section">
            <h2 className="section-title">
              <span className="section-icon">📋</span>
              Scenario
            </h2>
            <div className="scenario-cards">
              {SCENARIOS.map(s => (
                <button
                  key={s.id}
                  className={`scenario-card ${scenario === s.id ? 'active' : ''}`}
                  onClick={() => setScenario(s.id)}
                >
                  <span className="scenario-icon">{s.icon}</span>
                  <span className="scenario-name">{s.name}</span>
                  <span className="scenario-desc">{s.desc}</span>
                </button>
              ))}
            </div>
          </section>

          {/* Port Configuration */}
          <section className="setup-section">
            <h2 className="section-title">
              <span className="section-icon">🏗️</span>
              Port Configuration
            </h2>
            <div className="config-group">
              <label>
                <span className="config-label">Number of Berths</span>
                <div className="input-with-hint">
                  <input type="range" min="2" max="12" value={berthCount}
                    onChange={e => setBerthCount(Number(e.target.value))} />
                  <span className="range-value">{berthCount}</span>
                </div>
              </label>
              <label>
                <span className="config-label">Incoming Ships</span>
                <div className="input-with-hint">
                  <input type="range" min="5" max="40" value={shipCount}
                    onChange={e => setShipCount(Number(e.target.value))} />
                  <span className="range-value">{shipCount}</span>
                </div>
              </label>
              <label>
                <span className="config-label">Random Seed</span>
                <input type="number" className="text-input" value={seed}
                  onChange={e => setSeed(Number(e.target.value))} />
              </label>
            </div>

            {/* Scenario-specific params */}
            {scenario === 'weather_cluster' && (
              <div className="config-group conditional-config">
                <label>
                  <span className="config-label">Storm Intensity</span>
                  <div className="input-with-hint">
                    <input type="range" min="0.1" max="1" step="0.1" value={stormIntensity}
                      onChange={e => setStormIntensity(Number(e.target.value))} />
                    <span className="range-value">{(stormIntensity * 100).toFixed(0)}%</span>
                  </div>
                </label>
              </div>
            )}
            {scenario === 'port_congestion' && (
              <div className="config-group conditional-config">
                <label>
                  <span className="config-label">Congestion Level</span>
                  <div className="input-with-hint">
                    <input type="range" min="0.5" max="1" step="0.05" value={congestionLevel}
                      onChange={e => setCongestionLevel(Number(e.target.value))} />
                    <span className="range-value">{(congestionLevel * 100).toFixed(0)}%</span>
                  </div>
                </label>
              </div>
            )}
          </section>

          {/* Policy Selection */}
          <section className="setup-section">
            <h2 className="section-title">
              <span className="section-icon">🧠</span>
              Queue Policy
            </h2>
            <div className="policy-cards">
              {POLICIES.map(p => (
                <button
                  key={p.id}
                  className={`policy-card ${policy === p.id ? 'active' : ''}`}
                  onClick={() => setPolicy(p.id)}
                >
                  <span className="policy-name">{p.name}</span>
                  <span className="policy-desc">{p.desc}</span>
                </button>
              ))}
            </div>
          </section>

          {/* Speed */}
          <section className="setup-section">
            <h2 className="section-title">
              <span className="section-icon">⏱️</span>
              Playback Speed
            </h2>
            <div className="speed-buttons">
              {[0.5, 1, 2, 5, 10].map(s => (
                <button key={s}
                  className={`speed-btn ${speed === s ? 'active' : ''}`}
                  onClick={() => setSpeed(s)}
                >
                  {s}x
                </button>
              ))}
            </div>
          </section>

          {/* Ship Type Reference */}
          <section className="setup-section reference-section">
            <h2 className="section-title">
              <span className="section-icon">📐</span>
              Ship Type Reference
            </h2>
            <div className="reference-table">
              <div className="ref-header">
                <span>Type</span><span>Avg Length</span><span>Avg Draft</span><span>Equipment</span>
              </div>
              {Object.entries(SHIP_TYPE_PRESETS).map(([type, info]) => (
                <div key={type} className="ref-row">
                  <span className="ref-type">
                    <span className={`type-dot type-${type.toLowerCase().replace(/\s/g, '-')}`}></span>
                    {type}
                  </span>
                  <span>{info.avgLength}m</span>
                  <span>{info.avgDraft}m</span>
                  <span className="ref-equip">{info.equipment.join(', ')}</span>
                </div>
              ))}
            </div>
          </section>
        </div>

        <button className={`start-button ${isLaunching ? 'launching' : ''}`} onClick={handleStart}>
          <span className="start-icon">🚀</span>
          <span>{isLaunching ? 'Launching Simulation...' : 'Start Simulation'}</span>
        </button>
      </div>
    </div>
  );
}

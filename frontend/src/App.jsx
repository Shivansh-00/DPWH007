import { useState, useEffect, useRef, useCallback } from 'react';
import SetupScreen from './components/SetupScreen';
import SimulationBoard from './components/SimulationBoard';
import MetricsDashboard from './components/MetricsDashboard';
import ControlPanel from './components/ControlPanel';
import AIAssistant from './components/AIAssistant';
import AnomalyPanel from './components/AnomalyPanel';
import './App.css';

const API_BASE = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/simulation';

function App() {
  const [screen, setScreen] = useState('setup'); // 'setup' | 'simulation'
  const [ships, setShips] = useState([]);
  const [berths, setBerths] = useState([]);
  const [events, setEvents] = useState([]);
  const [metrics, setMetrics] = useState({});
  const [isRunning, setIsRunning] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [anomalyMode, setAnomalyMode] = useState('NORMAL');
  const [weatherCenter, setWeatherCenter] = useState(null);
  const [weatherActive, setWeatherActive] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');

  const wsRef = useRef(null);

  // ─── WebSocket Connection ────────────────────────────────────────────
  const connectWebSocket = useCallback(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus('connected');
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        setShips(payload.ships || []);
        setBerths(payload.berths || []);
        setEvents(payload.events || []);
        setMetrics(payload.metrics || {});
        if (payload.anomaly_mode) setAnomalyMode(payload.anomaly_mode);
        setWeatherCenter(payload.weather_center || null);
        setWeatherActive(!!payload.weather_center);
      } catch (e) {
        console.error('Failed to parse WS message:', e);
      }
    };

    ws.onclose = () => {
      setConnectionStatus('disconnected');
      console.log('WebSocket disconnected');
    };

    ws.onerror = (err) => {
      setConnectionStatus('error');
      console.error('WebSocket error:', err);
    };
  }, [WS_URL, setShips, setBerths, setEvents, setMetrics, setAnomalyMode, setWeatherCenter, setWeatherActive]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // ─── API Calls ───────────────────────────────────────────────────────
  const startSimulation = async (config) => {
    try {
      // Connect WebSocket first
      connectWebSocket();

      // Wait a beat for WS to connect
      await new Promise(r => setTimeout(r, 500));

      const res = await fetch(`${API_BASE}/api/simulation/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (res.ok) {
        setIsRunning(true);
        setIsPaused(false);
        setSpeed(config.playback_speed);
        setScreen('simulation');
      }
    } catch (err) {
      console.error('Failed to start simulation:', err);
      // Still switch to simulation view for demo
      setScreen('simulation');
    }
  };

  const sendCommand = async (endpoint, body = {}) => {
    try {
      await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
    } catch (err) {
      console.error(`Failed: ${endpoint}`, err);
    }
  };

  const handlePause = () => {
    sendCommand('/api/simulation/pause');
    setIsPaused(true);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: 'pause' }));
    }
  };

  const handleResume = () => {
    sendCommand('/api/simulation/resume');
    setIsPaused(false);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: 'resume' }));
    }
  };

  const handleReset = () => {
    sendCommand('/api/simulation/reset');
    setIsRunning(false);
    setIsPaused(false);
    setShips([]);
    setBerths([]);
    setEvents([]);
    setMetrics({});
    setScreen('setup');
    if (wsRef.current) wsRef.current.close();
  };

  const handleSpeedChange = (newSpeed) => {
    setSpeed(newSpeed);
    sendCommand('/api/simulation/speed', { speed: newSpeed });
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: 'speed', value: newSpeed }));
    }
  };

  const handleSetAnomaly = (mode) => {
    setAnomalyMode(mode);
    sendCommand('/api/simulation/anomaly', { mode });
  };

  const handleToggleWeather = () => {
    const nextActive = !weatherActive;
    setWeatherActive(nextActive);
    if (nextActive) {
      // Spawn storm in a common lane (middle-ish)
      sendCommand('/api/simulation/weather', {
        center: { x: 400, y: 300 },
        radius: 150
      });
    } else {
      sendCommand('/api/simulation/weather', { center: null });
    }
  };

  // ─── Render ──────────────────────────────────────────────────────────
  if (screen === 'setup') {
    return <SetupScreen onStart={startSimulation} />;
  }

  return (
    <div className="simulation-view">
      {/* Header */}
      <header className="sim-header">
        <div className="sim-header-left">
          <span className="sim-logo-icon">⚓</span>
          <h1 className="sim-title">Smart Docking System</h1>
          <span className={`conn-badge conn-${connectionStatus}`}>
            {connectionStatus === 'connected' ? '● Connected' : '○ Disconnected'}
          </span>
        </div>
        <ControlPanel
          isRunning={isRunning}
          isPaused={isPaused}
          speed={speed}
          onPause={handlePause}
          onResume={handleResume}
          onReset={handleReset}
          onSpeedChange={handleSpeedChange}
        />
      </header>

      {/* Main Content */}
      <main className="sim-main">
        <div className="sim-board-wrapper">
          <SimulationBoard
            ships={ships}
            berths={berths}
            events={events}
            clockMs={metrics.clock_ms || 0}
            weatherCenter={weatherCenter}
            anomalyMode={anomalyMode}
          />
        </div>

        <aside className="sim-sidebar">
          <AnomalyPanel 
            anomalyMode={anomalyMode}
            weatherActive={weatherActive}
            onSetAnomaly={handleSetAnomaly}
            onToggleWeather={handleToggleWeather}
          />
          <MetricsDashboard metrics={metrics} ships={ships} />

          {/* Queue View */}
          <div className="queue-panel glass-card">
            <h3 className="queue-title">
              <span>📋</span> Entry Queue
            </h3>
            <div className="queue-list">
              {ships
                .filter(s => s.zone === 'WAITING' || s.zone === 'CLEARED_TO_ENTER')
                .sort((a, b) => (b.priority_score || 0) - (a.priority_score || 0))
                .map(ship => (
                  <div key={ship.ship_id} className={`queue-item zone-${ship.zone?.toLowerCase()}`}>
                    <div className="qi-header">
                      <span className="qi-id">#{ship.ship_id}</span>
                      <span className={`qi-type qi-type-${ship.ship_type?.toLowerCase().replace(/\s/g, '-')}`}>
                        {ship.ship_type}
                      </span>
                      <span className="qi-score">{(ship.priority_score || 0).toFixed(3)}</span>
                    </div>
                    <div className="qi-details">
                      <span>ETA: {(ship.eta_minutes || 0).toFixed(0)}m</span>
                      <span>Fuel: {((ship.fuel_criticality || 0) * 100).toFixed(0)}%</span>
                      <span className={`qi-zone qi-zone-${ship.zone?.toLowerCase()}`}>
                        {ship.zone?.replace(/_/g, ' ')}
                      </span>
                    </div>
                    {ship.assignment_reason && (
                      <div className="qi-reason">{ship.assignment_reason}</div>
                    )}
                  </div>
                ))}
              {ships.filter(s => s.zone === 'WAITING' || s.zone === 'CLEARED_TO_ENTER').length === 0 && (
                <div className="queue-empty">No ships in queue</div>
              )}
            </div>
          </div>
        </aside>
      </main>

      <AIAssistant 
        ships={ships} 
        metrics={metrics} 
        anomalyMode={anomalyMode} 
        weatherActive={weatherActive} 
      />
    </div>
  );
}

export default App;

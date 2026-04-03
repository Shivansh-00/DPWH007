import './MetricsDashboard.css';

const SHIP_TYPE_COLORS = {
  Container: '#3b82f6',
  'Bulk Carrier': '#8b5cf6',
  Tanker: '#f97316',
  'Roll-On': '#14b8a6',
  Food: '#22c55e',
};

export default function MetricsDashboard({ metrics, ships }) {
  if (!metrics) return null;

  // Count ships by zone
  const zoneCounts = {};
  const typeCounts = {};
  if (ships) {
    ships.forEach(s => {
      zoneCounts[s.zone] = (zoneCounts[s.zone] || 0) + 1;
      typeCounts[s.ship_type] = (typeCounts[s.ship_type] || 0) + 1;
    });
  }

  const formatTime = (ms) => {
    const totalSec = Math.floor(ms / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    return `${h}h ${m}m`;
  };

  const handleExport = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({metrics, zoneCounts, typeCounts}, null, 2));
    const dt = new Date().toISOString().replace(/:/g, '-');
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", `sim_metrics_${dt}.json`);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
  };

  return (
    <div className="metrics-dashboard">
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
        <h3 className="metrics-title" style={{margin: 0}}>
          <span className="metrics-icon">📊</span>
          Performance Metrics
        </h3>
        <button onClick={handleExport} style={{
          background: 'var(--bg-surface-elevated)', border: '1px solid var(--border-subtle)', 
          color: 'var(--text-accent)', padding: '4px 8px', borderRadius: '4px', cursor: 'pointer', fontSize: '0.75rem'
        }}>
          💾 Export
        </button>
      </div>

      {/* Primary KPIs */}
      <div className="kpi-grid">
        <KpiCard
          label="Ships Processed"
          value={metrics.ships_processed || 0}
          icon="✅"
          color="var(--accent-green)"
        />
        <KpiCard
          label="Avg Wait Time"
          value={`${(metrics.avg_wait_min || 0).toFixed(1)}m`}
          icon="⏳"
          color="var(--accent-amber)"
        />
        <KpiCard
          label="Berth Utilization"
          value={`${(metrics.berth_utilization_pct || 0).toFixed(0)}%`}
          icon="🏗️"
          color="var(--accent-blue)"
        />
        <KpiCard
          label="Throughput/hr"
          value={(metrics.throughput_per_hr || 0).toFixed(1)}
          icon="📈"
          color="var(--accent-cyan)"
        />
        <KpiCard
          label="Fuel Wastage"
          value={(metrics.fuel_wastage || 0).toFixed(2)}
          icon="⛽"
          color="var(--accent-orange)"
        />
        <KpiCard
          label="Reshuffles"
          value={metrics.reshuffles || 0}
          icon="🔄"
          color="var(--accent-purple)"
        />
        <KpiCard
          label="Deadlocks"
          value={metrics.deadlocks || 0}
          icon="🚫"
          color="var(--accent-red)"
        />
        <KpiCard
          label="Queue Length"
          value={metrics.queue_length || 0}
          icon="📋"
          color="var(--accent-teal)"
        />
      </div>

      {/* Ship Distribution */}
      <div className="distribution-section">
        <h4 className="dist-title">Ship Distribution by Zone</h4>
        <div className="zone-bars">
          {Object.entries(zoneCounts).map(([zone, count]) => (
            <div key={zone} className="zone-bar-row">
              <span className="zone-label">{zone.replace(/_/g, ' ')}</span>
              <div className="zone-bar-track">
                <div
                  className="zone-bar-fill"
                  style={{ width: `${(count / (ships?.length || 1)) * 100}%` }}
                />
              </div>
              <span className="zone-count">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Ship Type Breakdown */}
      <div className="distribution-section">
        <h4 className="dist-title">Fleet Composition</h4>
        <div className="type-chips">
          {Object.entries(typeCounts).map(([type, count]) => (
            <div key={type} className="type-chip" style={{ borderColor: SHIP_TYPE_COLORS[type] || '#64748b' }}>
              <span className="chip-dot" style={{ backgroundColor: SHIP_TYPE_COLORS[type] || '#64748b' }}></span>
              <span className="chip-label">{type}</span>
              <span className="chip-count">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Sim Clock */}
      <div className="sim-clock">
        <span className="clock-label">Sim Time</span>
        <span className="clock-value">{formatTime(metrics.clock_ms || 0)}</span>
        <span className="clock-speed">{metrics.speed || 1}x</span>
      </div>
    </div>
  );
}

function KpiCard({ label, value, icon, color }) {
  return (
    <div className="kpi-card">
      <div className="kpi-icon" style={{ color }}>{icon}</div>
      <div className="kpi-value" style={{ color }}>{value}</div>
      <div className="kpi-label">{label}</div>
    </div>
  );
}

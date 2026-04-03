import { useRef, useEffect, useCallback, useState } from 'react';
import './SimulationBoard.css';

const SHIP_COLORS = {
  Container: '#3b82f6',
  'Bulk Carrier': '#8b5cf6',
  Tanker: '#f97316',
  'Roll-On': '#14b8a6',
  Food: '#22c55e',
};

const ZONE_LABELS = {
  OPEN_SEA: 'Open Sea',
  APPROACHING: 'Approaching',
  WAITING: 'Anchorage',
  CLEARED_TO_ENTER: 'Cleared',
  IN_CHANNEL: 'In Channel',
  DOCKED: 'Docked',
  COMPLETED: 'Completed',
};

const SHIP_ICONS = {
  Container: '📦',
  'Bulk Carrier': '⛏️',
  Tanker: '🛢️',
  'Roll-On': '🚗',
  Food: '🍎',
};

export default function SimulationBoard({ ships, berths, events, clockMs }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const mousePosRef = useRef(null);

  const drawSimulation = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const rect = container.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';

    const ctx = canvas.getContext('2d');
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    const W = rect.width;
    const H = rect.height;

    // ─── Clear ─────────────────────────────────────────
    ctx.clearRect(0, 0, W, H);

    // ─── Background gradient (ocean) ───────────────────
    const bgGrad = ctx.createLinearGradient(0, 0, W, 0);
    bgGrad.addColorStop(0, '#0c1929');
    bgGrad.addColorStop(0.45, '#0f2744');
    bgGrad.addColorStop(0.7, '#1a2e4a');
    bgGrad.addColorStop(1, '#243b53');
    ctx.fillStyle = bgGrad;
    ctx.fillRect(0, 0, W, H);

    // ─── Zone markers ──────────────────────────────────
    const boundaryX = W * 0.4;
    const channelX = W * 0.7;
    const dockX = W * 0.88;

    // Zone divider lines
    ctx.setLineDash([8, 8]);

    // Boundary line
    ctx.strokeStyle = 'rgba(6, 182, 212, 0.3)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(boundaryX, 0);
    ctx.lineTo(boundaryX, H);
    ctx.stroke();

    // Channel line
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.3)';
    ctx.beginPath();
    ctx.moveTo(channelX, 0);
    ctx.lineTo(channelX, H);
    ctx.stroke();

    ctx.setLineDash([]);

    // Zone labels
    ctx.font = '600 11px Inter, sans-serif';
    ctx.textAlign = 'center';

    ctx.fillStyle = 'rgba(6, 182, 212, 0.5)';
    ctx.fillText('OPEN SEA', boundaryX * 0.45, 20);

    ctx.fillStyle = 'rgba(6, 182, 212, 0.6)';
    ctx.fillText('⚓ BOUNDARY', boundaryX, 20);

    ctx.fillStyle = 'rgba(96, 165, 250, 0.5)';
    ctx.fillText('ANCHORAGE', (boundaryX + channelX) / 2, 20);

    ctx.fillStyle = 'rgba(245, 158, 11, 0.5)';
    ctx.fillText('CHANNEL ENTRY', channelX, 20);

    ctx.fillStyle = 'rgba(34, 197, 94, 0.5)';
    ctx.fillText('PORT CHANNEL', (channelX + dockX) / 2, 20);

    // ─── Dock (right side) ─────────────────────────────
    ctx.fillStyle = '#1e3a5f';
    ctx.fillRect(dockX - 4, 0, W - dockX + 4, H);
    ctx.strokeStyle = 'rgba(34, 197, 94, 0.4)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(dockX, 0);
    ctx.lineTo(dockX, H);
    ctx.stroke();

    ctx.fillStyle = 'rgba(34, 197, 94, 0.6)';
    ctx.font = '700 12px Inter, sans-serif';
    ctx.fillText('DOCK', dockX + (W - dockX) / 2, 20);

    // ─── Draw Berths ───────────────────────────────────
    if (berths && berths.length > 0) {
      const berthH = Math.min(60, (H - 80) / berths.length);
      const berthGap = 8;
      const totalBerthH = berths.length * (berthH + berthGap);
      const berthStartY = (H - totalBerthH) / 2 + 20;

      berths.forEach((berth, i) => {
        const by = berthStartY + i * (berthH + berthGap);
        const bx = dockX + 8;
        const bw = W - dockX - 20;

        // Berth background
        const isOccupied = berth.status === 'Occupied';
        ctx.fillStyle = isOccupied ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.1)';
        ctx.strokeStyle = isOccupied ? 'rgba(239, 68, 68, 0.4)' : 'rgba(34, 197, 94, 0.3)';
        ctx.lineWidth = 1.5;
        roundRect(ctx, bx, by, bw, berthH, 6);
        ctx.fill();
        ctx.stroke();

        // Berth label
        ctx.fillStyle = isOccupied ? '#fca5a5' : '#86efac';
        ctx.font = '600 10px Inter, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`B${berth.berth_id}`, bx + 6, by + 14);

        // Equipment icons
        ctx.font = '9px Inter, sans-serif';
        ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
        const eqText = (berth.equipment_types || []).join(' · ');
        ctx.fillText(eqText, bx + 6, by + berthH - 8);

        // Progress bar if occupied
        if (isOccupied && berth.cargo_processed_pct > 0) {
          const barW = bw - 12;
          const barH = 4;
          const barY = by + berthH / 2 + 4;
          ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
          roundRect(ctx, bx + 6, barY, barW, barH, 2);
          ctx.fill();
          ctx.fillStyle = '#22c55e';
          roundRect(ctx, bx + 6, barY, barW * (berth.cargo_processed_pct / 100), barH, 2);
          ctx.fill();
        }

        // Docked ship name
        if (isOccupied) {
          const dockedShip = ships?.find(s => s.ship_id === berth.currently_docked_ship_id);
          if (dockedShip) {
            ctx.fillStyle = '#e2e8f0';
            ctx.font = '500 9px Inter, sans-serif';
            ctx.fillText(`${SHIP_ICONS[dockedShip.ship_type] || '🚢'} #${dockedShip.ship_id}`, bx + 30, by + 14);
          }
        }
      });
    }

    // ─── Draw Ships ────────────────────────────────────
    if (ships && ships.length > 0) {
      const activeShips = ships.filter(s => s.zone !== 'COMPLETED' && s.zone !== 'DOCKED');

      activeShips.forEach(ship => {
        let sx, sy;
        const color = SHIP_COLORS[ship.ship_type] || '#94a3b8';

        // Position ships based on zone
        switch (ship.zone) {
          case 'OPEN_SEA':
            sx = (ship.position_x / 500) * (boundaryX * 0.8);
            sy = ship.position_y % (H - 60) + 30;
            break;
          case 'APPROACHING':
            sx = boundaryX * 0.6 + (ship.position_x / 500) * (boundaryX * 0.4);
            sy = ship.position_y % (H - 60) + 30;
            break;
          case 'WAITING':
            sx = boundaryX + 20 + ((ship.ship_id * 37) % 120);
            sy = 40 + ((ship.ship_id * 53) % (H - 80));
            break;
          case 'CLEARED_TO_ENTER':
            sx = channelX - 30;
            sy = 40 + ((ship.ship_id * 53) % (H - 80));
            break;
          case 'IN_CHANNEL':
            sx = channelX + 20 + ((ship.ship_id * 31) % 80);
            sy = 40 + ((ship.ship_id * 47) % (H - 80));
            break;
          default:
            sx = 50;
            sy = 50;
        }

        // Ship glow
        ctx.shadowColor = color;
        ctx.shadowBlur = 12;

        // Ship body (triangle pointing right)
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(sx + 18, sy);
        ctx.lineTo(sx - 8, sy - 8);
        ctx.lineTo(sx - 8, sy + 8);
        ctx.closePath();
        ctx.fill();

        ctx.shadowBlur = 0;

        // Ship label
        ctx.fillStyle = '#e2e8f0';
        ctx.font = '500 8px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`#${ship.ship_id}`, sx + 4, sy - 12);

        // Priority score badge (for WAITING ships)
        if (ship.zone === 'WAITING' || ship.zone === 'CLEARED_TO_ENTER') {
          ctx.fillStyle = 'rgba(0,0,0,0.6)';
          roundRect(ctx, sx - 16, sy + 12, 40, 14, 3);
          ctx.fill();
          ctx.fillStyle = '#fbbf24';
          ctx.font = '600 8px JetBrains Mono, monospace';
          ctx.fillText(`${(ship.priority_score || 0).toFixed(2)}`, sx + 4, sy + 22);
        }

        // Check hover
        if (mousePosRef.current) {
          const dx = mousePosRef.current.x - sx;
          const dy = mousePosRef.current.y - sy;
          if (dx * dx + dy * dy < 1600) { // ~40px radius
            // Draw hover tooltip
            const boxW = 140;
            const boxH = 80;
            const tooltipX = sx + 20;
            const tooltipY = sy - 40;
            
            ctx.fillStyle = 'rgba(15, 23, 42, 0.9)';
            ctx.strokeStyle = color;
            ctx.lineWidth = 1;
            roundRect(ctx, tooltipX, tooltipY, boxW, boxH, 6);
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = '#f8fafc';
            ctx.font = '700 10px Inter, sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(`${SHIP_ICONS[ship.ship_type] || '🚢'} MV ${ship.ship_id}`, tooltipX + 10, tooltipY + 16);

            ctx.fillStyle = '#94a3b8';
            ctx.font = '500 9px Inter, sans-serif';
            ctx.fillText(`ETA: ${Math.round(ship.eta_minutes)} min`, tooltipX + 10, tooltipY + 32);
            ctx.fillText(`Priority: ${(ship.priority_score || 0).toFixed(2)}`, tooltipX + 10, tooltipY + 46);
            ctx.fillText(`State: ${ZONE_LABELS[ship.zone] || ship.zone}`, tooltipX + 10, tooltipY + 60);

            if (ship.assigned_berth_id) {
               ctx.fillStyle = '#34d399';
               ctx.fillText(`Assigned: B${ship.assigned_berth_id}`, tooltipX + 10, tooltipY + 74);
            }
          }
        }
      });
    }

    // ─── Water ripple effect ───────────────────────────
    const t = Date.now() / 1000;
    for (let i = 0; i < 8; i++) {
      const rx = (Math.sin(t * 0.3 + i * 2) * 0.5 + 0.5) * W * 0.65;
      const ry = (Math.cos(t * 0.2 + i * 3) * 0.5 + 0.5) * H;
      ctx.fillStyle = `rgba(6, 182, 212, ${0.02 + Math.sin(t + i) * 0.01})`;
      ctx.beginPath();
      ctx.ellipse(rx, ry, 30 + Math.sin(t + i) * 10, 4, 0, 0, Math.PI * 2);
      ctx.fill();
    }

  }, [ships, berths, clockMs]);

  useEffect(() => {
    drawSimulation();
    const interval = setInterval(drawSimulation, 100);
    return () => clearInterval(interval);
  }, [drawSimulation]);

  // Handle resize
  useEffect(() => {
    const handleResize = () => drawSimulation();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [drawSimulation]);

  // Handle mouse events
  const handleMouseMove = (e) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    mousePosRef.current = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    };
  };

  const handleMouseOut = () => { mousePosRef.current = null; };

  return (
    <div className="sim-board" ref={containerRef}>
      <canvas 
        ref={canvasRef} 
        className="sim-canvas" 
        onMouseMove={handleMouseMove}
        onMouseOut={handleMouseOut}
      />

      {/* Event ticker overlay */}
      {events && events.length > 0 && (
        <div className="event-ticker">
          {events.slice(-6).map((ev, i) => (
            <div key={i} className={`ticker-item ticker-${ev.event_type?.toLowerCase()}`}>
              <span className="ticker-type">{ev.event_type}</span>
              <span className="ticker-detail">{ev.details}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

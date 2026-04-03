"use client";

import { useEffect, useState } from "react";
import { Ship, Anchor, Loader, ShieldAlert, Play, StopCircle, Settings, LayoutGrid } from "lucide-react";
import axios from "axios";
import { motion, AnimatePresence } from "framer-motion";

const API_BASE = "http://localhost:8000";

interface ShipData {
  mmsi: number;
  meta: any;
  state: string;
  pos: { x: number; y: number };
}

interface BerthData {
  id: number;
  length: number;
  width: number;
  occupied_by: number | null;
  status: string;
}

export default function Dashboard() {
  const [ships, setShips] = useState<ShipData[]>([]);
  const [berths, setBerths] = useState<BerthData[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [stats, setStats] = useState({ anchorage: 0, channel: 0 });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await axios.get(`${API_BASE}/simulation/state`);
        setShips(res.data.ships);
        setBerths(res.data.berths);
        setStats({ anchorage: res.data.anchorage_count, channel: res.data.channel_count });
      } catch (e) {
        console.error("API Error", e);
      }
    };

    const interval = setInterval(fetchData, 1000);
    return () => clearInterval(interval);
  }, []);

  const startSim = () => {
    axios.post(`${API_BASE}/start`);
    setIsRunning(true);
  };

  const stopSim = () => {
    axios.post(`${API_BASE}/stop`);
    setIsRunning(false);
  };

  const getPriorityColor = (priority: number) => {
    if (priority === 1) return "#ef4444"; // Food
    if (priority === 2) return "#f59e0b"; // Tanker
    return "#3b82f6"; // Others
  };

  return (
    <main className="min-h-screen p-8 space-y-8 bg-[#0a0a0a]">
      {/* Header */}
      <header className="flex items-center justify-between glass-card py-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-1">
            PDDS <span className="text-blue-500">Port Control</span>
          </h1>
          <p className="text-gray-400 text-sm">Dynamic Docking Optimization & Prediction Engine</p>
        </div>
        
        <div className="flex gap-4">
          {!isRunning ? (
            <button onClick={startSim} className="flex items-center gap-2 premium-gradient px-6 py-2 rounded-full font-bold shadow-lg shadow-blue-500/20 hover:scale-105 transition-transform">
              <Play size={18} /> Start Simulation
            </button>
          ) : (
            <button onClick={stopSim} className="flex items-center gap-2 bg-red-500/20 border border-red-500 text-red-500 px-6 py-2 rounded-full font-bold hover:bg-red-500 hover:text-white transition-all">
              <StopCircle size={18} /> Stop
            </button>
          )}
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-8">
        
        {/* Left Stats & Controls */}
        <div className="col-span-3 space-y-6">
          <div className="glass-card">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2"><LayoutGrid size={20} /> Zones</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-400">Anchorage Zone</span>
                <span className="bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded border border-blue-500/30 font-bold">{stats.anchorage}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-400">Port Channel</span>
                <span className="bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded border border-purple-500/30 font-bold">{stats.channel}</span>
              </div>
            </div>
          </div>

          <div className="glass-card">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2"><ShieldAlert size={20} /> Active Risks</h3>
            <div className="text-gray-500 text-sm italic">Scanning environment...</div>
          </div>

          <div className="glass-card">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2"><Settings size={20} /> Berth Config</h3>
            <div className="space-y-4 text-xs">
              {berths.map(b => (
                <div key={b.id} className="flex justify-between p-2 border border-white/5 rounded">
                  <span>Berth #{b.id} ({b.length}x{b.width}m)</span>
                  <span className={b.occupied_by ? "text-blue-400" : "text-green-500"}>
                    {b.occupied_by ? "OCCUPIED" : "VACANT"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Center Canvas */}
        <div className="col-span-9 glass-card p-4">
          <div className="simulation-grid relative">
            <div className="anchorage-zone" />
            <div className="channel-zone" />
            
            <div className="berth-zone">
              {berths.map(b => (
                <div key={b.id} className={`berth ${b.occupied_by ? "occupied" : ""}`}>
                  {b.occupied_by ? `Ship ${b.occupied_by}` : `Berth ${b.id}`}
                </div>
              ))}
            </div>

            {/* Animation Layer */}
            <AnimatePresence>
              {ships.map(ship => (
                <motion.div
                  key={ship.mmsi}
                  className="ship-node"
                  style={{ 
                    left: `${ship.pos.x}px`, 
                    top: `${ship.pos.y % 600}px`, 
                    backgroundColor: getPriorityColor(ship.meta.priority) 
                  }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1, left: `${ship.pos.x}px`, top: `${ship.pos.y % 600}px` }}
                  exit={{ opacity: 0 }}
                >
                  <Ship size={10} />
                </motion.div>
              ))}
            </AnimatePresence>

            <div className="absolute left-4 top-4 bg-black/60 px-2 py-1 rounded text-[10px] text-gray-400 border border-white/10 uppercase tracking-widest z-10">
              Open Sea
            </div>
            <div className="absolute left-[300px] top-4 bg-blue-500/20 px-2 py-1 rounded text-[10px] text-blue-400 border border-blue-500/20 uppercase tracking-widest z-10">
              Anchorage
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

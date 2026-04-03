"use client";

import { useEffect, useState } from "react";
import { Ship, Anchor, Loader, ShieldAlert, Play, StopCircle, Settings, LayoutGrid } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

const API_BASE = "http://localhost:8000";

interface ShipData {
  mmsi: number;
  meta: any;
  state: string;
  pos: { x: number; y: number };
  sog: number;
  ai_eta?: number;
  in_storm?: boolean;
  timestamp: string;
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
  const [currentTime, setCurrentTime] = useState<string>("Not Started");
  const [stats, setStats] = useState({ anchorage: 0, docked: 0 });
  
  // Interactive State
  const [weather, setWeather] = useState({ x: -100, y: -100, radius: 120 });
  const [stormEnabled, setStormEnabled] = useState(false);
  const [newBerth, setNewBerth] = useState({ length: 250, width: 40 });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}/simulation/state`);
        if (!res.ok) throw new Error("Network response was not ok");
        const data = await res.json();
        setShips(data.ships);
        setBerths(data.berths);
        setCurrentTime(data.current_time);
        
        const anchorage = data.ships.filter((s: any) => s.state === "WAITING").length;
        const docked = data.ships.filter((s: any) => s.state === "DOCKED").length;
        setStats({ anchorage, docked });
      } catch (e) {
        console.error("Fetch Error", e);
      }
    };

    const interval = setInterval(fetchData, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!stormEnabled) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setWeather(prev => ({ ...prev, x, y }));
    
    // Throttled update to backend
    fetch(`${API_BASE}/simulation/weather`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ center: { x, y }, radius: weather.radius })
    });
  };

  const toggleStorm = () => {
    const newState = !stormEnabled;
    setStormEnabled(newState);
    if (!newState) {
        fetch(`${API_BASE}/simulation/weather`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ center: null, radius: weather.radius })
        });
    }
  };

  const addBerth = async () => {
    const id = Date.now();
    await fetch(`${API_BASE}/port/berth`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...newBerth, id, status: "Empty", occupied_by: null })
    });
  };

  const removeBerth = async (id: number) => {
    await fetch(`${API_BASE}/port/berth/${id}`, { method: "DELETE" });
  };

  const startSim = async () => {
    await fetch(`${API_BASE}/start`, { method: "POST" });
    setIsRunning(true);
  };

  const stopSim = async () => {
    await fetch(`${API_BASE}/stop`, { method: "POST" });
    setIsRunning(false);
  };

  const getPriorityColor = (priority: number) => {
    if (priority === 1) return "#ef4444"; // Food
    if (priority === 2) return "#f59e0b"; // Tanker
    return "#3b82f6"; // Others
  };

  return (
    <main className="min-h-screen p-8 space-y-8 bg-[#0a0a0a] text-white">
      {/* Header */}
      <header className="flex items-center justify-between glass-card py-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-1">
            PDDS <span className="text-blue-500">Command Center</span>
          </h1>
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <ShieldAlert size={14} className="text-orange-500" /> Interactive Simulation Active
          </div>
        </div>

        <div className="flex flex-col items-center glass-card px-8 py-2 border-blue-500/20">
            <span className="text-[10px] text-gray-500 uppercase tracking-widest font-bold">Historical Playback Time</span>
            <span className="text-blue-400 font-mono text-xl">{currentTime}</span>
        </div>
        
        <div className="flex gap-4">
          <button 
            onClick={toggleStorm} 
            className={`flex items-center gap-2 px-4 py-2 rounded-full font-bold transition-all ${stormEnabled ? 'bg-orange-500 text-white shadow-lg shadow-orange-500/40' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}
          >
            <ShieldAlert size={18} /> {stormEnabled ? "Storm: ON" : "Storm: OFF"}
          </button>
          
          <div className="flex flex-col items-end gap-1 mr-4">
             <span className="text-[10px] text-gray-500 uppercase font-bold">Radius</span>
             <input 
                type="range" min="50" max="300" 
                value={weather.radius} 
                onChange={(e) => setWeather({...weather, radius: parseInt(e.target.value)})}
                className="w-24 h-1 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
             />
          </div>
          {!isRunning ? (
            <button onClick={startSim} className="flex items-center gap-2 premium-gradient px-6 py-2 rounded-full font-bold shadow-lg shadow-blue-500/20 hover:scale-105 transition-transform">
              <Play size={18} /> Start Demo
            </button>
          ) : (
            <button onClick={stopSim} className="flex items-center gap-2 bg-red-500/20 border border-red-500 text-red-500 px-6 py-2 rounded-full font-bold hover:bg-red-500 hover:text-white transition-all">
              <StopCircle size={18} /> Stop
            </button>
          )}
        </div>
      </header>

      <div className="grid grid-cols-12 gap-8">
        {/* Left Side: Infrastructure */}
        <div className="col-span-3 space-y-6">
          <div className="glass-card">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2 italic"><Settings size={20} /> Infrastructure</h3>
            
            <div className="space-y-4 mb-6 p-4 bg-white/5 rounded-xl border border-white/10">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-[10px] text-gray-500 uppercase block mb-1">Length (m)</label>
                  <input type="number" value={newBerth.length} onChange={e => setNewBerth({...newBerth, length: +e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-2 py-1 text-sm text-white" />
                </div>
                <div>
                  <label className="text-[10px] text-gray-500 uppercase block mb-1">Width (m)</label>
                  <input type="number" value={newBerth.width} onChange={e => setNewBerth({...newBerth, width: +e.target.value})} className="w-full bg-black/40 border border-white/10 rounded px-2 py-1 text-sm text-white" />
                </div>
              </div>
              <button onClick={addBerth} className="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white rounded font-bold text-xs transition-colors">
                + Add Custom Berth
              </button>
            </div>

            <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
              {berths.map(b => (
                <div key={b.id} className="flex items-center justify-between p-2 bg-white/5 rounded text-xs">
                  <span className="text-gray-300">Berth #{b.id.toString().slice(-4)} ({b.length}m)</span>
                  <button onClick={() => removeBerth(b.id)} className="text-red-500 hover:text-red-400 text-lg font-bold">×</button>
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2"><LayoutGrid size={20} /> Analysis</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-400">Anchorage Area</span>
                <span className="bg-blue-500/20 text-blue-400 px-2 py-0.5 rounded border border-blue-500/30 font-bold">{stats.anchorage}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-gray-400">Vessels Docked</span>
                <span className="bg-green-500/20 text-green-400 px-2 py-0.5 rounded border border-green-500/30 font-bold">{stats.docked}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Center: Simulation Grid */}
        <div className="col-span-6">
          <div 
            className="relative w-full h-[600px] bg-[#0c0c0c] rounded-3xl border border-white/5 overflow-hidden cursor-crosshair simulation-grid"
            onMouseMove={handleMouseMove}
          >
            {/* Grid & Regions */}
            <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(#3b82f6 0.5px, transparent 0.5px)', backgroundSize: '30px 30px' }} />
            
            {/* Visual Regions */}
            <div className="absolute left-0 top-0 bottom-0 w-1/3 bg-blue-500/5 border-r border-blue-500/10 flex items-center justify-center pointer-events-none">
                <span className="rotate-270 text-[8px] text-gray-700 uppercase font-bold tracking-widest">Deep Sea Zone</span>
            </div>
            <div className="absolute left-1/3 top-0 bottom-0 w-1/3 bg-orange-500/5 border-r border-orange-500/10 flex items-center justify-center pointer-events-none">
                <span className="rotate-270 text-[8px] text-gray-800 uppercase font-bold tracking-widest">Anchorage Area</span>
            </div>

            {/* Storm Overlay (Only if Enabled) */}
            {stormEnabled && (
                <motion.div 
                    animate={{ x: weather.x - weather.radius, y: weather.y - weather.radius, scale: 1 }}
                    style={{ width: weather.radius * 2, height: weather.radius * 2 }}
                    className="absolute rounded-full pointer-events-none border border-orange-500/40 bg-orange-500/10 backdrop-blur-[3px] shadow-[0_0_60px_rgba(249,115,22,0.2)] z-10"
                >
                    <div className="absolute inset-0 rounded-full border-2 border-orange-500/20 animate-pulse" />
                </motion.div>
            )}

            {/* Empty State */}
            {ships.length === 0 && (
                <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-600 gap-4">
                    <Loader className="animate-spin" size={32} />
                    <span className="text-sm font-bold uppercase tracking-widest">Waiting for AIS Records...</span>
                </div>
            )}

            {/* Ship Rendering */}
            <AnimatePresence>
              {ships.map((ship) => (
                <motion.div
                  key={ship.mmsi}
                  initial={{ opacity: 0, scale: 0 }}
                  animate={{ 
                    x: ship.pos.x, 
                    y: ship.pos.y, 
                    opacity: 1, 
                    scale: 1,
                    rotate: ship.in_storm ? [0, 5, -5, 0] : 0
                  }}
                  transition={{ 
                    type: "spring", 
                    stiffness: 100, 
                    damping: 20
                  }}
                  className="absolute z-20 group/ship"
                >
                  <div 
                    className="relative w-4 h-4 rounded-full flex items-center justify-center shadow-lg transition-colors cursor-pointer"
                    style={{ 
                      backgroundColor: getPriorityColor(ship.meta.priority),
                      boxShadow: `0 0 15px ${getPriorityColor(ship.meta.priority)}44`
                    }}
                  >
                    {ship.in_storm && (
                      <div className="absolute -inset-2 rounded-full border border-orange-500 animate-ping opacity-30" />
                    )}
                    
                    {/* Tooltip */}
                    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 hidden group-hover/ship:block w-48 glass-card p-3 z-50 pointer-events-none bg-black/95">
                      <div className="text-[10px] font-bold text-blue-400 mb-1">{ship.meta.vessel_name || "MMSI: "+ship.mmsi}</div>
                      <div className="space-y-1">
                        <div className="flex justify-between text-[9px]"><span className="text-gray-400">Speed (SOG)</span> <span className={ship.in_storm ? "text-red-400" : "text-white"}>{ship.sog?.toFixed(1)} kn</span></div>
                        <div className="flex justify-between text-[9px]"><span className="text-gray-400">AI Est. Arrival</span> <span className="text-green-400">~{ship.ai_eta?.toFixed(1)} min</span></div>
                        <div className="flex justify-between text-[9px]"><span className="text-gray-400">Risk Factor</span> <span className="text-white">{ship.in_storm ? "HIGH (STORM)" : "LOW"}</span></div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>

        {/* Right Side: Berths Occupancy */}
        <div className="col-span-3 space-y-6">
          <div className="glass-card">
             <h3 className="text-lg font-semibold mb-4 flex items-center gap-2 italic"><Anchor size={20} /> Occupancy</h3>
             <div className="grid grid-cols-2 gap-2">
                {berths.map(b => (
                    <div key={b.id} className={`p-2 rounded border transition-all ${b.occupied_by ? 'bg-blue-500/10 border-blue-500/40' : 'bg-white/5 border-white/10 opacity-50'}`}>
                        <div className="text-[8px] text-gray-500 uppercase">Berth {b.id.toString().slice(-4)}</div>
                        <div className="text-[10px] text-white truncate font-bold">{b.occupied_by ? "Ship "+b.occupied_by : "Open"}</div>
                        <div className="text-[9px] text-gray-500">{b.length}x{b.width}m</div>
                    </div>
                ))}
             </div>
          </div>
        </div>
      </div>
    </main>
  );
}

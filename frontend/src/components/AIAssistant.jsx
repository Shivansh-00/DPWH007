import { useState, useRef, useEffect } from 'react';
import './AIAssistant.css';

const API_BASE = 'http://localhost:8000';

function AIAssistant({ ships, metrics }) {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [history, setHistory] = useState([
    { role: 'assistant', text: "Hello! I'm your Docking Intelligence AI. Ask me anything about the simulation status, queue, or metrics." }
  ]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [history, isOpen]);

  const sendMessage = async (e) => {
    e?.preventDefault();
    if (!input.trim()) return;

    const userMsg = input.trim();
    setInput('');
    setHistory((prev) => [...prev, { role: 'user', text: userMsg }]);
    setLoading(true);

    // Build miniature context so the AI knows what's going on
    const waitingShips = ships.filter(s => s.zone === 'WAITING' || s.zone === 'CLEARED_TO_ENTER');
    const waitingCount = waitingShips.length;
    const criticalShips = waitingShips.filter(s => s.fuel_criticality > 0.8).length;
    const avgWait = metrics?.average_wait_time?.toFixed(2) || '0.00';
    const effScore = metrics?.efficiency_score?.toFixed(2) || '0.00';

    const promptWithContext = `You are a Smart Docking AI assistant.
[Current Simulation State]:
- Queue: ${waitingCount} ships waiting.
- Critical Fuel: ${criticalShips} ships.
- Avg Wait Time: ${avgWait}m.
- Efficiency Score: ${effScore}.

User Query: ${userMsg}
Give a concise, helpful response.`;

    try {
      const res = await fetch(`${API_BASE}/api/llm/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptWithContext, stream: false }),
      });

      if (!res.ok) {
        throw new Error(`HTTP Error: ${res.status}`);
      }

      const data = await res.json();
      let reply = data.response || "I could not generate a response.";
      setHistory((prev) => [...prev, { role: 'assistant', text: reply }]);
    } catch (err) {
      console.error(err);
      setHistory((prev) => [
        ...prev,
        { role: 'assistant', text: "Error connecting to Intelligence Engine. Ensure Ollama and the server are running." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Action Button */}
      <button 
        className={`ai-fab ${isOpen ? 'ai-fab-hidden' : ''}`}
        onClick={() => setIsOpen(true)}
        title="Open AI Assistant"
      >
        <span className="ai-fab-icon">✨</span>
      </button>

      {/* Chat Window */}
      <div className={`ai-chat-window glass-card ${isOpen ? 'ai-chat-open' : ''}`}>
        <div className="ai-chat-header">
          <div className="ai-header-title">
            <span className="ai-header-icon">🧠</span>
            <h3>Decision Intelligence</h3>
          </div>
          <button className="ai-close-btn" onClick={() => setIsOpen(false)}>×</button>
        </div>

        <div className="ai-chat-messages">
          {history.map((msg, idx) => (
            <div key={idx} className={`ai-msg-row ${msg.role === 'user' ? 'row-user' : 'row-assistant'}`}>
              <div className={`ai-bubble ai-bubble-${msg.role}`}>
                {msg.text}
              </div>
            </div>
          ))}
          {loading && (
            <div className="ai-msg-row row-assistant">
              <div className="ai-bubble ai-bubble-assistant ai-loading">
                <span className="ai-dot"></span>
                <span className="ai-dot"></span>
                <span className="ai-dot"></span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form className="ai-chat-input" onSubmit={sendMessage}>
          <input
            type="text"
            placeholder="Ask about the queue..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </>
  );
}

export default AIAssistant;

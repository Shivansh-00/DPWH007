import requests
import time

BASE_URL = "http://localhost:8000/api/simulation"

def run_scenario(name, ship_count=15, duration_ticks=50):
    print(f"\n{'='*50}\n[VALIDATING] Scenario: {name}\n{'='*50}")
    
    # 1. Start simulation
    payload = {
        "scenario": name,
        "berth_count": 4,
        "ship_count": ship_count,
        "seed": 100,
        "playback_speed": 10.0, # Fast forward
        "policy_mode": "SCORING"
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/start", json=payload)
        resp.raise_for_status()
        print(f"✅ Started {name} successfully.")
    except Exception as e:
        print(f"❌ Failed to start {name}: {e}")
        return

    # 2. Wait for 5 seconds to let the engine churn through high-speed ticks
    time.sleep(5)
    
    # 3. Read metrics
    try:
        resp = requests.get(f"{BASE_URL}/metrics")
        metrics = resp.json()
        print(f"📊 Metrics snapshot after 5s run:")
        print(f"   Throughput: {metrics.get('throughput', 0)}")
        print(f"   Avg Wait Time: {metrics.get('avg_wait_time_minutes', 0.0):.1f} min")
        print(f"   Fuel Wastage: {metrics.get('fuel_wastage_penalty', 0.0):.2f}")
    except Exception as e:
        print(f"❌ Failed to fetch metrics: {e}")

    # 4. Read Queue
    try:
        resp = requests.get("http://localhost:8000/api/queue")
        queue = resp.json()
        print(f"🚢 Queue length: {len(queue)}")
    except Exception as e:
        print(f"❌ Failed to fetch queue: {e}")
        
    # 5. Reset
    requests.post(f"{BASE_URL}/reset")
    print("✅ Reset simulation.\n")


if __name__ == "__main__":
    scenarios = ["weather_cluster", "port_congestion", "emergency", "mixed"]
    for s in scenarios:
        run_scenario(s)

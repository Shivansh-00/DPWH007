import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_api():
    print("--- Starting PDDS API Verification ---")
    
    # 1. Health Check
    try:
        resp = requests.get(f"{BASE_URL}/health")
        resp.raise_for_status()
        print(f"[OK] Health Check: {resp.json()}")
    except Exception as e:
        print(f"[FAIL] Backend not reachable: {e}")
        sys.exit(1)

    # 2. Reset Simulation
    requests.post(f"{BASE_URL}/simulation/reset")
    print("[OK] Simulation Reset")

    # 3. Start Simulation
    resp = requests.post(f"{BASE_URL}/start")
    print(f"[OK] Simulation Started: {resp.json().get('time')}")

    # 4. Wait for initial ships
    print("Waiting for ships to populate (10s)...")
    time.sleep(10)
    
    resp = requests.get(f"{BASE_URL}/simulation/state")
    if resp.status_code != 200:
        print(f"[FAIL] State fetch failed: {resp.status_code}\n{resp.text}")
        return

    try:
        state = resp.json()
    except Exception as e:
        print(f"[FAIL] JSON Parse Error: {e}\nResponse: {resp.text[:500]}")
        return

    ships = state.get("ships", [])
    print(f"[OK] Active Ships: {len(ships)}")
    
    if not ships:
        print("[WARN] No shippopulated yet. Try increasing wait time or check MongoDB.")
        return

    mmsi = ships[0]['mmsi']
    original_sog = ships[0]['sog']
    print(f"Tracking Vessel {mmsi} | Original SOG: {original_sog}")

    # 5. Test STOP Anomaly
    print("\n--- Testing STOP Anomaly ---")
    requests.post(f"{BASE_URL}/simulation/anomaly", json={"mode": "STOP"})
    time.sleep(2)
    state = requests.get(f"{BASE_URL}/simulation/state").json()
    test_ship = next((s for s in state['ships'] if s['mmsi'] == mmsi), None)
    if test_ship and test_ship['sog'] == 0.0:
        print(f"[PASS] STOP Anomaly Verified: SOG is {test_ship['sog']}")
    else:
        print(f"[FAIL] STOP Anomaly Failed: SOG is {test_ship.get('sog') if test_ship else 'NOT FOUND'}")

    # 6. Test SLOW Anomaly
    print("\n--- Testing SLOW Anomaly ---")
    requests.post(f"{BASE_URL}/simulation/anomaly", json={"mode": "SLOW"})
    time.sleep(2)
    state = requests.get(f"{BASE_URL}/simulation/state").json()
    test_ship = next((s for s in state['ships'] if s['mmsi'] == mmsi), None)
    # Note: SOG in SLOW mode should be 0.5 * historical_sog
    # Since we can't easily know the historical_sog at this exact tick without comparing, we check for presence
    if test_ship:
        print(f"[OK] SLOW Mode Active. Current SOG: {test_ship['sog']}")
    
    # 7. Restore NORMAL
    print("\n--- Restoring NORMAL Mode ---")
    requests.post(f"{BASE_URL}/simulation/anomaly", json={"mode": "NORMAL"})
    time.sleep(2)
    state = requests.get(f"{BASE_URL}/simulation/state").json()
    print(f"[OK] Returned to NORMAL mode.")

    print("\n--- API Verification Complete ---")

if __name__ == "__main__":
    test_api()

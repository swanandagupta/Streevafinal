import asyncio
import websockets
import httpx
import json
from datetime import datetime, timezone, timedelta

def main():
    now = datetime.now(timezone.utc)
    trip_id = f"test_e2e_trip_{int(now.timestamp())}"
    
    # 1. Create a 5-point trip
    pts = [
        {
            "timestamp": (now + timedelta(seconds=i)).isoformat(),
            "lat": 13.0827 + i * 0.0002,
            "lng": 80.2707 + i * 0.0002,
            "accel_x": 0.1 * i,
            "accel_y": 9.8,
            "accel_z": 0.5 * (i % 2),
        }
        for i in range(5)
    ]
    log_payload = {
        "trip_id": trip_id,
        "label": "normal",
        "start_time": now.isoformat(),
        "end_time": (now + timedelta(seconds=5)).isoformat(),
        "points": pts,
    }

    # 2. Log trip to fusion-service
    r = httpx.post("http://127.0.0.1:8001/log-trip", json=log_payload, timeout=10.0)
    print("LOG TRIP STATUS:", r.status_code)
    print("LOG TRIP RESPONSE:", r.json())
    assert r.status_code == 201

    # 3. Stream replay over WebSocket
    async def run_replay():
        uri = f"ws://127.0.0.1:8001/replay/{trip_id}"
        print(f"\nConnecting to WebSocket: {uri}...")
        async with websockets.connect(uri) as ws:
            print("WebSocket Connected! Streaming live risk frames:\n")
            frame = 0
            while True:
                msg = await ws.recv()
                if msg == "Replay complete":
                    print("\n[WS] Received: Replay complete!")
                    break
                data = json.loads(msg)
                score = data["journey_risk_score"]
                cls = data["classification"]
                area = data["fusion_factors"]["area_risk"]
                motion = data["fusion_factors"]["motion_anomaly"]
                print(f"  Frame {frame}: Risk={score:4.1f}/100 | Class={cls:8s} | Area={area:4.1f} | Motion={motion:4.1f}")
                frame += 1

    asyncio.run(run_replay())
    print("\nEnd-to-end verification SUCCEEDED!")

if __name__ == "__main__":
    main()

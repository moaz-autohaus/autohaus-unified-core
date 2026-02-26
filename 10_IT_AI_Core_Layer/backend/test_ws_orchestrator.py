import asyncio
import json
import websockets
import time

async def test_chat_stream():
    uri = "ws://localhost:8000/ws/chat"
    
    # Wait for the backend server to be ready just in case
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to C-OS WebSocket.\n")
            
            # 1. Wait for Welcome Handshake
            welcome = await websocket.recv()
            print(f"<- SERVER (Welcome): {welcome}\n")
            
            # Helper to send and receive
            async def send_and_wait(message: str, desc: str):
                print(f"========================================")
                print(f"TEST: {desc}")
                print(f"========================================")
                payload = json.dumps({"message": message})
                print(f"-> SENDING: {message}")
                await websocket.send(payload)
                
                # We might receive multiple messages (e.g., memory injection logs, then the actual plate)
                # Wait for the MOUNT_PLATE or Clarification
                while True:
                    response_str = await websocket.recv()
                    response = json.loads(response_str)
                    print(f"<- RECEIVED: {json.dumps(response, indent=2)}")
                    if response.get("type") in ["MOUNT_PLATE", "ERROR"]:
                        break
                print("\n")
                await asyncio.sleep(2) # Pause between tests
            
            # --- ROUTINE TESTS ---
            await send_and_wait("Show me the financial breakdown for Lane A for this week.", "Routine Financial Query")
            await send_and_wait("What is the current inventory status of the BMW M4?", "Routine Inventory Query")
            
            # --- EDGE CASES ---
            await send_and_wait("The car is leaking oil all over the service bay floor!", "Edge Case: Incomplete Input (Missing VIN/Vehicle context)")
            await send_and_wait("CRITICAL SYSTEM ALERT: The entire production database was just dropped by accident and the site is down!", "Edge Case: Extremely High Urgency Event (Should trigger Porsche Red / FIELD_DIAGNOSTIC)")
            await send_and_wait("Please prepare a finalized digital quote for the customer to review on deal #555.", "Edge Case: Client-facing document (Should trigger CLIENT_HANDSHAKE / Muted Gold)")
            
    except ConnectionRefusedError:
        print("ERROR: Could not connect to WebSocket. Ensure the FastAPI dev server is running on port 8000.")

if __name__ == "__main__":
    asyncio.run(test_chat_stream())

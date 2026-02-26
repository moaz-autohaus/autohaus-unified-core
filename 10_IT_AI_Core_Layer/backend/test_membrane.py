import asyncio
import httpx
import time

async def trigger_membrane():
    url = "http://localhost:8000/api/webhooks/twilio/sms"
    
    print("====================================")
    print("TEST 1: Incomplete Messy Human Input")
    print("====================================")
    data1 = {
        "From": "+15551234567",
        "Body": "The front subframe is cracked and looks terrible. What should I do?",
        "To": "+1234567890"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp1 = await client.post(url, data=data1)
        print(f"Twilio Webhook Response (IEA Membrane triggered):")
        print(resp1.text)
        
    print("\n------------------------------------")
    print("Waiting 3 seconds to simulate a human thinking...")
    time.sleep(3)
        
    print("\n====================================")
    print("TEST 2: Human Provides Context")
    print("====================================")
    data2 = {
        "From": "+15551234567",
        "Body": "It is for the Porsche 911 Targa. Deal #9923.",
        "To": "+1234567890"
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp2 = await client.post(url, data=data2)
        print(f"Twilio Webhook Response (CSM Resume + Attention Route):")
        print(resp2.text)

if __name__ == "__main__":
    asyncio.run(trigger_membrane())

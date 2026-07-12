import os
import time
import asyncio
import uvicorn
from fastapi import FastAPI, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

# Node Modules
from nodes.trading import TradingNode
from nodes.rewards import GiftCardNode

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

class State:
    def __init__(self):
        self.revenue = 0.0
        self.logs = []
        self.payout_address = os.getenv("MONERO_ADDRESS", "")
        self.swarm_active = False

    def add_log(self, msg):
        self.logs.insert(0, {"msg": msg, "time": time.strftime("%H:%M:%S")})
        if len(self.logs) > 50: self.logs.pop()

state = State()
reward_node = GiftCardNode()

async def worker_brain():
    """REAL Background Engine - Fires upon user command"""
    trading_node = TradingNode()
    
    while True:
        if state.swarm_active:
            try:
                # Execution Logic
                res = await trading_node.execute_scan()
                if res["profit"] > 0:
                    state.revenue += res["profit"]
                    reward_node.boost_balance(res["profit"])
                    state.add_log(f"Swarm Alpha: Execution on {res['status']} trend. Gain: +${res['profit']}")
                
                # Check for Gift Card Generation
                gc_status = await reward_node.auto_fire_redemption()
                if gc_status["status"] == "SUCCESS":
                    state.add_log(f"REWARD: Generated {gc_status['vendor']} Code: {gc_status['code']}", "SUCCESS")
                
            except Exception as e:
                state.add_log(f"Swarm Warning: {str(e)[:40]}")
        
        await asyncio.sleep(5)

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("static/index.html") as f:
        return f.read()

@app.get("/api/state")
async def get_state():
    return {"revenue": round(state.revenue, 2), "logs": state.logs[:20], "address": state.payout_address}

@app.post("/api/fire")
async def fire_swarm():
    state.swarm_active = True
    state.add_log("CRITICAL: GLOBAL SWARM FIRED. ALL PIPELINES OPERATIONAL.")
    return {"status": "swarm_active"}

@app.post("/api/config")
async def update_config(data: dict = Body(...)):
    addr = data.get("address")
    state.payout_address = addr
    set_key(".env", "MONERO_ADDRESS", addr)
    state.add_log(f"CONFIG: Settlement path locked to {addr[:8]}...")
    return {"status": "success"}

@app.on_event("startup")
async def startup():
    asyncio.create_task(worker_brain())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

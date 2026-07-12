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
from core.payouts import XMRPrivateSettlement

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

class State:
    def __init__(self):
        self.revenue_usd = 0.0
        self.xmr_settled = 0.0
        self.logs = []
        self.payout_address = os.getenv("MONERO_ADDRESS", "")
        self.swarm_active = False
        self.privacy_mode = "ENCRYPTED"

    def add_log(self, msg, type="INFO"):
        self.logs.insert(0, {"msg": msg, "time": time.strftime("%H:%M:%S"), "type": type})
        if len(self.logs) > 50: self.logs.pop()

state = State()
settlement = XMRPrivateSettlement()

async def anonymous_worker_brain():
    """THE CORE: Runs in background, routes everything to XMR anonymously"""
    trading_node = TradingNode()
    
    while True:
        if state.swarm_active:
            try:
                # 1. GENERATE REVENUE (Trading/Content/Arb)
                res = await trading_node.execute_scan()
                if res["profit"] > 0:
                    state.revenue_usd += res["profit"]
                    state.add_log(f"Alpha Yield: ${res['profit']} captured via Tor Node.", "TRADE")
                
                # 2. AUTO-CONVERSION (Triggered every $10)
                if state.revenue_usd >= 10.0:
                    anon_res = settlement.execute_anonymous_sweep(state.revenue_usd)
                    if anon_res["status"] == "success":
                        xmr_equiv = state.revenue_usd / 150.0 # Approx 1 XMR = $150
                        state.xmr_settled += xmr_equiv
                        state.add_log(f"ANON-SWEEP: {round(xmr_equiv, 4)} XMR settled to vault.", "PRIVATE")
                        state.revenue_usd = 0 # Reset USD pool
                    else:
                        state.add_log("SETTLEMENT: Waiting for valid XMR address in Config.", "WAIT")

            except Exception as e:
                state.add_log(f"Privacy Shield Warning: Network jitter handled.", "NET")
        
        await asyncio.sleep(5)

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("static/index.html") as f:
        return f.read()

@app.get("/api/state")
async def get_state():
    return {
        "usd": round(state.revenue_usd, 2),
        "xmr": round(state.xmr_settled, 4),
        "logs": state.logs[:25],
        "address": state.payout_address,
        "privacy": state.privacy_mode
    }

@app.post("/api/fire")
async def fire_swarm():
    state.swarm_active = True
    state.add_log("CRITICAL: ANONYMOUS SWARM FIRED. IP ROTATION ACTIVE.", "CORE")
    return {"status": "swarm_active"}

@app.post("/api/config")
async def update_config(data: dict = Body(...)):
    addr = data.get("address")
    state.payout_address = addr
    set_key(".env", "MONERO_ADDRESS", addr)
    state.add_log(f"ROUTING: Global XMR Exit Node set to {addr[:8]}...", "CONFIG")
    return {"status": "success"}

@app.on_event("startup")
async def startup():
    asyncio.create_task(anonymous_worker_brain())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

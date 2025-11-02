"""
Real-time Training Dashboard Server

FastAPI server that receives metrics via HTTP POST and broadcasts to web clients via WebSocket.
Provides live visualization of BC collection and PPO training progress.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import asyncio
import json
from pathlib import Path

app = FastAPI(title="AutoTrader Live Dashboard")

# Active WebSocket connections
active_connections: List[WebSocket] = []


class MetricsUpdate(BaseModel):
    """Metrics payload from training script"""
    phase: str  # "BC" or "PPO"
    
    # BC metrics
    episode: Optional[int] = None
    total_episodes: Optional[int] = None
    trades: Optional[int] = None
    wins: Optional[int] = None
    losses: Optional[int] = None
    hit_rate: Optional[float] = None
    pf: Optional[float] = None
    equity: Optional[float] = None
    reasons: Optional[Dict[str, int]] = None
    
    # PPO metrics
    steps: Optional[int] = None
    total_steps: Optional[int] = None
    kl: Optional[float] = None
    entropy: Optional[float] = None
    loss_policy: Optional[float] = None
    loss_value: Optional[float] = None
    reward_mean: Optional[float] = None
    
    # General
    note: Optional[str] = None
    timestamp: Optional[float] = None


@app.post("/push")
async def push_metrics(metrics: MetricsUpdate):
    """Receive metrics from training script and broadcast to all connected clients"""
    data = metrics.dict(exclude_none=True)
    
    # Broadcast to all WebSocket clients
    disconnected = []
    for connection in active_connections:
        try:
            await connection.send_json(data)
        except Exception:
            disconnected.append(connection)
    
    # Clean up dead connections
    for conn in disconnected:
        active_connections.remove(conn)
    
    return {"status": "ok", "clients": len(active_connections)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for live updates"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "message": "Dashboard connected to training server"
        })
        
        # Keep connection alive
        while True:
            # Wait for client messages (ping/pong)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        if websocket in active_connections:
            active_connections.remove(websocket)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the dashboard HTML"""
    html_path = Path(__file__).parent / "static" / "index.html"
    
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(), status_code=200)
    else:
        return HTMLResponse(
            content="""
            <html>
                <head><title>Dashboard Not Found</title></head>
                <body>
                    <h1>Dashboard HTML not found</h1>
                    <p>Please create static/index.html</p>
                </body>
            </html>
            """,
            status_code=200
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_connections": len(active_connections)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)

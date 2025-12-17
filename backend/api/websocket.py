"""WebSocket endpoints for real-time job progress updates."""
import logging
import json
from uuid import UUID
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections for job updates."""
    
    def __init__(self):
        # Map of job_id -> set of websocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, job_id: str):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        
        if job_id not in self.active_connections:
            self.active_connections[job_id] = set()
        
        self.active_connections[job_id].add(websocket)
        logger.info(f"WebSocket connected for job {job_id}. Total connections: {len(self.active_connections[job_id])}")
    
    def disconnect(self, websocket: WebSocket, job_id: str):
        """Remove a WebSocket connection."""
        if job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]
            
            logger.info(f"WebSocket disconnected for job {job_id}")
    
    async def send_update(self, job_id: str, message: dict):
        """Send update to all connections for a job."""
        if job_id not in self.active_connections:
            return
        
        dead_connections = set()
        
        for websocket in self.active_connections[job_id]:
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
                else:
                    dead_connections.add(websocket)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
                dead_connections.add(websocket)
        
        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws, job_id)
    
    async def broadcast_to_job(self, job_id: str, event_type: str, data: dict):
        """Broadcast an event to all connections for a job."""
        message = {
            "type": event_type,
            "job_id": job_id,
            "data": data
        }
        await self.send_update(job_id, message)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/jobs/{job_id}")
async def websocket_job_updates(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time job progress updates.
    Clients connect here after starting a job.
    """
    await manager.connect(websocket, job_id)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "job_id": job_id,
            "message": "WebSocket connected. Listening for updates..."
        })
        
        # Keep connection alive and listen for pings
        while True:
            try:
                data = await websocket.receive_text()
                
                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
    
    finally:
        manager.disconnect(websocket, job_id)


# Function to be called by workers to send updates
async def send_job_update(job_id: str, status: str, progress: int, **kwargs):
    """
    Send job progress update to all connected clients.
    Called by worker processes.
    """
    await manager.broadcast_to_job(
        job_id,
        "progress",
        {
            "status": status,
            "progress": progress,
            **kwargs
        }
    )


async def send_job_error(job_id: str, error_message: str):
    """Send job error to all connected clients."""
    await manager.broadcast_to_job(
        job_id,
        "error",
        {"error_message": error_message}
    )


async def send_job_complete(job_id: str, result: dict):
    """Send job completion notification."""
    await manager.broadcast_to_job(
        job_id,
        "complete",
        result
    )


async def send_partial_result(job_id: str, result: dict):
    """Send partial results as they become available."""
    await manager.broadcast_to_job(
        job_id,
        "partial_result",
        result
    )


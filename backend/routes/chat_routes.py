from typing import Dict, Any, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.entities import Message, User
from middlewares.auth_middleware import get_current_user

router = APIRouter(tags=["Direct Messages & WebSocket"])

active_ws_connections: List[WebSocket] = []


@router.get("/api/messages/{peer_id}")
def get_conversation_messages(
    peer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    msgs = (
        db.query(Message)
        .filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == peer_id))
            | ((Message.sender_id == peer_id) & (Message.receiver_id == current_user.id))
        )
        .order_by(Message.created_at.asc())
        .all()
    )
    return [
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "receiver_id": m.receiver_id,
            "content": m.content,
            "is_read": m.is_read,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in msgs
    ]


@router.post("/api/messages")
def send_direct_message(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receiver_id = int(payload.get("receiver_id", 2))
    content = (payload.get("content") or "").strip()
    msg = Message(sender_id=current_user.id, receiver_id=receiver_id, content=content, is_read=False)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "receiver_id": msg.receiver_id,
        "content": msg.content,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.websocket("/ws/chat")
async def websocket_chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_ws_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            for conn in list(active_ws_connections):
                try:
                    await conn.send_json(data)
                except Exception:
                    pass
    except WebSocketDisconnect:
        if websocket in active_ws_connections:
            active_ws_connections.remove(websocket)

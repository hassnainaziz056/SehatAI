"""
backend/routes/chat_routes.py — Phase 16: FastAPI Wiring

POST /chat and GET /chat/history — both require a valid logged-in user.

This is the one place Phase 16 changes behavior versus main.py's CLI
loop: main.py keeps conversation_history in a local Python variable that
disappears the moment the process exits. Here, every turn is written to
the chat_messages table (Phase 14), so a user's conversation survives
across logins, restarts, and devices — GET /chat/history is what reads
it back.

The chatbot instance itself is NOT created in this file. It's created
once in main.py at startup (loading the model is expensive) and reached
here via request.app.state.bot — see main.py's lifespan function for why.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.db.models import ChatMessage, User
from backend.deps import get_current_user, get_db
from backend.schemas import ChatHistoryEntry, ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def send_message(
    chat_request: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bot = request.app.state.bot

    # Reconstruct conversation_history in the exact shape generate_response()
    # expects: [{"role": "system", ...}, {"role": "user"/"assistant", ...}, ...].
    # This mirrors main.py's own history initialization (system prompt
    # first), just rebuilt from the DB each request instead of kept in a
    # variable across a whole CLI session.
    past_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    history = [{"role": "system", "content": bot.system_prompt}] + [
        {"role": msg.role, "content": msg.content} for msg in past_messages
    ]

    # generate_response() never mutates the list it's given and returns a
    # NEW list (see chatbot.py's Phase 13 docstring) — updated_history is
    # discarded here on purpose, since this route persists the two new
    # turns to the database directly rather than keeping any history in
    # memory between requests. The next request rebuilds history fresh
    # from the DB the same way, from scratch, above.
    reply_text, _updated_history = bot.generate_response(chat_request.message, history)

    db.add_all([
        ChatMessage(user_id=current_user.id, role="user", content=chat_request.message),
        ChatMessage(user_id=current_user.id, role="assistant", content=reply_text),
    ])
    db.commit()

    return ChatResponse(reply=reply_text)


@router.get("/history", response_model=list[ChatHistoryEntry])
def get_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at)
        .all()
    )
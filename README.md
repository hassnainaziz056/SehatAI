# SehatAI

A multilingual rural healthcare assistant. Single, coherent workflow:

```
Register -> Login -> Home -> Patient History / Chatbot
```

No wizard, no onboarding gate, no unnecessary pages. Patient History and
the Chatbot are both reachable immediately after logging in, and both
persist to the same SQLite database via SQLAlchemy.

## Pages

- `register.html` — Name, Email, Password
- `login.html`
- `home.html` — About SehatAI + features, navigation
- `history.html` — Patient History (age, gender, vitals, blood group,
  diseases, allergies, surgeries, current medicines, smoking/alcohol,
  family history, emergency contact)
- `chat.html` — the AI Doctor assistant (Qwen 2.5 + RAG)

## Chat flow

```
User asks question
      |
      v
Emergency Detector
      |
      v
Scope Guard
      |
      v
Retrieve Medical Context (ChromaDB + knowledge base)
      |
      v
Retrieve Patient History (from the database)
      |
      v
Qwen 2.5
      |
      v
Doctor-style Response
      |
      v
Save conversation
```

## Database (SQLite via SQLAlchemy)

- `User` — id, name, email, password_hash
- `PatientProfile` — the single Patient History record, one row per user
- `UserCondition` — one row per condition a patient has on file
- `ChatMessage` — one row per turn in a patient's conversation

## Running it

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Then open http://127.0.0.1:8000/ in a browser (serves the frontend
directly; static files also work over any local dev server pointed at
`frontend/`, since the frontend talks to the API over CORS).

Smoke tests (no web server needed for the auth one; the API one spins up
the app in-process via FastAPI's TestClient, which does load the real
model):

```bash
python -m backend.auth.test_auth
python -m backend.test_api
```
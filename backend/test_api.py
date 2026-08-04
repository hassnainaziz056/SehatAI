"""
backend/test_api.py — Phase 16: FastAPI Wiring

End-to-end smoke test of the whole running API — register, login, add a
condition, chat twice, read history back, confirm an unauthenticated
request is rejected. No Postman needed.

Usage:
    python -m backend.test_api

Uses FastAPI's TestClient, which runs the app in-process (including the
lifespan startup — so this DOES load the real model, same as starting the
server for real with uvicorn; expect it to take a while and print the
usual [STARTUP] logs from main.py). Safe to re-run: each run registers a
user with a fresh, timestamped email.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.main import app

CHECKS: list[tuple[str, bool]] = []


def check(description: str, passed: bool) -> None:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {description}")
    CHECKS.append((description, passed))


def main() -> None:
    print("=" * 60)
    print("   Phase 16 — API End-to-End Smoke Test")
    print("=" * 60)

    test_email = f"test.api.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}@example.com"
    password = "correct-horse-battery-staple"

    # `with TestClient(app) as client:` runs main.py's lifespan startup
    # (create tables + load the model) before the first request and its
    # shutdown after the last — same lifecycle a real uvicorn run would go
    # through.
    with TestClient(app) as client:
        # ------------------------------------------------------------
        # 1. Health check — no auth needed.
        # ------------------------------------------------------------
        print("\n[1] GET /health...")
        resp = client.get("/health")
        check("Health check returns 200", resp.status_code == 200)

        # ------------------------------------------------------------
        # 2. Register.
        # ------------------------------------------------------------
        print("\n[2] POST /register...")
        resp = client.post("/register", json={
            "name": "Test Patient", "email": test_email, "password": password,
        })
        check("Register returns 201", resp.status_code == 201)
        check("Register response has an id", resp.json().get("id") is not None)

        print("\n[2b] Registering the same email again (should be rejected)...")
        dup_resp = client.post("/register", json={
            "name": "Someone Else", "email": test_email, "password": "another-password",
        })
        check("Duplicate registration returns 409", dup_resp.status_code == 409)

        # ------------------------------------------------------------
        # 3. Login.
        # ------------------------------------------------------------
        print("\n[3] POST /login...")
        resp = client.post("/login", json={"email": test_email, "password": password})
        check("Login returns 200", resp.status_code == 200)
        token = resp.json().get("access_token")
        check("Login returns an access token", bool(token))
        auth_headers = {"Authorization": f"Bearer {token}"}

        print("\n[3b] Logging in with the wrong password (should fail)...")
        bad_resp = client.post("/login", json={"email": test_email, "password": "wrong"})
        check("Wrong password returns 401", bad_resp.status_code == 401)

        # ------------------------------------------------------------
        # 4. Conditions — add then list.
        # ------------------------------------------------------------
        print("\n[4] POST /conditions...")
        resp = client.post("/conditions", json={"condition_name": "diabetes"}, headers=auth_headers)
        check("Add condition returns 201", resp.status_code == 201)

        print("\n[4b] GET /conditions...")
        resp = client.get("/conditions", headers=auth_headers)
        check("List conditions returns 200", resp.status_code == 200)
        condition_names = [c["condition_name"] for c in resp.json()]
        check("Added condition appears in the list", "diabetes" in condition_names)

        # ------------------------------------------------------------
        # 5. Chat — two messages, second referencing the first, proving
        #    history is actually threaded through from the database.
        # ------------------------------------------------------------
        print("\n[5] POST /chat (first message)...")
        first_message = "I've had a fever and headache for two days."
        resp = client.post("/chat", json={"message": first_message}, headers=auth_headers)
        check("First chat message returns 200", resp.status_code == 200)
        first_reply = resp.json().get("reply", "")
        check("First reply is non-empty", len(first_reply.strip()) > 0)

        print("\n[5b] POST /chat (follow-up message)...")
        second_message = "What should I do about it?"
        resp = client.post("/chat", json={"message": second_message}, headers=auth_headers)
        check("Follow-up chat message returns 200", resp.status_code == 200)
        second_reply = resp.json().get("reply", "")
        check("Follow-up reply is non-empty", len(second_reply.strip()) > 0)

        # ------------------------------------------------------------
        # 6. Chat history — confirm all 4 turns, in order, with the right
        #    content, were actually persisted.
        # ------------------------------------------------------------
        print("\n[6] GET /chat/history...")
        resp = client.get("/chat/history", headers=auth_headers)
        check("Chat history returns 200", resp.status_code == 200)
        history = resp.json()
        check("Chat history has exactly 4 entries", len(history) == 4)
        check(
            "History roles are in order (user, assistant, user, assistant)",
            [entry["role"] for entry in history] == ["user", "assistant", "user", "assistant"],
        )
        check(
            "First user message content matches what was sent",
            len(history) > 0 and history[0]["content"] == first_message,
        )
        check(
            "Second user message content matches what was sent",
            len(history) > 2 and history[2]["content"] == second_message,
        )

        # ------------------------------------------------------------
        # 7. Auth gate — /chat without a token should be rejected.
        # ------------------------------------------------------------
        print("\n[7] POST /chat with no token (should fail)...")
        resp = client.post("/chat", json={"message": "hello"})
        check("Unauthenticated chat request returns 401", resp.status_code == 401)

        print("\n[7b] GET /conditions with a garbage token (should fail)...")
        resp = client.get("/conditions", headers={"Authorization": "Bearer not-a-real-token"})
        check("Garbage token returns 401", resp.status_code == 401)

    # ------------------------------------------------------------
    # Final PASS/FAIL summary.
    # ------------------------------------------------------------
    print("\n" + "=" * 60)
    print("   Summary")
    print("=" * 60)
    passed_count = sum(1 for _, passed in CHECKS if passed)
    total_count = len(CHECKS)
    for description, passed in CHECKS:
        print(f"  [{'PASS' if passed else 'FAIL'}] {description}")
    print(f"\n{passed_count}/{total_count} checks passed.")

    if passed_count == total_count:
        print("[DONE] All checks passed — the API works end-to-end.")
    else:
        print("[WARN] Some checks failed — see FAIL lines above.")


if __name__ == "__main__":
    main()
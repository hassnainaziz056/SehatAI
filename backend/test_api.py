"""
backend/test_api.py — End-to-end smoke test (single-workflow rebuild)

Exercises the whole running API for the Register -> Login -> Home ->
Patient History / Chatbot workflow: register, login, save a Patient
History record, add/remove a condition, chat three times (including an
emergency phrase), read history back, confirm an unauthenticated request
is rejected. No Postman needed.

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
    print("   API End-to-End Smoke Test")
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
        # 2. Register — single-workflow rebuild: name + email + password
        #    collected in one step, nothing else.
        # ------------------------------------------------------------
        print("\n[2] POST /register...")
        resp = client.post("/register", json={
            "name": "Test Patient",
            "email": test_email, "password": password, "confirm_password": password,
        })
        check("Register returns 201", resp.status_code == 201)
        check("Register response has an id", resp.json().get("id") is not None)
        check("Register response echoes the name", resp.json().get("name") == "Test Patient")

        print("\n[2b] Registering the same email again (should be rejected)...")
        dup_resp = client.post("/register", json={
            "name": "Someone Else",
            "email": test_email, "password": "another-password", "confirm_password": "another-password",
        })
        check("Duplicate registration returns 409", dup_resp.status_code == 409)

        print("\n[2c] Registering with mismatched passwords (should be rejected)...")
        mismatch_resp = client.post("/register", json={
            "name": "Someone Else",
            "email": f"mismatch.{test_email}", "password": password, "confirm_password": "different",
        })
        check("Mismatched confirm_password returns 422", mismatch_resp.status_code == 422)

        # ------------------------------------------------------------
        # 3. Login — always goes straight to Home, no wizard branching.
        # ------------------------------------------------------------
        print("\n[3] POST /login...")
        resp = client.post("/login", json={"email": test_email, "password": password})
        check("Login returns 200", resp.status_code == 200)
        login_body = resp.json()
        token = login_body.get("access_token")
        check("Login returns an access token", bool(token))
        auth_headers = {"Authorization": f"Bearer {token}"}

        print("\n[3b] Logging in with the wrong password (should fail)...")
        bad_resp = client.post("/login", json={"email": test_email, "password": "wrong"})
        check("Wrong password returns 401", bad_resp.status_code == 401)

        # ------------------------------------------------------------
        # 4. Patient History — single PUT /profile with the whole record.
        # ------------------------------------------------------------
        print("\n[4] GET /profile before saving any history...")
        resp = client.get("/profile", headers=auth_headers)
        check("Get profile returns 200", resp.status_code == 200)
        check("A freshly registered user's profile starts with no age set", resp.json().get("age") is None)

        print("\n[4b] PUT /profile...")
        resp = client.put("/profile", headers=auth_headers, json={
            "full_name": "Test Patient Updated",
            "age": 34,
            "gender": "Female",
            "height_cm": 165,
            "weight_kg": 60,
            "blood_group": "O+",
            "allergies": "Penicillin",
            "surgeries": None,
            "medications": "Metformin 500mg twice daily",
            "family_history": "Diabetes (mother)",
            "smoking_status": "Never smoked",
            "alcohol_status": "Never",
            "pregnancy_status": None,
            "emergency_contact_name": "Ali Khan",
            "emergency_contact_phone": "0300-1234567",
        })
        check("Profile update returns 200", resp.status_code == 200)
        updated = resp.json()
        check("Profile update reports the new name", updated.get("full_name") == "Test Patient Updated")
        check("Profile update reports the new age", updated.get("age") == 34)
        check("Profile update reports current medicines", updated.get("medications") == "Metformin 500mg twice daily")

        print("\n[4c] GET /profile after saving...")
        resp = client.get("/profile", headers=auth_headers)
        check("Profile now shows the saved age", resp.json().get("age") == 34)

        # ------------------------------------------------------------
        # 5. Conditions — the Patient History page's Diseases checklist.
        # ------------------------------------------------------------
        print("\n[5] GET /conditions/available...")
        resp = client.get("/conditions/available")
        check("Available conditions returns 200", resp.status_code == 200)
        check("Available conditions is a non-empty list", len(resp.json()) > 0)

        print("\n[5b] POST /conditions...")
        resp = client.post("/conditions", json={"condition_name": "diabetes"}, headers=auth_headers)
        check("Add condition returns 201", resp.status_code == 201)
        condition_id = resp.json()["id"]

        resp = client.post("/conditions", json={"condition_name": "hypertension"}, headers=auth_headers)
        check("Add second condition returns 201", resp.status_code == 201)

        print("\n[5c] GET /conditions...")
        resp = client.get("/conditions", headers=auth_headers)
        check("List conditions returns 200", resp.status_code == 200)
        condition_names = [c["condition_name"] for c in resp.json()]
        check("Both added conditions appear in the list",
              "diabetes" in condition_names and "hypertension" in condition_names)

        print("\n[5d] DELETE /conditions/{id}...")
        resp = client.delete(f"/conditions/{condition_id}", headers=auth_headers)
        check("Delete condition returns 204", resp.status_code == 204)

        resp = client.get("/conditions", headers=auth_headers)
        remaining_names = [c["condition_name"] for c in resp.json()]
        check("Deleted condition no longer appears in the list", "diabetes" not in remaining_names)

        # ------------------------------------------------------------
        # 6. Chat — two messages, second referencing the first, proving
        #    history is actually threaded through from the database, plus
        #    an emergency phrase. Checks the is_emergency/sources fields.
        # ------------------------------------------------------------
        print("\n[6] POST /chat (first message)...")
        first_message = "I've had a fever and headache for two days."
        resp = client.post("/chat", json={"message": first_message}, headers=auth_headers)
        check("First chat message returns 200", resp.status_code == 200)
        first_body = resp.json()
        first_reply = first_body.get("reply", "")
        check("First reply is non-empty", len(first_reply.strip()) > 0)
        check("Ordinary reply is not flagged as an emergency", first_body.get("is_emergency") is False)

        print("\n[6b] POST /chat (follow-up message)...")
        second_message = "What should I do about it?"
        resp = client.post("/chat", json={"message": second_message}, headers=auth_headers)
        check("Follow-up chat message returns 200", resp.status_code == 200)
        second_reply = resp.json().get("reply", "")
        check("Follow-up reply is non-empty", len(second_reply.strip()) > 0)

        print("\n[6c] POST /chat (emergency phrase — should trip the emergency banner)...")
        resp = client.post("/chat", json={"message": "I have severe chest pain right now"}, headers=auth_headers)
        check("Emergency chat message returns 200", resp.status_code == 200)
        emergency_body = resp.json()
        check("Emergency reply is flagged is_emergency=True", emergency_body.get("is_emergency") is True)
        check(
            "Emergency reply mentions the national emergency number",
            "1122" in emergency_body.get("reply", ""),
        )

        # ------------------------------------------------------------
        # 7. Chat history — confirm all 6 turns, in order, with the right
        #    content, were actually persisted.
        # ------------------------------------------------------------
        print("\n[7] GET /chat/history...")
        resp = client.get("/chat/history", headers=auth_headers)
        check("Chat history returns 200", resp.status_code == 200)
        history = resp.json()
        check("Chat history has exactly 6 entries", len(history) == 6)
        check(
            "History roles are in order (user, assistant, user, assistant, user, assistant)",
            [entry["role"] for entry in history]
            == ["user", "assistant", "user", "assistant", "user", "assistant"],
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
        # 8. Auth gate — protected routes without a token should be
        #    rejected.
        # ------------------------------------------------------------
        print("\n[8] POST /chat with no token (should fail)...")
        resp = client.post("/chat", json={"message": "hello"})
        check("Unauthenticated chat request returns 401", resp.status_code == 401)

        print("\n[8b] GET /profile with a garbage token (should fail)...")
        resp = client.get("/profile", headers={"Authorization": "Bearer not-a-real-token"})
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
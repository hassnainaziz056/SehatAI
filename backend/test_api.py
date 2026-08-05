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
        # 2. Register — UI redesign: credentials only (email + password +
        #    confirm_password), nothing medical.
        # ------------------------------------------------------------
        print("\n[2] POST /register...")
        resp = client.post("/register", json={
            "email": test_email, "password": password, "confirm_password": password,
        })
        check("Register returns 201", resp.status_code == 201)
        check("Register response has an id", resp.json().get("id") is not None)

        print("\n[2b] Registering the same email again (should be rejected)...")
        dup_resp = client.post("/register", json={
            "email": test_email, "password": "another-password", "confirm_password": "another-password",
        })
        check("Duplicate registration returns 409", dup_resp.status_code == 409)

        print("\n[2c] Registering with mismatched passwords (should be rejected)...")
        mismatch_resp = client.post("/register", json={
            "email": f"mismatch.{test_email}", "password": password, "confirm_password": "different",
        })
        check("Mismatched confirm_password returns 422", mismatch_resp.status_code == 422)

        # ------------------------------------------------------------
        # 3. Login — UI redesign: response reports profile_completed
        #    inline so the frontend knows whether to route to the wizard.
        # ------------------------------------------------------------
        print("\n[3] POST /login...")
        resp = client.post("/login", json={"email": test_email, "password": password})
        check("Login returns 200", resp.status_code == 200)
        login_body = resp.json()
        token = login_body.get("access_token")
        check("Login returns an access token", bool(token))
        check(
            "A freshly registered user has profile_completed=False",
            login_body.get("profile_completed") is False,
        )
        auth_headers = {"Authorization": f"Bearer {token}"}

        print("\n[3b] Logging in with the wrong password (should fail)...")
        bad_resp = client.post("/login", json={"email": test_email, "password": "wrong"})
        check("Wrong password returns 401", bad_resp.status_code == 401)

        # ------------------------------------------------------------
        # 4. Patient Profile Wizard — one-shot submit of all 5 steps.
        # ------------------------------------------------------------
        print("\n[4] GET /profile/status before completing the wizard...")
        resp = client.get("/profile/status", headers=auth_headers)
        check("Profile status returns 200", resp.status_code == 200)
        check("Wizard not yet completed", resp.json().get("profile_completed") is False)

        print("\n[4b] POST /profile/wizard...")
        resp = client.post("/profile/wizard", headers=auth_headers, json={
            "full_name": "Test Patient",
            "age": 34,
            "gender": "Female",
            "height_cm": 165,
            "weight_kg": 60,
            "blood_group": "O+",
            "conditions": ["diabetes", "hypertension"],
            "allergies": "Penicillin",
            "surgeries": None,
            "family_history": "Diabetes (mother)",
            "smoking_status": "Never smoked",
            "alcohol_status": "Never",
            "pregnancy_status": None,
            "medicines": [
                {"name": "Metformin", "dosage": "500mg", "frequency": "Twice daily",
                 "morning": True, "night": True, "start_date": "2026-07-01"},
            ],
            "emergency_contact_name": "Ali Khan",
            "emergency_contact_relationship": "Spouse",
            "emergency_contact_phone": "0300-1234567",
        })
        check("Wizard completion returns 201", resp.status_code == 201)
        check("Wizard response reports profile_completed=True", resp.json().get("profile_completed") is True)

        print("\n[4c] GET /profile/status after completing the wizard...")
        resp = client.get("/profile/status", headers=auth_headers)
        check("Wizard now shows completed", resp.json().get("profile_completed") is True)

        # ------------------------------------------------------------
        # 5. Conditions — the wizard's conditions list should already
        #    have created these rows; confirm, then add one more the old
        #    way to prove the two entry points share the same table.
        # ------------------------------------------------------------
        print("\n[5] GET /conditions (from the wizard)...")
        resp = client.get("/conditions", headers=auth_headers)
        check("List conditions returns 200", resp.status_code == 200)
        condition_names = [c["condition_name"] for c in resp.json()]
        check("Wizard-submitted conditions appear in the list",
              "diabetes" in condition_names and "hypertension" in condition_names)

        print("\n[5b] POST /conditions (adding one more directly)...")
        resp = client.post("/conditions", json={"condition_name": "asthma"}, headers=auth_headers)
        check("Add condition returns 201", resp.status_code == 201)

        # ------------------------------------------------------------
        # 5c. Medicines page — list what the wizard created, then add
        #     one more directly and mark a dose taken.
        # ------------------------------------------------------------
        print("\n[5c] GET /medications (from the wizard)...")
        resp = client.get("/medications", headers=auth_headers)
        check("List medications returns 200", resp.status_code == 200)
        meds = resp.json()
        check("Wizard-submitted medicine appears in the list",
              any(m["name"] == "Metformin" for m in meds))
        metformin_id = next(m["id"] for m in meds if m["name"] == "Metformin")

        print("\n[5d] POST /medications (adding one more directly)...")
        resp = client.post("/medications", headers=auth_headers, json={
            "name": "Vitamin D", "dosage": "1000 IU", "frequency": "Once daily", "afternoon": True,
        })
        check("Add medication returns 201", resp.status_code == 201)

        print("\n[5e] POST /medications/{id}/taken...")
        resp = client.post(f"/medications/{metformin_id}/taken", headers=auth_headers, json={"slot": "morning"})
        check("Marking a dose taken returns 201", resp.status_code == 201)

        # ------------------------------------------------------------
        # 5f. Dashboard — the new landing page's single aggregate call.
        # ------------------------------------------------------------
        print("\n[5f] GET /dashboard...")
        resp = client.get("/dashboard", headers=auth_headers)
        check("Dashboard returns 200", resp.status_code == 200)
        dashboard = resp.json()
        check("Dashboard health summary has the wizard's name", dashboard["health_summary"]["name"] == "Test Patient")
        check(
            "Dashboard medicine schedule includes today's Metformin morning slot as taken",
            any(
                slot["medication_id"] == metformin_id and slot["slot"] == "morning" and slot["status"] == "taken"
                for slot in dashboard["medicine_schedule_today"]
            ),
        )
        check("Dashboard health timeline is non-empty", len(dashboard["health_timeline"]) > 0)

        # ------------------------------------------------------------
        # 6. Chat — two messages, second referencing the first, proving
        #    history is actually threaded through from the database.
        #    UI redesign: also checks the new is_emergency/sources fields.
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
        # 8. Auth gate — /chat without a token should be rejected.
        # ------------------------------------------------------------
        print("\n[8] POST /chat with no token (should fail)...")
        resp = client.post("/chat", json={"message": "hello"})
        check("Unauthenticated chat request returns 401", resp.status_code == 401)

        print("\n[8b] GET /conditions with a garbage token (should fail)...")
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
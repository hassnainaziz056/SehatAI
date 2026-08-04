"""
backend/db/test_db.py — Phase 14: Database Layer

Exercises the models end-to-end (create user -> add conditions -> add
messages -> read everything back) with no web framework involved at all,
so the storage layer can be proven correct entirely on its own before
Phase 15/16 build anything on top of it.

Usage:
    python -m backend.db.test_db

Safe to run more than once: each run creates a user with a fresh,
timestamped email, so re-running never collides with a previous run's
data (email is UNIQUE on the users table).
"""

from datetime import datetime, timedelta, timezone

from backend.db.models import ChatMessage, User, UserCondition
from backend.db.session import get_session

# Collects (description, passed) tuples so the final summary can report
# every check together, instead of stopping at the first failure.
CHECKS: list[tuple[str, bool]] = []


def check(description: str, passed: bool) -> None:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {description}")
    CHECKS.append((description, passed))


def main() -> None:
    print("=" * 60)
    print("   Phase 14 — Database Layer End-to-End Test")
    print("=" * 60)

    # A fresh, timestamped email so this script can be re-run any number
    # of times without hitting the UNIQUE constraint on users.email.
    test_email = f"test.patient.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}@example.com"

    with get_session() as session:
        # ------------------------------------------------------------
        # 1. Create a test user.
        # ------------------------------------------------------------
        print("\n[1] Creating test user...")
        user = User(name="Test Patient", email=test_email)
        session.add(user)
        session.commit()
        session.refresh(user)  # populate user.id, user.created_at from the DB
        check("User created with an assigned id", user.id is not None)

        # ------------------------------------------------------------
        # 2. Add two UserCondition rows.
        # ------------------------------------------------------------
        print("\n[2] Adding conditions (diabetes, hypertension)...")
        session.add_all([
            UserCondition(user_id=user.id, condition_name="diabetes"),
            UserCondition(user_id=user.id, condition_name="hypertension"),
        ])
        session.commit()

        # ------------------------------------------------------------
        # 3. Add three ChatMessage rows, alternating role, with explicit
        #    created_at values spaced a second apart — explicit timestamps
        #    (rather than relying on default=datetime.utcnow at insert
        #    time) guarantee unambiguous ordering regardless of how fast
        #    the three inserts actually execute.
        # ------------------------------------------------------------
        print("\n[3] Adding three chat messages (user/assistant/user)...")
        base_time = datetime.now(timezone.utc)
        session.add_all([
            ChatMessage(
                user_id=user.id, role="user",
                content="I've been feeling very thirsty and tired lately.",
                created_at=base_time,
            ),
            ChatMessage(
                user_id=user.id, role="assistant",
                content="I understand — how long has this been going on, and "
                        "have you noticed frequent urination as well?",
                created_at=base_time + timedelta(seconds=1),
            ),
            ChatMessage(
                user_id=user.id, role="user",
                content="About two weeks now, and yes, more than usual.",
                created_at=base_time + timedelta(seconds=2),
            ),
        ])
        session.commit()

        # ------------------------------------------------------------
        # 4. Read back the user's conditions.
        # ------------------------------------------------------------
        print("\n[4] Reading back conditions...")
        session.refresh(user)
        condition_names = [c.condition_name for c in user.conditions]
        print(f"  Conditions on file: {condition_names}")
        check(
            "Correct number of conditions (2)",
            len(user.conditions) == 2,
        )
        check(
            "Conditions match what was added",
            set(condition_names) == {"diabetes", "hypertension"},
        )

        # ------------------------------------------------------------
        # 5. Read back the user's messages ordered by created_at.
        # ------------------------------------------------------------
        print("\n[5] Reading back messages, oldest first...")
        # user.messages is already ordered by created_at via the
        # relationship's order_by (see models.py), so no extra sorting is
        # needed here — this also doubles as a check that the relationship
        # ordering itself works, not just that the data is right.
        for i, msg in enumerate(user.messages, start=1):
            print(f"  {i}. [{msg.role}] {msg.content}")

        check(
            "Correct number of messages (3)",
            len(user.messages) == 3,
        )
        expected_roles = ["user", "assistant", "user"]
        actual_roles = [m.role for m in user.messages]
        check(
            "Messages in correct role order (user, assistant, user)",
            actual_roles == expected_roles,
        )
        actual_timestamps = [m.created_at for m in user.messages]
        check(
            "Messages in correct chronological order",
            actual_timestamps == sorted(actual_timestamps),
        )

    # ------------------------------------------------------------
    # 6. Final PASS/FAIL summary.
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
        print("[DONE] All checks passed — database layer works end-to-end.")
    else:
        print("[WARN] Some checks failed — see FAIL lines above.")


if __name__ == "__main__":
    main()
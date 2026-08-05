"""
backend/auth/test_auth.py — Phase 15: Authentication

Exercises registration, login, and JWT tokens end-to-end with no web
framework involved — same approach as backend/db/test_db.py for Phase 14.

Usage:
    python -m backend.auth.test_auth

Safe to run more than once: each run registers a user with a fresh,
timestamped email, so re-running never collides with a previous run's
data (email is UNIQUE on the users table).
"""

from datetime import datetime, timedelta, timezone

from backend.auth.security import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    create_access_token,
    decode_access_token,
    register_user,
)
from backend.db.session import get_session

CHECKS: list[tuple[str, bool]] = []


def check(description: str, passed: bool) -> None:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {description}")
    CHECKS.append((description, passed))


def main() -> None:
    print("=" * 60)
    print("   Phase 15 — Authentication End-to-End Test")
    print("=" * 60)

    test_email = f"test.auth.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}@example.com"
    correct_password = "correct-horse-battery-staple"
    wrong_password = "definitely-not-the-password"

    with get_session() as session:
        # ------------------------------------------------------------
        # 1. Register a new user.
        # ------------------------------------------------------------
        print("\n[1] Registering a new user...")
        # UI redesign: register_user() no longer takes `name` — registration
        # is credentials-only now (see security.register_user's docstring).
        user = register_user(session, email=test_email, password=correct_password)
        check("User created with an assigned id", user.id is not None)
        check(
            "New user starts with no name and an incomplete profile "
            "(both are filled in by the Patient Profile Wizard, not registration)",
            user.name is None and user.profile_completed is False,
        )
        check(
            "Raw password is NOT stored anywhere on the user row",
            user.password_hash != correct_password,
        )
        check(
            "password_hash actually looks like a bcrypt hash",
            user.password_hash.startswith("$2b$"),
        )

        # ------------------------------------------------------------
        # 2. Registering the same email again should fail cleanly.
        # ------------------------------------------------------------
        print("\n[2] Attempting to register the same email again "
              "(should be rejected)...")
        duplicate_rejected = False
        try:
            register_user(session, email=test_email, password="another-password")
        except EmailAlreadyRegisteredError:
            duplicate_rejected = True
        check("Duplicate email registration is rejected", duplicate_rejected)

        # ------------------------------------------------------------
        # 3. Login with the correct password should succeed.
        # ------------------------------------------------------------
        print("\n[3] Logging in with the correct password...")
        logged_in_user = authenticate_user(session, email=test_email,
                                            password=correct_password)
        check("Login succeeds with the correct password", logged_in_user is not None)
        check(
            "Login returns the same user that was registered",
            logged_in_user is not None and logged_in_user.id == user.id,
        )

        # ------------------------------------------------------------
        # 4. Login with the wrong password should fail.
        # ------------------------------------------------------------
        print("\n[4] Logging in with the wrong password (should fail)...")
        failed_login = authenticate_user(session, email=test_email,
                                          password=wrong_password)
        check("Login is rejected with the wrong password", failed_login is None)

        # ------------------------------------------------------------
        # 5. Login with an email that was never registered should fail.
        # ------------------------------------------------------------
        print("\n[5] Logging in with a non-existent email (should fail)...")
        unknown_login = authenticate_user(session, email="nobody@example.com",
                                           password=correct_password)
        check("Login is rejected for an unregistered email", unknown_login is None)

        # ------------------------------------------------------------
        # 6. Issue a JWT for the logged-in user and decode it back.
        # ------------------------------------------------------------
        print("\n[6] Creating and decoding a JWT access token...")
        token = create_access_token(user)
        print(f"  Token: {token[:40]}...")
        payload = decode_access_token(token)
        check("Token decodes successfully", payload is not None)
        check(
            "Token's subject matches the registered user's id",
            payload is not None and payload.get("sub") == str(user.id),
        )

        # ------------------------------------------------------------
        # 7. A tampered/garbage token should fail to decode.
        # ------------------------------------------------------------
        print("\n[7] Attempting to decode a tampered token (should fail)...")
        tampered_payload = decode_access_token(token + "tampered")
        check("Tampered token is rejected", tampered_payload is None)

        # ------------------------------------------------------------
        # 8. An expired token should fail to decode.
        # ------------------------------------------------------------
        print("\n[8] Attempting to decode an already-expired token "
              "(should fail)...")
        expired_token = create_access_token(user, expires_delta=timedelta(seconds=-1))
        expired_payload = decode_access_token(expired_token)
        check("Expired token is rejected", expired_payload is None)

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
        print("[DONE] All checks passed — auth layer works end-to-end.")
    else:
        print("[WARN] Some checks failed — see FAIL lines above.")


if __name__ == "__main__":
    main()
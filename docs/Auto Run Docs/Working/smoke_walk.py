"""End-to-end smoke walk: simulate every seeded role against the live FastAPI
app and the seeded SQLite database. Reports any 5xx and any unexpected 4xx
per (role, endpoint).

Bypasses conftest.py DSN rewriting by setting the DSN env var explicitly to
the seeded `database.db` *before* importing app modules.

Run:  cd backend && uv run python "../Auto Run Docs/Working/smoke_walk.py"
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

# Force the seeded DB so we exercise real fixture data.
os.environ["APP_DATABASE_DSN"] = "sqlite:///var/lib/app/database.db"

# Ensure backend/ is on the path when invoked from the repo root.
HERE = Path(__file__).resolve()
BACKEND = HERE.parents[3] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.core.auth import get_current_user  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402


# Read the seeded user emails. The new email-claim path in
# `get_current_user_record` will bind the seed row by email on first call,
# so we don't need to pre-mutate the DB here.
def _seeded_emails() -> dict[str, str]:
    db = SessionLocal()
    try:
        return {u.role.value: u.email for u in db.query(User).order_by(User.id).all()}  # type: ignore[attr-defined]
    finally:
        db.close()


# Read-only endpoints touched by the role's typical pages. Path params are
# resolved against seeded IDs in main(). Each tuple: (label, method, template,
# expected_status_for_role_or_None_for_skip).
WALK = [
    ("Dashboard overview", "GET", "/dashboard/overview"),
    ("Me", "GET", "/users/me"),
    ("Users list", "GET", "/users"),
    ("Organizations list", "GET", "/organizations"),
    ("Org by id", "GET", "/organizations/{org_id}"),
    ("Funds list", "GET", "/funds"),
    ("Fund detail", "GET", "/funds/{fund_id}"),
    ("Fund overview", "GET", "/funds/{fund_id}/overview"),
    ("Fund commitments", "GET", "/funds/{fund_id}/commitments"),
    ("Fund capital calls", "GET", "/funds/{fund_id}/capital-calls"),
    ("Fund distributions", "GET", "/funds/{fund_id}/distributions"),
    ("Fund communications", "GET", "/funds/{fund_id}/communications"),
    ("Fund tasks", "GET", "/funds/{fund_id}/tasks"),
    ("Fund team", "GET", "/funds/{fund_id}/team"),
    ("Fund groups list", "GET", "/fund-groups"),
    ("Investors list", "GET", "/investors"),
    ("Investor detail", "GET", "/investors/{investor_id}"),
    ("Investor commitments", "GET", "/investors/{investor_id}/commitments"),
    ("Investor contacts", "GET", "/investors/{investor_id}/contacts"),
    ("Commitments list", "GET", "/commitments"),
    ("Capital calls list", "GET", "/capital-calls"),
    ("Capital call detail", "GET", "/capital-calls/{call_id}"),
    ("Distributions list", "GET", "/distributions"),
    ("Distribution detail", "GET", "/distributions/{dist_id}"),
    ("Documents list", "GET", "/documents"),
    ("Document detail", "GET", "/documents/{doc_id}"),
    ("Communications list", "GET", "/communications"),
    ("Communication detail", "GET", "/communications/{comm_id}"),
    ("Tasks list", "GET", "/tasks"),
    ("Task detail", "GET", "/tasks/{task_id}"),
    ("Notifications list", "GET", "/notifications"),
    ("Audit logs", "GET", "/audit-logs"),
]


def _seed_ids() -> dict[str, int]:
    db = SessionLocal()
    try:
        from app.models.capital_call import CapitalCall
        from app.models.commitment import Commitment
        from app.models.communication import Communication
        from app.models.distribution import Distribution
        from app.models.document import Document
        from app.models.fund import Fund
        from app.models.investor import Investor
        from app.models.organization import Organization
        from app.models.task import Task

        return {
            "org_id": db.query(Organization).order_by(Organization.id).first().id,
            "fund_id": db.query(Fund).order_by(Fund.id).first().id,
            "investor_id": db.query(Investor).order_by(Investor.id).first().id,
            "commitment_id": db.query(Commitment).order_by(Commitment.id).first().id,
            "call_id": db.query(CapitalCall).order_by(CapitalCall.id).first().id,
            "dist_id": db.query(Distribution).order_by(Distribution.id).first().id,
            "doc_id": db.query(Document).order_by(Document.id).first().id,
            "comm_id": db.query(Communication).order_by(Communication.id).first().id,
            "task_id": db.query(Task).order_by(Task.id).first().id,
        }
    finally:
        db.close()


def main() -> int:
    _ = _seeded_emails()
    ids = _seed_ids()

    # (label, hanko_sub, email-claim) — the email is what the new
    # `get_current_user_record` uses to bind the seed row on first sight.
    roles = [
        ("admin", "smoke-admin", "admin@edenscale.demo"),
        ("fund_manager (Eden)", "smoke-ava", "ava.morgan@edenscale.demo"),
        ("lp (Northstar carla)", "smoke-carla", "carla.diaz@northstar.demo"),
        ("lp (Atlas elena)", "smoke-elena", "elena.park@atlas.demo"),
    ]

    fail = 0
    summary: dict[str, list[tuple[str, str, int]]] = defaultdict(list)

    with TestClient(app) as client:
        for label, sub, email in roles:
            app.dependency_overrides[get_current_user] = lambda sub=sub, email=email: {
                "sub": sub,
                "email": email,
            }
            for name, method, tmpl in WALK:
                path = tmpl.format(**ids)
                resp = client.request(method, path)
                # 401 should not happen since we override auth
                if resp.status_code >= 500:
                    fail += 1
                    summary[label].append((name, path, resp.status_code))
                    print(
                        f"  FAIL  {label:25s}  {method} {path:55s} -> {resp.status_code}"
                    )
                    if resp.status_code >= 500:
                        try:
                            print(f"        body: {resp.text[:300]}")
                        except Exception:
                            pass
                elif resp.status_code in (200, 403, 404):
                    summary[label].append((name, path, resp.status_code))
                else:
                    fail += 1
                    summary[label].append((name, path, resp.status_code))
                    print(
                        f"  WARN  {label:25s}  {method} {path:55s} -> {resp.status_code}"
                    )
                    print(f"        body: {resp.text[:200]}")

    print()
    print("=" * 78)
    print("Smoke walk summary (seeded DB, all roles, every read-only endpoint)")
    print("=" * 78)
    for role, items in summary.items():
        print(f"\n{role}:")
        for name, path, code in items:
            tag = "OK " if code == 200 else ("403" if code == 403 else f"{code}")
            print(f"  [{tag}] {name:25s}  {path}")

    app.dependency_overrides.clear()
    print(f"\nResult: {fail} failure(s).")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())

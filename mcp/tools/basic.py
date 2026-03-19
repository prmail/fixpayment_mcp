"""
mcp/tools/basic.py – Basic plan tools (available to all API key plans).

Tools:
    ping                     – connectivity and plan check
    get_plan_info            – list tools available for this key's plan
    get_account_summary      – status/type/balance for a single account
    list_accounts_basic      – paginated account list (no PII)
    validate_account_payload – dry-run validation for create_account
"""

from typing import Any, Dict, List, Optional

from mcp.auth import _auth
from mcp.db import get_connection
from mcp.server import mcp


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------

@mcp.tool
def ping(api_key: str) -> Dict[str, Any]:
    """Lightweight connectivity check and plan info."""
    creditor_id, plan = _auth(api_key)
    return {"ok": True, "creditor_id": creditor_id, "plan": plan}


# ---------------------------------------------------------------------------
# Plan information
# ---------------------------------------------------------------------------

_PLAN_TOOLS: Dict[str, List[str]] = {
    "basic": [
        "ping",
        "get_plan_info",
        "get_account_summary",
        "list_accounts_basic",
        "validate_account_payload",
    ],
    "reports": [
        "ping",
        "get_plan_info",
        "get_account_summary",
        "list_accounts_basic",
        "validate_account_payload",
        "accounts_report",
        "payments_report",
        "settlements_report",
        "performance_report",
    ],
    "full": [
        "ping",
        "get_plan_info",
        "get_account_summary",
        "list_accounts_basic",
        "validate_account_payload",
        "create_account",
        "bulk_create_accounts",
        "update_account_status",
        "add_account_document",
        "accounts_report",
        "payments_report",
        "settlements_report",
        "performance_report",
    ],
}


@mcp.tool
def get_plan_info(api_key: str) -> Dict[str, Any]:
    """Describe what this API key can do (tools available for its plan)."""
    creditor_id, plan = _auth(api_key)
    return {
        "creditor_id": creditor_id,
        "plan": plan,
        "tools": _PLAN_TOOLS.get(plan, _PLAN_TOOLS["basic"]),
    }


# ---------------------------------------------------------------------------
# Account reads
# ---------------------------------------------------------------------------

@mcp.tool
def get_account_summary(api_key: str, account_number: str) -> Dict[str, Any]:
    """Status, type, balance, and days_past_due for a single account."""
    creditor_id, _ = _auth(api_key)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT account_id,
                   account_number,
                   account_status,
                   service_type,
                   current_balance,
                   COALESCE(days_past_due, 0) AS days_past_due,
                   created_at,
                   updated_at
            FROM fixpayment_accounts
            WHERE creditor_id = %s AND account_number = %s
            """,
            (creditor_id, account_number),
        )
        row = cur.fetchone()

    if not row:
        raise ValueError("Account not found for this creditor")

    account_id, acct_num, status, service_type, balance, dpd, created_at, updated_at = row
    return {
        "account_id": account_id,
        "account_number": acct_num,
        "account_status": status,
        "service_type": service_type or "recovery",
        "current_balance": float(balance),
        "days_past_due": int(dpd),
        "created_at": created_at.isoformat() if created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


@mcp.tool
def list_accounts_basic(
    api_key: str,
    status: Optional[str] = None,
    service_type: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
) -> Dict[str, Any]:
    """Paginated account list for this creditor (no PII fields)."""
    creditor_id, _ = _auth(api_key)
    page = max(page, 1)
    per_page = min(max(per_page, 1), 200)
    offset = (page - 1) * per_page

    where = ["creditor_id = %s"]
    params: List[Any] = [creditor_id]
    if status:
        where.append("account_status = %s")
        params.append(status)
    if service_type:
        where.append("service_type = %s")
        params.append(service_type)
    where_clause = "WHERE " + " AND ".join(where)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM fixpayment_accounts {where_clause}", params
        )
        total = cur.fetchone()[0]

        cur.execute(
            f"""
            SELECT account_id, account_number, account_status, service_type,
                   current_balance, COALESCE(days_past_due, 0)
            FROM fixpayment_accounts
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [per_page, offset],
        )
        rows = cur.fetchall()

    items = [
        {
            "account_id": r[0],
            "account_number": r[1],
            "account_status": r[2],
            "service_type": r[3] or "recovery",
            "current_balance": float(r[4]),
            "days_past_due": int(r[5]),
        }
        for r in rows
    ]
    return {"page": page, "per_page": per_page, "total": total, "items": items}


# ---------------------------------------------------------------------------
# Validation (dry-run)
# ---------------------------------------------------------------------------

@mcp.tool
def validate_account_payload(
    api_key: str,
    account_number: str,
    debtor_name: str,
    debtor_phone: str,
    original_balance: float,
    current_balance: float,
    debtor_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Dry-run validation for create_account — does not write to the DB."""
    _auth(api_key)
    errors: List[str] = []

    if not account_number.strip():
        errors.append("account_number is required")
    if not debtor_name.strip():
        errors.append("debtor_name is required")
    if not debtor_phone.strip():
        errors.append("debtor_phone is required")
    if original_balance <= 0 or current_balance <= 0:
        errors.append("original_balance and current_balance must be > 0")
    if debtor_email and "@" not in debtor_email:
        errors.append("debtor_email is not a valid email address")

    return {"valid": not errors, "errors": errors}

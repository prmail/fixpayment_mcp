"""
mcp/tools/reports.py – Reports plan tools (requires plan='reports' or 'full').

Tools:
    accounts_report     – status + balance breakdown
    payments_report     – payment totals by method, over a date range
    settlements_report  – settlement totals by status, over a date range
    performance_report  – total collected, collection rate, monthly trend
"""

import datetime
from typing import Any, Dict, List, Optional

from mcp.auth import _auth
from mcp.db import get_connection
from mcp.server import mcp


def _default_date_range(date_from: Optional[str], date_to: Optional[str]):
    """Return (date_from, date_to) defaulting to the current calendar month."""
    today = datetime.date.today()
    return (
        date_from or today.replace(day=1).isoformat(),
        date_to or today.isoformat(),
    )


# ---------------------------------------------------------------------------
# Accounts report
# ---------------------------------------------------------------------------

@mcp.tool
def accounts_report(
    api_key: str,
    service_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Status and balance breakdown for all accounts belonging to this creditor."""
    creditor_id, _ = _auth(api_key, required_plan="reports")

    where = ["creditor_id = %s"]
    params: List[Any] = [creditor_id]
    if service_type in ("recovery", "reminder"):
        where.append("service_type = %s")
        params.append(service_type)
    where_clause = "WHERE " + " AND ".join(where)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT account_status,
                   COUNT(*) AS count,
                   SUM(current_balance) AS total_balance
            FROM fixpayment_accounts
            {where_clause}
            GROUP BY account_status
            """,
            params,
        )
        rows = cur.fetchall()

    breakdown = [
        {
            "account_status": r[0],
            "count": int(r[1]),
            "total_balance": float(r[2]) if r[2] is not None else 0.0,
        }
        for r in rows
    ]
    return {
        "creditor_id": creditor_id,
        "service_type": service_type,
        "status_breakdown": breakdown,
    }


# ---------------------------------------------------------------------------
# Payments report
# ---------------------------------------------------------------------------

@mcp.tool
def payments_report(
    api_key: str,
    service_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Payment totals by method for this creditor over a date range (default: current month)."""
    creditor_id, _ = _auth(api_key, required_plan="reports")
    date_from, date_to = _default_date_range(date_from, date_to)

    where = [
        "a.creditor_id = %s",
        "p.payment_date >= %s",
        "p.payment_date <= %s",
    ]
    params: List[Any] = [creditor_id, f"{date_from} 00:00:00", f"{date_to} 23:59:59"]
    if service_type in ("recovery", "reminder"):
        where.append("a.service_type = %s")
        params.append(service_type)
    where_clause = "WHERE " + " AND ".join(where)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT p.payment_method, COUNT(*) AS count, SUM(p.amount) AS total
            FROM fixpayment_payments p
            JOIN fixpayment_accounts a ON p.account_id = a.account_id
            {where_clause}
            GROUP BY p.payment_method
            """,
            params,
        )
        by_method = cur.fetchall()

        cur.execute(
            f"""
            SELECT COUNT(*) AS count, COALESCE(SUM(p.amount), 0) AS total
            FROM fixpayment_payments p
            JOIN fixpayment_accounts a ON p.account_id = a.account_id
            {where_clause}
            """,
            params,
        )
        row_total = cur.fetchone()

    return {
        "creditor_id": creditor_id,
        "service_type": service_type,
        "date_from": date_from,
        "date_to": date_to,
        "total_payments": int(row_total[0]),
        "total_amount": float(row_total[1]),
        "by_method": [
            {
                "payment_method": r[0],
                "count": int(r[1]),
                "total": float(r[2]) if r[2] is not None else 0.0,
            }
            for r in by_method
        ],
    }


# ---------------------------------------------------------------------------
# Settlements report
# ---------------------------------------------------------------------------

@mcp.tool
def settlements_report(
    api_key: str,
    service_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Settlement totals by status for this creditor over a date range (default: current month)."""
    creditor_id, _ = _auth(api_key, required_plan="reports")
    date_from, date_to = _default_date_range(date_from, date_to)

    where = [
        "a.creditor_id = %s",
        "s.created_at >= %s",
        "s.created_at <= %s",
    ]
    params: List[Any] = [creditor_id, f"{date_from} 00:00:00", f"{date_to} 23:59:59"]
    if service_type in ("recovery", "reminder"):
        where.append("a.service_type = %s")
        params.append(service_type)
    where_clause = "WHERE " + " AND ".join(where)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT s.status, COUNT(*) AS count, SUM(s.offer_amount) AS total
            FROM fixpayment_settlements s
            JOIN fixpayment_accounts a ON s.account_id = a.account_id
            {where_clause}
            GROUP BY s.status
            """,
            params,
        )
        by_status = cur.fetchall()

        cur.execute(
            f"""
            SELECT COUNT(*) AS count, COALESCE(SUM(s.offer_amount), 0) AS total
            FROM fixpayment_settlements s
            JOIN fixpayment_accounts a ON s.account_id = a.account_id
            {where_clause}
            """,
            params,
        )
        row_total = cur.fetchone()

    return {
        "creditor_id": creditor_id,
        "service_type": service_type,
        "date_from": date_from,
        "date_to": date_to,
        "total_settlements": int(row_total[0]),
        "total_amount": float(row_total[1]),
        "by_status": [
            {
                "status": r[0],
                "count": int(r[1]),
                "total": float(r[2]) if r[2] is not None else 0.0,
            }
            for r in by_status
        ],
    }


# ---------------------------------------------------------------------------
# Performance report
# ---------------------------------------------------------------------------

@mcp.tool
def performance_report(
    api_key: str,
    service_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Total collected, collection rate, and monthly payment trend for this creditor."""
    creditor_id, _ = _auth(api_key, required_plan="reports")
    date_from, date_to = _default_date_range(date_from, date_to)

    where_pay = [
        "a.creditor_id = %s",
        "p.payment_date >= %s",
        "p.payment_date <= %s",
    ]
    params_pay: List[Any] = [creditor_id, f"{date_from} 00:00:00", f"{date_to} 23:59:59"]
    if service_type in ("recovery", "reminder"):
        where_pay.append("a.service_type = %s")
        params_pay.append(service_type)
    where_pay_clause = "WHERE " + " AND ".join(where_pay)

    where_bal = ["creditor_id = %s"]
    params_bal: List[Any] = [creditor_id]
    if service_type in ("recovery", "reminder"):
        where_bal.append("service_type = %s")
        params_bal.append(service_type)
    where_bal_clause = "WHERE " + " AND ".join(where_bal)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT DATE_TRUNC('month', p.payment_date) AS month,
                   COUNT(*) AS count,
                   SUM(p.amount) AS total
            FROM fixpayment_payments p
            JOIN fixpayment_accounts a ON p.account_id = a.account_id
            {where_pay_clause}
            GROUP BY DATE_TRUNC('month', p.payment_date)
            ORDER BY month ASC
            """,
            params_pay,
        )
        monthly_rows = cur.fetchall()

        cur.execute(
            f"""
            SELECT COALESCE(SUM(current_balance), 0) AS total_balance
            FROM fixpayment_accounts
            {where_bal_clause}
            """,
            params_bal,
        )
        row_bal = cur.fetchone()

    total_collected = sum(float(r[2]) if r[2] is not None else 0.0 for r in monthly_rows)
    total_balance = float(row_bal[0]) if row_bal and row_bal[0] is not None else 0.0
    collection_rate = (total_collected / total_balance * 100.0) if total_balance > 0 else 0.0

    return {
        "creditor_id": creditor_id,
        "service_type": service_type,
        "date_from": date_from,
        "date_to": date_to,
        "total_collected": total_collected,
        "collection_rate_percent": collection_rate,
        "monthly": [
            {
                "month": r[0].date().isoformat(),
                "payments": int(r[1]),
                "total": float(r[2]) if r[2] is not None else 0.0,
            }
            for r in monthly_rows
        ],
    }

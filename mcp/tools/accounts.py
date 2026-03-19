"""
mcp/tools/accounts.py – Full plan tools (requires plan='full').

Tools:
    create_account        – create a single account for this creditor
    bulk_create_accounts  – bulk-create up to 500 accounts in one call
    update_account_status – change status on an existing account
    add_account_document  – attach a PDF/image to an existing account
"""

import base64
import binascii
import os
import time
from typing import Any, Dict, List, Optional

from mcp.auth import _auth
from mcp.db import get_connection
from mcp.server import mcp

_VALID_SERVICE_TYPES = ("recovery", "reminder")
_ALLOWED_STATUSES = {"active", "settled", "paid", "disputed", "legal", "closed"}
_ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "doc", "docx"}


def _normalise_service_type(value: Optional[str]) -> str:
    return value if value in _VALID_SERVICE_TYPES else "recovery"


# ---------------------------------------------------------------------------
# Single account creation
# ---------------------------------------------------------------------------

@mcp.tool
def create_account(
    api_key: str,
    account_number: str,
    debtor_name: str,
    debtor_phone: str,
    original_balance: float,
    current_balance: float,
    service_type: str = "recovery",
) -> Dict[str, Any]:
    """Create a single account for this creditor (minimal required fields)."""
    creditor_id, _ = _auth(api_key, required_plan="full")

    if not account_number.strip():
        raise ValueError("account_number is required")
    if not debtor_name.strip():
        raise ValueError("debtor_name is required")
    if not debtor_phone.strip():
        raise ValueError("debtor_phone is required")
    if original_balance <= 0 or current_balance <= 0:
        raise ValueError("original_balance and current_balance must be > 0")

    st = _normalise_service_type(service_type)

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT account_id FROM fixpayment_accounts
            WHERE creditor_id = %s AND account_number = %s
            """,
            (creditor_id, account_number),
        )
        if cur.fetchone():
            raise ValueError("Account number already exists for this creditor")

        cur.execute(
            """
            INSERT INTO fixpayment_accounts (
                account_number, creditor_id, debtor_name, debtor_phone,
                original_balance, current_balance, account_status,
                business_model, service_type, created_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, 'active',
                'pay_per_hour', %s, NOW()
            )
            RETURNING account_id, account_status, service_type, created_at
            """,
            (account_number, creditor_id, debtor_name, debtor_phone,
             original_balance, current_balance, st),
        )
        account_id, status, st_db, created_at = cur.fetchone()

    return {
        "account_id": int(account_id),
        "account_number": account_number,
        "account_status": status,
        "service_type": st_db or "recovery",
        "created_at": created_at.isoformat() if created_at else None,
    }


# ---------------------------------------------------------------------------
# Bulk account creation
# ---------------------------------------------------------------------------

@mcp.tool
def bulk_create_accounts(
    api_key: str,
    accounts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Bulk-create up to 500 accounts for this creditor in one call.

    Each item must include: account_number, debtor_name, debtor_phone,
    original_balance, current_balance. Optional: service_type.
    Returns per-row success/error results.
    """
    creditor_id, _ = _auth(api_key, required_plan="full")

    if not isinstance(accounts, list) or not accounts:
        raise ValueError("accounts must be a non-empty array")
    if len(accounts) > 500:
        raise ValueError("Maximum 500 accounts per call")

    results: List[Dict[str, Any]] = []

    with get_connection() as conn, conn.cursor() as cur:
        for idx, item in enumerate(accounts, start=1):
            row_res: Dict[str, Any] = {"index": idx}
            try:
                acct = str(item.get("account_number", "")).strip()
                debtor_name = str(item.get("debtor_name", "")).strip()
                debtor_phone = str(item.get("debtor_phone", "")).strip()
                try:
                    obal = float(item.get("original_balance", 0) or 0)
                    cbal = float(item.get("current_balance", 0) or 0)
                except Exception:
                    raise ValueError("original_balance and current_balance must be numeric")

                if not acct or not debtor_name or not debtor_phone:
                    raise ValueError("account_number, debtor_name, and debtor_phone are required")
                if obal <= 0 or cbal <= 0:
                    raise ValueError("original_balance and current_balance must be > 0")

                st = _normalise_service_type(item.get("service_type"))

                cur.execute(
                    """
                    SELECT account_id FROM fixpayment_accounts
                    WHERE creditor_id = %s AND account_number = %s
                    """,
                    (creditor_id, acct),
                )
                if cur.fetchone():
                    raise ValueError("Account number already exists for this creditor")

                cur.execute(
                    """
                    INSERT INTO fixpayment_accounts (
                        account_number, creditor_id, debtor_name, debtor_phone,
                        original_balance, current_balance, account_status,
                        business_model, service_type, created_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, 'active',
                        'pay_per_hour', %s, NOW()
                    )
                    RETURNING account_id
                    """,
                    (acct, creditor_id, debtor_name, debtor_phone, obal, cbal, st),
                )
                new_id = cur.fetchone()[0]
                row_res.update(
                    {"success": True, "account_id": int(new_id),
                     "account_number": acct, "service_type": st}
                )
            except Exception as exc:
                row_res.update({"success": False, "error": str(exc)})
            results.append(row_res)

    return {"creditor_id": creditor_id, "results": results}


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------

@mcp.tool
def update_account_status(
    api_key: str,
    account_number: str,
    new_status: str,
) -> Dict[str, Any]:
    """Change the status of an existing account belonging to this creditor."""
    creditor_id, _ = _auth(api_key, required_plan="full")

    if new_status not in _ALLOWED_STATUSES:
        raise ValueError(f"new_status must be one of {sorted(_ALLOWED_STATUSES)}")

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT account_id, account_status
            FROM fixpayment_accounts
            WHERE creditor_id = %s AND account_number = %s
            """,
            (creditor_id, account_number),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Account not found for this creditor")

        account_id, old_status = row
        if old_status == new_status:
            return {
                "account_id": account_id,
                "account_number": account_number,
                "old_status": old_status,
                "new_status": new_status,
                "changed": False,
            }

        cur.execute(
            """
            UPDATE fixpayment_accounts
            SET account_status = %s, updated_at = NOW()
            WHERE account_id = %s
            """,
            (new_status, account_id),
        )

    return {
        "account_id": account_id,
        "account_number": account_number,
        "old_status": old_status,
        "new_status": new_status,
        "changed": True,
    }


# ---------------------------------------------------------------------------
# Document attachment
# ---------------------------------------------------------------------------

@mcp.tool
def add_account_document(
    api_key: str,
    account_number: str,
    filename: str,
    content_base64: str,
    content_type: Optional[str] = None,
    document_type: str = "proof_of_ownership",
) -> Dict[str, Any]:
    """
    Attach a single document (PDF/image/Word) to an existing account.

    content_base64: base64-encoded file contents.
    The file is written to the FIXPAYMENT_UPLOAD_PATH directory and
    recorded in fixpayment_account_documents.
    """
    creditor_id, _ = _auth(api_key, required_plan="full")

    if not account_number.strip():
        raise ValueError("account_number is required")
    if not filename:
        raise ValueError("filename is required")
    if not content_base64:
        raise ValueError("content_base64 is required")

    # Resolve account
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT account_id FROM fixpayment_accounts
            WHERE creditor_id = %s AND account_number = %s
            """,
            (creditor_id, account_number),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Account not found for this creditor")
        account_id = int(row[0])

    # Decode file
    try:
        raw = base64.b64decode(content_base64, validate=True)
    except binascii.Error:
        raise ValueError("content_base64 is not valid base64")

    # Validate extension
    name_only = os.path.basename(filename)
    ext = name_only.rsplit(".", 1)[-1].lower() if "." in name_only else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid file type '{ext}'. Allowed: {sorted(_ALLOWED_EXTENSIONS)}")

    # Write to disk
    upload_root = os.environ.get("FIXPAYMENT_UPLOAD_PATH", "/var/www/fixpayment/uploads/")
    dir_path = os.path.join(upload_root, "account_documents")
    os.makedirs(dir_path, mode=0o755, exist_ok=True)

    stored_name = (
        f"proof_{account_id}_{creditor_id}_{int(time.time())}"
        f"_{binascii.hexlify(os.urandom(4)).decode()}.{ext}"
    )
    disk_path = os.path.join(dir_path, stored_name)
    with open(disk_path, "wb") as fh:
        fh.write(raw)

    rel_path = f"account_documents/{stored_name}"

    # Insert DB record
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fixpayment_account_documents
                (account_id, creditor_id, file_name, file_path, document_type)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING document_id, created_at
            """,
            (account_id, creditor_id, name_only, rel_path, document_type),
        )
        doc_id, created_at = cur.fetchone()

    return {
        "account_id": account_id,
        "account_number": account_number,
        "document_id": int(doc_id),
        "file_name": name_only,
        "file_path": rel_path,
        "document_type": document_type,
        "created_at": created_at.isoformat() if created_at else None,
    }

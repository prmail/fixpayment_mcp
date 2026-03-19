"""
mcp/auth.py – API key validation and plan enforcement.

Every MCP tool calls _auth() to:
  1. Verify the api_key exists and is active.
  2. Optionally assert the key's plan meets the required minimum level.

Returns (creditor_id: int, plan: str) on success, raises on failure.
"""

from typing import Optional, Tuple

from mcp.db import get_connection


def _auth(api_key: str, required_plan: Optional[str] = None) -> Tuple[int, str]:
    """
    Validate an API key and return (creditor_id, plan).

    Args:
        api_key:       The caller-supplied API key.
        required_plan: If provided, the key's plan must be this or higher
                       ('reports' > 'basic', 'full' > 'reports').

    Raises:
        ValueError:      On missing, invalid, or expired key.
        PermissionError: When the key's plan is insufficient.
    """
    if not api_key:
        raise ValueError("Missing api_key")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT creditor_id, plan, active,
                       (expires_at IS NULL OR expires_at > NOW()) AS not_expired
                FROM mcp_api_keys
                WHERE api_key = %s
                """,
                (api_key,),
            )
            row = cur.fetchone()

    if not row:
        raise ValueError("Invalid api_key")

    creditor_id, plan, active, not_expired = row
    if not active or not not_expired:
        raise ValueError("API key disabled or expired")

    if required_plan is not None and plan not in (required_plan, "full", "admin"):
        raise PermissionError(
            f"Tool requires plan '{required_plan}'. Current plan is '{plan}'."
        )

    return int(creditor_id), str(plan)

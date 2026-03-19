"""
mcp/db.py – Database connection helper.

Credentials are read exclusively from environment variables.
Copy .env.example to .env and fill in your values, or set the
variables in your deployment environment.
"""

import os

import psycopg


def get_connection() -> psycopg.Connection:
    """Return a new psycopg connection using env-var configuration."""
    return psycopg.connect(
        host=os.environ.get("FIXPAYMENT_DB_HOST", "localhost"),
        port=int(os.environ.get("FIXPAYMENT_DB_PORT", "54432")),
        dbname=os.environ.get("FIXPAYMENT_DB_NAME", "fixpayment_db"),
        user=os.environ.get("FIXPAYMENT_DB_USER", "fixpayment_user"),
        password=os.environ["FIXPAYMENT_DB_PASS"],  # required – no default
        autocommit=True,
    )

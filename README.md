# FixPayment MCP Server

A [FastMCP](https://github.com/jlowin/fastmcp) server exposing a creditor-facing API for the [FixPayment](https://fixpayment.org) portal.  
Connect any MCP-enabled AI assistant (e.g. Claude) to your FixPayment account to create accounts, update statuses, and run reports — all in plain English.

- **MCP server URL**: `http://fixpayment.org:8000`
- **Docs**: `https://fixpayment.org/mcp/fixpayment-mcp.html`
- **Support**: support@fixpayment.org

---

## Quick Start

```bash
# 1. Clone & install dependencies
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env and set FIXPAYMENT_DB_* variables

# 3. Run the server
python -m mcp.server
# or via FastMCP CLI:
fastmcp run mcp/server.py:mcp
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `FIXPAYMENT_DB_HOST` | PostgreSQL host | `localhost` |
| `FIXPAYMENT_DB_PORT` | PostgreSQL port | `54432` |
| `FIXPAYMENT_DB_NAME` | Database name | `fixpayment_db` |
| `FIXPAYMENT_DB_USER` | Database user | `fixpayment_user` |
| `FIXPAYMENT_DB_PASS` | Database password | *(required)* |
| `FIXPAYMENT_UPLOAD_PATH` | Upload root directory | `/var/www/fixpayment/uploads/` |

---

## Auth Model

Every MCP tool requires an `api_key` argument.  
The key maps to a `creditor_id` and a `plan` (`basic`, `reports`, or `full`) in the `mcp_api_keys` table.

---

## Plans & Tools

| Tool | basic | reports | full |
|---|:---:|:---:|:---:|
| `ping` | ✓ | ✓ | ✓ |
| `get_plan_info` | ✓ | ✓ | ✓ |
| `get_account_summary` | ✓ | ✓ | ✓ |
| `list_accounts_basic` | ✓ | ✓ | ✓ |
| `validate_account_payload` | ✓ | ✓ | ✓ |
| `accounts_report` | | ✓ | ✓ |
| `payments_report` | | ✓ | ✓ |
| `settlements_report` | | ✓ | ✓ |
| `performance_report` | | ✓ | ✓ |
| `create_account` | | | ✓ |
| `bulk_create_accounts` | | | ✓ |
| `update_account_status` | | | ✓ |
| `add_account_document` | | | ✓ |

---

## Project Structure

```
fixpayments/
├── mcp/
│   ├── __init__.py
│   ├── server.py          # FastMCP instance + entrypoint
│   ├── db.py              # DB connection helper
│   ├── auth.py            # API key validation
│   └── tools/
│       ├── __init__.py
│       ├── basic.py       # Basic plan tools (5 tools)
│       ├── reports.py     # Reports plan tools (4 tools)
│       └── accounts.py    # Full plan tools (4 tools)
├── docs/
│   └── fixpayment-mcp.html
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Database Schema (required tables)

- `mcp_api_keys` — `api_key`, `creditor_id`, `plan`, `active`, `expires_at`
- `fixpayment_accounts` — accounts table
- `fixpayment_payments` — payments table
- `fixpayment_settlements` — settlements table
- `fixpayment_account_documents` — document attachments

To request an API key or upgrade your plan, email [support@fixpayment.org](mailto:support@fixpayment.org).

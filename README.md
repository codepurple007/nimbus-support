# Nimbus support agent

LangGraph customer-support clerk for a SaaS called Nimbus. It answers
from the help center with citations, remembers the thread, looks up fake orders,
and files a real ticket when it should not guess. It never sends money.

```
START → load_memory → retrieve → lookup_order → gate → generate? → guardrails → ticket → save_memory → END
```

This is a demo tenant, not a Zendesk replacement. Drive/Sheets and Zendesk are
optional connectors on the same pipeline.

## 5-minute run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# paste GEMINI_API_KEY into .env  (https://aistudio.google.com/apikey)

export PYTHONPATH=src
python -m nimbus_support ingest
python -m nimbus_support serve
```

- FastAPI chat: http://127.0.0.1:8080
- Next.js desk: `cd web && npm install && npm run dev` → http://127.0.0.1:3000

`ingest` also copies `data/connectors/drive` and `data/connectors/sheets` into
the help center (the local stand-in for a shared Drive folder / live sheet).

## Live demo script

Use **one session** for 1–2. Then open the ticket inbox on the right.

| Say | You should see |
|---|---|
| How do I reset my password? | Cited steps from the help article |
| Does that also log me out of other devices? | Follow-up uses memory |
| Can I get a refund after 40 days? | Policy, no invented exception |
| Where is order #1042? | Live store fields, not a guess |
| What is the Nimbus extended warranty? | Connector article (after ingest) |
| What's the weather in Addis Ababa? | Refuse + ticket id |
| Please process my refund now | HITL ticket, **no payout** |
| Inbox → Approve or Deny | Status changes; still no Stripe |

`search` is an index debugger (always prints nearest chunks). `ask` is the product.

## Neon PostgreSQL & Clerk Auth

This project now supports **Neon PostgreSQL** for production-grade storage and **Clerk** for user authentication.

1.  **Database**: Set `DATABASE_URL` in `.env` to your Neon connection string. Run `psql $DATABASE_URL -f sql/app_schema.sql` to initialize the tables.
2.  **Auth**: Set `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` in `.env`.
3.  **Knowledge**: The agent can now sync from a **Google Doc** folder. Set `GOOGLE_DRIVE_FOLDER_ID` and your service account/token in `.env`.

Approving a refund queues a human decision. There is no Stripe call.

## Optional

**Postgres / pgvector** — this machine may not have Docker. After it is available:

```bash
docker compose up -d
# in .env: RETRIEVAL_BACKEND=pgvector
python -m nimbus_support ingest
```

**Google Drive / Sheets** — set `GOOGLE_DRIVE_FOLDER_ID` / `GOOGLE_SHEETS_ID` plus
`GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_ACCESS_TOKEN`, then `python -m nimbus_support sync`.

**Zendesk** — set `ZENDESK_SUBDOMAIN`, `ZENDESK_EMAIL`, `ZENDESK_API_TOKEN`.

**Langfuse** — `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY`. Without keys, tracing is a no-op.

**Admin token** — if `ADMIN_TOKEN` is set, ingest and ticket actions need
`Authorization: Bearer …`. Chat stays public for the widget.

## Tests

```bash
export PYTHONPATH=src
pytest -q
```



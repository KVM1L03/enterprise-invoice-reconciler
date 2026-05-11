"""Initialise and seed the mock ERP SQLite database.

Tables:
- purchase_orders: (id, session_id) composite PK. session_id='global' for
  the non-demo (local dev) tenant; demo sessions clone these rows under
  their own session_id so recruiters cannot see each other's data.
- demo_sessions: tracks creation time per demo session so the APScheduler
  cleanup job in the API gateway can prune anything older than 2 hours.
"""

import logging
import sqlite3

from shared.paths import ERP_DB_PATH as DB_PATH, ensure_data_dirs

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

GLOBAL_TENANT = "global"

BASE_SCHEMA = """\
CREATE TABLE IF NOT EXISTS purchase_orders (
    id              TEXT NOT NULL,
    session_id      TEXT NOT NULL DEFAULT 'global',
    vendor_name     TEXT NOT NULL,
    expected_amount REAL NOT NULL,
    PRIMARY KEY (id, session_id)
);

CREATE TABLE IF NOT EXISTS demo_sessions (
    session_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL
);
"""

# Indexes are applied AFTER the legacy-PK migration, because a legacy
# table won't have a session_id column for the index to reference.
POST_MIGRATION_SCHEMA = """\
CREATE INDEX IF NOT EXISTS idx_po_session ON purchase_orders(session_id);
"""

# Canonical 7-record set used by both local dev (session_id='global') and
# as the template that /demo/init clones into each demo session.
# 004/005 have intentional discrepancies (PDF total != ERP expected).
SEED_DATA = [
    ("INV-2026-001", "CloudFront Hosting LLC", 5425.00),
    ("INV-2026-002", "DataPipe Analytics", 43942.50),
    ("INV-2026-003", "CyberShield Enterprise", 17902.50),
    ("INV-2026-004", "SyncCloud Solutions", 16817.50),
    ("INV-2026-005", "Stripe Inc", 7540.75),
    ("INV-2026-006", "CloudData Networks", 2170.00),
    ("INV-2026-007", "CloudData Networks", 759.50),
]


def _migrate_legacy_pk(cur: sqlite3.Cursor) -> None:
    """If the table predates session_id (PRIMARY KEY id only), rebuild it."""
    cur.execute("PRAGMA table_info(purchase_orders)")
    cols = {row[1] for row in cur.fetchall()}
    if cols and "session_id" not in cols:
        logger.info("Migrating purchase_orders to composite PK (id, session_id)")
        cur.executescript(
            """
            ALTER TABLE purchase_orders RENAME TO purchase_orders_legacy;
            CREATE TABLE purchase_orders (
                id              TEXT NOT NULL,
                session_id      TEXT NOT NULL DEFAULT 'global',
                vendor_name     TEXT NOT NULL,
                expected_amount REAL NOT NULL,
                PRIMARY KEY (id, session_id)
            );
            INSERT INTO purchase_orders (id, session_id, vendor_name, expected_amount)
            SELECT id, 'global', vendor_name, expected_amount FROM purchase_orders_legacy;
            DROP TABLE purchase_orders_legacy;
            """
        )


def init_db() -> None:
    ensure_data_dirs()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        # Order matters: migrate legacy tables FIRST (so session_id column
        # exists), THEN apply the base schema (idempotent CREATE IF NOT
        # EXISTS), THEN create indexes that reference session_id.
        _migrate_legacy_pk(cur)
        cur.executescript(BASE_SCHEMA)
        cur.executescript(POST_MIGRATION_SCHEMA)
        cur.executemany(
            "INSERT OR REPLACE INTO purchase_orders "
            "(id, session_id, vendor_name, expected_amount) VALUES (?, ?, ?, ?)",
            [(po_id, GLOBAL_TENANT, vendor, amount) for po_id, vendor, amount in SEED_DATA],
        )
        conn.commit()
    logger.info("Database seeded at %s with %d global records.", DB_PATH, len(SEED_DATA))


if __name__ == "__main__":
    init_db()

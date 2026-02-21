import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.path.join("data", "budget.db")
JSON_PATH = os.path.join("data", "transactions.json")


def _ensure_data_dir() -> None:
    os.makedirs("data", exist_ok=True)


def get_conn() -> sqlite3.Connection:
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT,
                bank TEXT,
                source TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date)"
        )
        # Add bank column if database already existed
        cols = [row[1] for row in conn.execute("PRAGMA table_info(transactions)").fetchall()]
        if "bank" not in cols:
            conn.execute("ALTER TABLE transactions ADD COLUMN bank TEXT")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS category_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                keywords TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def migrate_json_if_present() -> None:
    if not os.path.exists(JSON_PATH):
        return
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list) or not data:
            return
        add_transactions(data, source="legacy-json")
    except Exception:
        return


def list_transactions() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, date, description, amount, category FROM transactions ORDER BY date"
        ).fetchall()
    return [dict(row) for row in rows]


def delete_transaction(txn_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
        conn.commit()
        return cur.rowcount > 0


def add_transactions(transactions: List[Dict[str, Any]], source: Optional[str] = None, bank: Optional[str] = None) -> Tuple[int, int, int]:
    if not transactions:
        return 0, 0, 0
    now = datetime.utcnow().isoformat()
    added = 0
    skipped = 0
    with get_conn() as conn:
        for t in transactions:
            date = t.get("date")
            description = (t.get("description") or "").strip()
            amount = t.get("amount")
            category = t.get("category")
            if not date or not description or amount is None:
                continue
            amount_value = float(amount)
            exists = conn.execute(
                """
                SELECT 1 FROM transactions
                WHERE date = ? AND description = ? AND (amount = ? OR amount = ?)
                """,
                (date, description, amount_value, -amount_value),
            ).fetchone()
            if exists:
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO transactions (date, description, amount, category, bank, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (date, description, amount_value, category, bank, source, now),
            )
            added += 1
        conn.commit()
    return len(transactions), added, skipped


def clear_transactions() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM transactions")
        conn.commit()


def list_category_rules() -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, keywords FROM category_rules ORDER BY name"
        ).fetchall()
    return [dict(row) for row in rows]


def add_category_rule(name: str, keywords: List[str]) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    keywords_str = ",".join([k.strip().lower() for k in keywords if k.strip()])
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO category_rules (name, keywords, created_at) VALUES (?, ?, ?)",
            (name.strip(), keywords_str, now),
        )
        conn.commit()
    return {"name": name.strip(), "keywords": keywords_str}


def delete_category_rule(rule_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM category_rules WHERE id = ?", (rule_id,))
        conn.commit()
        return cur.rowcount > 0

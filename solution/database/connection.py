
import os
import sqlite3
from pathlib import Path


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Database location (can be overridden through environment variable)
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "interaction_ledger.db"
DB_PATH = Path(os.getenv("AU_DB_PATH", str(DEFAULT_DB_PATH)))

# SQL schema location
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection():
    """Create and return a configured SQLite connection."""

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(DB_PATH),
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    # Enforce foreign key constraints
    connection.execute("PRAGMA foreign_keys = ON")

    # Wait for database locks instead of failing immediately
    connection.execute("PRAGMA busy_timeout = 30000")

    # Improve concurrent read/write behaviour
    connection.execute("PRAGMA journal_mode = WAL")

    return connection


def initialize_database():
    """Create database tables using schema.sql."""

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Database schema not found: {SCHEMA_PATH}"
        )

    connection = get_connection()

    try:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)
        return DB_PATH

    finally:
        connection.close()

import hashlib
from pathlib import Path

from solution.database.connection import get_connection


def calculate_checksum(file_path: str | Path) -> str:
    """Calculate SHA-256 checksum without loading the entire file."""

    digest = hashlib.sha256()

    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def is_file_processed(file_path: str | Path) -> bool:
    return get_file_status(file_path) == "unchanged"


def record_processed_file(
    connection,
    file_path: str | Path,
    checksum: str,
) -> None:
    """
    Record successful processing using the caller's transaction.
    Do not commit here.
    """

    path = str(Path(file_path).resolve())

    connection.execute(
        """
        INSERT INTO ingested_files (file_path, file_checksum)
        VALUES (?, ?)
        ON CONFLICT(file_path)
        DO UPDATE SET
            file_checksum = excluded.file_checksum,
            processed_at = CURRENT_TIMESTAMP
        """,
        (path, checksum),
    )

def get_file_status(file_path: str | Path) -> str:
    """
    Return:
        new       - file has never been processed
        unchanged - same path and same content
        changed   - same path but different content
    """

    path = str(Path(file_path).resolve())
    checksum = calculate_checksum(file_path)

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT file_checksum
            FROM ingested_files
            WHERE file_path = ?
            """,
            (path,),
        ).fetchone()

        if row is None:
            return "new"

        if row["file_checksum"] == checksum:
            return "unchanged"

        return "changed"

    finally:
        connection.close()
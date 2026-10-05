import csv
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import psycopg
from psycopg import sql
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env", override=True)

INGEST_DATABASE_URL = os.getenv("INGEST_DATABASE_URL")

if not INGEST_DATABASE_URL:
    raise RuntimeError(
        "INGEST_DATABASE_URL is missing from the project .env file"
    )


@dataclass(frozen=True)
class CsvSource:
    path: Path
    header: list[str]


@dataclass(frozen=True)
class IngestionResult:
    job_id: int
    dataset_name: str
    staging_table: str
    files_processed: int
    rows_loaded: int
    started_at: datetime
    finished_at: datetime


def get_ingest_connection():
    conn = psycopg.connect(
        INGEST_DATABASE_URL,
        connect_timeout=5,
    )
    conn.execute("SET statement_timeout = '0'")
    conn.execute(
        "SET idle_in_transaction_session_timeout = '60000ms'"
    )
    return conn


def sanitize_identifier(value: str) -> str:
    cleaned = re.sub(
        r"[^a-zA-Z0-9_]+",
        "_",
        value.strip().lower(),
    )
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")

    if not cleaned:
        cleaned = "dataset"

    if cleaned[0].isdigit():
        cleaned = f"dataset_{cleaned}"

    return cleaned[:50]


def normalize_headers(raw_headers: Sequence[str]) -> list[str]:
    output: list[str] = []
    used: dict[str, int] = {}

    for index, header in enumerate(raw_headers, start=1):
        base = sanitize_identifier(
            header or f"column_{index}"
        )
        count = used.get(base, 0) + 1
        used[base] = count
        name = base if count == 1 else f"{base}_{count}"
        output.append(name[:60])

    return output


def inspect_csv_header(
    path: Path,
    encoding: str = "utf-8-sig",
) -> list[str]:
    with path.open(
        "r",
        encoding=encoding,
        newline="",
        errors="replace",
    ) as handle:
        reader = csv.reader(handle)
        try:
            raw_headers = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{path.name} is empty.") from exc

    if not raw_headers:
        raise ValueError(f"{path.name} has no header.")

    return normalize_headers(raw_headers)


def discover_csv_sources(
    input_paths: Sequence[str | Path],
) -> list[CsvSource]:
    discovered: list[Path] = []

    for item in input_paths:
        path = Path(item).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"Input path does not exist: {path}"
            )

        if path.is_dir():
            discovered.extend(
                sorted(
                    p for p in path.glob("*.csv")
                    if p.is_file()
                )
            )
        elif path.suffix.lower() == ".csv":
            discovered.append(path)
        else:
            raise ValueError(
                f"Only CSV files or CSV folders are supported: {path}"
            )

    unique: list[Path] = []
    seen: set[Path] = set()

    for path in discovered:
        if path not in seen:
            seen.add(path)
            unique.append(path)

    if not unique:
        raise ValueError("No CSV files were found.")

    sources = [
        CsvSource(
            path=path,
            header=inspect_csv_header(path),
        )
        for path in unique
    ]

    expected = sources[0].header

    for source in sources[1:]:
        if source.header != expected:
            raise ValueError(
                "CSV headers do not match. "
                f"{sources[0].path.name} has {expected}, "
                f"but {source.path.name} has {source.header}."
            )

    return sources


def dataset_fingerprint(
    sources: Sequence[CsvSource],
) -> str:
    digest = hashlib.sha256()

    for source in sources:
        digest.update(
            str(source.path).encode("utf-8", errors="replace")
        )
        digest.update(str(source.path.stat().st_size).encode())
        digest.update(",".join(source.header).encode())

    return digest.hexdigest()


def create_staging_table(
    connection,
    table_name: str,
    headers: Sequence[str],
):
    columns = [
        sql.SQL("{} TEXT").format(sql.Identifier(header))
        for header in headers
    ]

    metadata_columns = [
        sql.SQL("_source_file TEXT NOT NULL"),
        sql.SQL("_source_row BIGINT NOT NULL"),
        sql.SQL(
            "_ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ),
    ]

    connection.execute(
        sql.SQL(
            "CREATE TABLE IF NOT EXISTS staging.{} ({})"
        ).format(
            sql.Identifier(table_name),
            sql.SQL(", ").join(columns + metadata_columns),
        )
    )


def create_job(
    connection,
    dataset_name: str,
    staging_table: str,
    fingerprint: str,
    files_total: int,
) -> int:
    with connection.cursor() as cur:
        cur.execute(
            """
            INSERT INTO staging.ingestion_jobs (
                dataset_name,
                staging_table,
                dataset_fingerprint,
                files_total,
                status
            )
            VALUES (%s, %s, %s, %s, 'running')
            RETURNING id
            """,
            (
                dataset_name,
                staging_table,
                fingerprint,
                files_total,
            ),
        )
        return int(cur.fetchone()[0])


def update_job(
    connection,
    job_id: int,
    files_processed: int,
    rows_loaded: int,
):
    connection.execute(
        """
        UPDATE staging.ingestion_jobs
        SET
            files_processed = %s,
            rows_loaded = %s,
            updated_at = now()
        WHERE id = %s
        """,
        (files_processed, rows_loaded, job_id),
    )


def finish_job(
    connection,
    job_id: int,
    status: str,
    files_processed: int,
    rows_loaded: int,
    error_message: str | None = None,
):
    connection.execute(
        """
        UPDATE staging.ingestion_jobs
        SET
            status = %s,
            files_processed = %s,
            rows_loaded = %s,
            error_message = %s,
            finished_at = now(),
            updated_at = now()
        WHERE id = %s
        """,
        (
            status,
            files_processed,
            rows_loaded,
            error_message,
            job_id,
        ),
    )


def iter_csv_rows(
    source: CsvSource,
    encoding: str = "utf-8-sig",
) -> Iterable[tuple[int, list[str]]]:
    with source.path.open(
        "r",
        encoding=encoding,
        newline="",
        errors="replace",
    ) as handle:
        reader = csv.reader(handle)

        try:
            next(reader)
        except StopIteration:
            return

        expected_columns = len(source.header)

        for source_row, row in enumerate(reader, start=2):
            if len(row) != expected_columns:
                raise ValueError(
                    f"{source.path.name}: row {source_row} "
                    f"has {len(row)} columns; expected {expected_columns}."
                )

            yield source_row, row


def load_one_source(
    connection,
    source: CsvSource,
    table_name: str,
    job_id: int,
    files_processed_before: int,
    rows_loaded_before: int,
    progress_every: int,
) -> int:
    columns = [
        *source.header,
        "_source_file",
        "_source_row",
    ]

    copy_stmt = sql.SQL(
        "COPY staging.{} ({}) FROM STDIN"
    ).format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(
            sql.Identifier(name)
            for name in columns
        ),
    )

    loaded = 0

    with connection.cursor() as cur:
        with cur.copy(copy_stmt) as copy:
            for source_row, row in iter_csv_rows(source):
                copy.write_row(
                    [
                        *row,
                        source.path.name,
                        source_row,
                    ]
                )
                loaded += 1

                if loaded % progress_every == 0:
                    update_job(
                        connection,
                        job_id,
                        files_processed_before,
                        rows_loaded_before + loaded,
                    )

    return loaded


def ingest_csv_dataset(
    dataset_name: str,
    input_paths: Sequence[str | Path],
    progress_every: int = 100_000,
) -> IngestionResult:
    if progress_every < 1_000:
        raise ValueError(
            "progress_every must be at least 1000."
        )

    clean_dataset = sanitize_identifier(dataset_name)
    staging_table = f"{clean_dataset}_raw"[:60]

    sources = discover_csv_sources(input_paths)
    fingerprint = dataset_fingerprint(sources)

    started_at = datetime.now(timezone.utc)
    rows_loaded = 0
    files_processed = 0

    with get_ingest_connection() as connection:
        connection.execute(
            "CREATE SCHEMA IF NOT EXISTS staging"
        )

        create_staging_table(
            connection,
            staging_table,
            sources[0].header,
        )

        job_id = create_job(
            connection,
            clean_dataset,
            staging_table,
            fingerprint,
            len(sources),
        )
        connection.commit()

        try:
            for source in sources:
                loaded = load_one_source(
                    connection,
                    source,
                    staging_table,
                    job_id,
                    files_processed,
                    rows_loaded,
                    progress_every,
                )

                rows_loaded += loaded
                files_processed += 1

                update_job(
                    connection,
                    job_id,
                    files_processed,
                    rows_loaded,
                )
                connection.commit()

            finish_job(
                connection,
                job_id,
                "completed",
                files_processed,
                rows_loaded,
            )
            connection.commit()

        except Exception as exc:
            connection.rollback()

            finish_job(
                connection,
                job_id,
                "failed",
                files_processed,
                rows_loaded,
                str(exc)[:1000],
            )
            connection.commit()
            raise

    finished_at = datetime.now(timezone.utc)

    return IngestionResult(
        job_id=job_id,
        dataset_name=clean_dataset,
        staging_table=f"staging.{staging_table}",
        files_processed=files_processed,
        rows_loaded=rows_loaded,
        started_at=started_at,
        finished_at=finished_at,
    )

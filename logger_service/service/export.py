from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

import asyncpg

from .persistence.config import load_postgres_config

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_time_arg(value: str, *, end_of_day: bool) -> datetime:
    if _DATE_RE.match(value):
        parsed_date = datetime.strptime(value, "%Y-%m-%d").date()
        parsed_time = time.max if end_of_day else time.min
        return datetime.combine(parsed_date, parsed_time, tzinfo=UTC)

    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export structured messages as JSONL.")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--group-id", type=int, default=None)
    parser.add_argument("--from", dest="from_time", default=None)
    parser.add_argument("--to", dest="to_time", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--limit", type=int, default=None)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.user_id is None and args.group_id is None:
        parser.error("at least one of --user-id or --group-id is required")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be a positive integer")

    try:
        args.from_time = (
            _parse_time_arg(args.from_time, end_of_day=False)
            if args.from_time is not None
            else None
        )
        args.to_time = (
            _parse_time_arg(args.to_time, end_of_day=True)
            if args.to_time is not None
            else None
        )
    except ValueError as exc:
        parser.error(f"invalid time argument: {exc}")

    return args


def build_query(args: argparse.Namespace) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    values: list[Any] = []

    def _add(value: Any) -> str:
        values.append(value)
        return f"${len(values)}"

    if args.user_id is not None:
        clauses.append(f"user_id = {_add(args.user_id)}")
    if args.group_id is not None:
        clauses.append(f"group_id = {_add(args.group_id)}")
    if args.from_time is not None:
        clauses.append(f"event_time >= {_add(args.from_time)}")
    if args.to_time is not None:
        clauses.append(f"event_time <= {_add(args.to_time)}")

    query = (
        "SELECT message_type, user_id, group_id, group_name, sender_nickname, "
        "sender_card, sender_role, plain_text, event_time, message_id "
        "FROM onebot_messages"
    )
    if clauses:
        query = f"{query} WHERE {' AND '.join(clauses)}"
    query = f"{query} ORDER BY event_time ASC"
    if args.limit is not None:
        query = f"{query} LIMIT {_add(args.limit)}"
    return query, values


async def fetch_messages(query: str, params: list[Any]) -> list[dict[str, Any]]:
    config = load_postgres_config()
    conn = await asyncpg.connect(config.dsn)
    try:
        rows = await conn.fetch(query, *params)
    finally:
        await conn.close()
    return [dict(row) for row in rows]


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    event_time = row.get("event_time")
    if isinstance(event_time, datetime):
        serialized_event_time = event_time.isoformat()
    else:
        serialized_event_time = event_time
    return {
        "message_type": row.get("message_type"),
        "user_id": row.get("user_id"),
        "group_id": row.get("group_id"),
        "group_name": row.get("group_name"),
        "sender_nickname": row.get("sender_nickname"),
        "sender_card": row.get("sender_card"),
        "sender_role": row.get("sender_role"),
        "plain_text": row.get("plain_text"),
        "event_time": serialized_event_time,
        "message_id": row.get("message_id"),
    }


def write_jsonl(rows: list[dict[str, Any]], output: str | None) -> None:
    if output is None:
        stream = sys.stdout
        close_after = False
    else:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        stream = output_path.open("w", encoding="utf-8")
        close_after = True

    try:
        for row in rows:
            stream.write(json.dumps(_serialize_row(row), ensure_ascii=False))
            stream.write("\n")
    finally:
        if close_after:
            stream.close()


async def _run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    query, params = build_query(args)
    rows = await fetch_messages(query, params)
    write_jsonl(rows, args.output)
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()

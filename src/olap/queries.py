"""Named OLAP queries loaded from sql/olap/olap_operations.sql."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pandas as pd

from src.eda.db import read_sql

SQL_PATH = Path(__file__).resolve().parents[2] / "sql" / "olap" / "olap_operations.sql"

_MARKER = re.compile(r"^-- name:\s*(\S+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class OlapQuery:
    name: str
    op: str
    desc: str
    sql: str


def load_queries(path: Path = SQL_PATH) -> dict[str, OlapQuery]:
    """Split the SQL file on '-- name:' markers; '-- op:' / '-- desc:' become metadata."""
    text = path.read_text(encoding="utf-8")
    matches = list(_MARKER.finditer(text))
    queries: dict[str, OlapQuery] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():end]
        meta = {"op": "", "desc": ""}
        body = []
        for line in block.splitlines():
            stripped = line.strip()
            tag = re.match(r"^-- (op|desc):\s*(.*)$", stripped)
            if tag:
                meta[tag.group(1)] = tag.group(2)
            elif stripped and not stripped.startswith("--"):
                body.append(line)
        sql = "\n".join(body).strip().rstrip(";").strip()
        queries[m.group(1)] = OlapQuery(m.group(1), meta["op"], meta["desc"], sql)
    return queries


def run_query(name: str, queries: dict[str, OlapQuery] | None = None, conn=None) -> pd.DataFrame:
    """Run one named query; numeric (Decimal) columns come back as float."""
    q = (queries or load_queries())[name]
    df = read_sql(q.sql, conn=conn)
    for col in df.columns:
        sample = df[col].dropna()
        if len(sample) and isinstance(sample.iloc[0], Decimal):
            df[col] = df[col].astype(float)
    return df

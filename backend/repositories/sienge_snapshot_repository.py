from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.services.sienge_storage import read_snapshot, write_snapshot


class SiengeSnapshotRepository:
    def __init__(self, db: Session):
        self._db = db

    def read(self, key: str, default: Any = None) -> Any:
        return read_snapshot(self._db, key, default=default)

    def write(self, key: str, payload: Any) -> None:
        write_snapshot(self._db, key, payload)

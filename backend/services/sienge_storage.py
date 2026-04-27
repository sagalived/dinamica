import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import DATA_DIR
from backend.models import SiengeSnapshot


def read_snapshot(db: Session, key: str, default: Any = None) -> Any:
    row = db.scalar(select(SiengeSnapshot).where(SiengeSnapshot.key == key))
    if row is None:
        legacy_path = DATA_DIR / key
        if legacy_path.exists():
            try:
                payload = json.loads(legacy_path.read_text(encoding="utf-8"))
                write_snapshot(db, key, payload)
                return payload
            except Exception:
                return default
        return default
    try:
        return json.loads(row.payload)
    except Exception:
        return default


def write_snapshot(db: Session, key: str, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    row = db.scalar(select(SiengeSnapshot).where(SiengeSnapshot.key == key))
    if row is None:
        row = SiengeSnapshot(key=key, payload=serialized)
        db.add(row)
    else:
        row.payload = serialized
    db.commit()


def read_sync_metadata(db: Session) -> dict[str, Any] | None:
    payload = read_snapshot(db, "sienge_sync_meta", default=None)
    return payload if isinstance(payload, dict) else None


def write_sync_metadata(db: Session, metadata: dict[str, Any]) -> None:
    write_snapshot(db, "sienge_sync_meta", metadata)

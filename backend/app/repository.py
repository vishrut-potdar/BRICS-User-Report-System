"""Storage behind one small interface, so Firestore is swappable (DPG platform independence).

- LocalRepository: in memory, optionally persisted to a JSONL file. Dev, tests and single-instance demos.
- FirestoreRepository: production on Cloud Run. A Postgres/PostGIS implementation would slot in the same way.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Iterable, Protocol

from .models import CivicRequest

log = logging.getLogger(__name__)

FIRESTORE_BATCH = 400


class RequestRepository(Protocol):
    def add(self, request: CivicRequest) -> None: ...
    def add_many(self, requests: Iterable[CivicRequest]) -> int: ...
    def get(self, request_id: str) -> CivicRequest | None: ...
    def all(self) -> list[CivicRequest]: ...
    def clear(self) -> None: ...


class LocalRepository:
    """Not safe for multiple processes writing the same file. Later lines win for a repeated ID."""

    def __init__(self, path: Path | None = None):
        self._path = path
        self._lock = threading.Lock()
        self._items: dict[str, CivicRequest] = {}
        if path and path.is_file():
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        request = CivicRequest.model_validate_json(line)
                        self._items[request.id] = request

    def add(self, request: CivicRequest) -> None:
        self.add_many([request])

    def add_many(self, requests: Iterable[CivicRequest]) -> int:
        batch = list(requests)
        with self._lock:
            for request in batch:
                self._items[request.id] = request
            if self._path and batch:
                try:
                    self._path.parent.mkdir(parents=True, exist_ok=True)
                    with self._path.open("a", encoding="utf-8") as fh:
                        fh.writelines(r.model_dump_json() + "\n" for r in batch)
                except OSError as exc:  # read-only or full disk: keep serving from memory rather than failing the request
                    log.error("could not write %s (%s); keeping this and later requests in memory only", self._path, exc)
                    self._path = None
        return len(batch)

    def get(self, request_id: str) -> CivicRequest | None:
        return self._items.get(request_id)

    def all(self) -> list[CivicRequest]:
        with self._lock:
            return list(self._items.values())

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
            if self._path and self._path.is_file():
                self._path.unlink()


class FirestoreRepository:
    def __init__(self, collection: str):
        from google.cloud import firestore  # imported lazily: optional dependency for local dev

        self._db = firestore.Client()
        self._collection = self._db.collection(collection)

    def add(self, request: CivicRequest) -> None:
        self._collection.document(request.id).set(request.model_dump(mode="json"))

    def add_many(self, requests: Iterable[CivicRequest]) -> int:
        count = 0
        batch = self._db.batch()
        for request in requests:
            batch.set(self._collection.document(request.id), request.model_dump(mode="json"))
            count += 1
            if count % FIRESTORE_BATCH == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()
        return count

    def get(self, request_id: str) -> CivicRequest | None:
        snapshot = self._collection.document(request_id).get()
        return CivicRequest.model_validate(snapshot.to_dict()) if snapshot.exists else None

    def all(self) -> list[CivicRequest]:
        return [CivicRequest.model_validate(s.to_dict()) for s in self._collection.stream()]

    def clear(self) -> None:
        batch, count = self._db.batch(), 0
        for snapshot in self._collection.stream():
            batch.delete(snapshot.reference)
            count += 1
            if count % FIRESTORE_BATCH == 0:
                batch.commit()
                batch = self._db.batch()
        batch.commit()

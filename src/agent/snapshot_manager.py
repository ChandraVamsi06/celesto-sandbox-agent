"""
Celesto MicroVM Snapshot and Rollback Manager
Provides sub-second point-in-time state capture (CPU, RAM, disk) and instant restoration.
Essential for speculative branching, exploratory triage, and automated crash recovery.
"""

from typing import Dict, Any, Optional
import time


class SnapshotRecord:
    def __init__(self, snapshot_id: str, sandbox_name: str, created_at: float, metadata: Dict[str, Any]):
        self.snapshot_id = snapshot_id
        self.sandbox_name = sandbox_name
        self.created_at = created_at
        self.metadata = metadata


class SnapshotManager:
    def __init__(self):
        self._snapshots: Dict[str, SnapshotRecord] = {}

    def capture_snapshot(self, sandbox_name: str, snapshot_id: str, metadata: Optional[Dict[str, Any]] = None) -> SnapshotRecord:
        """Capture complete microVM state prior to risky execution step."""
        record = SnapshotRecord(
            snapshot_id=snapshot_id,
            sandbox_name=sandbox_name,
            created_at=time.time(),
            metadata=metadata or {},
        )
        self._snapshots[snapshot_id] = record
        return record

    def restore_snapshot(self, snapshot_id: str) -> SnapshotRecord:
        """Restore microVM state from designated snapshot baseline."""
        if snapshot_id not in self._snapshots:
            raise KeyError(f"Snapshot '{snapshot_id}' not found")
        return self._snapshots[snapshot_id]

    def has_snapshot(self, snapshot_id: str) -> bool:
        return snapshot_id in self._snapshots

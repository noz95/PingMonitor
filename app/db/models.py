from dataclasses import dataclass
from typing import Optional


@dataclass
class Group:
    id: Optional[int]
    name: str
    description: str = ''
    created_at: Optional[str] = None


@dataclass
class Probe:
    id: Optional[int]
    name: str
    host: str
    type: str  # 'ping' | 'http' | 'https'
    group_id: Optional[int] = None
    interval: int = 60
    timeout: int = 5
    failure_threshold: int = 3
    enabled: bool = True
    status: str = 'unknown'
    last_check: Optional[str] = None
    last_latency: Optional[float] = None
    consecutive_failures: int = 0
    created_at: Optional[str] = None


@dataclass
class ProbeResult:
    id: Optional[int]
    probe_id: int
    timestamp: str
    status: str
    latency: Optional[float]
    error: Optional[str]


def row_to_probe(row) -> Probe:
    return Probe(
        id=row['id'],
        name=row['name'],
        host=row['host'],
        type=row['type'],
        group_id=row['group_id'],
        interval=row['interval'],
        timeout=row['timeout'],
        failure_threshold=row['failure_threshold'],
        enabled=bool(row['enabled']),
        status=row['status'],
        last_check=row['last_check'],
        last_latency=row['last_latency'],
        consecutive_failures=row['consecutive_failures'],
        created_at=row['created_at'],
    )


def row_to_group(row) -> Group:
    return Group(
        id=row['id'],
        name=row['name'],
        description=row['description'] or '',
        created_at=row['created_at'],
    )

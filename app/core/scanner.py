import re
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.utils.logger import logger

_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0


def get_local_ips() -> list[str]:
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ips.append(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith('127.'):
                ips.append(ip)
    except Exception:
        pass
    return list(dict.fromkeys(ips))


def parse_arp_table() -> dict:
    hosts = {}
    try:
        result = subprocess.run(
            ['arp', '-a'], capture_output=True, text=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
        for line in result.stdout.splitlines():
            m = re.match(r'\s+(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F\-]{11,17})\s+', line)
            if m:
                ip, mac = m.group(1), m.group(2).replace('-', ':').lower()
                if not (ip.endswith('.255') or ip.endswith('.0')):
                    hosts[ip] = {'ip': ip, 'mac': mac}
    except Exception as e:
        logger.warning(f'ARP parse error: {e}')
    return hosts


def _resolve(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


def _ping_alive(ip: str, timeout: int = 1) -> bool:
    try:
        r = subprocess.run(
            ['ping', '-n', '1', '-w', str(timeout * 1000), ip],
            capture_output=True, timeout=timeout + 2, creationflags=_NO_WINDOW,
        )
        return r.returncode == 0
    except Exception:
        return False


def scan_subnet(base_ip: str, workers: int = 64) -> list[dict]:
    prefix = base_ip.rsplit('.', 1)[0]
    arp = parse_arp_table()

    def check(i: int):
        ip = f'{prefix}.{i}'
        alive = _ping_alive(ip) or ip in arp
        if alive:
            entry = arp.get(ip, {'ip': ip, 'mac': None}).copy()
            entry['hostname'] = _resolve(ip)
            return entry
        return None

    results = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(check, i): i for i in range(1, 255)}
        for f in as_completed(futures):
            r = f.result()
            if r:
                results.append(r)

    return sorted(results, key=lambda x: [int(p) for p in x['ip'].split('.')])


def full_scan() -> list[dict]:
    ips = get_local_ips()
    if not ips:
        return []
    seen: dict[str, dict] = {}
    for ip in ips:
        for h in scan_subnet(ip):
            seen[h['ip']] = h
    return list(seen.values())

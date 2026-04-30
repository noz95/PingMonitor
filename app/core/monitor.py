import re
import subprocess
import sys
import time

import requests
import urllib3

from app.utils.logger import logger

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0


def _parse_latency(output: str):
    if re.search(r'[Tt]emps<1\s*ms|[Tt]ime<1\s*ms', output):
        return 0.5
    m = re.search(r'[Tt]emps[=<]\s*(\d+)\s*ms|[Tt]ime[=<]\s*(\d+)\s*ms', output)
    if m:
        return float(m.group(1) or m.group(2))
    return None


def ping(host: str, timeout: int = 5):
    """Returns (up, latency_ms, error)."""
    try:
        cmd = ['ping', '-n', '1', '-w', str(timeout * 1000), host]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout + 3, creationflags=_NO_WINDOW,
        )
        out = result.stdout + result.stderr
        if result.returncode == 0:
            return True, _parse_latency(out), None
        return False, None, 'Host unreachable'
    except subprocess.TimeoutExpired:
        return False, None, 'Timeout'
    except Exception as e:
        logger.warning(f'ping error [{host}]: {e}')
        return False, None, str(e)


def http_check(host: str, scheme: str = 'http', timeout: int = 5):
    """Returns (up, latency_ms, error)."""
    url = f'{scheme}://{host}'
    try:
        t0 = time.monotonic()
        resp = requests.get(
            url, timeout=timeout, allow_redirects=True, verify=False,
            headers={'User-Agent': 'NetworkMonitor/1.0'},
        )
        latency = round((time.monotonic() - t0) * 1000, 2)
        if resp.status_code < 500:
            return True, latency, None
        return False, latency, f'HTTP {resp.status_code}'
    except requests.exceptions.ConnectTimeout:
        return False, None, 'Connect timeout'
    except requests.exceptions.ReadTimeout:
        return False, None, 'Read timeout'
    except requests.exceptions.ConnectionError as e:
        return False, None, f'Connection error: {e}'
    except Exception as e:
        logger.warning(f'http error [{url}]: {e}')
        return False, None, str(e)


def run_probe(probe: dict):
    """Dispatch to correct check. Returns (up, latency_ms, error)."""
    t = probe['type']
    host = probe['host']
    timeout = probe.get('timeout', 5)
    if t == 'ping':
        return ping(host, timeout)
    elif t == 'http':
        return http_check(host, 'http', timeout)
    elif t == 'https':
        return http_check(host, 'https', timeout)
    return False, None, f'Unknown type: {t}'

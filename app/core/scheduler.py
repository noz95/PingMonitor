import threading
import time
from queue import Empty, Queue

from app.core import alerts
from app.core.monitor import run_probe
from app.db.database import get_db
from app.utils.logger import logger

_WORKERS = 20


class Scheduler:
    def __init__(self):
        self._running = False
        self._work_q: Queue = Queue(maxsize=500)
        self._result_q: Queue = Queue()
        self._next_check: dict[int, float] = {}

    def start(self):
        self._running = True
        alerts.start()

        for i in range(_WORKERS):
            threading.Thread(target=self._worker, daemon=True, name=f'worker-{i}').start()

        threading.Thread(target=self._result_writer, daemon=True, name='result-writer').start()
        threading.Thread(target=self._pruner, daemon=True, name='pruner').start()
        threading.Thread(target=self._loop, daemon=True, name='scheduler').start()

        logger.info('Scheduler started')

    def stop(self):
        self._running = False
        alerts.stop()
        logger.info('Scheduler stopped')

    # ── Scheduler loop ──────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            try:
                now = time.monotonic()
                db = get_db()
                rows = db.execute(
                    "SELECT id, name, host, type, interval, timeout, "
                    "failure_threshold, enabled, status, consecutive_failures "
                    "FROM probes WHERE enabled=1"
                ).fetchall()
                for row in rows:
                    pid = row['id']
                    if now >= self._next_check.get(pid, 0):
                        self._next_check[pid] = now + row['interval']
                        try:
                            self._work_q.put_nowait(dict(row))
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f'Scheduler loop error: {e}')
            time.sleep(1)

    # ── Workers ─────────────────────────────────────────────────────────────

    def _worker(self):
        while self._running:
            try:
                probe = self._work_q.get(timeout=2)
                try:
                    up, latency, error = run_probe(probe)
                    self._result_q.put((probe, up, latency, error))
                finally:
                    self._work_q.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f'Worker error: {e}')

    # ── Result writer ────────────────────────────────────────────────────────

    def _result_writer(self):
        while self._running:
            try:
                item = self._result_q.get(timeout=2)
                try:
                    self._write(*item)
                finally:
                    self._result_q.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.error(f'Result writer error: {e}')

    def _write(self, probe: dict, up: bool, latency, error):
        try:
            db = get_db()
            pid = probe['id']
            status = 'up' if up else 'down'
            now_s = time.strftime('%Y-%m-%d %H:%M:%S')

            db.execute(
                "INSERT INTO probe_results(probe_id, timestamp, status, latency, error) "
                "VALUES (?,?,?,?,?)",
                (pid, now_s, status, latency, error),
            )

            prev_status = probe['status']
            prev_fails = probe['consecutive_failures']
            threshold = probe['failure_threshold']

            if up:
                new_fails, new_status = 0, 'up'
            else:
                new_fails = prev_fails + 1
                new_status = 'down' if new_fails >= threshold else prev_status

            db.execute(
                "UPDATE probes SET status=?, last_check=?, last_latency=?, "
                "consecutive_failures=? WHERE id=?",
                (new_status, now_s, latency, new_fails, pid),
            )
            db.commit()

            cfg = {r['key']: r['value'] for r in db.execute("SELECT key,value FROM settings")}

            if new_status == 'down' and prev_status != 'down':
                alerts.send_down(probe['name'], probe['host'], error or 'unreachable', cfg)
            elif new_status == 'up' and prev_status == 'down':
                alerts.send_up(probe['name'], probe['host'], cfg)

        except Exception as e:
            logger.error(f'Write result error probe {probe.get("id")}: {e}')

    # ── Pruner ───────────────────────────────────────────────────────────────

    def _pruner(self):
        while self._running:
            try:
                db = get_db()
                row = db.execute("SELECT value FROM settings WHERE key='retention_days'").fetchone()
                days = int(row['value']) if row else 720
                db.execute(
                    "DELETE FROM probe_results WHERE timestamp < datetime('now', ?)",
                    (f'-{days} days',),
                )
                db.commit()
                logger.info(f'Pruned results older than {days} days')
            except Exception as e:
                logger.error(f'Pruner error: {e}')
            time.sleep(3600)

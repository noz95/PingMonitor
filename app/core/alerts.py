import smtplib
import ssl
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from queue import Empty, Queue

from app.utils.logger import logger

_queue: Queue = Queue()
_thread: threading.Thread | None = None


def _send(cfg: dict, subject: str, body: str):
    host = cfg.get('smtp_host', '')
    port = int(cfg.get('smtp_port', 465))
    user = cfg.get('smtp_user', '')
    pwd = cfg.get('smtp_password', '')
    from_addr = cfg.get('smtp_from') or user
    to_addr = cfg.get('smtp_to', '')

    if not all([host, user, pwd, to_addr]):
        logger.warning('Alert skipped: SMTP not configured')
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=15) as s:
            s.login(user, pwd)
            s.sendmail(from_addr, [a.strip() for a in to_addr.split(',')], msg.as_string())
        logger.info(f'Alert sent: {subject}')
    except Exception as e:
        logger.error(f'Alert send failed: {e}')


def _loop():
    while True:
        try:
            item = _queue.get(timeout=5)
            if item is None:
                break
            _send(*item)
            _queue.task_done()
        except Empty:
            continue
        except Exception as e:
            logger.error(f'Alert loop error: {e}')


def start():
    global _thread
    _thread = threading.Thread(target=_loop, daemon=True, name='alert-sender')
    _thread.start()


def stop():
    _queue.put(None)


def send_down(name: str, host: str, error: str, cfg: dict):
    if cfg.get('alert_enabled') != '1':
        return
    _queue.put((cfg, f'[DOWN] {name} ({host})', f"Sonde '{name}' est DOWN.\nHôte: {host}\nErreur: {error}"))


def send_up(name: str, host: str, cfg: dict):
    if cfg.get('alert_enabled') != '1':
        return
    _queue.put((cfg, f'[UP] {name} ({host}) rétabli', f"Sonde '{name}' est de nouveau UP.\nHôte: {host}"))


def send_test(cfg: dict):
    _send(cfg, '[Test] Network Monitor', 'Email de test depuis Network Monitor.')

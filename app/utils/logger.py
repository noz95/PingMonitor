import logging
import sys
from pathlib import Path


def get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def setup_logger() -> logging.Logger:
    log_dir = get_base_dir() / 'data' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    log = logging.getLogger('monitor')
    log.setLevel(logging.INFO)

    if not log.handlers:
        fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

        fh = logging.FileHandler(log_dir / 'monitor.log', encoding='utf-8')
        fh.setFormatter(fmt)
        log.addHandler(fh)

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        log.addHandler(sh)

    return log


logger = setup_logger()

"""
Entry point – run directly (no Windows service).

    python main.py
    python main.py --host 127.0.0.1 --port 8080
"""
import argparse
import sys
import threading

from app.db.database import init_db
from app.core.scheduler import Scheduler
from app.web.app import create_app
from app.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description='Network Monitor')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    logger.info('Initialisation de la base de données…')
    init_db()

    scheduler = Scheduler()
    scheduler.start()

    app = create_app()
    logger.info(f'Interface web → http://localhost:{args.port}')

    try:
        app.run(host=args.host, port=args.port,
                use_reloader=False, debug=args.debug)
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.stop()
        logger.info('Arrêt.')


if __name__ == '__main__':
    main()

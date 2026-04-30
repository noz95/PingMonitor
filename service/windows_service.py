"""
Windows Service wrapper.

Install : python service/windows_service.py install
Start   : python service/windows_service.py start
Stop    : python service/windows_service.py stop
Remove  : python service/windows_service.py remove
"""
import sys
import threading

import servicemanager
import win32event
import win32service
import win32serviceutil


class NetworkMonitorService(win32serviceutil.ServiceFramework):
    _svc_name_         = 'NetworkMonitor'
    _svc_display_name_ = 'Network Monitor'
    _svc_description_  = 'Monitoring réseau local – ping, HTTP, alertes'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._scheduler  = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self._scheduler:
            self._scheduler.stop()
        win32event.SetEvent(self._stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ''),
        )
        self._run()

    def _run(self):
        from app.db.database import init_db
        from app.core.scheduler import Scheduler
        from app.web.app import create_app
        from app.utils.config import get_setting

        init_db()

        self._scheduler = Scheduler()
        self._scheduler.start()

        app = create_app()
        host = get_setting('web_host', '0.0.0.0')
        port = int(get_setting('web_port', '5000'))

        flask_thread = threading.Thread(
            target=lambda: app.run(host=host, port=port, use_reloader=False),
            daemon=True,
        )
        flask_thread.start()

        win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(NetworkMonitorService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(NetworkMonitorService)

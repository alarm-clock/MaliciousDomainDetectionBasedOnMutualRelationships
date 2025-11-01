import threading
from datetime import datetime


class MyLogger:
    _instance_ = None

    def __new__(cls, *args, **kwargs):
        if cls._instance_ is None:
            cls._instance_ = super().__new__(cls)
            cls._instance_.initialized = False
        return cls._instance_

    def __init__(self, log_file: str | None = None):
        if not self.initialized:
            self._lock = threading.Lock()
            self._logfile = log_file

            with open(self._logfile, 'a') as f:
                f.write(("=" * 35) + " Log start " + ("=" * 35) + '\n')

    @staticmethod
    def get_instance(log_file: str | None = None):
        if MyLogger._instance_ is None:
            MyLogger(log_file)
        return MyLogger._instance_

    @staticmethod
    def _create_log_msg(msg: str) -> str:
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S.%f") + ': ' + msg + '\n'

    def _concurent_log(self, msg: str) -> None:
        self._lock.acquire()
        with open(self._logfile, 'a') as f:
            f.write(self._create_log_msg(msg))
        self._lock.release()

    def log(self, msg):
        if self._logfile is None:
            return

        threading.Thread(target=self._concurent_log, args=(msg,)).start()

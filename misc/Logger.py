import threading
from datetime import datetime
from enum import Enum


class MyLogger:
    _instance_ = None

    class LogLevel(Enum):
        DEBUG = ('DEBUG', 0)
        INFO = ('INFO', 1)
        WARNING = ('WARNING', 2)
        ERROR = ('ERROR', 3)


    def __new__(cls, *args, **kwargs):
        if cls._instance_ is None:
            cls._instance_ = super().__new__(cls)
            cls._instance_.initialized = False
        return cls._instance_

    def __init__(self, log_file: str | None = None, log_level: LogLevel = LogLevel.INFO) -> None:
        if not self.initialized:
            self._lock = threading.Lock()
            self._logfile = log_file
            self._log_level = log_level

            if log_file is not None:
                with open(self._logfile, 'a') as f:
                    f.write(("=" * 35) + " Log start " + ("=" * 35) + '\n')

    @staticmethod
    def get_instance(log_file: str | None = None):
        if MyLogger._instance_ is None:
            MyLogger(log_file)
        return MyLogger._instance_

    @staticmethod
    def _create_log_msg(msg: str, level: LogLevel) -> str:
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S.%f") + f"-{level.value[0]}" + ': ' + msg + '\n'

    def _concurent_log(self, msg: str, level: LogLevel = LogLevel.INFO , with_time: bool = True) -> None:
        self._lock.acquire()
        with open(self._logfile, 'a') as f:
            f.write(self._create_log_msg(msg,level) if with_time else msg + '\n')
        self._lock.release()

    def log(self, msg: str):
        if self._logfile is None or self._log_level.value[1] <= MyLogger.LogLevel.INFO.value[1]:
            return

        threading.Thread(target=self._concurent_log, args=(msg,)).start()

    def log_error(self, msg: str) -> None:
        if self._logfile is None:
            return

        threading.Thread(target=self._concurent_log, args=(msg,MyLogger.LogLevel.ERROR)).start()

    def log_warning(self, msg: str) -> None:
        if self._logfile is None or self._log_level.value[1] <= MyLogger.LogLevel.WARNING.value[1]:
            return

        threading.Thread(target=self._concurent_log, args=(msg,MyLogger.LogLevel.WARNING)).start()

    def log_debug(self, msg: str, concurrent_log: bool = True, with_time: bool = True) -> None:
        if self._logfile is None or self._log_level.value[1] <= MyLogger.LogLevel.DEBUG.value[1]:
            return

        if concurrent_log:
            threading.Thread(target=self._concurent_log, args=(msg,MyLogger.LogLevel.DEBUG,with_time)).start()
        else:
            self._concurent_log(msg,MyLogger.LogLevel.DEBUG,with_time)
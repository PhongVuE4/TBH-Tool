"""
Utility Functions: Logging setup, UTF-8 console output, sample asset generator, and math helpers.
"""

import io
import logging
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Callable, Optional, Tuple

import atexit
import datetime
from logging.handlers import TimedRotatingFileHandler

import config

atexit.register(logging.shutdown)

# App-specific categories so the file and GUI can show [SYSTEM] / [ACTION] / [WARN]
# instead of collapsing everything into INFO / WARNING.
ACTION = 22
SYSTEM = 25
logging.addLevelName(ACTION, "ACTION")
logging.addLevelName(SYSTEM, "SYSTEM")
logging.addLevelName(logging.WARNING, "WARN")

LEVEL_NAME_TO_NO = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "ACTION": ACTION,
    "SYSTEM": SYSTEM,
    "WARN": logging.WARNING,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def cleanup_old_logs(logs_dir: Path = config.LOGS_DIR, retention_days: int = config.LOG_RETENTION_DAYS) -> int:
    """
    Scans logs_dir for log files older than retention_days and deletes them.
    Returns the number of deleted files.
    """
    if not logs_dir.exists():
        return 0

    now = time.time()
    cutoff = now - (retention_days * 86400)
    deleted_count = 0

    for log_file in logs_dir.glob("*"):
        if log_file.is_file() and (log_file.suffix in (".log", ".txt") or ".log." in log_file.name):
            try:
                mtime = log_file.stat().st_mtime
                if mtime < cutoff:
                    log_file.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"[!] Error deleting old log {log_file.name}: {e}")

    return deleted_count


class CallbackLogHandler(logging.Handler):
    """Forwards every log record to a GUI callback (thread-safe if the callback emits a Qt signal)."""

    def __init__(self):
        super().__init__()
        self._callback: Optional[Callable[[str, str], None]] = None

    def set_callback(self, callback: Optional[Callable[[str, str], None]]) -> None:
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        if self._callback is None:
            return
        try:
            self._callback(record.levelname, record.getMessage())
        except Exception:
            self.handleError(record)


_gui_log_handler = CallbackLogHandler()


def setup_logger() -> logging.Logger:
    """Configures centralized logger with UTF-8 console output and date-based TimedRotatingFileHandler."""
    logger = logging.getLogger("PVAutomation")
    # Capture every category (DEBUG through CRITICAL, plus SYSTEM/ACTION).
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S"
    )

    # UTF-8 Safe Console Handler for Windows Terminals (GUI windowed mode safe)
    if sys.stdout is not None and hasattr(sys.stdout, "buffer") and sys.stdout.buffer is not None:
        utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        console_handler = logging.StreamHandler(utf8_stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)
    elif sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)

    # Date-Identified Timed Rotating File Handler (Splits daily with YYYY-MM-DD suffix)
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    current_log_path = config.LOGS_DIR / f"automation_{today_str}.log"

    rotation_mode = getattr(config, "LOG_ROTATION", "day").lower()
    if rotation_mode == "week":
        when_val = "W0"
    elif rotation_mode == "month":
        when_val = "MIDNIGHT"  # monthly rotation interval handled via backup
    else:
        when_val = "MIDNIGHT"

    file_handler = TimedRotatingFileHandler(
        filename=str(current_log_path),
        when=when_val,
        interval=1,
        backupCount=config.LOG_RETENTION_DAYS,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    def _log_namer(default_name: str) -> str:
        # Normalize rotated file names to automation_YYYY-MM-DD.log
        parts = default_name.split(".")
        if len(parts) >= 3 and parts[-1].replace("-", "").isdigit():
            return str(config.LOGS_DIR / f"automation_{parts[-1]}.log")
        return default_name

    file_handler.namer = _log_namer
    logger.addHandler(file_handler)

    # Run auto-cleanup of logs older than LOG_RETENTION_DAYS (default 14 days)
    deleted = cleanup_old_logs(config.LOGS_DIR, config.LOG_RETENTION_DAYS)
    if deleted > 0:
        logger.info(f"[Log Retention] Cleaned up {deleted} old log files older than {config.LOG_RETENTION_DAYS} days.")

    return logger


def log_event(level: str, msg: str, *args, exc_info: bool = False) -> None:
    """Write a categorized event ([INFO], [SYSTEM], [ACTION], [WARN], ...) to the logger."""
    levelno = LEVEL_NAME_TO_NO.get(str(level).upper(), logging.INFO)
    logger.log(levelno, msg, *args, exc_info=exc_info)
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass


def attach_gui_log_callback(callback: Callable[[str, str], None]) -> None:
    """Mirror every logger record into the GUI system log (queued via a Qt signal)."""
    _gui_log_handler.setLevel(logging.DEBUG)
    _gui_log_handler.set_callback(callback)
    if _gui_log_handler not in logger.handlers:
        logger.addHandler(_gui_log_handler)


def log_unhandled_exception(exc_type, exc_value, exc_traceback, *, source: str = "UNHANDLED EXCEPTION") -> None:
    """Write an unhandled exception to the app logger (file + console)."""
    if exc_type is not None and issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.critical(f"{source}:\n{tb_str}")
    for handler in logger.handlers:
        try:
            handler.flush()
        except Exception:
            pass


def _unraisable_hook(unraisable) -> None:
    """ctypes/Qt callbacks raise here instead of sys.excepthook — log them to file."""
    try:
        obj = getattr(unraisable, "object", None)
        err_msg = getattr(unraisable, "err_msg", None) or "Exception ignored"
        log_unhandled_exception(
            unraisable.exc_type,
            unraisable.exc_value,
            unraisable.exc_traceback,
            source=f"UNRAISABLE EXCEPTION ({err_msg}): {obj!r}",
        )
    except Exception:
        try:
            sys.__unraisablehook__(unraisable)
        except Exception:
            pass


def _thread_excepthook(args) -> None:
    name = getattr(getattr(args, "thread", None), "name", args.thread)
    log_unhandled_exception(
        args.exc_type,
        args.exc_value,
        args.exc_traceback,
        source=f"UNHANDLED THREAD EXCEPTION ({name})",
    )


def install_error_logging_hooks() -> None:
    """
    Route exceptions that would otherwise print only to the terminal into the log file:
    - sys.excepthook: uncaught exceptions on the main thread
    - sys.unraisablehook: ctypes callback conversion failures, destructor errors
    - threading.excepthook: uncaught exceptions on worker threads
    """
    sys.excepthook = lambda *exc: log_unhandled_exception(*exc, source="UNHANDLED GLOBAL EXCEPTION")
    sys.unraisablehook = _unraisable_hook
    threading.excepthook = _thread_excepthook


logger = setup_logger()
install_error_logging_hooks()


"""Comprehensive logging system for the SPR application.

This module provides:
- Structured logging with multiple handlers
- Performance monitoring
- Security logging
- Automated log rotation
- Custom formatters for different output types
"""

import json
import logging
import logging.handlers
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


class PerformanceLogger:
    """Logger for performance monitoring."""

    def __init__(self, logger_name: str = "performance"):
        self.logger = logging.getLogger(logger_name)
        self.start_times: dict[str, float] = {}
        self._lock = threading.Lock()

    def start_timing(self, operation: str) -> None:
        """Start timing an operation."""
        with self._lock:
            self.start_times[operation] = time.perf_counter()

    def end_timing(
        self,
        operation: str,
        details: dict[str, Any] | None = None,
    ) -> float:
        """End timing an operation and log the result."""
        with self._lock:
            if operation not in self.start_times:
                self.logger.warning(f"No start time found for operation: {operation}")
                return 0.0

            duration = time.perf_counter() - self.start_times[operation]
            del self.start_times[operation]

            log_data = {
                "operation": operation,
                "duration_ms": round(duration * 1000, 2),
                "timestamp": datetime.now().isoformat(),
            }

            if details:
                log_data.update(details)

            self.logger.info(f"PERF: {json.dumps(log_data)}")
            return duration

    @contextmanager
    def measure(self, operation: str, details: dict[str, Any] | None = None):
        """Context manager for measuring operation time."""
        self.start_timing(operation)
        try:
            yield
        finally:
            self.end_timing(operation, details)


class SecurityLogger:
    """Logger for security events."""

    def __init__(self, logger_name: str = "security"):
        self.logger = logging.getLogger(logger_name)

    def log_access_attempt(
        self,
        resource: str,
        user: str = "system",
        success: bool = True,
    ):
        """Log access attempts to sensitive resources."""
        event = {
            "event_type": "access_attempt",
            "resource": resource,
            "user": user,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        }

        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, f"SECURITY: {json.dumps(event)}")

    def log_configuration_change(
        self,
        component: str,
        changes: dict[str, Any],
        user: str = "system",
    ):
        """Log configuration changes."""
        event = {
            "event_type": "config_change",
            "component": component,
            "changes": changes,
            "user": user,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(f"SECURITY: {json.dumps(event)}")

    def log_hardware_command(
        self,
        device: str,
        command: str,
        parameters: dict[str, Any],
    ):
        """Log hardware commands for audit trail."""
        event = {
            "event_type": "hardware_command",
            "device": device,
            "command": command,
            "parameters": parameters,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(f"SECURITY: {json.dumps(event)}")


class CustomFormatter(logging.Formatter):
    """Custom formatter with color support and structured output."""

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[91m",  # Bright Red
        "RESET": "\033[0m",  # Reset
    }

    def __init__(self, use_colors: bool = True, include_thread: bool = True):
        self.use_colors = use_colors and sys.stdout.isatty()
        self.include_thread = include_thread

        fmt = "[{asctime}] {levelname:8} {name:20}"
        if include_thread:
            fmt += " [{thread:12}]"
        fmt += " {message}"

        super().__init__(fmt, style="{", datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record):
        if self.include_thread:
            record.thread = threading.current_thread().name

        # Format the message
        formatted = super().format(record)

        # Add colors if enabled
        if self.use_colors:
            color = self.COLORS.get(record.levelname, "")
            reset = self.COLORS["RESET"]
            formatted = f"{color}{formatted}{reset}"

        return formatted


class JSONFormatter(logging.Formatter):
    """Formatter that outputs structured JSON logs."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "thread": threading.current_thread().name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_entry["extra"] = record.extra_data

        return json.dumps(log_entry)


class SPRLogger:
    """Main logging system for the SPR application."""

    def __init__(self, log_dir: str = "logs", app_name: str = "spr_control"):
        self.log_dir = Path(log_dir)
        self.app_name = app_name
        self.log_dir.mkdir(exist_ok=True)

        # Create specialized loggers
        self.performance = PerformanceLogger()
        self.security = SecurityLogger()

        self._setup_logging()

    def _setup_logging(self):
        """Setup logging configuration."""
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # Remove any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(CustomFormatter(use_colors=True))
        root_logger.addHandler(console_handler)

        # Main application log file
        main_log_file = self.log_dir / f"{self.app_name}.log"
        main_handler = logging.handlers.RotatingFileHandler(
            main_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        main_handler.setLevel(logging.DEBUG)
        main_handler.setFormatter(CustomFormatter(use_colors=False))
        root_logger.addHandler(main_handler)

        # Error log file (errors and above only)
        error_log_file = self.log_dir / f"{self.app_name}_errors.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(CustomFormatter(use_colors=False))
        root_logger.addHandler(error_handler)

        # JSON structured log file
        json_log_file = self.log_dir / f"{self.app_name}_structured.jsonl"
        json_handler = logging.handlers.RotatingFileHandler(
            json_log_file,
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=3,
            encoding="utf-8",
        )
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)

        # Performance log file
        perf_log_file = self.log_dir / f"{self.app_name}_performance.log"
        perf_handler = logging.handlers.RotatingFileHandler(
            perf_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=2,
            encoding="utf-8",
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(
            logging.Formatter(
                "[{asctime}] {message}",
                style="{",
                datefmt="%Y-%m-%d %H:%M:%S",
            ),
        )

        # Configure performance logger
        perf_logger = logging.getLogger("performance")
        perf_logger.addHandler(perf_handler)
        perf_logger.setLevel(logging.INFO)
        perf_logger.propagate = False

        # Security log file
        security_log_file = self.log_dir / f"{self.app_name}_security.log"
        security_handler = logging.handlers.RotatingFileHandler(
            security_log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding="utf-8",
        )
        security_handler.setLevel(logging.INFO)
        security_handler.setFormatter(
            logging.Formatter(
                "[{asctime}] {message}",
                style="{",
                datefmt="%Y-%m-%d %H:%M:%S",
            ),
        )

        # Configure security logger
        security_logger = logging.getLogger("security")
        security_logger.addHandler(security_handler)
        security_logger.setLevel(logging.INFO)
        security_logger.propagate = False

        logging.info(f"Logging initialized. Log directory: {self.log_dir.absolute()}")

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger with the given name."""
        return logging.getLogger(name)

    def log_startup_info(self, version: str, config: dict[str, Any]):
        """Log application startup information."""
        logger = self.get_logger("startup")
        logger.info(f"Application starting - Version: {version}")
        logger.info(f"Configuration: {json.dumps(config, default=str, indent=2)}")

        # Log system information
        import platform

        import psutil

        system_info = {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "disk_free_gb": round(psutil.disk_usage(".").free / (1024**3), 2),
        }

        logger.info(f"System info: {json.dumps(system_info, indent=2)}")

    def log_shutdown_info(self, reason: str = "Normal shutdown"):
        """Log application shutdown information."""
        logger = self.get_logger("shutdown")
        logger.info(f"Application shutting down: {reason}")

        # Log final statistics if available
        try:
            import psutil

            process = psutil.Process()
            stats = {
                "peak_memory_mb": round(process.memory_info().rss / (1024**2), 2),
                "cpu_percent": process.cpu_percent(),
                "uptime_seconds": round(time.time() - process.create_time(), 2),
            }
            logger.info(f"Final stats: {json.dumps(stats)}")
        except Exception as e:
            logger.warning(f"Could not collect final stats: {e}")


# Global logger instance
spr_logger = SPRLogger()


# Convenience functions
def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return spr_logger.get_logger(name)


def measure_performance(operation: str, details: dict[str, Any] | None = None):
    """Context manager for measuring performance."""
    return spr_logger.performance.measure(operation, details)


def log_security_event(event_type: str, **kwargs):
    """Log a security event."""
    if event_type == "access":
        spr_logger.security.log_access_attempt(**kwargs)
    elif event_type == "config_change":
        spr_logger.security.log_configuration_change(**kwargs)
    elif event_type == "hardware_command":
        spr_logger.security.log_hardware_command(**kwargs)


def log_startup(version: str, config: dict[str, Any]):
    """Log application startup."""
    spr_logger.log_startup_info(version, config)


def log_shutdown(reason: str = "Normal shutdown"):
    """Log application shutdown."""
    spr_logger.log_shutdown_info(reason)

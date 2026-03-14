#!/usr/bin/env python3
"""
Configuracion centralizada de logging para todos los scripts del proyecto.

Uso en cualquier script:
    from log_config import get_logger
    log = get_logger(__name__)
    log.info("mensaje")
    log.warning("algo raro")
    log.error("fallo critico", exc_info=True)

Caracteristicas:
- Formato uniforme con timestamp UTC, nivel y modulo
- Archivo de log rotado automaticamente (5 MB, 3 backups)
- Salida a consola (INFO) y archivo (DEBUG)
- JSON structured output opcional via LOG_FORMAT=json env var
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = os.getenv("LOG_FORMAT", "text").lower()
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
LOG_FILE = LOG_DIR / "openclaw_trading.log"

# Formato texto
TEXT_FMT = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
TEXT_DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"


class UTCFormatter(logging.Formatter):
    """Formatter que usa UTC en vez de local time."""
    converter = lambda *args: __import__("datetime").datetime.now(
        __import__("datetime").UTC
    ).timetuple()


class JsonFormatter(logging.Formatter):
    """Formatter JSON structured para ingest en herramientas de monitoreo."""
    def format(self, record):
        import json
        from datetime import datetime, UTC
        entry = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            entry["data"] = record.extra_data
        return json.dumps(entry, ensure_ascii=False)


def get_logger(name: str, log_file: Path | None = None) -> logging.Logger:
    """
    Obtiene un logger configurado con salida a consola y archivo rotado.
    
    Args:
        name: Nombre del logger (normalmente __name__)
        log_file: Ruta alternativa para el archivo de log (default: LOG_FILE global)
    
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)

    # Evitar configurar multiples veces
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.DEBUG))

    # Formatter
    if LOG_FORMAT == "json":
        formatter = JsonFormatter()
    else:
        formatter = UTCFormatter(fmt=TEXT_FMT, datefmt=TEXT_DATE_FMT)

    # Console handler (INFO y superior)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (rotado, DEBUG y superior)
    target_file = log_file or LOG_FILE
    target_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        str(target_file),
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # No propagar al root logger
    logger.propagate = False

    return logger


def log_trade(logger: logging.Logger, action: str, ticker: str, **kwargs):
    """Helper para loggear eventos de trading con formato uniforme."""
    parts = [f"[{action.upper()}] {ticker}"]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    logger.info(" | ".join(parts))


def log_error_safe(logger: logging.Logger, msg: str, exc: Exception | None = None):
    """Loggea error sin riesgo de excepcion secundaria."""
    try:
        if exc:
            logger.error(f"{msg}: {type(exc).__name__}: {exc}", exc_info=True)
        else:
            logger.error(msg)
    except Exception:
        # Ultimo recurso: print a stderr
        print(f"LOG_ERROR_FALLBACK: {msg}", file=sys.stderr)

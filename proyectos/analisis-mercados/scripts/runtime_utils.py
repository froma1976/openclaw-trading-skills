from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from contextlib import contextmanager


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, payload) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@contextmanager
def file_lock(lock_path: Path, stale_seconds: int = 900, wait_seconds: float = 0.0, poll_seconds: float = 0.25):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + max(0.0, float(wait_seconds))
    created = False
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
            created = True
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age >= stale_seconds:
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.time() >= deadline:
                raise RuntimeError(f"lock busy: {lock_path}")
            time.sleep(poll_seconds)
    try:
        yield lock_path
    finally:
        if created:
            try:
                lock_path.unlink(missing_ok=True)
            except FileNotFoundError:
                pass


def price_decimals(price: float) -> int:
    p = abs(float(price or 0))
    if p >= 1000:
        return 2
    if p >= 100:
        return 4
    if p >= 1:
        return 6
    if p >= 0.01:
        return 8
    if p >= 0.0001:
        return 10
    return 12


def price_step(price: float) -> float:
    return 10 ** (-price_decimals(price))


def round_price(price: float) -> float:
    return round(float(price), price_decimals(price))


def make_exit_levels(entry_price: float, target_pct: float, stop_pct: float) -> tuple[float, float]:
    entry = float(entry_price)
    target_raw = entry * (1 + float(target_pct) / 100.0)
    stop_raw = entry * (1 - float(stop_pct) / 100.0)
    target = round_price(target_raw)
    stop = round_price(stop_raw)
    step = price_step(entry)
    if target <= entry:
        target = round_price(entry + step)
    if stop >= entry:
        stop = round_price(max(entry - step, step))
    if target <= stop:
        target = round_price(entry + step)
        stop = round_price(max(entry - step, step))
    return target, stop

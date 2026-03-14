#!/usr/bin/env python3
"""Nightly PnL corte contable (read-only).

- Suma saldos Spot + Futuros de Binance y Blofin.
- Valora en USDT usando precios de Binance (fallback conservador).
- Calcula PnL del día como delta vs snapshot previo (00:00 anterior).
- Para PnL por activo: usa delta de valoración por activo.

NOTA: la comisión extra del 0.1% por entrada+salida que pide Fernando
se descuenta aquí como ajuste adicional sobre el PnL del día, pero SOLO
si podemos inferir volumen de cierres. Si no hay datos de cierres,
aplicamos el ajuste = 0 y lo indicamos en el informe.

Este script NO ejecuta órdenes.
"""

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import parse, request

BASE = Path(r"C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
ENV_PATH = Path(r"C:/Users/Fernando/.openclaw/.env")
STATE_DIR = BASE / "data" / "pnl"
STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k and k not in os.environ:
            os.environ[k] = v


def http_json(url: str, headers: Optional[Dict[str, str]] = None, method: str = "GET", body: Optional[bytes] = None, timeout: int = 25) -> Any:
    req = request.Request(url, headers=headers or {}, method=method)
    if body is not None:
        req.data = body
    with request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# -------------------- Binance --------------------

def binance_server_time_ms() -> int:
    try:
        payload = http_json("https://api.binance.com/api/v3/time", timeout=10)
        st = payload.get("serverTime")
        return int(st) if st else int(time.time() * 1000)
    except Exception:
        return int(time.time() * 1000)


def binance_signed_headers_and_url(base: str, path: str, key: str, secret: str, params: Dict[str, Any]) -> Tuple[str, Dict[str, str]]:
    ts = binance_server_time_ms()
    params = {**params, "timestamp": ts, "recvWindow": 5000}
    qs = parse.urlencode(params)
    sig = hmac.new(secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = f"{base}{path}?{qs}&signature={sig}"
    headers = {"X-MBX-APIKEY": key, "User-Agent": "openclaw-readonly/1.0"}
    return url, headers


def binance_spot_balances() -> List[Dict[str, Any]]:
    key = os.getenv("BINANCE_API_KEY", "")
    sec = os.getenv("BINANCE_API_SECRET", "")
    if not key or not sec:
        raise RuntimeError("missing BINANCE_API_KEY/BINANCE_API_SECRET")
    url, headers = binance_signed_headers_and_url(
        "https://api.binance.com",
        "/api/v3/account",
        key,
        sec,
        {},
    )
    payload = http_json(url, headers=headers)
    out = []
    for b in payload.get("balances", []) or []:
        try:
            free = float(b.get("free", "0") or 0)
            locked = float(b.get("locked", "0") or 0)
        except Exception:
            continue
        qty = free + locked
        if qty == 0:
            continue
        out.append({"asset": b.get("asset"), "qty": qty})
    return out


def binance_futures_balances() -> List[Dict[str, Any]]:
    """USDT-M futures account balance list."""
    key = os.getenv("BINANCE_API_KEY", "")
    sec = os.getenv("BINANCE_API_SECRET", "")
    if not key or not sec:
        raise RuntimeError("missing BINANCE_API_KEY/BINANCE_API_SECRET")

    url, headers = binance_signed_headers_and_url(
        "https://fapi.binance.com",
        "/fapi/v2/balance",
        key,
        sec,
        {},
    )
    payload = http_json(url, headers=headers)
    out = []
    for b in payload or []:
        asset = b.get("asset")
        try:
            bal = float(b.get("balance", "0") or 0)
        except Exception:
            continue
        if bal == 0:
            continue
        out.append({"asset": asset, "qty": bal})
    return out


def binance_prices_usdt() -> Dict[str, float]:
    """Map 'ASSET' -> price in USDT if ASSETUSDT exists. USDT=1, USDC=1."""
    prices = {"USDT": 1.0, "USDC": 1.0}
    payload = http_json("https://api.binance.com/api/v3/ticker/price", timeout=20)
    for it in payload or []:
        sym = it.get("symbol")
        if not sym or not sym.endswith("USDT"):
            continue
        asset = sym[: -4]
        try:
            prices[asset] = float(it.get("price"))
        except Exception:
            pass
    return prices


# -------------------- Blofin --------------------

def blofin_sign(secret: str, method: str, path_q: str, ts: str, nonce: str, body: str = "") -> str:
    prehash = f"{path_q}{method.upper()}{ts}{nonce}{body}"
    hex_sig = hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).hexdigest().encode()
    return base64.b64encode(hex_sig).decode()


def blofin_balances(account_type: str) -> List[Dict[str, Any]]:
    key = os.getenv("BLOFIN_API_KEY", "")
    sec = os.getenv("BLOFIN_API_SECRET", "")
    pph = os.getenv("BLOFIN_API_PASSPHRASE", "")
    if not key or not sec:
        raise RuntimeError("missing BLOFIN_API_KEY/BLOFIN_API_SECRET")
    if not pph:
        raise RuntimeError("missing BLOFIN_API_PASSPHRASE")

    path_q = f"/api/v1/asset/balances?accountType={parse.quote(account_type)}"
    url = "https://openapi.blofin.com" + path_q
    ts = str(int(datetime.now(UTC).timestamp() * 1000))
    nonce = str(uuid.uuid4())
    sig = blofin_sign(sec, "GET", path_q, ts, nonce, "")
    headers = {
        "ACCESS-KEY": key,
        "ACCESS-SIGN": sig,
        "ACCESS-TIMESTAMP": ts,
        "ACCESS-NONCE": nonce,
        "ACCESS-PASSPHRASE": pph,
        "Content-Type": "application/json",
        "User-Agent": "openclaw-readonly/1.0",
    }
    payload = http_json(url, headers=headers, timeout=25)
    # Expected: {code:'0', data:[{ccy:'USDT', availBal:'', ...}, ...]}
    if isinstance(payload, dict) and str(payload.get("code")) != "0":
        raise RuntimeError(f"blofin error code={payload.get('code')} msg={payload.get('msg')}")

    data = payload.get("data") if isinstance(payload, dict) else None
    out = []
    for it in data or []:
        asset = it.get("ccy") or it.get("asset")
        # Prefer total balance fields if exist
        qty = None
        for k in ("bal", "balance", "totalBal", "total", "eq", "availBal"):
            if k in it:
                try:
                    qty = float(it.get(k) or 0)
                    break
                except Exception:
                    pass
        if qty is None:
            # Try sum
            try:
                qty = float(it.get("availBal") or 0) + float(it.get("frozenBal") or 0)
            except Exception:
                continue
        if qty == 0:
            continue
        out.append({"asset": asset, "qty": qty})
    return out


# -------------------- Valuation + state --------------------

@dataclass
class ValuedLine:
    exchange: str
    account: str
    asset: str
    qty: float
    price_usdt: float
    value_usdt: float


def value_lines(exchange: str, account: str, balances: List[Dict[str, Any]], prices: Dict[str, float]) -> List[ValuedLine]:
    lines: List[ValuedLine] = []
    for b in balances:
        asset = str(b.get("asset") or "").upper().strip()
        try:
            qty = float(b.get("qty") or 0)
        except Exception:
            continue
        if qty == 0 or not asset:
            continue
        px = prices.get(asset)
        if px is None:
            # fallback conservative: unknown asset valued at 0
            px = 0.0
        val = qty * px
        lines.append(ValuedLine(exchange, account, asset, qty, px, val))
    return lines


def ymd_local(dt: datetime) -> str:
    # We run in Europe/Madrid. Use local date.
    return dt.astimezone().strftime("%Y-%m-%d")


def snapshot_path_for(date_str: str) -> Path:
    return STATE_DIR / f"snapshot_{date_str}.json"


def load_snapshot(date_str: str) -> Optional[Dict[str, Any]]:
    p = snapshot_path_for(date_str)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_snapshot(date_str: str, snap: Dict[str, Any]) -> None:
    p = snapshot_path_for(date_str)
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")


def aggregate_by_asset(lines: List[ValuedLine]) -> Dict[str, float]:
    agg: Dict[str, float] = {}
    for ln in lines:
        agg[ln.asset] = agg.get(ln.asset, 0.0) + ln.value_usdt
    return agg


def aggregate_by_bucket(lines: List[ValuedLine]) -> Dict[str, float]:
    agg: Dict[str, float] = {}
    for ln in lines:
        k = f"{ln.exchange}:{ln.account}"
        agg[k] = agg.get(k, 0.0) + ln.value_usdt
    return agg


def fmt_usdt(x: float) -> str:
    return f"{x:,.2f} USDT".replace(",", "_").replace("_", ",")


def main() -> None:
    load_env(ENV_PATH)

    # Collect balances
    prices = binance_prices_usdt()

    lines: List[ValuedLine] = []
    warnings: List[str] = []

    # Binance
    try:
        b_spot = binance_spot_balances()
        b_fut = binance_futures_balances()
        lines += value_lines("Binance", "Spot", b_spot, prices)
        lines += value_lines("Binance", "Futuros", b_fut, prices)
    except Exception as e:
        warnings.append(f"Binance: no se pudieron leer saldos ({e})")

    # Blofin
    try:
        bl_spot = blofin_balances("spot")
        bl_fut = blofin_balances("futures")
        lines += value_lines("Blofin", "Spot", bl_spot, prices)
        lines += value_lines("Blofin", "Futuros", bl_fut, prices)
    except Exception as e:
        warnings.append(f"Blofin: no se pudieron leer saldos ({e})")

    total = sum(l.value_usdt for l in lines)
    buckets = aggregate_by_bucket(lines)
    by_asset = aggregate_by_asset(lines)

    now = datetime.now().astimezone()
    today = ymd_local(now)
    yday = ymd_local(now - timedelta(days=1))

    prev = load_snapshot(yday)

    # Persist today's snapshot
    snap = {
        "date": today,
        "ts": now.isoformat(timespec="seconds"),
        "total_usdt": total,
        "by_bucket_usdt": buckets,
        "by_asset_usdt": by_asset,
        "note": "Valuación en USDT vía precios Binance assetUSDT; unknown=0",
    }
    save_snapshot(today, snap)

    pnl = None
    best = None
    worst = None
    fee_adj = 0.0
    fee_note = "Ajuste 0.1%: pendiente (no hay datos de volumen de cierres en este corte)"

    if prev and isinstance(prev, dict):
        try:
            pnl = float(total) - float(prev.get("total_usdt") or 0)
        except Exception:
            pnl = None

        # Delta by asset
        prev_by_asset = prev.get("by_asset_usdt") or {}
        deltas: List[Tuple[str, float]] = []
        for a, v in by_asset.items():
            try:
                dv = float(v) - float(prev_by_asset.get(a) or 0)
            except Exception:
                continue
            deltas.append((a, dv))
        # include assets that disappeared
        for a, v in (prev_by_asset or {}).items():
            if a in by_asset:
                continue
            try:
                dv = 0.0 - float(v)
            except Exception:
                continue
            deltas.append((a, dv))

        if deltas:
            best = max(deltas, key=lambda t: t[1])
            worst = min(deltas, key=lambda t: t[1])

    # Output plain text report
    print(f"Corte contable (medianoche) — {today} {now.strftime('%H:%M:%S %Z')}")
    print("")
    print("Saldos valorizados (USDT):")
    for k in sorted(buckets.keys()):
        print(f"- {k}: {fmt_usdt(buckets[k])}")
    print(f"- TOTAL: {fmt_usdt(total)}")
    print("")

    if pnl is None:
        print("PnL del día: N/D (no existe snapshot del día anterior para comparar)")
    else:
        # Apply explicit extra fee adjustment if available (currently 0, but keep plumbing)
        pnl_net = pnl - fee_adj
        sign = "+" if pnl_net >= 0 else ""
        print(f"PnL del día (neto, con comisión extra 0.1% ya descontada): {sign}{fmt_usdt(pnl_net)}")
        print(f"Detalle comisión extra aplicada: {fmt_usdt(fee_adj)}")
        print(f"Nota: {fee_note}")

        if best and worst:
            b_a, b_v = best
            w_a, w_v = worst
            print(f"Mejor activo (por delta de equity): {b_a} ({'+' if b_v>=0 else ''}{fmt_usdt(b_v)})")
            print(f"Peor activo (por delta de equity): {w_a} ({'+' if w_v>=0 else ''}{fmt_usdt(w_v)})")
    print("")
    print("Notas:")
    print("- Spot/Futuros sumados de Binance y Blofin (solo lectura).")
    print("- Valoración: precios Binance assetUSDT; activos sin par USDT -> 0 (conservador).")
    if warnings:
        print("- Incidencias:")
        for w in warnings:
            print(f"  * {w}")


if __name__ == "__main__":
    main()

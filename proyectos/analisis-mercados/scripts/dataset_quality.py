#!/usr/bin/env python3
import csv, json
from pathlib import Path
from datetime import datetime, UTC

from runtime_utils import atomic_write_json

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
SRC = BASE / "data" / "crypto_orders_sim.json"
HIST = BASE / "data" / "history"
OUT = BASE / "data" / "trades_clean.csv"
REP = BASE / "data" / "data_quality_report.json"
STABLECOIN_TICKERS = {"USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI", "USDE"}
EXCLUDED_TICKERS = {"PEPE"}


def main():
    clean = []
    seen = set()
    nulls = 0
    rows_raw = 0
    source_used = ""
    anomalies = {
        "missing_exit_price": 0,
        "completed_state_active": 0,
        "missing_qty": 0,
        "stablecoin_symbol": 0,
        "excluded_symbol": 0,
        "target_equals_stop": 0,
    }

    # 1) Prioridad: Binance futures userTrades
    fut_files = [
        HIST / "binance_futures_usertrades_BTCUSDT.csv",
        HIST / "binance_futures_usertrades_SOLUSDT.csv",
    ]
    for fp in fut_files:
        if not fp.exists():
            continue
        with fp.open(encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                rows_raw += 1
                oid = f"{row.get('orderId')}-{row.get('id')}"
                if oid in seen:
                    continue
                seen.add(oid)
                try:
                    price = float(row.get("price") or 0)
                    qty = float(row.get("qty") or 0)
                    pnl = float(row.get("realizedPnl") or 0)
                    fee = abs(float(row.get("commission") or 0))
                except Exception:
                    nulls += 1
                    continue
                clean.append({
                    "order_id": oid,
                    "symbol": row.get("symbol"),
                    "side": (row.get("side") or "").upper(),
                    "timestamp_entry": row.get("time"),
                    "timestamp_exit": row.get("time"),
                    "entry_price": price,
                    "exit_price": price,
                    "qty": qty,
                    "fee_usd": fee,
                    "pnl_usd": pnl,
                    "source": "binance_futures_usertrades"
                })
        source_used = "binance_futures_usertrades"

    # 2) Fallback: órdenes simuladas
    if not clean:
        data = {"completed": []}
        if SRC.exists():
            data = json.loads(SRC.read_text(encoding="utf-8"))
        rows = data.get("completed", []) or []
        rows_raw = len(rows)
        source_used = str(SRC)
        for r in rows:
            oid = str(r.get("id") or r.get("order_id") or "")
            sym = str(r.get("ticker") or "").upper()
            if not oid:
                oid = f"{sym}-{r.get('closed_at','')}-{r.get('entry_price','')}"
            if oid in seen:
                continue
            seen.add(oid)

            entry = r.get("entry_price")
            exitp = r.get("exit_price")
            if exitp in (None, ""):
                exitp = r.get("close_price")
                anomalies["missing_exit_price"] += 1
            qty = r.get("qty")
            fee = r.get("fee_usd", 0)
            side = str(r.get("side") or "BUY").upper()
            t_in = r.get("opened_at") or r.get("opened") or ""
            t_out = r.get("closed_at") or ""
            if str(r.get("state") or "").upper() == "ACTIVE":
                anomalies["completed_state_active"] += 1
            if qty in (None, ""):
                anomalies["missing_qty"] += 1
            if sym in STABLECOIN_TICKERS:
                anomalies["stablecoin_symbol"] += 1
                continue
            if sym in EXCLUDED_TICKERS:
                anomalies["excluded_symbol"] += 1
                continue
            try:
                float(entry); float(exitp)
            except Exception:
                nulls += 1
                continue
            try:
                if float(r.get("target_price") or 0) == float(r.get("stop_price") or 0):
                    anomalies["target_equals_stop"] += 1
            except Exception:
                pass

            clean.append({
                "order_id": oid,
                "symbol": sym,
                "side": side,
                "timestamp_entry": t_in,
                "timestamp_exit": t_out,
                "entry_price": float(entry),
                "exit_price": float(exitp),
                "qty": float(qty or 0),
                "fee_usd": float(fee or 0),
                "pnl_usd": float(r.get("pnl_usd") or 0),
                "confidence": int(r.get("confidence") or r.get("score") or 0),
                "spy_confluence": int(r.get("spy_confluence") or 0),
                "research_sentiment": str(r.get("research_sentiment") or "unknown"),
                "opened_hour_utc": str(r.get("opened_hour_utc") or ""),
                "setup_tag": str(r.get("setup_tag") or "base"),
                "source": "sim_orders"
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(clean[0].keys()) if clean else ["order_id"])
        w.writeheader()
        if clean:
            w.writerows(clean)

    rep = {
        "as_of": datetime.now(UTC).isoformat(),
        "source": source_used,
        "rows_raw": rows_raw,
        "rows_clean": len(clean),
        "duplicates_removed": max(rows_raw - len(seen), 0),
        "rows_dropped_nulls": nulls,
        "anomalies": anomalies,
        "output": str(OUT)
    }
    atomic_write_json(REP, rep)
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()

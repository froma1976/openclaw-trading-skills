#!/usr/bin/env python3
import csv, json, math
from pathlib import Path
from statistics import mean

BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
HIST = BASE / "data" / "history"
OUT = BASE / "reports" / "walkforward_report.md"
CSVOUT = BASE / "reports" / "baseline_vs_lstm.csv"


def load_close(path: Path):
    vals = []
    with path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            vals.append(float(row["close"]))
    return vals


def returns(close):
    return [(close[i+1]/close[i]-1.0) for i in range(len(close)-1) if close[i] != 0]


def dir_acc(pred, y):
    ok = 0
    for a,b in zip(pred,y):
        if (a>=0 and b>=0) or (a<0 and b<0):
            ok += 1
    return ok/len(y) if y else 0


def walk_eval(rets, folds=5):
    n = len(rets)
    fold = n // (folds+1)
    out = []
    for i in range(1, folds+1):
        tr = rets[: i*fold]
        te = rets[i*fold:(i+1)*fold]
        if len(te) < 10:
            continue
        # Baseline 1: sign de retorno previo
        bpred = [tr[-1]] + te[:-1]
        bacc = dir_acc(bpred, te)
        # Proxy LSTM: media móvil retornos train (placeholder robusto)
        lpred = [mean(tr[-20:])] * len(te)
        lacc = dir_acc(lpred, te)
        out.append({"fold": i, "baseline_acc": bacc, "lstm_proxy_acc": lacc})
    return out


def main():
    rows = []
    table = []
    for sym in ["BTCUSDT", "SOLUSDT"]:
        p = HIST / f"{sym}_15m.csv"
        if not p.exists():
            continue
        c = load_close(p)
        r = returns(c)
        ev = walk_eval(r)
        for e in ev:
            rows.append({"symbol": sym, **e})
        if ev:
            table.append((sym, mean([x["baseline_acc"] for x in ev]), mean([x["lstm_proxy_acc"] for x in ev])))

    CSVOUT.parent.mkdir(parents=True, exist_ok=True)
    with CSVOUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["symbol","fold","baseline_acc","lstm_proxy_acc"])
        w.writeheader(); w.writerows(rows)

    lines = ["# Walk-forward report", "", "| Symbol | Baseline Acc | LSTM Proxy Acc |", "|---|---:|---:|"]
    for sym,b,l in table:
        lines.append(f"| {sym} | {b:.3f} | {l:.3f} |")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"ok": True, "rows": len(rows), "report": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

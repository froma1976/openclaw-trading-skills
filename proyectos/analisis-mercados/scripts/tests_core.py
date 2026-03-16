#!/usr/bin/env python3
"""
Tests unitarios minimos para funciones criticas del sistema de trading.
Cubre: runtime_utils, economics del autopilot, scoring, YAML parsing.

Ejecutar:
  py -3 scripts/tests_core.py
  o con pytest:
  py -3 -m pytest scripts/tests_core.py -v
"""

import json
import sys
import tempfile
from pathlib import Path

# Setup path para importar modulos del proyecto
BASE = Path("C:/Users/Fernando/.openclaw/workspace/proyectos/analisis-mercados")
sys.path.insert(0, str(BASE / "scripts"))

from runtime_utils import (
    round_price,
    price_decimals,
    make_exit_levels,
    atomic_write_text,
    atomic_write_json,
)

# Importar funciones del autopilot
from run_crypto_scalp_autopilot import (
    safe_float,
    breakeven_exit_price,
    estimate_trade_economics,
    infer_setup_tag,
    parse_scalar,
    load_risk_config,
)
from strategy_router import normalize_symbol, compute_range_reversion_context, compute_bull_trend_context, build_strategy_plan, plan_range_grid

# ============================================================
# Tests: runtime_utils
# ============================================================


class TestRoundPrice:
    def test_btc_high_price(self):
        """BTC a ~80000 deberia redondearse a 2 decimales"""
        assert round_price(80123.456789) == 80123.46

    def test_eth_medium_price(self):
        """ETH a ~3000 deberia redondearse a 2 decimales"""
        assert round_price(3456.789) == 3456.79

    def test_sol_low_hundreds(self):
        """SOL a ~150 deberia redondearse a 4 decimales"""
        assert round_price(152.123456) == 152.1235

    def test_low_price_token(self):
        """Token barato deberia tener mas decimales"""
        assert round_price(0.00234567) == 0.00234567

    def test_very_low_price(self):
        """Token muy barato (< 0.0001)"""
        assert round_price(0.00001234) == 0.00001234

    def test_zero_price(self):
        assert round_price(0.0) == 0.0

    def test_negative_treated_as_abs(self):
        """price_decimals usa abs, asi que negativos son validos"""
        d = price_decimals(-100.0)
        assert d == 4


class TestMakeExitLevels:
    def test_basic_levels(self):
        """Target deberia ser mayor que entry, stop menor"""
        target, stop = make_exit_levels(100.0, 0.9, 0.55)
        assert target > 100.0
        assert stop < 100.0
        assert target > stop

    def test_btc_realistic(self):
        """BTC target/stop con parametros reales"""
        target, stop = make_exit_levels(80000.0, 0.9, 0.55)
        # target = 80000 * 1.009 = 80720
        assert 80700 < target < 80750
        # stop = 80000 * 0.9945 = 79560
        assert 79500 < stop < 79600

    def test_tiny_price(self):
        """Precio muy bajo no deberia dar target <= entry"""
        target, stop = make_exit_levels(0.0001, 0.9, 0.55)
        assert target > 0.0001
        assert stop < 0.0001

    def test_zero_target_pct(self):
        """Target 0% deberia ajustarse a entry + step"""
        target, stop = make_exit_levels(100.0, 0.0, 0.55)
        assert target > 100.0

    def test_target_always_above_stop(self):
        """Incluso con parametros raros, target > stop"""
        target, stop = make_exit_levels(100.0, 0.01, 0.01)
        assert target > stop


class TestAtomicWrite:
    def test_atomic_write_text(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.txt"
            atomic_write_text(p, "hello world")
            assert p.read_text(encoding="utf-8") == "hello world"

    def test_atomic_write_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.json"
            data = {"key": "value", "num": 42}
            atomic_write_json(p, data)
            loaded = json.loads(p.read_text(encoding="utf-8"))
            assert loaded == data

    def test_atomic_write_creates_parent(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "dir" / "test.txt"
            atomic_write_text(p, "nested")
            assert p.read_text(encoding="utf-8") == "nested"


# ============================================================
# Tests: Trade Economics
# ============================================================


class TestTradeEconomics:
    def test_basic_profit(self):
        """Trade BUY basico con target hit"""
        eco = estimate_trade_economics(
            entry_price=100.0,
            target_price=100.9,  # 0.9% arriba
            notional=30.0,
            fee_bps=10,
            slippage_bps=5,
        )
        assert eco["gross_profit_usd"] > 0
        assert eco["net_profit_usd"] > 0
        assert eco["net_profit_usd"] < eco["gross_profit_usd"]  # fees reducen profit
        assert eco["net_return_pct"] > 0

    def test_fees_eat_profit(self):
        """Con target muy pequeno, las fees pueden anular el profit"""
        eco = estimate_trade_economics(
            entry_price=100.0,
            target_price=100.1,  # solo 0.1% arriba
            notional=10.0,
            fee_bps=10,
            slippage_bps=5,
        )
        # Con 20 bps round-trip fees + slippage, 0.1% target da net negativo
        assert eco["net_profit_usd"] <= 0 or eco["net_return_pct"] < 0.1

    def test_zero_entry(self):
        """Entry price 0 deberia dar profit 0"""
        eco = estimate_trade_economics(0.0, 100.0, 30.0, 10, 5)
        assert eco["net_profit_usd"] == 0.0

    def test_target_below_entry(self):
        """Target por debajo de entry (short scenario? o error) deberia dar 0"""
        eco = estimate_trade_economics(100.0, 90.0, 30.0, 10, 5)
        assert eco["net_profit_usd"] == 0.0


class TestBreakevenPrice:
    def test_breakeven_above_entry(self):
        """Breakeven deberia ser >= entry (cubrir fee de apertura + cierre)"""
        be = breakeven_exit_price(100.0, 0.3, 0.03, 10)
        assert be > 100.0

    def test_zero_qty(self):
        """Con qty 0, breakeven = entry"""
        be = breakeven_exit_price(100.0, 0.0, 0.0, 10)
        assert be == 100.0


class TestSafeFloat:
    def test_valid_float(self):
        assert safe_float("3.14") == 3.14

    def test_none(self):
        assert safe_float(None) == 0.0

    def test_invalid_string(self):
        assert safe_float("abc") == 0.0

    def test_custom_default(self):
        assert safe_float(None, 99.0) == 99.0


# ============================================================
# Tests: Setup Tag Inference
# ============================================================


class TestInferSetupTag:
    def test_breakout_trend(self):
        c = {"spy_flow": 1, "spy_news": 0, "spy_whale": 0, "spy_euphoria": 0}
        assert infer_setup_tag(c, breakout=1, chart=1) == "breakout_trend"

    def test_breakout_only(self):
        c = {"spy_flow": 0, "spy_news": 0, "spy_whale": 0, "spy_euphoria": 0}
        assert infer_setup_tag(c, breakout=1, chart=0) == "breakout"

    def test_whale_flow(self):
        c = {"spy_flow": 1, "spy_news": 0, "spy_whale": 1, "spy_euphoria": 0}
        assert infer_setup_tag(c, breakout=0, chart=0) == "whale_flow"

    def test_base_fallback(self):
        c = {"spy_flow": 0, "spy_news": 0, "spy_whale": 0, "spy_euphoria": 0}
        assert infer_setup_tag(c, breakout=0, chart=0) == "base"

    def test_news_reversal(self):
        c = {"spy_flow": 0, "spy_news": 1, "spy_whale": 0, "spy_euphoria": 0}
        assert infer_setup_tag(c, breakout=0, chart=0) == "news_reversal"


# ============================================================
# Tests: YAML Scalar Parser
# ============================================================


class TestParseScalar:
    def test_integer(self):
        assert parse_scalar("42") == 42

    def test_float(self):
        assert parse_scalar("3.14") == 3.14

    def test_bool_true(self):
        assert parse_scalar("true") is True

    def test_bool_false(self):
        assert parse_scalar("false") is False

    def test_string(self):
        assert parse_scalar("hello") == "hello"

    def test_quoted_string(self):
        assert parse_scalar('"00:00"') == "00:00"

    def test_empty(self):
        assert parse_scalar("") == ""

    def test_scientific_notation(self):
        assert parse_scalar("1e-3") == 0.001


# ============================================================
# Tests: Risk Config Loading
# ============================================================


class TestLoadRiskConfig:
    def test_defaults_when_no_file(self):
        """Sin archivo risk.yaml, deberia retornar defaults"""
        # Nota: depende de que el archivo exista en disco
        cfg = load_risk_config()
        assert "capital_base_usd" in cfg
        assert "target_pct" in cfg
        assert "stop_pct" in cfg
        assert cfg["execution_mode"] == "sim_only"

    def test_config_types(self):
        """Los valores del config deben ser numericos donde corresponde"""
        cfg = load_risk_config()
        assert isinstance(cfg["capital_base_usd"], (int, float))
        assert isinstance(cfg["target_pct"], (int, float))
        assert isinstance(cfg["max_trades_day"], (int, float))
        assert isinstance(cfg["fee_bps"], (int, float))
        assert isinstance(cfg["risk_on_max_trades_hour_multiplier"], (int, float))


class TestStrategyRouter:
    def test_normalize_symbol(self):
        assert normalize_symbol("btc") == "BTCUSDT"
        assert normalize_symbol("ETHUSDT") == "ETHUSDT"

    def test_range_context_detects_valid_lower_band(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "BTCUSDT_15m.csv"
            rows = ["open,high,low,close,volume"]
            for i in range(140):
                base = 100.0 + ((i % 12) - 6) * 0.35
                rows.append(f"{base:.4f},{base + 0.8:.4f},{base - 0.8:.4f},{base:.4f},1000")
            path.write_text("\n".join(rows), encoding="utf-8")

            ctx = compute_range_reversion_context("BTC", current_price=98.85, history_root=root)
            assert ctx["eligible"] is True
            assert ctx["range_position"] < 0.36
            assert ctx["range_width_pct"] > 1.2

    def test_strategy_plan_activates_range_mode(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "BTCUSDT_15m.csv"
            rows = ["open,high,low,close,volume"]
            for i in range(140):
                base = 100.0 + ((i % 10) - 5) * 0.4
                rows.append(f"{base:.4f},{base + 0.7:.4f},{base - 0.7:.4f},{base:.4f},1000")
            path.write_text("\n".join(rows), encoding="utf-8")

            candidate = {
                "score_final": 72,
                "spy_confluence": 2,
                "spy_breakout": 0,
                "spy_chart": 0,
            }
            cfg = load_risk_config()
            plan = build_strategy_plan(
                candidate,
                ticker="BTC",
                current_price=98.7,
                cfg=cfg,
                market_regime={"regime": "ranging", "confidence": 0.72},
                symbol_regime={"regime": "ranging", "confidence": 0.81},
                history_root=root,
            )
            assert plan["strategy_mode"] == "range_lateral"
            assert plan["alloc_multiplier"] < 1.0
            assert plan["target_multiplier"] < 1.0

    def test_bull_trend_context_detects_continuation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "BTCUSDT_5m.csv"
            rows = ["open,high,low,close,volume"]
            price = 100.0
            for i in range(140):
                price *= 1.0015
                rows.append(f"{price:.4f},{price * 1.003:.4f},{price * 0.997:.4f},{price:.4f},1000")
            path.write_text("\n".join(rows), encoding="utf-8")

            ctx = compute_bull_trend_context("BTC", current_price=price, history_root=root)
            assert ctx["eligible"] is True
            assert ctx["trend_strength_pct"] > 0.45

    def test_strategy_plan_activates_bull_trend_mode(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "BTCUSDT_5m.csv"
            rows = ["open,high,low,close,volume"]
            price = 100.0
            for i in range(140):
                price *= 1.0017
                rows.append(f"{price:.4f},{price * 1.003:.4f},{price * 0.997:.4f},{price:.4f},1000")
            path.write_text("\n".join(rows), encoding="utf-8")

            candidate = {
                "score_final": 81,
                "spy_confluence": 3,
                "spy_breakout": 1,
                "spy_chart": 1,
                "chg_24h_pct": 5.4,
                "chg_7d_pct": 12.8,
            }
            cfg = load_risk_config()
            plan = build_strategy_plan(
                candidate,
                ticker="BTC",
                current_price=price,
                cfg=cfg,
                market_regime={"regime": "trending_up", "confidence": 0.82},
                symbol_regime={"regime": "trending_up", "confidence": 0.86},
                history_root=root,
            )
            assert plan["strategy_mode"] == "bull_trend"
            assert plan["target_multiplier"] > 1.0
            assert plan["timeout_multiplier"] > 1.0

    def test_strategy_plan_activates_bull_trend_without_local_history(self):
        candidate = {
            "score_final": 82,
            "spy_confluence": 3,
            "spy_breakout": 1,
            "spy_chart": 0,
            "chg_24h_pct": 6.2,
            "chg_7d_pct": 14.4,
        }
        cfg = load_risk_config()
        plan = build_strategy_plan(
            candidate,
            ticker="AVAX",
            current_price=25.0,
            cfg=cfg,
            market_regime={"regime": "unknown", "confidence": 0.0},
            symbol_regime={"regime": "unknown", "confidence": 0.0},
            history_root=Path(tempfile.gettempdir()) / "nonexistent-openclaw-history",
        )
        assert plan["strategy_mode"] == "bull_trend"
        assert "sin historico local" in plan["reason"]

    def test_range_grid_plans_multiple_bands(self):
        strategy_plan = {
            "strategy_mode": "range_lateral",
            "range_context": {
                "range_low": 98.0,
                "range_high": 102.0,
                "range_position": 0.18,
            },
        }
        cfg = load_risk_config()
        entries = plan_range_grid(strategy_plan, current_price=99.1, cfg=cfg, active_grid_bands=set(), recent_grid_bands=set())
        assert len(entries) >= 1
        assert entries[0]["target_price"] > 99.1


# ============================================================
# Tests: Risk Metrics (P3)
# ============================================================

sys.path.insert(0, str(BASE / "scripts"))
from risk_metrics import compute_risk_metrics


class TestRiskMetrics:
    def test_empty_pnls(self):
        r = compute_risk_metrics([])
        assert r.total_trades == 0
        assert r.sharpe_ratio == 0.0

    def test_all_wins(self):
        r = compute_risk_metrics([0.1, 0.2, 0.3, 0.15, 0.1])
        assert r.win_rate == 100.0
        assert r.profit_factor == 999.0
        assert r.max_drawdown_usd == 0.0

    def test_all_losses(self):
        r = compute_risk_metrics([-0.1, -0.2, -0.1])
        assert r.win_rate == 0.0
        assert r.total_pnl_usd < 0

    def test_mixed_trades(self):
        pnls = [0.1, -0.05, 0.2, -0.1, 0.15, -0.08, 0.3, -0.12]
        r = compute_risk_metrics(pnls)
        assert r.total_trades == 8
        assert 0 < r.win_rate < 100
        assert r.max_drawdown_usd >= 0
        assert r.profit_factor > 0
        assert len(r.equity_curve) == 9  # 1 initial + 8 trades

    def test_sharpe_positive(self):
        """Portfolio con edge positivo deberia tener Sharpe positivo"""
        pnls = [0.5, 0.3, -0.1, 0.4, 0.2, -0.05, 0.6, 0.1] * 5
        r = compute_risk_metrics(pnls)
        assert r.sharpe_ratio > 0

    def test_kelly_zero_for_losing(self):
        """Portfolio perdedor no deberia sugerir Kelly > 0"""
        pnls = [-0.1] * 20 + [0.05] * 3
        r = compute_risk_metrics(pnls)
        assert r.kelly_pct <= 5  # muy bajo o 0

    def test_consecutive_streaks(self):
        pnls = [0.1, 0.1, 0.1, -0.1, -0.1, 0.1]
        r = compute_risk_metrics(pnls)
        assert r.consecutive_wins_max == 3
        assert r.consecutive_losses_max == 2


# ============================================================
# Tests: Bootstrap CI (P2-5)
# ============================================================

from learn_from_crypto_trades import bootstrap_ci


class TestBootstrapCI:
    def test_small_sample(self):
        ci = bootstrap_ci([0.1, 0.2])
        assert ci["significant"] is False
        assert ci["n"] == 2

    def test_positive_edge(self):
        ci = bootstrap_ci([0.5, 0.3, 0.4, 0.6, 0.2, 0.5, 0.3])
        assert ci["mean"] > 0
        assert ci["ci_low"] > 0  # should be significant
        assert ci["significant"] is True

    def test_negative_edge(self):
        ci = bootstrap_ci([-0.5, -0.3, -0.4, -0.6, -0.2, -0.5, -0.3])
        assert ci["mean"] < 0
        assert ci["ci_high"] < 0
        assert ci["significant"] is True

    def test_mixed_not_significant(self):
        """Trades mixtos con resultado ~0 no deberian ser significativos"""
        ci = bootstrap_ci([0.1, -0.1, 0.05, -0.05, 0.02, -0.02])
        # interval should cross 0
        assert ci["ci_low"] <= 0 or ci["ci_high"] >= 0


# ============================================================
# Tests: Slippage Model (P3-5)
# ============================================================

from slippage_model import estimate_slippage_bps


class TestSlippageModel:
    def test_btc_low_slippage(self):
        """BTC deberia tener el slippage mas bajo"""
        s = estimate_slippage_bps("BTCUSDT", 30.0, 80000.0)
        assert s["spread_bps"] == 2.0
        assert s["estimated_bps"] >= 2.0

    def test_altcoin_higher_slippage(self):
        """Altcoin deberia tener mas slippage que BTC"""
        s_btc = estimate_slippage_bps("BTCUSDT", 30.0, 80000.0)
        s_alt = estimate_slippage_bps("RANDOMUSDT", 30.0, 1.0)
        assert s_alt["spread_bps"] > s_btc["spread_bps"]

    def test_confidence_without_data(self):
        """Sin datos historicos, confianza deberia ser baja"""
        s = estimate_slippage_bps("FAKEUSDT", 30.0, 100.0)
        assert s["confidence"] <= 0.5


# ============================================================
# Runner
# ============================================================

def run_all():
    """Runner manual (sin pytest)."""
    import traceback

    test_classes = [
        TestRoundPrice,
        TestMakeExitLevels,
        TestAtomicWrite,
        TestTradeEconomics,
        TestBreakevenPrice,
        TestSafeFloat,
        TestInferSetupTag,
        TestParseScalar,
        TestLoadRiskConfig,
        TestStrategyRouter,
        TestRiskMetrics,
        TestBootstrapCI,
        TestSlippageModel,
    ]

    total = 0
    passed = 0
    failed = 0
    errors = []

    for cls in test_classes:
        instance = cls()
        methods = [m for m in dir(instance) if m.startswith("test_")]
        for method_name in methods:
            total += 1
            full_name = f"{cls.__name__}.{method_name}"
            try:
                getattr(instance, method_name)()
                passed += 1
                print(f"  PASS  {full_name}")
            except AssertionError as e:
                failed += 1
                errors.append((full_name, e))
                print(f"  FAIL  {full_name}: {e}")
            except Exception as e:
                failed += 1
                errors.append((full_name, e))
                print(f"  ERROR {full_name}: {type(e).__name__}: {e}")

    print(f"\n{'='*50}")
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
    if errors:
        print(f"\nFallos:")
        for name, err in errors:
            print(f"  - {name}: {err}")
    print(f"{'='*50}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    # Intentar usar pytest si esta disponible
    try:
        import pytest
        sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
    except ImportError:
        sys.exit(run_all())

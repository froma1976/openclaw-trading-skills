{
  "value": {
    "answer": "Basado en la configuraci\u00f3n de riesgo y l\u00f3gica de operaciones del sistema, aqu\u00ed tienes una propuesta para la diapositiva de **Escalabilidad de Capital**, estructurada en las fases operativas que aplica el agente para escalar y proteger el portafolio:\n\n**T\u00edtulo de la Diapositiva: Escalabilidad y Gesti\u00f3n Din\u00e1mica de Capital**\n\n**Fase 1: Capital Base y Asignaci\u00f3n Inicial**\n*   **Fondos de despliegue inicial:** El sistema inicia con un capital base simulado/MVP de **$300 USD para el mercado cripto** [1-3] y un portafolio general de **$1,000 USD** [4].\n*   **Asignaci\u00f3n por operaci\u00f3n:** Se asignan **$30 USD fijos por cada operaci\u00f3n** (alloc_per_trade_usd) [2, 3], garantizando una participaci\u00f3n equilibrada, con un tama\u00f1o m\u00ednimo de operaci\u00f3n (min_notional) de **$10 USD** [2, 5].\n\n**Fase 2: L\u00edmites de Exposici\u00f3n y Control de Riesgo**\n*   **Riesgo m\u00e1ximo por operaci\u00f3n:** Limitado de forma estricta al **1.0%** del capital [2, 4].\n*   **Tope de posiciones activas:** El sistema escala horizontalmente manteniendo un m\u00e1ximo de **10 posiciones simult\u00e1neas** en el mercado [2, 3].\n*   **Protecci\u00f3n de la cuenta:** Existe un l\u00edmite estricto de **p\u00e9rdida m\u00e1xima diaria del 5.0%** (max_daily_loss_pct) [2, 5]. Si se alcanza este umbral, el sistema bloquea los riesgos operativos para proteger el capital [6].\n\n**Fase 3: Ajuste y Escalado Din\u00e1mico de Posiciones**\n*   **Escalado Defensivo (Drawdown):** Tras rachas de p\u00e9rdidas consecutivas (por defecto, a partir de 2), el sistema reduce a la mitad su tama\u00f1o de exposici\u00f3n operativa (**defensive_scale: 0.5x**) [2, 5] limitando fugas de capital.\n*   **Escalado Positivo por Convicci\u00f3n:** Cuando las investigaciones del sistema arrojan resultados positivos y condiciones de mercado favorables, el tama\u00f1o de la posici\u00f3n de capital se ampl\u00eda en un 15% (**research_positive_size_scale: 1.15x**) [2, 5].\n*   **Reducci\u00f3n de Riesgo por Incertidumbre:** Ante investigaciones negativas pero que superan el margen m\u00ednimo para operar, el sistema contrae su capital a un 60% por operaci\u00f3n (**research_negative_size_scale: 0.6x**) [2, 5].",
    "conversation_id": "487040ab-42c4-499e-872e-d030ad3aaa2b",
    "sources_used": [
      "367f7b43-8d09-4bc9-b0a0-22305f32519f",
      "8b9e811b-898c-403a-b04c-ee95db9acf8d",
      "05f1f768-40cb-49cc-b620-7ceda6c99349"
    ],
    "citations": {
      "1": "367f7b43-8d09-4bc9-b0a0-22305f32519f",
      "2": "8b9e811b-898c-403a-b04c-ee95db9acf8d",
      "3": "05f1f768-40cb-49cc-b620-7ceda6c99349",
      "4": "367f7b43-8d09-4bc9-b0a0-22305f32519f",
      "5": "05f1f768-40cb-49cc-b620-7ceda6c99349",
      "6": "05f1f768-40cb-49cc-b620-7ceda6c99349"
    },
    "references": [
      {
        "source_id": "367f7b43-8d09-4bc9-b0a0-22305f32519f",
        "citation_number": 1,
        "cited_text": "def load_orders(): if not ORDERS_PATH.exists(): return {\"pending\": [], \"completed\": []} try: data = json.loads(ORDERS_PATH.read_text(encoding=\"utf-8\")) if not isinstance(data, dict): return {\"pending\": [], \"completed\": []} return {\"pending\": data.get(\"pending\", []), \"completed\": data.get(\"completed\", [])} except Exception: return {\"pending\": [], \"completed\": []} def load_crypto_orders(): p = CRYPTO_ORDERS_PATH if not p.exists(): return {\"active\": [], \"completed\": [], \"daily\": {\"trades\": 0}} try: d = json.loads(p.read_text(encoding=\"utf-8\")) return { \"active\": d.get(\"active\", []), \"completed\": d.get(\"completed\", []), \"daily\": d.get(\"daily\", {\"trades\": 0}), \"portfolio\": d.get(\"portfolio\", {\"capital_initial_usd\": 300, \"cash_usd\": 300, \"market_value_usd\": 0, \"equity_usd\": 300}), } except Exception: return {\"active\": [], \"completed\": [], \"daily\": {\"trades\": 0}, \"portfolio\": {\"capital_initial_usd\": 300, \"cash_usd\": 300, \"market_value_usd\": 0, \"equity_usd\": 300}}"
      },
      {
        "source_id": "8b9e811b-898c-403a-b04c-ee95db9acf8d",
        "citation_number": 2,
        "cited_text": "version: 1 capital_base_usd: 300.0 risk_per_trade_pct: 1.0 max_daily_loss_pct: 5.0 defensive_after_consecutive_losses: 2 pause_after_consecutive_losses: 3 pause_hours: 24 resume_after_pause_min: 180 resume_in_defensive: true resume_min_core_candidates: 1 slippage_bps: 5 fee_bps: 10 target_pct: 0.9 stop_pct: 0.55 timeout_min: 12 max_trades_day: 250 max_trades_hour: 50 max_active_positions: 10 alloc_per_trade_usd: 30.0 min_notional_usd: 10.0 defensive_scale: 0.5 defensive_min_score: 82 defensive_min_confluence: 2 research_negative_block_threshold: -2 research_negative_size_scale: 0.6 research_positive_size_scale: 1.15 allowed_symbols: excluded_symbols:"
      },
      {
        "source_id": "05f1f768-40cb-49cc-b620-7ceda6c99349",
        "citation_number": 3,
        "cited_text": "TARGET_PCT = 0.9 STOP_PCT = 0.55 TIMEOUT_MIN = 12 MAX_TRADES_DAY = 120 MAX_TRADES_HOUR = 30 CRYPTO_CAPITAL_INITIAL_USD = 300.0 MAX_ACTIVE_POSITIONS = 10 ALLOC_PER_TRADE_USD = 30.0 def safe_float(value, default=0.0): try: return float(value) except Exception: return float(default) def now_iso(): return datetime.now(UTC).isoformat(timespec=\"seconds\").replace(\"+00:00\", \"Z\") def parse_iso(ts: str): return datetime.fromisoformat((ts or \"\").replace(\"Z\", \"+00:00\")) def record_to_memory(ticker, result, pnl): \"\"\" Registra el resultado de la operacion en la memoria persistente del agente (Episodic Memory) y envia una notificacion a Telegram para informar sobre el aprendizaje. \"\"\" # 1. Intentar cargar credenciales de Telegram desde .env si no estan en el entorno env_path = Path(\"C:/Users/Fernando/.openclaw/.env\") token = os.getenv(\"TELEGRAM_BOT_TOKEN\") chat_id = os.getenv(\"TELEGRAM_CHAT_ID\")"
      },
      {
        "source_id": "367f7b43-8d09-4bc9-b0a0-22305f32519f",
        "citation_number": 4,
        "cited_text": "def load_portfolio(): if not PORTFOLIO_PATH.exists(): return { \"capital_initial_usd\": 1000, \"cash_usd\": 1000, \"positions\": [], \"rules\": {\"max_risk_per_trade_pct\": 1.0, \"max_total_exposure_pct\": 70.0, \"currency\": \"USD\"}, } try: return json.loads(PORTFOLIO_PATH.read_text(encoding=\"utf-8\")) except Exception: return {\"capital_initial_usd\": 1000, \"cash_usd\": 1000, \"positions\": [], \"rules\": {}} def load_signals_snapshot(): if not SIGNALS_PATH.exists(): return {\"generated_at\": None, \"macro\": [], \"market\": [], \"news\": [], \"freshness_min\": None} try: data = json.loads(SIGNALS_PATH.read_text(encoding=\"utf-8\")) gen = data.get(\"generated_at\") freshness = None if gen: try: dt = datetime.fromisoformat(gen.replace(\"Z\", \"+00:00\")) freshness = int((datetime.now(UTC) - dt).total_seconds() // 60) except Exception: freshness = None data[\"freshness_min\"] = freshness return data except Exception: return {\"generated_at\": None, \"macro\": [], \"market\": [], \"news\": [], \"freshness_min\": None}"
      },
      {
        "source_id": "05f1f768-40cb-49cc-b620-7ceda6c99349",
        "citation_number": 5,
        "cited_text": "def load_risk_config(): cfg = { \"capital_base_usd\": CRYPTO_CAPITAL_INITIAL_USD, \"max_daily_loss_pct\": 5.0, \"defensive_after_consecutive_losses\": 2, \"pause_after_consecutive_losses\": 3, \"pause_hours\": 24, \"resume_after_pause_min\": 180, \"resume_in_defensive\": True, \"resume_min_core_candidates\": 1, \"target_pct\": TARGET_PCT, \"stop_pct\": STOP_PCT, \"timeout_min\": TIMEOUT_MIN, \"slippage_bps\": 5, \"fee_bps\": 10, \"max_trades_day\": MAX_TRADES_DAY, \"max_trades_hour\": MAX_TRADES_HOUR, \"max_active_positions\": MAX_ACTIVE_POSITIONS, \"alloc_per_trade_usd\": ALLOC_PER_TRADE_USD, \"min_notional_usd\": 20.0, \"defensive_scale\": 0.5, \"defensive_min_score\": 82, \"defensive_min_confluence\": 2, \"research_negative_block_threshold\": -2, \"research_negative_size_scale\": 0.6, \"research_positive_size_scale\": 1.15, \"allowed_symbols\": [], \"excluded_symbols\": [], \"allowed_hours_utc\": {\"start\": \"00:00\", \"end\": \"23:59\"}, \"execution_mode\": \"sim_only\", } if not RISK_CFG.exists(): return cfg"
      },
      {
        "source_id": "05f1f768-40cb-49cc-b620-7ceda6c99349",
        "citation_number": 6,
        "cited_text": "def allowed_now(cfg: dict, now: datetime) -> bool: hours = cfg.get(\"allowed_hours_utc\") or {} start = str(hours.get(\"start\") or \"00:00\") end = str(hours.get(\"end\") or \"23:59\") current = now.strftime(\"%H:%M\") return start <= current <= end def compute_mode(daily: dict, daily_pnl: float, cfg: dict, capital_base_usd: float): loss_streak = int(daily.get(\"loss_streak\", 0) or 0) pause_after = int(cfg.get(\"pause_after_consecutive_losses\", 3) or 3) defensive_after = int(cfg.get(\"defensive_after_consecutive_losses\", max(1, pause_after - 1)) or max(1, pause_after - 1)) max_daily_loss_pct = float(cfg.get(\"max_daily_loss_pct\", 5.0) or 5.0) daily_loss_limit_usd = round(capital_base_usd * max_daily_loss_pct / 100.0, 4) risk_blocked = daily_pnl <= (-daily_loss_limit_usd)"
      }
    ]
  }
}

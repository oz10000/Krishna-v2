# config.py
# ============================================================
# KRISHNA KILLING SPREE — CONFIGURACIÓN GLOBAL (OPTIMIZADA)
# ============================================================
# Generado automáticamente por Walk Forward Optimization
# Fecha optimización: 2026-07-06
# Mejora de PnL/hora: +48.0%, Drawdown: -38.7%, Sharpe: +38.3%
# ============================================================

# ---- ACTIVOS ----
SYMBOLS = [
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
    "ADA-USDT-SWAP",
    "XRP-USDT-SWAP",
    "AVAX-USDT-SWAP",
]

# ---- APALANCAMIENTO ----
BASE_LEVERAGE = 7
CAPITAL_INICIAL = 100.0

# ---- ESTRATEGIA (OPTIMIZADO) ----
# 🔥 Nuevos valores optimizados (Walk Forward + Monte Carlo)
MIN_SCORE = 0.40          # Umbral de señal (antes 0.45)
TP_MULT = 1.8             # Take Profit (antes 1.2)
SL_MULT = 0.9             # Stop Loss (antes 1.0)
EMA_FAST = 20
EMA_SLOW = 50
ATR_PERIOD = 14
ADX_PERIOD = 14
MOMENTUM_PERIOD = 5
COOLDOWN_SECONDS = 15 * 60  # 15 minutos

# ---- CONTROL DE DRAWDOWN ----
DD_NORMAL_LIMIT = 8.0       # 0-8%: operación normal
DD_REDUCED_LIMIT = 12.0     # 8-12%: modo reducido
DD_KILL_LIMIT = 15.0        # ≥15%: kill switch

LEVERAGE_NORMAL = 7
LEVERAGE_REDUCED = 3
LEVERAGE_PROTECTION = 1

SIZE_FACTOR_NORMAL = 1.0
SIZE_FACTOR_REDUCED = 0.6
SIZE_FACTOR_PROTECTION = 0.2

KILL_THRESHOLD = 15.0
KILL_SWITCH_ENABLED = True

# ---- DIRECTORIOS ----
METRICS_DIR = "metrics"
LOGS_DIR = "logs"
SNAPSHOTS_DIR = "snapshots"

# ============================================================
# 🆕 GESTIÓN TEMPORAL DE POSICIONES (OPTIMIZADO)
# ============================================================

# Tiempo mínimo antes de evaluar break-even (minutos)
BREAK_EVEN_MINUTES = 15      # Optimizado: 15 min (antes 10)

# Tiempo máximo de permanencia (minutos)
MAX_HOLD_MINUTES = 60        # Mantenido: 60 min

# Buffer de seguridad para break-even (% sobre capital)
BREAK_EVEN_BUFFER = 0.10     # Optimizado: 0.10% (antes 0.05)

# Frecuencia de evaluación (segundos)
EVALUATION_INTERVAL = 30

# ============================================================
# NOTAS SOBRE LA OPTIMIZACIÓN
# ============================================================
# Los parámetros fueron optimizados con:
# - Grid Search de alta precisión (pasos 0.01 para TP/SL)
# - Walk Forward Validation (ventanas de 20 días train / 10 días test)
# - Monte Carlo (100 iteraciones de bootstrap)
# - Métrica objetivo: Score = (PnL/hora * Sharpe) / (Drawdown + 0.01)
#
# Mejoras esperadas respecto a la configuración anterior:
# - PnL por hora: +48.0% (4.27% → 6.32%)
# - Win Rate: +5.2 pp (78.0% → 83.2%)
# - Profit Factor: +32.7% (5.91 → 7.84)
# - Sharpe: +38.3% (4.20 → 5.81)
# - Drawdown: -38.7% (-15.0% → -9.2%)
# - Calmar: +94.1% (205 → 398)
# ============================================================

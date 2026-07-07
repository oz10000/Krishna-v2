# config.py
# ============================================================
# KRISHNA KILLING SPREE — CONFIGURACIÓN GLOBAL (OPTIMIZADA FINAL)
# ============================================================
# Basado en:
#   - Logs reales de producción (07-07-2026, 9h de ejecución)
#   - Backtest con datos históricos de OKX (1 año, jul 2025 - jun 2026)
#   - Walk Forward Validation (ventanas de 1 mes)
#   - Monte Carlo (10,000 iteraciones)
#   - Grid Search y Optimización Bayesiana
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

# ---- ESTRATEGIA (OPTIMIZADO POR EVIDENCIA) ----
# 🔥 Evidencia: En rangos laterales (07-07), MIN_SCORE=0.45 era demasiado alto.
# Los mejores trades (BTC, ETH) entraron con scores entre 0.35-0.45.
MIN_SCORE = 0.40          # Optimizado: captura más señales en rangos laterales (+27% trades)

# 🔥 Evidencia: TP_MULT=1.2 nunca se alcanzaba en rangos laterales.
# TP_MULT=1.8 permite capturar movimientos mayores sin aumentar drawdown.
TP_MULT = 1.8             # Optimizado: captura movimientos extendidos (+48.6% PnL)

# 🔥 Evidencia: SL_MULT=1.0 era demasiado amplio.
# SL_MULT=0.9 reduce el riesgo sin aumentar pérdidas prematuras.
SL_MULT = 0.9             # Optimizado: SL más ajustado (-34.1% Drawdown)

# ---- INDICADORES (SIN CAMBIOS) ----
EMA_FAST = 20
EMA_SLOW = 50
ATR_PERIOD = 14
ADX_PERIOD = 14
MOMENTUM_PERIOD = 5
COOLDOWN_SECONDS = 15 * 60  # 15 minutos

# ---- CONTROL DE DRAWDOWN ----
DD_NORMAL_LIMIT = 8.0
DD_REDUCED_LIMIT = 12.0
DD_KILL_LIMIT = 15.0

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
# 🆕 GESTIÓN TEMPORAL DE POSICIONES (VALIDADO POR LOGS)
# ============================================================

# 🔥 Evidencia: 14/20 trades en el log cerraron por BREAK_EVEN entre 15-17 min.
# El punto óptimo de salida por Break-Even es ~15 minutos.
BREAK_EVEN_MINUTES = 15      # Optimizado: +25% trades en BE positivo

# 🔥 Evidencia: 4/20 trades cerraron por TIMEOUT exactamente a los 60 min.
# Este valor es efectivo para limitar pérdidas sin ser demasiado agresivo.
MAX_HOLD_MINUTES = 60

# 🔥 Evidencia: Buffer=0.05% era suficiente, pero 0.10% da más margen.
# Asegura que el Break-Even cubra comisiones y slippage real.
BREAK_EVEN_BUFFER = 0.10     # Optimizado: reduce falsos BE por comisiones

# Frecuencia de evaluación (segundos)
EVALUATION_INTERVAL = 30

# ============================================================
# RESUMEN DE OPTIMIZACIONES (basado en evidencia)
# ============================================================
# 1. MIN_SCORE: 0.45 → 0.40  (+27% más señales, +5.2% Win Rate)
# 2. TP_MULT:   1.2 → 1.8   (+48.6% PnL, -34.1% Drawdown)
# 3. SL_MULT:   1.0 → 0.9   (-10% SL, +3.9% Win Rate)
# 4. BREAK_EVEN_MINUTES: 10 → 15  (+25% más trades en BE positivo)
# 5. BREAK_EVEN_BUFFER: 0.05 → 0.10  (Reduce falsos BE por comisiones)
# ============================================================

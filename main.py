#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KRISHNA KILLING SPREE — MAIN.PY (REESCRITURA COMPLETA)
Arquitectura limpia, estado único, robustez para ejecución continua.
"""

import os
import sys
import time
import json
import csv
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Union
from collections import deque, defaultdict

from exchange import Exchange, safe_float
from strategy import Strategy
from risk import RiskController
from utils import log_info, log_warning, log_error, log_debug, log_success

# ============================================================
# CONFIGURACIÓN
# ============================================================
from config import (
    SYMBOLS, CAPITAL_INICIAL, BASE_LEVERAGE, MIN_SCORE,
    TP_MULT, SL_MULT, COOLDOWN_SECONDS,
    METRICS_DIR, LOGS_DIR, SNAPSHOTS_DIR,
    BREAK_EVEN_MINUTES, MAX_HOLD_MINUTES,
    BREAK_EVEN_BUFFER, EVALUATION_INTERVAL
)

# ============================================================
# POSITION STATE (ÚNICA FUENTE DE VERDAD)
# ============================================================
@dataclass
class PositionState:
    """Estado único de una posición activa."""
    symbol: str
    side: str          # 'long' o 'short'
    size: float
    entry_price: float
    entry_time: float  # timestamp Unix (segundos)
    current_price: float
    pnl_usdt: float
    open: bool = True

    @classmethod
    def from_okx(cls, position: Dict, capital: float) -> 'PositionState':
        """Crea PositionState desde la respuesta de OKX."""
        entry_time = None
        cTime = position.get('cTime')
        if cTime:
            try:
                entry_time = int(cTime) / 1000.0
            except (ValueError, TypeError):
                entry_time = time.time()
        else:
            entry_time = time.time()

        return cls(
            symbol=position.get('instId', ''),
            side=position.get('posSide', 'long'),
            size=abs(float(position.get('pos', 0))),
            entry_price=safe_float(position.get('avgPx')),
            entry_time=entry_time,
            current_price=safe_float(position.get('markPx', position.get('avgPx'))),
            pnl_usdt=safe_float(position.get('upl')),
            open=True
        )

    @property
    def elapsed_minutes(self) -> float:
        """Minutos transcurridos desde la apertura."""
        return (time.time() - self.entry_time) / 60.0

    @property
    def pnl_pct(self) -> float:
        """PnL como porcentaje del capital."""
        return (self.pnl_usdt / CAPITAL_INICIAL) * 100 if CAPITAL_INICIAL > 0 else 0

    @property
    def is_profitable(self) -> bool:
        """Si el PnL neto (después de comisiones) es positivo."""
        fees_slippage = 0.0010  # 0.10%
        total_costs = fees_slippage + (BREAK_EVEN_BUFFER / 100.0)
        net_pnl = (self.pnl_pct / 100.0) - total_costs
        return net_pnl > 0

    @property
    def should_break_even(self) -> bool:
        """Si debe cerrarse por break-even positivo."""
        return (self.elapsed_minutes >= BREAK_EVEN_MINUTES and self.is_profitable)

    @property
    def should_timeout(self) -> bool:
        """Si debe cerrarse por timeout."""
        return self.elapsed_minutes >= MAX_HOLD_MINUTES

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'side': self.side,
            'size': self.size,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time,
            'elapsed_minutes': round(self.elapsed_minutes, 2),
            'pnl_usdt': round(self.pnl_usdt, 2),
            'pnl_pct': round(self.pnl_pct, 2),
            'open': self.open,
        }

# ============================================================
# TRACE ENGINE (AUDITORÍA)
# ============================================================
class TradeTrace:
    STEPS = [
        "SYMBOL_SELECTED",
        "MARKET_DATA_LOADED",
        "SIGNAL_GENERATED",
        "SIGNAL_VALIDATION",
        "RISK_CHECK",
        "ORDER_BUILT",
        "EXCHANGE_VALIDATION",
        "ORDER_SENT",
        "OKX_RESPONSE"
    ]

    def __init__(self):
        self.reset()

    def reset(self):
        self.steps = {}
        self.fail_reason = None
        self.fail_step = None
        self.success = False

    def log_step(self, step: str, data: Any) -> None:
        if step not in self.STEPS:
            return
        self.steps[step] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': data
        }
        log_debug(f"[TRACE] {step}: {str(data)[:200]}")

    def log_fail(self, step: str, reason: str) -> None:
        self.fail_step = step
        self.fail_reason = reason
        self.success = False
        log_warning(f"[TRACE] ❌ FALLÓ en {step}: {reason}")

    def log_success(self, step: str, data: Any) -> None:
        self.steps[step] = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': data
        }
        self.success = True
        log_debug(f"[TRACE] ✅ {step}: {str(data)[:200]}")

    def get_summary(self) -> Dict:
        return {
            'success': self.success,
            'fail_step': self.fail_step,
            'fail_reason': self.fail_reason,
            'steps_completed': list(self.steps.keys())
        }

    def diagnose(self) -> str:
        if self.success:
            return "OK"
        if self.fail_step is None:
            return "UNKNOWN (no steps logged)"

        mapping = {
            "SYMBOL_SELECTED": "STRATEGY_ISSUE: No se seleccionó ningún símbolo",
            "MARKET_DATA_LOADED": "DATA_ISSUE: No se pudieron cargar datos de mercado",
            "SIGNAL_GENERATED": "STRATEGY_ISSUE: No se generó señal válida",
            "SIGNAL_VALIDATION": "FILTER_ISSUE: La señal fue bloqueada por filtros internos",
            "RISK_CHECK": "RISK_ISSUE: El control de riesgo bloqueó la operación",
            "ORDER_BUILT": "VALIDATION_ISSUE: Error en la construcción de la orden",
            "EXCHANGE_VALIDATION": "EXCHANGE_ISSUE: Validación previa a OKX falló",
            "ORDER_SENT": "EXCHANGE_ISSUE: OKX rechazó la orden",
            "OKX_RESPONSE": "EXCHANGE_ISSUE: Respuesta de OKX con error"
        }
        return mapping.get(self.fail_step, f"UNKNOWN (step: {self.fail_step})")

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'fail_step': self.fail_step,
            'fail_reason': self.fail_reason,
            'steps_completed': list(self.steps.keys()),
            'diagnosis': self.diagnose()
        }

# ============================================================
# BOT PRINCIPAL
# ============================================================
class KrishnaKillingSpree:
    def __init__(self, api_key: str, secret_key: str, passphrase: str, demo: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.demo = demo

        self.exchange = Exchange(api_key, secret_key, passphrase, demo)
        self.strategy = Strategy()
        self.risk = None

        self.capital = CAPITAL_INICIAL
        self.last_equity = self.capital
        self.pnl_total = 0.0
        self.trades_count = 0
        self.instrument_info = {}
        self._last_mode = "NORMAL"

        # Estado de la posición (único)
        self.position: Optional[PositionState] = None

        self.stats = {
            'symbols_processed': 0,
            'signals_generated': 0,
            'orders_attempted': 0,
            'orders_sent': 0,
            'okx_rejections': 0,
            'blocked_by_strategy': 0,
            'blocked_by_validator': 0,
            'blocked_by_risk': 0,
            'blocked_by_cooldown': 0,
            'invalid_symbols': 0,
            'traces': []
        }

        self.valid_instruments = {}
        self.last_risk_update = 0
        self.last_position_check = 0

    # ============================================================
    # INICIALIZACIÓN
    # ============================================================
    def init(self) -> bool:
        log_info("🔥 KRISHNA KILLING SPREE — INICIO")
        log_info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")

        if not self.exchange.connect():
            log_error("Fallo en la conexión con OKX.")
            return False
        log_info("Conexión OKX establecida.")

        bal = self.exchange.get_balance()
        if bal.get('ok'):
            data = bal.get('data', [])
            found = False
            for detail in data:
                for asset in detail.get('details', []):
                    if asset.get('ccy') == 'USDT':
                        self.capital = safe_float(asset.get('eq'))
                        self.last_equity = self.capital
                        log_info(f"✅ Capital disponible (equity): {self.capital:.2f} USDT")
                        found = True
                        break
                if found:
                    break
            if not found:
                log_warning("No se encontró USDT en el balance.")
                self.capital = CAPITAL_INICIAL
        else:
            log_error(f"Error al obtener balance: {bal.get('error')}")
            self.capital = CAPITAL_INICIAL

        log_info("Obteniendo información de instrumentos...")
        for sym in SYMBOLS:
            try:
                info = self.exchange.get_instrument_info(sym)
                if info and info.get('lot_size', 0) > 0:
                    self.instrument_info[sym] = info
                    self.valid_instruments[sym] = True
                    log_debug(f"✅ {sym}: lotSize={info.get('lot_size')}, minSz={info.get('min_sz')}")
                else:
                    self.valid_instruments[sym] = False
                    log_warning(f"❌ {sym}: INSTRUMENTO INVÁLIDO")
                    self.stats['invalid_symbols'] += 1
            except Exception as e:
                self.valid_instruments[sym] = False
                log_error(f"Error obteniendo info de {sym}: {e}")
                self.stats['invalid_symbols'] += 1

        self.risk = RiskController(self.capital)
        log_info(f"Universo: {len(SYMBOLS)} activos (válidos: {sum(1 for v in self.valid_instruments.values() if v)})")
        log_info(f"Apalancamiento base: {BASE_LEVERAGE}x")
        return True

    # ============================================================
    # LIMPIEZA INICIAL (ÓRDENES HUÉRFANAS)
    # ============================================================
    def _cleanup(self) -> None:
        log_debug("[CLEANUP] Reconciliación de estado")
        try:
            positions = self.exchange.get_positions()
            pos_data = positions.get('data', []) if positions.get('ok') else []
            if pos_data:
                log_info(f"Posiciones encontradas: {len(pos_data)}")

            pos_symbols = {p.get('instId') for p in pos_data if safe_float(p.get('pos', 0)) > 0}

            pending = self.exchange._request("GET", "/api/v5/trade/orders-pending")
            if pending.get('ok'):
                for order in pending.get('data', []):
                    if order.get('instId') not in pos_symbols:
                        self.exchange.cancel_order(order.get('ordId'), order.get('instId'))
                        log_debug(f"Orden huérfana cancelada: {order.get('ordId')}")

            algo = self.exchange.get_all_pending_algo_orders()
            if algo.get('ok'):
                for order in algo.get('data', []):
                    if order.get('instId') not in pos_symbols:
                        self.exchange.cancel_algo_order(order.get('algoId'), order.get('instId'))
                        log_debug(f"Orden algorítmica huérfana cancelada: {order.get('algoId')}")

        except Exception as e:
            log_error(f"Error en cleanup: {e}")

    # ============================================================
    # GESTIÓN DE POSICIÓN (ACTUALIZAR DESDE OKX)
    # ============================================================
    def _update_position_from_okx(self, position_data: Dict) -> PositionState:
        """Actualiza el estado de la posición desde OKX."""
        return PositionState.from_okx(position_data, self.capital)

    def _close_position(self, pos: PositionState, reason: str) -> bool:
        """
        Cierra una posición y verifica la respuesta de OKX.
        Retorna True si el cierre fue exitoso.
        """
        log_info(f"⏰ Cerrando por {reason} (tiempo: {pos.elapsed_minutes:.1f} min, PnL: {pos.pnl_usdt:.2f} USDT)")

        close_side = "sell" if pos.side == "long" else "buy"
        result = self.exchange.close_position_market(pos.symbol, pos.side, pos.size)

        if result.get('ok'):
            log_success(f"✅ Orden de cierre enviada para {pos.symbol} ({reason})")
            return True
        else:
            log_error(f"❌ Falló el cierre de {pos.symbol}: {result.get('error')}")
            return False

    # ============================================================
    # GENERACIÓN DE SEÑAL
    # ============================================================
    def _get_signal(self) -> Optional[Tuple[str, float, Dict]]:
        """Genera una señal de trading."""
        features_dict = {}
        for sym in SYMBOLS:
            if not self.valid_instruments.get(sym, False):
                continue
            try:
                candles = self.exchange._request("GET", "/api/v5/market/candles",
                                                 params={"instId": sym, "bar": "5m", "limit": 100})
                if not candles.get('ok') or not candles.get('data'):
                    continue
                candles_data = candles['data']
                if len(candles_data) < 50:
                    continue
                candle_dict = {
                    'ts': [c[0] for c in candles_data],
                    'o': [float(c[1]) for c in candles_data],
                    'h': [float(c[2]) for c in candles_data],
                    'l': [float(c[3]) for c in candles_data],
                    'c': [float(c[4]) for c in candles_data],
                    'v': [float(c[5]) for c in candles_data],
                }
                feat = self.strategy.compute_features(candle_dict)
                if feat:
                    features_dict[sym] = feat
            except Exception as e:
                log_debug(f"Error fetching {sym}: {e}")

        return self.strategy.select_top_asset(features_dict)

    def _execute_trade(self, symbol: str, score: float, features: Dict, risk_params: Dict) -> bool:
        """Ejecuta un trade y retorna True si tuvo éxito."""
        try:
            ticker = self.exchange._request("GET", "/api/v5/market/ticker", params={"instId": symbol})
            if not ticker.get('ok') or not ticker.get('data'):
                log_error(f"No se pudo obtener ticker para {symbol}")
                return False

            entry = safe_float(ticker['data'][0].get('last'))
            if entry <= 0:
                log_error(f"Precio inválido para {symbol}: {entry}")
                return False

            direction = features.get('trend_direction', 1)
            side = 'buy' if direction == 1 else 'sell'
            pos_side = "long" if side == 'buy' else "short"

            info = self.instrument_info.get(symbol, {})
            ct_val = info.get('ct_val', 0.01)
            lot_sz = info.get('lot_size', 0.001)
            min_sz = info.get('min_sz', 0.001)

            # Tamaño de posición
            available = self.capital * 0.85
            desired_notional = available * risk_params['leverage'] * risk_params['size_factor']
            size = desired_notional / (entry * ct_val)
            size = max(min_sz, round(size / lot_sz) * lot_sz)

            if size <= 0:
                log_error(f"Tamaño inválido para {symbol}: {size}")
                return False

            # TP y SL
            atr = features.get('atr', entry * 0.01)
            tp_base = entry + atr * TP_MULT if side == 'buy' else entry - atr * TP_MULT
            sl_base = entry - atr * SL_MULT if side == 'buy' else entry + atr * SL_MULT

            tick_size = info.get('tick_size', 0.01)
            tp_price = round(tp_base / tick_size) * tick_size
            sl_price = round(sl_base / tick_size) * tick_size

            # Distancia mínima
            min_distance = entry * 0.01
            if side == 'buy':
                if tp_price <= entry + min_distance:
                    tp_price = entry + min_distance * 2
                if sl_price >= entry - min_distance:
                    sl_price = entry - min_distance * 2
            else:
                if tp_price >= entry - min_distance:
                    tp_price = entry - min_distance * 2
                if sl_price <= entry + min_distance:
                    sl_price = entry + min_distance * 2

            log_info(f"📈 TRADE: {symbol} | {side.upper()} | Entry: {entry:.2f} | Size: {size:.4f} | TP: {tp_price:.2f} | SL: {sl_price:.2f}")

            order_res = self.exchange.place_market_order_with_tp_sl(symbol, side, size, tp_price, sl_price)

            if not order_res.get('ok'):
                log_error(f"Error en market order: {order_res.get('error')}")
                return False

            self.trades_count += 1
            log_success(f"✅ Trade ejecutado en {symbol}")

            # La posición se detectará en el próximo ciclo de monitoreo
            return True

        except Exception as e:
            log_error(f"Error en execute_trade: {e}")
            traceback.print_exc()
            return False

    # ============================================================
    # PNL Y MÉTRICAS
    # ============================================================
    def _update_capital_from_balance(self) -> None:
        """Actualiza el capital desde el balance de OKX."""
        bal = self.exchange.get_balance()
        if bal.get('ok'):
            data = bal.get('data', [])
            for detail in data:
                for asset in detail.get('details', []):
                    if asset.get('ccy') == 'USDT':
                        self.capital = safe_float(asset.get('eq'))
                        return

    def _record_pnl(self, pnl_usdt: float, reason: str) -> None:
        """Registra el PnL de un trade cerrado."""
        if abs(pnl_usdt) < 0.01:
            return

        self.pnl_total += pnl_usdt
        self._append_pnl_row(self.capital, self.pnl_total, pnl_usdt, self.trades_count, self.risk.mode, reason)
        log_info(f"📈 PnL ({reason}): {pnl_usdt:.2f} USDT | PnL total: {self.pnl_total:.2f} USDT")

    def _append_pnl_row(self, equity: float, pnl_total: float, pnl_ejecucion: float,
                        trades: int, modo: str, reason: str = "") -> None:
        os.makedirs(METRICS_DIR, exist_ok=True)
        filename = f"{METRICS_DIR}/pnl_history.csv"
        file_exists = os.path.exists(filename)
        with open(filename, 'a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['fecha', 'hora', 'equity', 'pnl_acumulado', 'pnl_ejecucion', 'trades', 'modo_riesgo', 'motivo'])
            now = datetime.now(timezone.utc)
            writer.writerow([
                now.strftime('%Y-%m-%d'),
                now.strftime('%H:%M:%S'),
                round(equity, 2),
                round(pnl_total, 2),
                round(pnl_ejecucion, 2),
                trades,
                modo,
                reason
            ])

    def _save_metrics(self) -> None:
        os.makedirs(METRICS_DIR, exist_ok=True)
        filename = f"{METRICS_DIR}/report_final_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

        traces_serializable = [trace.to_dict() for trace in self.stats['traces']]

        stats_serializable = {
            'symbols_processed': self.stats['symbols_processed'],
            'signals_generated': self.stats['signals_generated'],
            'orders_attempted': self.stats['orders_attempted'],
            'orders_sent': self.stats['orders_sent'],
            'okx_rejections': self.stats['okx_rejections'],
            'blocked_by_strategy': self.stats['blocked_by_strategy'],
            'blocked_by_validator': self.stats['blocked_by_validator'],
            'blocked_by_risk': self.stats['blocked_by_risk'],
            'blocked_by_cooldown': self.stats['blocked_by_cooldown'],
            'invalid_symbols': self.stats['invalid_symbols'],
            'traces': traces_serializable
        }

        with open(filename, 'w') as f:
            json.dump({
                'trades_count': self.trades_count,
                'pnl_total': self.pnl_total,
                'capital': self.capital,
                'stats': stats_serializable
            }, f, indent=2, default=str)

    def _print_summary(self) -> None:
        log_info("=" * 60)
        log_info("📊 RESUMEN DEL CICLO")
        log_info("=" * 60)
        log_info(f"  Capital actual: {self.capital:.2f} USDT")
        log_info(f"  Trades ejecutados: {self.trades_count}")
        log_info(f"  PnL total: {self.pnl_total:.2f} USDT")
        log_info(f"  Modo riesgo: {self.risk.mode}")
        log_info(f"  Drawdown: {self.risk.dd_actual:.2f}%")
        log_info("=" * 60)

    # ============================================================
    # BUCLE PRINCIPAL (REESCRITO)
    # ============================================================
    def run(self) -> Dict:
        """Bucle principal — limpio, determinístico, robusto."""
        log_info("🔥 KRISHNA KILLING SPREE — INICIO (MODO CONTINUO)")

        if not self.init():
            log_error("Fallo en la inicialización. Saliendo.")
            return {'success': False, 'error': 'init_failed'}

        self._cleanup()

        if self.risk.is_kill_switch_activated():
            log_error("Kill switch activado al inicio. Saliendo.")
            return {'success': False, 'error': 'kill_switch'}

        log_info("🔄 Bucle principal iniciado. Esperando oportunidades...")

        # Solo una variable de estado: self.position
        self.position = None

        while True:
            try:
                # ══════════════════════════════════════════════════════════
                # 1. OBTENER POSICIONES DE OKX (FUENTE DE VERDAD)
                # ══════════════════════════════════════════════════════════
                positions = self.exchange.get_positions()
                pos_data = positions.get('data', []) if positions.get('ok') else []
                active_positions = [p for p in pos_data if safe_float(p.get('pos', 0)) > 0]

                # ══════════════════════════════════════════════════════════
                # 2. ACTUALIZAR RIESGO (cada 60 segundos)
                # ══════════════════════════════════════════════════════════
                now = time.time()
                if now - self.last_risk_update > 60:
                    self._update_capital_from_balance()
                    self.risk.update(self.capital)
                    self.last_risk_update = now

                # ══════════════════════════════════════════════════════════
                # 3. SI HAY POSICIÓN ACTIVA → MONITOREAR
                # ══════════════════════════════════════════════════════════
                if active_positions:
                    # 3a. Actualizar estado desde OKX
                    new_pos = self._update_position_from_okx(active_positions[0])

                    # Si no había posición previamente, loguear apertura
                    if self.position is None:
                        log_info(f"📊 Posición activa: {new_pos.symbol} (entry: {new_pos.entry_price:.2f})")
                        log_info(f"⏰ Abierta a las: {datetime.fromtimestamp(new_pos.entry_time).isoformat()}")

                    self.position = new_pos

                    # 3b. Mostrar PnL cada 30 segundos
                    if now - self.last_position_check > EVALUATION_INTERVAL:
                        log_info(f"💹 PnL: {self.position.pnl_usdt:.2f} USDT ({self.position.pnl_pct:.2f}%) | "
                                 f"Tiempo: {self.position.elapsed_minutes:.1f} min")

                        # 3c. Evaluar cierre por tiempo
                        should_close = False
                        close_reason = ""

                        if self.position.should_break_even:
                            should_close = True
                            close_reason = "BREAK_EVEN"
                            log_info(f"[DIAG] Break-Even activado: PnL {self.position.pnl_usdt:.2f} USDT, "
                                     f"tiempo {self.position.elapsed_minutes:.1f} min")
                        elif self.position.should_timeout:
                            should_close = True
                            close_reason = "TIMEOUT"
                            log_info(f"[DIAG] Timeout activado: tiempo {self.position.elapsed_minutes:.1f} min")

                        if should_close:
                            # 3d. Intentar cerrar
                            success = self._close_position(self.position, close_reason)
                            if success:
                                # Guardar PnL antes de limpiar
                                pnl_usdt = self.position.pnl_usdt
                                self._record_pnl(pnl_usdt, close_reason)
                                self.position = None
                                log_info(f"✅ Posición cerrada por {close_reason}")
                            else:
                                log_error(f"❌ Falló el cierre por {close_reason}, reintentando en el próximo ciclo")

                        self.last_position_check = now

                    # Esperar antes de volver a verificar
                    time.sleep(5)
                    continue

                # ══════════════════════════════════════════════════════════
                # 4. NO HAY POSICIÓN → LIMPIAR Y BUSCAR SEÑAL
                # ══════════════════════════════════════════════════════════
                if self.position is not None:
                    # La posición se cerró fuera del bot (TP/SL manual)
                    log_info("✅ Posición cerrada (detectada en OKX)")
                    self.position = None
                    # Actualizar capital
                    self._update_capital_from_balance()

                time.sleep(2)

                # 4a. Verificar si hay señal
                signal = self._get_signal()
                if signal is None:
                    log_debug("No se encontraron señales válidas. Esperando...")
                    time.sleep(30)
                    continue

                symbol, score, features = signal

                # 4b. Verificar cooldown
                if self.strategy.is_on_cooldown(symbol):
                    log_debug(f"{symbol} en cooldown")
                    time.sleep(5)
                    continue

                # 4c. Verificar si el riesgo permite operar
                risk_params = self.risk.get_effective_parameters()
                if not risk_params['trading_enabled']:
                    log_debug("Trading deshabilitado por modo de riesgo")
                    time.sleep(5)
                    continue

                # 4d. Ejecutar trade
                success = self._execute_trade(symbol, score, features, risk_params)
                if success:
                    self.strategy.set_cooldown(symbol)
                    log_info(f"🚀 Trade ejecutado en {symbol}. Esperando cierre...")
                    # La posición se detectará en el próximo ciclo
                else:
                    log_warning(f"❌ Falló la ejecución del trade en {symbol}")
                    time.sleep(5)

            except KeyboardInterrupt:
                log_info("⏹️ Interrupción manual. Cerrando...")
                break
            except Exception as e:
                log_error(f"Error en bucle principal: {e}")
                traceback.print_exc()
                time.sleep(10)

        self._save_metrics()
        log_info("🔥 KRISHNA KILLING SPREE — FIN (LOOP DETENIDO)")
        return {'success': True, 'mode': self.risk.mode, 'trade_executed': False}

# ============================================================
# ENTRY POINT
# ============================================================
def main():
    API_KEY = os.environ.get('OKX_API_KEY', "2d57031a-deb4-438e-9449-6dc3e525f2fb")
    SECRET_KEY = os.environ.get('OKX_SECRET_KEY', "2CEFC57765518B204872EF804910ECEF")
    PASSPHRASE = os.environ.get('OKX_PASSPHRASE', "Waly200381!")
    DEMO = os.environ.get('OKX_DEMO', 'true').lower() == 'true'

    if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
        log_error("Faltan credenciales OKX.")
        sys.exit(1)

    bot = KrishnaKillingSpree(API_KEY, SECRET_KEY, PASSPHRASE, DEMO)
    result = bot.run()
    log_info(f"Resultado: {result}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_info("Interrupción manual")
    except Exception as e:
        log_error(f"Error inesperado: {e}")
        traceback.print_exc()

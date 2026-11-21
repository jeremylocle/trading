# execution.py
import math
import MetaTrader5 as mt5
from config import LOTE_OPERACION, MAX_SPREAD_PIPS
from logger import log_event, registrar_operacion_cerrada


def tiene_posicion_abierta(simbolo="EURUSD") -> bool:
    """Devuelve True si hay una posición activa en el símbolo."""
    positions = mt5.positions_get(symbol=simbolo)
    return positions is not None and len(positions) > 0


def obtener_balance_cuenta() -> float:
    """Devuelve el balance actual de la cuenta."""
    account_info = mt5.account_info()
    return account_info.balance if account_info is not None else 0.0


def calcular_lotaje_dinamico(simbolo: str, capital_por_micro_lote: float = 100.0, max_lotes: float = 0.50) -> float:
    """
    Calcula el lotaje dinámico según el balance actual de la cuenta en MT5.
    Escala 0.01 lotes por cada 100€ de balance (redondeando hacia abajo).
    """
    balance = obtener_balance_cuenta()
    if balance <= 0:
        return LOTE_OPERACION

    tramos = math.floor(balance / capital_por_micro_lote)
    lote_calculado = round(tramos * 0.01, 2)

    symbol_info = mt5.symbol_info(simbolo)
    vol_min = symbol_info.volume_min if symbol_info else 0.01
    vol_max = symbol_info.volume_max if symbol_info else max_lotes

    lote_final = max(vol_min, min(lote_calculado, max_lotes, vol_max))
    return round(lote_final, 2)


def abrir_orden_automatica(simbolo="EURUSD", tipo="BUY", pips_tp=30.0, pips_sl=15.0, volumen=None, razon_ia=""):
    """
    Envía una orden al mercado validando el spread máximo, calculando el lotaje
    dinámico según el balance y adaptando el SL y TP al Stops Level del broker.
    """
    symbol_info = mt5.symbol_info(simbolo)
    tick = mt5.symbol_info_tick(simbolo)

    if not tick or not symbol_info:
        log_event(f"❌ Error al obtener cotización actual de {simbolo}.")
        return False

    # 0. Calcular lotaje dinámico según saldo actual (si no se pasó un volumen manual)
    lote_a_operar = volumen if volumen is not None else calcular_lotaje_dinamico(
        simbolo=simbolo,
        capital_por_micro_lote=100.0,
        max_lotes=0.50
    )

    # 1. Definir la unidad base de 1 Pip según dígitos
    if symbol_info.digits == 5 or symbol_info.digits == 4:
        pip_unit = 0.0001
    elif symbol_info.digits == 3 or symbol_info.digits == 2:
        pip_unit = 0.01
    else:
        pip_unit = symbol_info.point * 10.0

    # 2. Protección de Spread Máximo en tiempo real (evita ejecución con spread inflado)
    spread_actual_pips = (tick.ask - tick.bid) / pip_unit if pip_unit > 0 else 999.0
    if spread_actual_pips > MAX_SPREAD_PIPS:
        log_event(f"🛡️ [{simbolo}] Orden cancelada: Spread demasiado alto ({spread_actual_pips:.2f}p > {MAX_SPREAD_PIPS}p)")
        return False

    # 3. Consultar el Stop Level mínimo exigido por el broker en Pips
    stops_level_points = symbol_info.trade_stops_level
    min_stop_pips = (stops_level_points * symbol_info.point) / pip_unit if pip_unit > 0 else 0.0

    # Asegurar que los pips aplicados respeten siempre el mínimo del broker (+ 2 pips de margen)
    safe_sl_pips = max(pips_sl, min_stop_pips + 2.0)
    safe_tp_pips = max(pips_tp, (min_stop_pips + 2.0) * 2.0)

    # 4. Calcular precio de entrada, SL y TP
    if tipo == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
        sl = price - (safe_sl_pips * pip_unit)
        tp = price + (safe_tp_pips * pip_unit)
    elif tipo == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
        sl = price + (safe_sl_pips * pip_unit)  # SL por encima en ventas
        tp = price - (safe_tp_pips * pip_unit)  # TP por debajo en ventas
    else:
        log_event(f"❌ Tipo de orden desconocido: {tipo}")
        return False

    # Redondear adecuadamente al número exacto de dígitos del broker
    price = round(price, symbol_info.digits)
    sl = round(sl, symbol_info.digits)
    tp = round(tp, symbol_info.digits)

    # 5. Enviar la orden a MT5
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": simbolo,
        "volume": lote_a_operar,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 1002024,
        "comment": "Bot IA Ollama",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        ret_code = result.retcode if result else "None"
        ret_comment = result.comment if result else "Sin respuesta"
        log_event(f"❌ Error al ejecutar orden en {simbolo} (Código {ret_code}): {ret_comment} | Price: {price:.5f} | SL: {sl:.5f} | TP: {tp:.5f} | BrokerMinStop: {min_stop_pips:.1f}p")
        return False

    balance = obtener_balance_cuenta()
    log_event(f"✅ ¡ORDEN {tipo} EJECUTADA EN {simbolo}! Vol: {lote_a_operar:.2f} | Spread: {spread_actual_pips:.2f}p | Entrada: {price:.5f} | SL: {sl:.5f} | TP: {tp:.5f} | Balance: ${balance:.2f}")
    return True


def verificar_historial_operaciones(razon_ia=""):
    """Revisa el historial de MT5 para comprobar el resultado real de la última orden cerrada en cualquier par."""
    import pandas as pd
    from datetime import datetime, timedelta

    from_date = datetime.now() - timedelta(days=2)
    to_date = datetime.now() + timedelta(days=1)

    # Sin filtro fijo de *EURUSD* para capturar cierres de todos los pares configurados
    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None or len(deals) < 2:
        return

    df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df_out = df[(df['entry'] == 1) & (df['magic'] == 1002024)]

    if not df_out.empty:
        last_deal = df_out.iloc[-1]
        profit_neto = last_deal['profit'] + last_deal['swap'] + last_deal['commission']
        symbol = last_deal['symbol']
        price_exit = last_deal['price']
        balance = obtener_balance_cuenta()

        pips_result = profit_neto / (last_deal['volume'] * 10) if last_deal['volume'] > 0 else 0.0

        log_event(f"📊 [OPERACIÓN CERRADA - {symbol}] Neto: ${profit_neto:+.2f} ({pips_result:+.1f} Pips) | Balance Actual: ${balance:.2f}")

        data_trade = {
            "time_entry": pd.to_datetime(last_deal['time'], unit='s'),
            "symbol": symbol,
            "type": "SELL" if last_deal['type'] == 1 else "BUY",  # El deal de salida tiene el tipo inverso a la orden original
            "price_entry": last_deal['price'],
            "price_exit": price_exit,
            "tp_pips": 0.0,
            "sl_pips": 0.0,
            "pips_result": round(pips_result, 1),
            "profit_money": round(profit_neto, 2),
            "current_balance": round(balance, 2),
            "reason_ia": razon_ia
        }
        registrar_operacion_cerrada(data_trade)
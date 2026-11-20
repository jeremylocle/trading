# main.py
import time
from datetime import datetime
import MetaTrader5 as mt5
from config import (
    SYMBOLS,
    UPDATE_INTERVAL,
    HISTORICAL_BARS,
    TESTING_MODE,
    HORA_CIERRE_NOCTURNO,
    MAX_PERDIDA_DIARIA_PIPS
)
from mt5_connector import init_mt5, get_latest_data, shutdown_mt5
from feature_engineering import process_ticks_to_features
from predictor import OllamaForexPredictor
from execution import (
    abrir_orden_automatica,
    tiene_posicion_abierta,
    obtener_balance_cuenta,
    verificar_historial_operaciones
)
from logger import log_event, init_journal_csv
from strategy import evaluar_estrategia


def cerrar_posiciones_simbolo_mt5(symbol: str) -> bool:
    """Tanca a mercat totes les posicions obertes d'un símbol a MT5 (per al tancament nocturn)."""
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return False

    cerrada = False
    for pos in positions:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            continue

        es_compra = (pos.type == mt5.POSITION_TYPE_BUY)
        tipo_cierre = mt5.ORDER_TYPE_SELL if es_compra else mt5.ORDER_TYPE_BUY
        precio_cierre = tick.bid if es_compra else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": pos.volume,
            "type": tipo_cierre,
            "position": pos.ticket,
            "price": precio_cierre,
            "deviation": 20,
            "magic": pos.magic,
            "comment": f"Cierre nocturno {HORA_CIERRE_NOCTURNO:02d}h",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            log_event(f"🌙 [{symbol}] Posición #{pos.ticket} cerrada por horario nocturno ({HORA_CIERRE_NOCTURNO:02d}:00h) @ {precio_cierre:.5f}")
            cerrada = True
        else:
            err = result.comment if result else mt5.last_error()
            log_event(f"❌ [{symbol}] Error al cerrar posición #{pos.ticket} en cierre nocturno: {err}")

    return cerrada


def obtener_pips_diarios_mt5(fecha_servidor: datetime) -> float:
    """Calcula els pips nets acumulats en el dia actual (hora servidor MT5) per les operacions del bot."""
    inicio_dia = fecha_servidor.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_dia = fecha_servidor.replace(hour=23, minute=59, second=59, microsecond=999999)

    deals = mt5.history_deals_get(inicio_dia, fin_dia)
    if not deals:
        return 0.0

    pips_totales = 0.0
    for d in deals:
        if d.entry == 1 and d.magic == 1002024 and d.volume > 0:
            net_money = d.profit + d.swap + d.commission
            pips_totales += net_money / (d.volume * 10.0)

    return round(pips_totales, 1)


def main():
    init_journal_csv()
    log_event(f"=== INICIANDO BOT EN TIEMPO REAL (MODO TESTING: {TESTING_MODE}) ===")

    if not init_mt5():
        return

    try:
        predictor = OllamaForexPredictor(model_name="martain7r/finance-llama-8b:q4_k_m")
    except Exception as e:
        log_event(f"❌ Error al conectar con Ollama: {e}")
        shutdown_mt5()
        return

    log_event(f"🚀 Monitoreando ({len(SYMBOLS)}) pares | Balance: ${obtener_balance_cuenta():.2f} | Límite diario: -{MAX_PERDIDA_DIARIA_PIPS}p")

    last_processed_times = {symbol: None for symbol in SYMBOLS}
    posiciones_previas = {symbol: False for symbol in SYMBOLS}
    candle_counter = {symbol: 0 for symbol in SYMBOLS}
    last_trade_candle = {symbol: -999 for symbol in SYMBOLS}
    bloqueo_diario_notificado = None

    try:
        while True:
            raw_data = get_latest_data()
            features_df = process_ticks_to_features(raw_data)

            # RECTIFICACIÓ: Descartem l'última fila (vela actual en formació) perquè
            # el bot avaluï EXCLUSIVAMENT veles 100% tancades, igual que al backtest.
            if not features_df.empty and len(features_df) > HISTORICAL_BARS + 1:
                features_df = features_df.iloc[:-1]
                ultimo_indice = len(features_df) - 1

                for symbol in SYMBOLS:
                    col_pips = f'{symbol}_pips_change'
                    if col_pips not in features_df.columns:
                        continue

                    current_time = features_df.index[-1]
                    hora_actual = current_time.hour

                    # 1. Comprovar posicions actives i tancament nocturn a les 20:00h
                    posicion_actual = tiene_posicion_abierta(symbol)

                    if posicion_actual and hora_actual >= HORA_CIERRE_NOCTURNO:
                        if cerrar_posiciones_simbolo_mt5(symbol):
                            verificar_historial_operaciones()
                            posicion_actual = False
                            last_trade_candle[symbol] = candle_counter[symbol]

                    # Rastrear tancaments naturals per TP o SL a MT5
                    if posiciones_previas[symbol] and not posicion_actual:
                        verificar_historial_operaciones()
                    posiciones_previas[symbol] = posicion_actual

                    # 2. Nova vela tancada
                    if current_time != last_processed_times[symbol]:
                        last_processed_times[symbol] = current_time
                        candle_counter[symbol] += 1

                        log_event(f"\n--- 📈 [{symbol}] Nueva Vela Cerrada [{current_time}] ---")

                        if posicion_actual:
                            log_event(f"⚠️ [{symbol}] Posición activa en curso. Omitiendo...")
                            continue

                        # 2.1 Tallafocs diari (Circuit Breaker per pèrdua màxima diària)
                        pips_hoy = obtener_pips_diarios_mt5(current_time.to_pydatetime())
                        if pips_hoy <= -MAX_PERDIDA_DIARIA_PIPS:
                            if bloqueo_diario_notificado != current_time.date():
                                log_event(f"🛑 TALLAFOCS DIARI ACTIVAT ({current_time.date()}): Pèrdua acumulada d'avui ({pips_hoy:.1f}p) supera -{MAX_PERDIDA_DIARIA_PIPS}p. S'aturen les operacions fins demà.")
                                bloqueo_diario_notificado = current_time.date()
                            continue

                        # 3. Avaluació de l'estratègia unificada
                        decision = evaluar_estrategia(
                            symbol=symbol,
                            features_df=features_df,
                            predictor=predictor,
                            historical_bars=HISTORICAL_BARS,
                            candle_index=ultimo_indice,
                            last_trade_candle=last_trade_candle,
                            candle_counter=candle_counter
                        )

                        log_event(f"🧠 [{symbol}] Razonamiento: {decision['razon']}")
                        log_event(f"📊 [{symbol}] Confianza: {decision['probabilidad']:.1f}% | Dir: {decision['direccion']} | TP: {decision['tp_pips']:.1f}p | SL: {decision['sl_pips']:.1f}p")

                        if decision["ejecutar"]:
                            log_event(f"🎯 ¡SEÑAL CONFIRMADA EN {symbol}! Ejecutando {decision['direccion']}...")
                            exito = abrir_orden_automatica(
                                simbolo=symbol,
                                tipo=decision['direccion'],
                                pips_tp=decision['tp_pips'],
                                pips_sl=decision['sl_pips'],
                                razon_ia=decision['razon']
                            )
                            if exito:
                                last_trade_candle[symbol] = candle_counter[symbol]
                                posiciones_previas[symbol] = True
                        elif decision["motivo_rechazo"]:
                            log_event(f"🛡️ [{symbol}] Bloqueada: {decision['motivo_rechazo']}")
                        else:
                            log_event(f"⏳ [{symbol}] Sin señal de alta confianza ({decision['probabilidad']:.1f}%).")

            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        log_event("\n🛑 Bot detenido por el usuario.")
    finally:
        shutdown_mt5()


if __name__ == "__main__":
    main()
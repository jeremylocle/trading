# mt5_connector.py
import MetaTrader5 as mt5
import pandas as pd
from config import SYMBOLS, TIMEFRAME, HISTORICAL_BARS

def init_mt5() -> bool:
    """Inicializa la conexión con MT5 y activa los pares multiactivo."""
    if not mt5.initialize():
        print(f"❌ Error al conectar con MT5: {mt5.last_error()}")
        return False
    
    print("✅ Conexión con MetaTrader 5 establecida.")
    
    # IMPORTANTE: Activar cada símbolo de config.py en el Observatorio de Mercado
    for symbol in SYMBOLS:
        if not mt5.symbol_select(symbol, True):
            print(f"⚠️ Atención: No se pudo seleccionar/activar el símbolo {symbol} en MT5.")
            
    return True

def get_latest_data() -> dict:
    """Obtiene el histórico reciente de velas para todos los símbolos configurados."""
    data = {}
    # Demanem +5 veles de marge per compensar la vela actual en formació que es descarta a main.py
    velas_a_descargar = max(HISTORICAL_BARS + 5, 900)
    for symbol in SYMBOLS:
        rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, velas_a_descargar)
        if rates is not None and len(rates) > 0:
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('time', inplace=True)
            data[symbol] = df
    return data

def shutdown_mt5():
    mt5.shutdown()
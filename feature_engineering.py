# feature_engineering.py
import pandas as pd
import numpy as np

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calcula el RSI clásico de 14 periodos."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

def calculate_atr_pips(df: pd.DataFrame, pip_unit: float, period: int = 14) -> pd.Series:
    """Calcula el ATR en PIPS."""
    high_low = df['high'] - df['low']
    high_cp = (df['high'] - df['close'].shift(1)).abs()
    low_cp = (df['low'] - df['close'].shift(1)).abs()
    
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean() / pip_unit
    return atr.fillna(12.0)  # Valor base por defecto por si no hay suficientes velas

def process_ticks_to_features(raw_data_dict: dict) -> pd.DataFrame:
    """
    Procesa las velas de múltiples activos y genera los 5 indicadores clave:
    Pips Change, RSI, ATR en Pips, Distancia a EMA200 (15M) y Distancia a EMA200 (H1).
    """
    if not raw_data_dict:
        return pd.DataFrame()

    processed_dfs = []

    for symbol, df in raw_data_dict.items():
        if df.empty:
            continue
            
        df = df.copy()

        # Respetar si 'time' ya viene en el índice o como columna
        if 'time' in df.columns:
            df.set_index('time', inplace=True)

        # Pip Unit según el par (0.01 para Yenes, 0.0001 estándar)
        pip_unit = 0.01 if "JPY" in symbol else 0.0001

        # 1. Indicadores principales
        df[f'{symbol}_pips_change'] = df['close'].diff() / pip_unit
        df[f'{symbol}_rsi'] = calculate_rsi(df['close'], period=14)
        df[f'{symbol}_atr_pips'] = calculate_atr_pips(df, pip_unit=pip_unit, period=14)
        
        # 2. EMA 200 en 15M y EMA 200 en H1 (200 * 4 velas de 15M = 800)
        ema200 = df['close'].ewm(span=200, adjust=False).mean()
        df[f'{symbol}_dist_ema200_pips'] = (df['close'] - ema200) / pip_unit

        ema200_h1 = df['close'].ewm(span=800, adjust=False).mean()
        df[f'{symbol}_dist_ema200_h1_pips'] = (df['close'] - ema200_h1) / pip_unit

        # 3. Incluir todas las columnas necesarias en la selección final
        cols = [
            f'{symbol}_pips_change', 
            f'{symbol}_rsi', 
            f'{symbol}_atr_pips', 
            f'{symbol}_dist_ema200_pips',
            f'{symbol}_dist_ema200_h1_pips'
        ]
        processed_dfs.append(df[cols])

    if not processed_dfs:
        return pd.DataFrame()

    # Concatenar todos los pares y limpiar filas iniciales sin datos
    final_df = pd.concat(processed_dfs, axis=1).dropna()
    return final_df
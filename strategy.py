# strategy.py
from config import (
    UMBRAL_PROBABILIDAD,
    COOLDOWN_VELAS,
    MIN_ATR_PIPS,
    MIN_DIST_EMA_PIPS,
    HORA_INICIO_TRADING,
    HORA_FIN_TRADING,
    VENTANAS_BLOQUEO_NOTICIAS
)

def _en_ventana_noticias(timestamp) -> bool:
    """Comprova si l'hora i minut actuals cauen dins d'una finestra de notícies macro."""
    actual_mins = timestamp.hour * 60 + timestamp.minute
    for (h_ini, m_ini), (h_fin, m_fin) in VENTANAS_BLOQUEO_NOTICIAS:
        ini_mins = h_ini * 60 + m_ini
        fin_mins = h_fin * 60 + m_fin
        if ini_mins <= actual_mins <= fin_mins:
            return True
    return False

def evaluar_estrategia(symbol: str, features_df, predictor, historical_bars: int, candle_index: int, last_trade_candle: dict, candle_counter: dict) -> dict:
    """
    Avalua horari, finestres de notícies, filtres tècnics de qualitat (15M + H1) i senyal d'Ollama.
    """
    col_pips = f'{symbol}_pips_change'
    col_rsi = f'{symbol}_rsi'
    col_ema = f'{symbol}_dist_ema200_pips'
    col_ema_h1 = f'{symbol}_dist_ema200_h1_pips'
    col_atr = f'{symbol}_atr_pips'

    timestamp_actual = features_df.index[candle_index]
    hora_actual = timestamp_actual.hour
    rsi_actual = features_df[col_rsi].iloc[candle_index]
    dist_ema_actual = features_df[col_ema].iloc[candle_index]
    atr_actual = features_df[col_atr].iloc[candle_index]
    dist_ema_h1_actual = features_df[col_ema_h1].iloc[candle_index] if col_ema_h1 in features_df.columns else dist_ema_actual

    def _rechazar(motivo: str) -> dict:
        return {
            "ejecutar": False,
            "direccion": "HOLD",
            "probabilidad": 0.0,
            "tp_pips": 0.0,
            "sl_pips": 0.0,
            "razon": motivo,
            "motivo_rechazo": motivo,
            "dist_ema": dist_ema_actual,
            "atr": atr_actual
        }

    # 1. Filtre Horari General (08:00 - 19:00)
    if not (HORA_INICIO_TRADING <= hora_actual < HORA_FIN_TRADING):
        return _rechazar(f"Fora d'horari operatiu ({hora_actual:02d}:{timestamp_actual.minute:02d}h)")

    # 2. Filtre de Notícies Macro EUA i Obertura Wall Street
    if _en_ventana_noticias(timestamp_actual):
        return _rechazar(f"Bloqueig notícies EUA / Wall Street ({hora_actual:02d}:{timestamp_actual.minute:02d}h)")

    # 3. Filtre de Cooldown
    if (candle_counter[symbol] - last_trade_candle[symbol]) < COOLDOWN_VELAS:
        return _rechazar("En periodo de Cooldown")

    # 4. Filtre de Volatilitat Mínima
    if atr_actual < MIN_ATR_PIPS:
        return _rechazar(f"ATR massa baix ({atr_actual:.1f}p < {MIN_ATR_PIPS}p)")

    # 5. Filtre de Distància Mínima a la EMA200 (15M)
    if abs(dist_ema_actual) < MIN_DIST_EMA_PIPS:
        return _rechazar(f"Massa prop de EMA200 15M ({dist_ema_actual:.1f}p)")

    # 5.1 Filtre d'alineació prèvia entre tendència 15M i tendència superior H1
    if (dist_ema_actual > 0 and dist_ema_h1_actual <= 0) or (dist_ema_actual < 0 and dist_ema_h1_actual >= 0):
        return _rechazar(f"Conflicte tendència 15M ({dist_ema_actual:+.1f}p) vs H1 ({dist_ema_h1_actual:+.1f}p)")

    # 6. Inferència amb Ollama (només es crida si passa tots els filtres anteriors)
    pips_series = features_df[col_pips].iloc[:candle_index].tail(historical_bars)
    resultado_ia = predictor.predict_next_pips(
        pips_series=pips_series,
        rsi_value=rsi_actual,
        dist_ema=dist_ema_actual,
        atr_pips=atr_actual
    )

    probabilidad = resultado_ia["probabilidad"]
    direccion_ia = resultado_ia["direccion"]
    razon_ia = resultado_ia.get("razonamiento", "Sin detalle")

    tp_dinamico = round(max(atr_actual * 2.0, 12.0), 1)
    sl_dinamico = round(max(atr_actual * 1.0, 8.0), 1)

    tendencia_15m_valida = (direccion_ia == "BUY" and dist_ema_actual > 0) or (direccion_ia == "SELL" and dist_ema_actual < 0)
    tendencia_h1_valida = (direccion_ia == "BUY" and dist_ema_h1_actual > 0) or (direccion_ia == "SELL" and dist_ema_h1_actual < 0)

    se_debe_ejecutar = False
    motivo_rechazo = None

    if probabilidad >= UMBRAL_PROBABILIDAD and direccion_ia in ["BUY", "SELL"]:
        if not tendencia_15m_valida:
            motivo_rechazo = f"Contra EMA200 15M (Dist: {dist_ema_actual:.1f}p)"
        elif not tendencia_h1_valida:
            motivo_rechazo = f"Contra EMA200 H1 (Dist H1: {dist_ema_h1_actual:.1f}p)"
        else:
            se_debe_ejecutar = True

    return {
        "ejecutar": se_debe_ejecutar,
        "direccion": direccion_ia,
        "probabilidad": probabilidad,
        "tp_pips": tp_dinamico,
        "sl_pips": sl_dinamico,
        "razon": razon_ia,
        "motivo_rechazo": motivo_rechazo,
        "dist_ema": dist_ema_actual,
        "atr": atr_actual
    }
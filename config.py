# config.py
import MetaTrader5 as mt5

# Lista de pares a monitorear (agrega más aquí cuando quieras: "GBPUSD", "USDJPY", etc.)
SYMBOLS = ["EURUSD", "GBPUSD", "EURGBP"]

# Temporalidad de las velas (M1 = 1 minuto, M5 = 5 minutos)
TIMEFRAME = mt5.TIMEFRAME_M15

# Tamaño del histórico para alimentar a la IA (ej. últimas 100 velas)
HISTORICAL_BARS = 100

LOTE_OPERACION = 0.01        # 1 pip ≈ 0.10$
MAX_SPREAD_PIPS = 0.8        # Spread màxim permès en executar (0.5 per Raw, 0.8-1.2 per Standard)

# --- CONTROL HORARI (Evita soroll nocturn i swaps) ---
HORA_INICIO_TRADING = 8      # No obre operacions abans de les 08:00
HORA_FIN_TRADING = 19        # No obre operacions noves a partir de les 19:00
HORA_CIERRE_NOCTURNO = 21    # Tanca totes les posicions obertes a les 21:00

VENTANAS_BLOQUEO_NOTICIAS = [
    #((14, 15), (14, 45)),
    #((15, 30), (16, 15))
]

# --- GESTIÓ DE RISC DIARI (CIRCUIT BREAKER) ---
MAX_PERDIDA_DIARIA_PIPS = 500.0   # Si en un mateix dia es perden 40 pips nets, el bot deixa d'operar fins l'endemà

# Frecuencia del bucle en tiempo real (en segundos)
UPDATE_INTERVAL = 1.0

UMBRAL_PROBABILIDAD = 90.0
COOLDOWN_VELAS = 8

MIN_ATR_PIPS = 4.0           # No operar si el mercat està mort (volatilitat < 4 pips)
MIN_DIST_EMA_PIPS = 5.0      # No operar si el preu està enganxat a la EMA200 (< 5 pips

# -----------------------------------------------------------------------------
# MODO TESTING VS PRODUCCIÓN
# True  => Optimizado para pruebas (Inferencia ultra-rápida y respuestas cortas)
# False => Modo producción completo (Inferencia detallada)
# -----------------------------------------------------------------------------
TESTING_MODE = True
VELAS_SIMULACION = 400  # Utilitzat quan USE_DATE_RANGE = False

# --- COSTOS REALS DEL BROKER PER AL SIMULADOR ---
COMISION_PIPS = 0.8          # Spread + comissió mitjana per operació (compte Raw/ECN)

USE_DATE_RANGE = True
# Format: (Any, Mes, Dia, Hora, Minut)
FECHA_INICIO = (2026, 1, 1, 0, 0)   
FECHA_FIN    = (2026, 11, 10, 23, 59) 
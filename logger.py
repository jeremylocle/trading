# logger.py
import os
import csv
from datetime import datetime

# Guardar los archivos en la misma carpeta donde se ejecuta el bot (C:\Users\tiran\python\)
LOG_FILE_TXT = "bot_log.txt"
JOURNAL_FILE_CSV = "trading_journal.csv"

def log_event(mensaje: str):
    """Escribe un evento en bot_log.txt con timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{timestamp}] {mensaje}\n"
    
    print(mensaje)
    with open(LOG_FILE_TXT, "a", encoding="utf-8") as f:
        f.write(linea)

def init_journal_csv():
    """Inicializa el archivo CSV si no existe."""
    if not os.path.exists(JOURNAL_FILE_CSV):
        with open(JOURNAL_FILE_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f,delimiter=";")
            writer.writerow([
                "Timestamp_Entrada", "Simbolo", "Tipo", "Precio_Entrada", 
                "Precio_Salida", "TP_Pips", "SL_Pips", "Resultado_Pips", 
                "Ganancia_Dinero", "Balance_Acumulado", "Razon_IA"
            ])

def registrar_operacion_cerrada(data_trade: dict):
    """Guarda una operación en el CSV."""
    init_journal_csv()
    with open(JOURNAL_FILE_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            data_trade.get("time_entry"),
            data_trade.get("symbol"),
            data_trade.get("type"),
            data_trade.get("price_entry"),
            data_trade.get("price_exit"),
            data_trade.get("tp_pips"),
            data_trade.get("sl_pips"),
            data_trade.get("pips_result"),
            data_trade.get("profit_money"),
            data_trade.get("current_balance"),
            data_trade.get("reason_ia")
        ])
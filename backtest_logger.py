# backtest_logger.py
import csv
import os

CSV_FILE = "backtest_resultados.csv"

def init_backtest_csv():
    """Inicialitza el fitxer CSV amb les capçaleres si no existeix."""
    headers = [
        "order_id", "symbol", "tipo", "fecha_entrada", "precio_entrada",
        "tp_pips", "sl_pips", "precio_tp", "precio_sl", "confianza",
        "estado", "fecha_salida", "precio_salida", "pips_ganados", "ganancia_usd", "razon"
    ]
    
    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

def registrar_orden_simulada(order_id, symbol, tipo, fecha, precio_entrada, tp_pips, sl_pips, pips_unit, confianza, razon):
    """Registra una nova ordre simulada al CSV en estat PENDIENTE."""
    precio_tp = precio_entrada + (tp_pips * pips_unit) if tipo == "BUY" else precio_entrada - (tp_pips * pips_unit)
    precio_sl = precio_entrada - (sl_pips * pips_unit) if tipo == "BUY" else precio_entrada + (sl_pips * pips_unit)

    # Neteja de text per evitar trencar la línia del CSV
    razon_limpia = str(razon).replace('\n', ' ').replace('\r', ' ').replace('"', "'")

    row = [
        order_id, symbol, tipo, fecha.strftime('%Y-%m-%d %H:%M:%S'), f"{precio_entrada:.5f}",
        f"{tp_pips:.1f}", f"{sl_pips:.1f}", f"{precio_tp:.5f}", f"{precio_sl:.5f}", f"{confianza:.1f}",
        "PENDIENTE", "", "", "", "", razon_limpia
    ]

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)

def actualizar_orden_simulada(order_id, fecha_salida, precio_salida, estado_final, pips_ganados, ganancia_usd):
    """Actualitza el resultat d'una ordre al fitxer CSV quan es tanca per TP o SL."""
    if not os.path.exists(CSV_FILE):
        return

    rows = []
    with open(CSV_FILE, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    for i in range(1, len(rows)):
        if rows[i] and rows[i][0] == str(order_id):
            rows[i][10] = estado_final
            rows[i][11] = fecha_salida.strftime('%Y-%m-%d %H:%M:%S')
            rows[i][12] = f"{precio_salida:.5f}"
            rows[i][13] = f"{pips_ganados:.1f}"
            rows[i][14] = f"{ganancia_usd:.2f}"
            break

    with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
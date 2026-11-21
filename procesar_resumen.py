import csv
import os
import re
import pandas as pd

archivo_origen = "backtest_resultados.csv"
archivo_limpio = "backtest_resultados_limpio.csv"

HEADERS = [
    "ID_Orden",
    "Symbol",
    "Tipo",
    "Fecha_Entrada",
    "Precio_Entrada",
    "TP_Pips",
    "SL_Pips",
    "Precio_TP",
    "Precio_SL",
    "Confianza_IA",
    "Estado",
    "Fecha_Salida",
    "Precio_Salida",
    "Resultado_Pips",
    "Ganancia_USD",
]


def reparar_y_limpiar_csv(origen, destino):
    filas_limpias = []

    with open(origen, mode="r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)

        for row in reader:
            if not row or len(row) == 0:
                continue

            if row[0].strip() == "ID_Orden":
                continue

            idx_estado = -1
            for i, elem in enumerate(row):
                elem_str = str(elem).strip().upper()
                if (
                    elem_str.startswith("WIN")
                    or elem_str.startswith("LOSS")
                    or elem_str.startswith("PENDIENTE")
                ):
                    idx_estado = i
                    break

            if idx_estado != -1 and idx_estado >= 10:
                id_orden = row[0].strip()
                symbol = row[1].strip()
                tipo = row[2].strip()
                fecha_in = row[3].strip()
                precio_in = row[4].strip()
                tp_pips = row[5].strip()
                sl_pips = row[6].strip()
                precio_tp = row[7].strip()
                precio_sl = row[8].strip()
                confianza = row[9].strip()
                estado = row[idx_estado].strip().upper()

                fecha_out = (
                    row[idx_estado + 1].strip()
                    if len(row) > idx_estado + 1
                    else ""
                )
                precio_out = (
                    row[idx_estado + 2].strip()
                    if len(row) > idx_estado + 2
                    else ""
                )
                res_pips = (
                    row[idx_estado + 3].strip()
                    if len(row) > idx_estado + 3
                    else ""
                )
                gan_usd = (
                    row[idx_estado + 4].strip()
                    if len(row) > idx_estado + 4
                    else ""
                )

                if "PENDIENTE" in estado or not re.match(
                    r"^-?\d+(\.\d+)?$", res_pips
                ):
                    fecha_out = ""
                    precio_out = ""
                    res_pips = ""
                    gan_usd = ""

                filas_limpias.append([
                    id_orden,
                    symbol,
                    tipo,
                    fecha_in,
                    precio_in,
                    tp_pips,
                    sl_pips,
                    precio_tp,
                    precio_sl,
                    confianza,
                    estado,
                    fecha_out,
                    precio_out,
                    res_pips,
                    gan_usd,
                ])

    with open(destino, mode="w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(HEADERS)
        writer.writerows(filas_limpias)

    print(
        f"✅ Archivo reconstruido y saneado correctamente: '{destino}' ({len(filas_limpias)} operaciones)"
    )


def generar_resumen(archivo_csv):
    df = pd.read_csv(archivo_csv)

    df["Resultado_Pips"] = pd.to_numeric(df["Resultado_Pips"], errors="coerce")
    df["Ganancia_USD"] = pd.to_numeric(df["Ganancia_USD"], errors="coerce")
    df["Estado"] = df["Estado"].astype(str).str.strip().str.upper()

    resumen = []
    simbolos = df["Symbol"].dropna().unique()

    for sim in simbolos:
        if not sim or str(sim).strip() == "":
            continue

        sub_df = df[df["Symbol"] == sim]

        ganadas = sub_df[sub_df["Estado"].str.startswith("WIN")]
        perdidas = sub_df[sub_df["Estado"].str.startswith("LOSS")]
        pendientes = sub_df[sub_df["Estado"].str.startswith("PENDIENTE")]

        pips_totales = (
            ganadas["Resultado_Pips"].sum() + perdidas["Resultado_Pips"].sum()
        )
        ganancia_usd = (
            ganadas["Ganancia_USD"].sum() + perdidas["Ganancia_USD"].sum()
        )

        resumen.append({
            "Symbol": sim,
            "Pips Totals": round(pips_totales, 1),
            "Ganancia USD Total": round(ganancia_usd, 1),
            "Operacions Guanyades": len(ganadas),
            "Operacions Perdudes": len(perdidas),
            "Pendents": len(pendientes),
        })

    df_resumen = pd.DataFrame(resumen)

    total_general = pd.DataFrame([{
        "Symbol": "TOTAL GENERAL",
        "Pips Totals": round(df_resumen["Pips Totals"].sum(), 1),
        "Ganancia USD Total": round(
            df_resumen["Ganancia USD Total"].sum(), 1
        ),
        "Operacions Guanyades": df_resumen["Operacions Guanyades"].sum(),
        "Operacions Perdudes": df_resumen["Operacions Perdudes"].sum(),
        "Pendents": df_resumen["Pendents"].sum(),
    }])

    return pd.concat([df_resumen, total_general], ignore_index=True)


def renombrar_csv_por_primera_fecha(ruta_csv):
    patron_fecha = r'\b(\d{4}[-/.]\d{2}[-/.]\d{2}|\d{2}[-/.]\d{2}[-/.]\d{4})\b'
    primera_fecha = None

    with open(ruta_csv, 'r', encoding='utf-8', errors='ignore') as archivo:
        for linea in archivo:
            coincidencia = re.search(patron_fecha, linea)
            if coincidencia:
                primera_fecha = coincidencia.group(1)
                break

    if not primera_fecha:
        print("⚠️ No se encontró ninguna fecha válida en el archivo CSV para renombrarlo.")
        return ruta_csv

    # Limpia caracteres que no son permitidos en los nombres de archivo de Windows (ej: / : .)
    fecha_limpia = re.sub(r'[/.:]', '-', primera_fecha)
    
    directorio, nombre_actual = os.path.split(ruta_csv)
    nuevo_nombre = f"{fecha_limpia}.csv"
    nueva_ruta = os.path.join(directorio, nuevo_nombre)

    try:
        os.rename(ruta_csv, nueva_ruta)
        print(f"🏷️ Archivo renombrado exitosamente a: '{nueva_ruta}'")
        return nueva_ruta
    except Exception as e:
        print(f"⚠️ Error al renombrar el archivo: {e}")
        return ruta_csv


if __name__ == "__main__":
    try:
        reparar_y_limpiar_csv(archivo_origen, archivo_limpio)
        resumen_df = generar_resumen(archivo_limpio)
        print("\n--- RESUMEN DE OPERACIONES ---")
        print(resumen_df.to_string(index=False))

        # Renombrar el CSV saneado con la primera fecha encontrada
        renombrar_csv_por_primera_fecha(archivo_limpio)
    except Exception as e:
        print(f"Error: {e}")

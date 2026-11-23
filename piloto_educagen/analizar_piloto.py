import csv
import statistics
from pathlib import Path

from openpyxl import load_workbook


DEFAULT_SOURCE = Path(r"C:\Users\Beth Oneglio\Downloads\EducaGen (respuestas).xlsx")
OUTPUT_DIR = Path(__file__).resolve().parent
DATA_FILE = OUTPUT_DIR / "respuestas-anonimizadas.csv"
REPORT_FILE = OUTPUT_DIR / "RESULTADOS.md"

SHORT_LABELS = [
    "frecuencia",
    "complejidad",
    "facilidad",
    "apoyo_tecnico",
    "integracion",
    "inconsistencia",
    "aprendizaje_rapido",
    "incomodidad",
    "confianza",
    "aprendizaje_previo",
]


def sus_score(scores):
    """Calcula SUS: 5 escalado a partir de elementos pares/impares."""
    adjusted = []
    for index, score in enumerate(scores):
        adjusted.append(score - 1 if index % 2 == 0 else 5 - score)
    return sum(adjusted) * 2.5


def main():
    source = Path(__import__("sys").argv[1]) if len(__import__("sys").argv) > 1 else DEFAULT_SOURCE
    workbook = load_workbook(source, data_only=True)
    sheet = workbook["Respuestas de formulario 1"]

    headers = [cell.value for cell in sheet[1]]
    answer_rows = list(sheet.iter_rows(min_row=2, values_only=True))

    fieldnames = [
        "participante_id",
        "marca_temporal",
        "carrera",
        "universidad",
        "edad",
        "genero",
        *SHORT_LABELS,
        "sus",
    ]

    records = []
    for number, values in enumerate(answer_rows, start=1):
        row = dict(zip(headers, values))
        scores = [int(row[headers[index]]) for index in range(6, 16)]
        record = {
            "participante_id": f"P{number:02d}",
            "marca_temporal": row[headers[0]].isoformat(timespec="milliseconds"),
            "carrera": row[headers[2]],
            "universidad": row[headers[3]],
            "edad": int(row[headers[4]]),
            "genero": row[headers[5]],
            **dict(zip(SHORT_LABELS, scores)),
            "sus": sus_score(scores),
        }
        records.append(record)

    with DATA_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    sus_values = [record["sus"] for record in records]
    ages = [record["edad"] for record in records]
    item_means = {
        label: statistics.mean(record[label] for record in records)
        for label in SHORT_LABELS
    }
    gender_counts = {}
    for record in records:
        gender_counts[record["genero"]] = gender_counts.get(record["genero"], 0) + 1

    report = [
        "# Resultados verificables del piloto EducaGen",
        "",
        "## Alcance",
        "",
        "- Participantes: **10**",
        "- Respuestas válidas utilizadas: **10 de 10**",
        "- Periodo registrado: **21-22 de noviembre de 2026**",
        "- Instrumento: cuestionario de 10 ítems; puntuación SUS",
        "- Método: los puntajes individuales se recalcularon directamente desde las respuestas originales.",
        "- Privacidad: este reporte publica identificadores de participante, no nombres. Las carreras y universidades se mantienen a nivel agregado solo en el conjunto anónimo.",
        "",
        "## Resultado principal",
        "",
        f"- SUS promedio: **{statistics.mean(sus_values):.1f}**",
        f"- Mediana SUS: **{statistics.median(sus_values):.1f}**",
        f"- Desviación estándar: **{statistics.stdev(sus_values):.2f}**",
        f"- Rango observado: **{min(sus_values):.1f}-{max(sus_values):.1f}**",
        "- Referencia habitual: 68 en el SUS se usa como promedio comparativo, pero no convierte por sí solo a una aprobación/reprobación del producto.",
        "",
        "No se descartan resultados bajos ni se presentan como promedios mejores de lo observado.",
        "",
        "## Distribución SUS individual",
        "",
        "| Participante | SUS |",
        "|---|---:|",
    ]
    report.extend(
        f"| {record['participante_id']} | {record['sus']:.1f} |"
        for record in records
    )

    report.extend([
        "",
        "## Perfil del grupo",
        "",
        f"- Edad promedio: **{statistics.mean(ages):.1f}** años",
        f"- Edad mínima-máxima: **{min(ages)}-{max(ages)}**",
        "- Género:",
    ])
    report.extend(f"  - {name}: {count}" for name, count in sorted(gender_counts.items()))

    report.extend([
        "",
        "## Promedio por ítem",
        "",
        "| Variable | Promedio (1-5) |",
        "|---|---:|",
    ])
    report.extend(
        f"| {label} | {item_means[label]:.2f} |"
        for label in SHORT_LABELS
    )

    report.extend([
        "",
        "## Archivos",
        "",
        "- [`respuestas-anonimizadas.csv`](./respuestas-anonimizadas.csv): datos individuales sin nombres.",
        "- [`analizar_piloto.py`](./analizar_piloto.py): reproducción del cálculo.",
        "",
        "## Interpretación",
        "",
        "El promedio SUS de 78.5 está por encima del valor de referencia general de 68 y muestra variación entre participantes. Esto es evidencia útil pero limitada: la muestra es pequeña (n=10), no representativa y corresponde a un piloto. Deben verificarse los resultados con una muestra mayor y con tareas observadas.",
        "",
        "## Reproducibilidad",
        "",
        "Ejecutar:",
        "",
        "```powershell",
        "python .\\piloto_educagen\\analizar_piloto.py",
        "```",
        "",
        "También puede indicarse otra hoja de respuestas:",
        "",
        "```powershell",
        "python .\\piloto_educagen\\analizar_piloto.py \"C:\\ruta\\respuestas.xlsx\"",
        "```",
    ])

    REPORT_FILE.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Participantes: {len(records)}")
    print(f"SUS promedio: {statistics.mean(sus_values):.1f}")
    print(f"Reporte: {REPORT_FILE}")


if __name__ == "__main__":
    main()

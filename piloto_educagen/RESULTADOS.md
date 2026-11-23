# Resultados verificables del piloto EducaGen

## Alcance

- Participantes: **10**
- Respuestas válidas utilizadas: **10 de 10**
- Periodo registrado: **21-22 de noviembre de 2026**
- Instrumento: cuestionario de 10 ítems; puntuación SUS
- Método: los puntajes individuales se recalcularon directamente desde las respuestas originales.
- Privacidad: este reporte publica identificadores de participante, no nombres. Las carreras y universidades se mantienen a nivel agregado solo en el conjunto anónimo.

## Resultado principal

- SUS promedio: **78.5**
- Mediana SUS: **80.0**
- Desviación estándar: **11.62**
- Rango observado: **55.0-97.5**
- Referencia habitual: 68 en el SUS se usa como promedio comparativo, pero no convierte por sí solo a una aprobación/reprobación del producto.

No se descartan resultados bajos ni se presentan como promedios mejores de lo observado.

## Distribución SUS individual

| Participante | SUS |
|---|---:|
| P01 | 67.5 |
| P02 | 72.5 |
| P03 | 55.0 |
| P04 | 97.5 |
| P05 | 80.0 |
| P06 | 85.0 |
| P07 | 82.5 |
| P08 | 80.0 |
| P09 | 77.5 |
| P10 | 87.5 |

## Perfil del grupo

- Edad promedio: **42.9** años
- Edad mínima-máxima: **23-53**
- Género:
  - Femenino: 2
  - Masculino: 8

## Promedio por ítem

| Variable | Promedio (1-5) |
|---|---:|
| frecuencia | 4.40 |
| complejidad | 2.20 |
| facilidad | 3.50 |
| apoyo_tecnico | 1.80 |
| integracion | 4.30 |
| inconsistencia | 1.80 |
| aprendizaje_rapido | 4.10 |
| incomodidad | 2.00 |
| confianza | 4.40 |
| aprendizaje_previo | 1.50 |

## Archivos

- [`respuestas-anonimizadas.csv`](./respuestas-anonimizadas.csv): datos individuales sin nombres.
- [`analizar_piloto.py`](./analizar_piloto.py): reproducción del cálculo.

## Interpretación

El promedio SUS de 78.5 está por encima del valor de referencia general de 68 y muestra variación entre participantes. Esto es evidencia útil pero limitada: la muestra es pequeña (n=10), no representativa y corresponde a un piloto. Deben verificarse los resultados con una muestra mayor y con tareas observadas.

## Reproducibilidad

Ejecutar:

```powershell
python .\piloto_educagen\analizar_piloto.py
```

También puede indicarse otra hoja de respuestas:

```powershell
python .\piloto_educagen\analizar_piloto.py "C:\ruta\respuestas.xlsx"
```

"""
Baixa dados históricos do Open-Meteo para múltiplos pontos geográficos
correspondentes às células de grade ICON-EU (~7 km) que cobrem cada bacia.

Saídas:
  dados/openmeteo_multipoint/pt_LAT_LON.parquet  — série horária por ponto
  dados/openmeteo_multipoint/index.json          — mapa bacia → lista de pontos
"""

import json
import time
from pathlib import Path

import polars as pl
import requests

# ── Coordenadas reais das estações CEMADEN por bacia ─────────────────────────
def get_grade_points():
    df = pl.read_parquet("dados/cemaden_abcd.parquet")
    with open("dados/estacoes_bacia.json") as f:
        estacoes = json.load(f)

    # Snap para grade ICON-EU (~7 km = 1/14 grau)
    bacia_points: dict[str, list[tuple[float, float]]] = {}
    all_points: set[tuple[float, float]] = set()

    for bacia, ests in estacoes.items():
        pts = (
            df.filter(pl.col("codEstacao").is_in(ests))
            .select(["latitude", "longitude"])
            .unique()
            .with_columns([
                (pl.col("latitude")  * 14).round(0) / 14,
                (pl.col("longitude") * 14).round(0) / 14,
            ])
            .unique()
            .sort(["latitude", "longitude"])
        )
        coords = [(round(r["latitude"], 6), round(r["longitude"], 6))
                  for r in pts.iter_rows(named=True)]
        bacia_points[bacia] = coords
        all_points.update(coords)

    return bacia_points, sorted(all_points)


def download_point(lat: float, lon: float, out_dir: Path) -> pl.DataFrame | None:
    fname = out_dir / f"pt_{lat:.6f}_{lon:.6f}.parquet".replace("-", "m")
    if fname.exists():
        print(f"  [{lat:.4f},{lon:.4f}] já existe — pulando")
        return pl.read_parquet(fname)

    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        "&start_date=2016-01-01&end_date=2025-12-31"
        "&hourly=precipitation,rain,temperature_2m,relative_humidity_2m"
        ",wind_speed_10m,pressure_msl"
        "&timezone=America%2FSao_Paulo"
        "&precipitation_unit=mm"
    )

    for attempt in range(3):
        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            if attempt == 2:
                print(f"  ERRO [{lat},{lon}]: {e}")
                return None
            time.sleep(5)

    h = data["hourly"]
    df = pl.DataFrame({
        "dt":             pl.Series(h["time"]).str.to_datetime("%Y-%m-%dT%H:%M", time_unit="us"),
        "precipitation_mm": pl.Series(h["precipitation"], dtype=pl.Float64).fill_null(0.0),
        "rain_mm":          pl.Series(h["rain"],          dtype=pl.Float64).fill_null(0.0),
        "temperature_c":    pl.Series(h["temperature_2m"],         dtype=pl.Float64),
        "humidity_pct":     pl.Series(h["relative_humidity_2m"],   dtype=pl.Float64),
        "wind_speed_kmh":   pl.Series(h["wind_speed_10m"],         dtype=pl.Float64),
        "pressure_hpa":     pl.Series(h["pressure_msl"],           dtype=pl.Float64),
        "latitude":  [lat]  * len(h["time"]),
        "longitude": [lon] * len(h["time"]),
    })
    df.write_parquet(fname)
    print(f"  [{lat:.4f},{lon:.4f}] {len(df):,} linhas salvas → {fname.name}")
    return df


def main():
    out_dir = Path("dados/openmeteo_multipoint")
    out_dir.mkdir(parents=True, exist_ok=True)

    bacia_points, all_points = get_grade_points()

    print(f"Pontos únicos a baixar: {len(all_points)}")
    for b, pts in bacia_points.items():
        print(f"  {b}: {pts}")

    # Salva índice bacia → pontos
    index = {b: [{"lat": p[0], "lon": p[1]} for p in pts]
             for b, pts in bacia_points.items()}
    with open(out_dir / "index.json", "w") as f:
        json.dump(index, f, indent=2)

    print("\nBaixando séries históricas (2016–2025)...")
    for lat, lon in all_points:
        download_point(lat, lon, out_dir)
        time.sleep(1)  # respeitar rate limit da API

    # Verificação rápida
    print("\nVerificação:")
    for lat, lon in all_points:
        fname = out_dir / f"pt_{lat:.6f}_{lon:.6f}.parquet".replace("-", "m")
        if fname.exists():
            df = pl.read_parquet(fname)
            nulls = df["precipitation_mm"].null_count()
            print(f"  [{lat:.4f},{lon:.4f}] {len(df):,} linhas, {nulls} nulls em precipitation_mm")
        else:
            print(f"  [{lat:.4f},{lon:.4f}] FALTANDO")


if __name__ == "__main__":
    main()

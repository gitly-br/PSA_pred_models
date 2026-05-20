"""
Organiza dados meteorologicos em Parquets mensais.

Fluxo:
  1. Audita a cobertura das estacoes CEMADEN exigidas por bacia.
  2. Estende os pontos Open-Meteo multipoint ate a data alvo, se necessario.
  3. Gera um Parquet por mes para:
     - historico CEMADEN observado;
     - forecast/proxy Open-Meteo multipoint.

Saidas:
  dados/weather/monthly/historic/cemaden_YYYY_MM.parquet
  dados/weather/monthly/forecast/openmeteo_YYYY_MM.parquet
  dados/weather/monthly/weather_audit.json
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.request import urlopen

import polars as pl

WORKDIR = Path(__file__).resolve().parents[2]
DATA_DIR = WORKDIR / "dados"
CEMADEN_PATH = DATA_DIR / "cemaden_abcd.parquet"
CEMADEN_2026_DIR = DATA_DIR / "CEMADEN" / "todos"
ESTACOES_BACIA_PATH = DATA_DIR / "estacoes_bacia.json"
OPENMETEO_DIR = DATA_DIR / "weather" / "openmeteo_multipoint"
MONTHLY_ROOT = DATA_DIR / "weather" / "monthly"
HISTORIC_OUT = MONTHLY_ROOT / "historic"
FORECAST_OUT = MONTHLY_ROOT / "forecast"

OPENMETEO_START = date(2026, 1, 1)
OPENMETEO_END = date(2026, 5, 19)


def month_key(dt: datetime | date) -> str:
    return f"{dt.year:04d}_{dt.month:02d}"


def cemaden_audit() -> dict:
    df = load_cemaden_all()
    with ESTACOES_BACIA_PATH.open() as f:
        estacoes_bacia = json.load(f)

    needed = sorted({s for stations in estacoes_bacia.values() for s in stations})
    present = set(df["codEstacao"].unique().to_list())
    missing = [s for s in needed if s not in present]
    dt_min = df["dt"].min()
    dt_max = df["dt"].max()

    return {
        "path": str(CEMADEN_PATH),
        "shape": df.shape,
        "dt_min": dt_min.isoformat() if dt_min else None,
        "dt_max": dt_max.isoformat() if dt_max else None,
        "needed_station_count": len(needed),
        "present_station_count": len(present),
        "missing_stations": missing,
    }


def _fname_pt(lat: float, lon: float) -> str:
    return f"pt_m{abs(lat):.6f}_m{abs(lon):.6f}.parquet"


def _load_cemaden_2026_csv(path: Path) -> pl.DataFrame:
    return (
        pl.read_csv(path, separator=";", decimal_comma=True, truncate_ragged_lines=True)
        .with_columns(
            pl.col("latitude").cast(pl.Utf8).str.replace(",", ".").cast(pl.Float64),
            pl.col("longitude").cast(pl.Utf8).str.replace(",", ".").cast(pl.Float64),
            pl.col("valorMedida").cast(pl.Utf8).str.replace(",", ".").cast(pl.Float64).alias("valor_mm"),
            pl.col("datahora").str.to_datetime("%Y-%m-%d %H:%M:%S%.f").alias("dt"),
        )
        .select(["municipio", "codEstacao", "nomeEstacao", "latitude", "longitude", "dt", "valor_mm"])
    )


def load_cemaden_all() -> pl.DataFrame:
    base = pl.read_parquet(CEMADEN_PATH)
    parts = [base]
    if CEMADEN_2026_DIR.exists():
        for path in sorted(CEMADEN_2026_DIR.glob("2026_*.csv")):
            parts.append(_load_cemaden_2026_csv(path))
    return (
        pl.concat(parts, how="vertical_relaxed")
        .drop_nulls(["dt", "codEstacao"])
        .sort(["dt", "codEstacao"])
    )


def fetch_openmeteo_point(lat: float, lon: float, start_date: date, end_date: date) -> pl.DataFrame:
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        "&hourly=precipitation,rain,temperature_2m,relative_humidity_2m,wind_speed_10m,pressure_msl"
        "&timezone=America%2FSao_Paulo"
        "&precipitation_unit=mm"
    )
    with urlopen(url, timeout=120) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    hourly = payload["hourly"]
    return pl.DataFrame(
        {
            "dt": pl.Series(hourly["time"]).str.to_datetime("%Y-%m-%dT%H:%M", time_unit="us"),
            "precipitation_mm": pl.Series(hourly["precipitation"], dtype=pl.Float64).fill_null(0.0),
            "rain_mm": pl.Series(hourly["rain"], dtype=pl.Float64).fill_null(0.0),
            "temperature_c": pl.Series(hourly["temperature_2m"], dtype=pl.Float64),
            "humidity_pct": pl.Series(hourly["relative_humidity_2m"], dtype=pl.Float64),
            "wind_speed_kmh": pl.Series(hourly["wind_speed_10m"], dtype=pl.Float64),
            "pressure_hpa": pl.Series(hourly["pressure_msl"], dtype=pl.Float64),
            "latitude": [lat] * len(hourly["time"]),
            "longitude": [lon] * len(hourly["time"]),
        }
    )


def extend_openmeteo_points() -> list[dict]:
    with (OPENMETEO_DIR / "index.json").open() as f:
        index = json.load(f)

    points: list[dict] = []
    seen: set[tuple[float, float]] = set()
    for bacia, coords in index.items():
        for coord in coords:
            key = (float(coord["lat"]), float(coord["lon"]))
            if key in seen:
                continue
            seen.add(key)
            points.append({"lat": key[0], "lon": key[1]})

    for p in points:
        path = OPENMETEO_DIR / _fname_pt(p["lat"], p["lon"])
        if path.exists():
            current = pl.read_parquet(path)
            current_max = current["dt"].max()
        else:
            current = None
            current_max = None

        if current_max is not None and current_max.date() >= OPENMETEO_END:
            continue

        fetch_start = OPENMETEO_START if current_max is None else max(current_max.date() + timedelta(days=1), OPENMETEO_START)
        if fetch_start > OPENMETEO_END:
            continue

        new_df = fetch_openmeteo_point(p["lat"], p["lon"], fetch_start, OPENMETEO_END)
        if current is not None:
            merged = pl.concat([current, new_df]).unique(subset=["dt"], keep="last").sort("dt")
        else:
            merged = new_df.sort("dt")
        merged.write_parquet(path)

    return points


def write_monthly_historic() -> list[dict]:
    df = load_cemaden_all().with_columns(pl.col("dt").dt.date().alias("data"))
    HISTORIC_OUT.mkdir(parents=True, exist_ok=True)

    summaries: list[dict] = []
    for month in df.select(pl.col("dt").dt.truncate("1mo").alias("month")).unique().sort("month")["month"].to_list():
        part = df.filter(pl.col("dt").dt.truncate("1mo") == month).drop("data")
        out = HISTORIC_OUT / f"cemaden_{month_key(month)}.parquet"
        part.write_parquet(out)
        summaries.append({"kind": "historic", "month": month_key(month), "rows": part.height, "path": str(out)})

    load_cemaden_all().write_parquet(CEMADEN_PATH)
    return summaries


def write_monthly_forecast(points: list[dict]) -> list[dict]:
    FORECAST_OUT.mkdir(parents=True, exist_ok=True)

    dfs: list[pl.DataFrame] = []
    for p in points:
        path = OPENMETEO_DIR / _fname_pt(p["lat"], p["lon"])
        if not path.exists():
            continue
        df = pl.read_parquet(path).with_columns(pl.col("dt").dt.truncate("1mo").alias("month"))
        dfs.append(df)

    if not dfs:
        return []

    df_all = pl.concat(dfs, how="vertical_relaxed")
    summaries: list[dict] = []
    for month in df_all.select("month").unique().sort("month")["month"].to_list():
        part = df_all.filter(pl.col("month") == month).drop("month")
        out = FORECAST_OUT / f"openmeteo_{month_key(month)}.parquet"
        part.write_parquet(out)
        summaries.append({"kind": "forecast", "month": month_key(month), "rows": part.height, "path": str(out)})
    return summaries


def main() -> None:
    MONTHLY_ROOT.mkdir(parents=True, exist_ok=True)

    audit = cemaden_audit()
    points = extend_openmeteo_points()
    historic = write_monthly_historic()
    forecast = write_monthly_forecast(points)

    report = {
        "cemaden": audit,
        "openmeteo_point_count": len(points),
        "openmeteo_target_end": OPENMETEO_END.isoformat(),
        "historic_months": len(historic),
        "forecast_months": len(forecast),
        "historic_summary": historic,
        "forecast_summary": forecast,
    }
    with (MONTHLY_ROOT / "weather_audit.json").open("w") as f:
        json.dump(report, f, indent=2, default=str)

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()

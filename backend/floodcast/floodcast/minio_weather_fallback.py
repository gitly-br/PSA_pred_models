from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from io import BytesIO
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytz
import polars as pl

try:
    from harvest.minio_client import MinioClientWrapper, MinioSettings
except ModuleNotFoundError:
    @dataclass(frozen=True)
    class MinioSettings:
        endpoint: str
        access_key: str
        secret_key: str
        bucket: str
        secure: bool = False

    class MinioClientWrapper:  # pragma: no cover - import-time fallback only
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("harvest.minio_client is not installed")

DEFAULT_MINIO_SETTINGS = MinioSettings(
    endpoint=os.getenv("MINIO_ENDPOINT", "localhost:19000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "psa"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "psa12345"),
    bucket=os.getenv("MINIO_BUCKET", "psa"),
    secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
)

TZ = pytz.timezone("America/Sao_Paulo")


class WeatherDataUnavailableError(RuntimeError):
    pass


def _utc_bounds(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    start_local = TZ.localize(datetime.combine(start_date, time.min))
    end_local = TZ.localize(datetime.combine(end_date, time.min))
    return start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)


def _load_station_bacias(path: str | None = None) -> dict[str, list[str]]:
    if path is None:
        path = str(Path(__file__).resolve().parents[3] / "notebooks" / "dados" / "estacoes_bacia.json")
    if not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    station_map: dict[str, list[str]] = defaultdict(list)
    for bacia, station_ids in data.items():
        for station_id in station_ids:
            station_map[str(station_id)].append(str(bacia))
    return {station_id: sorted(set(bacias)) for station_id, bacias in station_map.items()}


def _load_point_bacias_from_minio(minio: MinioClientWrapper, prefix: str = "weather/openmeteo/forecast/") -> dict[str, list[str]]:
    try:
        # Try to read index.json from the forecast source directory on local disk first
        local_path = Path(__file__).resolve().parents[3] / "notebooks" / "dados" / "weather" / "openmeteo_multipoint" / "index.json"
        if local_path.exists():
            index = json.loads(local_path.read_text(encoding="utf-8"))
        else:
            # Fallback: try to read from MinIO (if stored there)
            raw = minio.get_object_bytes(f"{prefix.rstrip('/')}/index.json")
            index = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}

    point_bacias: dict[str, list[str]] = defaultdict(list)
    for bacia, points in index.items():
        for point in points:
            point_id = f"{point['lat']}_{point['lon']}"
            point_bacias[point_id].append(bacia)
    return {point_id: sorted(set(bacias)) for point_id, bacias in point_bacias.items()}


class MinIOWeatherFallback:
    """Reads weather data directly from MinIO parquet files when MongoDB is empty."""

    def __init__(self, minio_settings: MinioSettings | None = None):
        self.minio = MinioClientWrapper(minio_settings or DEFAULT_MINIO_SETTINGS)
        self.station_bacias = _load_station_bacias()
        self.point_bacias = _load_point_bacias_from_minio(self.minio)
        self._historic_cache: dict[str, pl.DataFrame] = {}
        self._forecast_cache: dict[str, pl.DataFrame] = {}

    def _get_historic_frame(self) -> pl.DataFrame | None:
        """Load CEMADEN historic data from MinIO (cached)."""
        import polars as pl

        prefix = "weather/cemaden/"
        objects = [o for o in self.minio.list_objects(prefix) if o.endswith(".parquet")]
        if not objects:
            return None
        # Load and concatenate all parquets (necessary for full date range coverage)
        frames = []
        for key in objects:
            if key not in self._historic_cache:
                raw = self.minio.get_object_bytes(key)
                self._historic_cache[key] = pl.read_parquet(BytesIO(raw))
            frames.append(self._historic_cache[key])
        return pl.concat(frames, how="vertical_relaxed") if frames else None

    def _get_forecast_frames(self, prefix: str) -> dict[str, pl.DataFrame]:
        """Load forecast data from a MinIO prefix (cached)."""
        import polars as pl

        objects = [o for o in self.minio.list_objects(prefix) if o.endswith(".parquet")]
        frames: dict[str, pl.DataFrame] = {}
        for obj in objects:
            if obj not in self._forecast_cache:
                raw = self.minio.get_object_bytes(obj)
                self._forecast_cache[obj] = pl.read_parquet(BytesIO(raw))
            frames[obj] = self._forecast_cache[obj]
        return frames

    def fetch_historic_documents(
        self,
        bacia: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        frame = self._get_historic_frame()
        if frame is None:
            raise WeatherDataUnavailableError(f"Sem dados historicos em parquet para {bacia}")

        station_ids = [
            sid for sid, bacias in self.station_bacias.items() if bacia in bacias
        ]
        if not station_ids:
            raise WeatherDataUnavailableError(f"Sem mapeamento de estacoes em parquet para {bacia}")

        start_utc, end_utc = _utc_bounds(start_date, end_date)
        # Ensure dt column is timezone-aware UTC for comparison
        dt_col = pl.col("dt")
        if frame.schema["dt"].time_zone is None:
            dt_col = dt_col.dt.replace_time_zone("UTC", ambiguous="raise")
        filtered = frame.filter(
            pl.col("codEstacao").is_in(station_ids)
            & (dt_col >= pl.lit(start_utc))
            & (dt_col < pl.lit(end_utc))
        )

        docs: list[dict[str, Any]] = []
        for row in filtered.to_dicts():
            sid = str(row.get("codEstacao") or "unknown")
            bacias = self.station_bacias.get(sid, [])
            docs.append(
                {
                    "provider": "cemaden",
                    "station_id": sid,
                    "station_name": row.get("nomeEstacao"),
                    "municipio": row.get("municipio"),
                    "bacia": bacias[0] if bacias else None,
                    "bacias": bacias,
                    "latitude": row.get("latitude"),
                    "longitude": row.get("longitude"),
                    "dt": row.get("dt"),
                    "precipitation_mm": row.get("valor_mm") or 0.0,
                }
            )
        if not docs:
            raise WeatherDataUnavailableError(f"Sem dados historicos em parquet para {bacia}")
        return docs

    def fetch_forecast_documents(self, bacia: str, target_date: date) -> list[dict[str, Any]]:
        start_utc, end_utc = _utc_bounds(target_date, target_date + timedelta(days=1))
        for prefix in ("weather/openweather/forecast/", "weather/openmeteo/forecast/"):
            frames = self._get_forecast_frames(prefix)
            if not frames:
                continue

            docs: list[dict[str, Any]] = []
            for object_name, frame in frames.items():
                # Extract lat/lon from either the filename (`pt_...`) or the parquet rows.
                stem = Path(object_name).stem
                parts = stem.split("_")
                lat = lon = None
                if len(parts) >= 4 and parts[0] == "pt":
                    lat = float(parts[1].replace("m", "-").replace("p", ""))
                    lon = float(parts[2].replace("m", "-").replace("p", ""))
                elif {"latitude", "longitude"}.issubset(set(frame.columns)):
                    first = frame.select(["latitude", "longitude"]).head(1).to_dicts()
                    if first:
                        lat = float(first[0]["latitude"])
                        lon = float(first[0]["longitude"])
                if lat is None or lon is None:
                    continue
                point_id = f"{lat}_{lon}"
                bacias = self.point_bacias.get(point_id, [])
                if bacia not in bacias:
                    continue

                dt_col = pl.col("dt")
                if frame.schema["dt"].time_zone is None:
                    dt_col = dt_col.dt.replace_time_zone("UTC", ambiguous="raise")
                filtered = frame.filter(
                    (dt_col >= pl.lit(start_utc)) & (dt_col < pl.lit(end_utc))
                )
                if filtered.is_empty():
                    continue

                hourly = []
                for row in filtered.to_dicts():
                    hourly.append(
                        {
                            "dt": row.get("dt"),
                            "latitude": lat,
                            "longitude": lon,
                            "temperature": row.get("temperature_c") or row.get("temp"),
                            "dew_point": row.get("dew_point"),
                            "pressure": row.get("pressure_hpa"),
                            "humidity": row.get("humidity_pct"),
                            "wind_speed": row.get("wind_speed_kmh"),
                            "rain": row.get("rain_mm") or row.get("precipitation_mm") or 0.0,
                            "precipitation_mm": row.get("precipitation_mm") or row.get("rain_mm") or 0.0,
                        }
                    )

                docs.append(
                    {
                        "provider": "openweather" if "openweather" in prefix else "openmeteo",
                        "point_id": point_id,
                        "bacia": bacias[0] if bacias else None,
                        "bacias": bacias,
                        "dt_request": start_utc,
                        "timezone": "UTC",
                        "hourly": hourly,
                        "latitude": lat,
                        "longitude": lon,
                    }
                )
            if docs:
                return docs

        raise WeatherDataUnavailableError(f"Sem dados de forecast em parquet para {bacia}")

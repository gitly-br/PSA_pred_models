from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Iterable

import httpx
from httpx import HTTPStatusError

from harvest.sources.source_base import SourceBase, HarvestError


class DefesaCivilSource(SourceBase):
    """
    Concrete implementation of SourceBase for the Defesa Civil API.

    Fetches hourly readings from Santo André's Defesa Civil weather stations
    and normalizes them into api_data.historic documents.
    """

    target = "api_data.historic"

    def __init__(self, src_config, timeout: int = 30) -> None:
        super().__init__(src_config, timeout)
        self._station_map = self._load_station_mapping()

    def _load_station_mapping(self) -> dict[str, dict[str, Any]]:
        """Load station mapping from JSON file."""
        mapping_path = Path(__file__).parent.parent / "defesa_civil_stations.json"
        if not mapping_path.exists():
            return {}
        with open(mapping_path, encoding="utf-8") as f:
            return json.load(f)

    async def harvest(self) -> Iterable[dict[str, Any]]:
        """
        Fetch hourly readings from Defesa Civil API and normalize to
        api_data.historic documents.

        Raises:
            HarvestError: if credentials are missing or HTTP error occurs.
        """
        api_id = os.getenv("DEFESA_CIVIL_API_ID")
        sistema_id = os.getenv("DEFESA_CIVIL_SISTEMA_ID")
        if not api_id or not sistema_id:
            raise HarvestError("DEFESA_CIVIL_API_ID or DEFESA_CIVIL_SISTEMA_ID not set")

        import pytz
        tz = pytz.timezone("America/Sao_Paulo")
        now_local = dt.datetime.now(tz)
        one_hour_ago = now_local - dt.timedelta(hours=1)

        base_url = self.src_config.url
        periodicidade = self.src_config.args.get("periodicidade", 60)

        params = {
            "data_inicio": one_hour_ago.strftime("%Y-%m-%d %H:%M:%S"),
            "data_fim": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "periodicidade": periodicidade,
        }
        headers = {
            "api-id": api_id,
            "sistema-id": sistema_id,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(base_url, params=params, headers=headers)
                resp.raise_for_status()
            except HTTPStatusError as exc:
                raise HarvestError(
                    f"HTTP {exc.response.status_code} for Defesa Civil API"
                ) from exc
            except httpx.RequestError as exc:
                raise HarvestError(f"Network error for Defesa Civil: {exc}") from exc

        payload = resp.json()
        dados = payload.get("dados", {})
        if dados.get("apiResultado") != "S":
            raise HarvestError("Defesa Civil API returned error")

        api_data = dados.get("apiDados", [])
        if not api_data:
            return []

        loaded_at = dt.datetime.now(dt.timezone.utc)
        documents: list[dict[str, Any]] = []

        for reading in api_data:
            estacao_id = str(reading.get("estacao_id", "unknown"))
            station_info = self._station_map.get(estacao_id, {})

            intervalo_str = reading.get("intervalo")
            if intervalo_str:
                dt_value = dt.datetime.strptime(intervalo_str, "%Y-%m-%d %H:%M:%S")
                dt_value = tz.localize(dt_value).astimezone(dt.timezone.utc)
            else:
                dt_value = loaded_at

            bacias = station_info.get("bacias", [])
            documents.append({
                "provider": "defesa_civil",
                "station_id": estacao_id,
                "station_name": reading.get("localidade") or station_info.get("name"),
                "bacias": bacias,
                "latitude": station_info.get("latitude"),
                "longitude": station_info.get("longitude"),
                "dt": dt_value,
                "precipitation_mm": float(reading.get("pluviometro", 0.0)),
                "temperature": float(reading.get("temperatura", 0.0)) if reading.get("temperatura") else None,
                "humidity": float(reading.get("umidade", 0.0)) if reading.get("umidade") else None,
                "loaded_at": loaded_at,
            })

        return documents

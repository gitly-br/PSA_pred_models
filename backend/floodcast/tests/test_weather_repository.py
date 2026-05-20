from __future__ import annotations

from datetime import datetime, timezone

from floodcast.weather_repository import WeatherDataRepository


def test_summarize_forecast_documents_includes_period_totals():
    summary = WeatherDataRepository.summarize_forecast_documents(
        [
            {
                "hourly": [
                    {"dt": datetime(2025, 3, 19, 3, 0, tzinfo=timezone.utc), "rain": 1.0},
                    {"dt": datetime(2025, 3, 19, 12, 0, tzinfo=timezone.utc), "rain": 2.0},
                    {"dt": datetime(2025, 3, 19, 18, 0, tzinfo=timezone.utc), "rain": 3.0},
                    {"dt": datetime(2025, 3, 20, 0, 0, tzinfo=timezone.utc), "rain": 4.0},
                ]
            }
        ]
    )

    assert summary["total_mm"] == 10.0
    assert summary["rain_by_period_mm"] == {
        "night": 1.0,
        "morning": 2.0,
        "afternoon": 3.0,
        "evening": 4.0,
    }

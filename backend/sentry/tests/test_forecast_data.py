from __future__ import annotations

from datetime import datetime

from app.sanic_blueprints.forecast_data.forecast_data import _aggregate_hourly_forecast


def test_aggregate_hourly_forecast_averages_five_points():
    docs = []
    for point in range(5):
        docs.append(
            {
                "hourly": [
                    {
                        "dt": datetime(2026, 5, 18, 3, 0),
                        "temperature": 20 + point,
                        "rain": 1.0 + point,
                        "pop": 0.1 + (point * 0.1),
                        "humidity": 70 + point,
                        "pressure": 1000 + point,
                        "wind_speed": 5 + point,
                        "dew_point": 15 + point,
                        "clouds": 10 + point,
                    }
                ]
            }
        )

    result = _aggregate_hourly_forecast(docs)

    assert result == [
        {
            "temp": 22.0,
            "rain": 3.0,
            "pop": 0.3,
            "humidity": 72,
            "pressure": 1002,
            "wind_speed": 7.0,
            "dew_point": 17.0,
            "clouds": 12,
        }
    ]

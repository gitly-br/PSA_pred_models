from pathlib import Path
import json

from floodcast.seed_model_registry import _extract_features, _extract_station_ids, _extract_thresholds


ROBUST_META_PATH = Path(__file__).resolve().parents[3] / "notebooks" / "dados" / "results" / "psa_risk_v1_station_contract_robust_metadata.json"


def test_extract_robust_metadata_contract():
    meta = json.loads(ROBUST_META_PATH.read_text(encoding="utf-8"))

    features = _extract_features(meta)
    assert features[:3] == ["api_070", "api_085", "api_095"]
    assert "om_precip_sum_h24" in features

    station_ids = _extract_station_ids(meta, "guarara")
    assert station_ids[0] == "352940105A"
    assert len(station_ids) == 17

    thresholds = _extract_thresholds(meta, "guarara")
    assert set(thresholds) == {"1", "2", "3"}
    assert thresholds["1"] > 0


def test_extract_thresholds_applies_floor():
    meta = {
        "thresholds": {
            "1": 0.03,
            "2": 0.2,
            "3": 0.09,
        }
    }

    thresholds = _extract_thresholds(meta, "guarara")

    assert thresholds == {"1": 0.1, "2": 0.2, "3": 0.1}

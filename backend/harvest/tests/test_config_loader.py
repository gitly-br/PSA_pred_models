from pathlib import Path
from harvest.config_loader import ConfigLoader

def test_load_configs():
    # sample_configs.yml is in project root
    yaml_path = Path(__file__).parent.parent / "sample_configs.yml"
    loader = ConfigLoader(yaml_path)
    configs = loader.load()

    # basic sanity
    assert len(configs) >= 2
    first = configs[0]
    assert first.city in {"Santo André", "Blumenau"}
    assert first.source_id in {"openweather", "inmet"}
    assert isinstance(first.params, dict)

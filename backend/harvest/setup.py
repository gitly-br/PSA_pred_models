from setuptools import setup, find_packages

# Read the contents of your requirements.txt file
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="harvest",
    version="0.1.0",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "psa-harvest = harvest.main:main_sync",
            "psa-bootstrap-api-data = harvest.bootstrap_api_data:main_sync",
            "psa-bootstrap-local-weather = harvest.bootstrap_local_weather:main_sync",
            "psa-seed-minio = harvest.seed_minio:main_sync",
            "psa-seed-model-registry = harvest.seed_model_registry:main_sync",
        ],
    },
)

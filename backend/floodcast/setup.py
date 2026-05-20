from setuptools import setup, find_packages

# Read the contents of your requirements.txt file
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="floodcast",
    version="0.1.0",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "psa-floodcast = floodcast.main:main_sync",
            "psa-floodcast-once = floodcast.main:main_sync",
            "psa-floodcast-scheduler = floodcast.scheduler:main_sync",
            "psa-seed-champion = floodcast.seed_model_registry:main_sync",
        ],
    },
)

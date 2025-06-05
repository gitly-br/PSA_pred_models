import pytest
import asyncio
from mongomock_motor import AsyncMongoMockClient

from harvest.mongo_client import MongoClientWrapper
from harvest.config_loader import ConfigLoader, SourceConfig

@pytest.fixture
def mongo_wrapper():
    """
    Retorna um MongoClientWrapper cujos atributos client e config_db
    são substituídos por um AsyncMongoMockClient em memória.
    """
    client = AsyncMongoMockClient()
    wrapper = MongoClientWrapper(uri=None)
    wrapper.client = client
    wrapper.config_db = client["harvest_config"]
    wrapper.data_db = client["harvest_data"]
    return wrapper

def normalize(text: str) -> str:
    """
    Remove quebras de linha e múltiplos espaços para facilitar comparação.
    """
    return " ".join(text.split())

@pytest.mark.asyncio
async def test_empty_collections(mongo_wrapper):
    """
    1. Sem documentos em 'sources' nem em 'source_types'.
    load() deve retornar lista vazia sem erro.
    """
    loader = ConfigLoader(mongo_wrapper)
    configs = await loader.load()
    assert configs == []

@pytest.mark.asyncio
async def test_single_valid_source(mongo_wrapper):
    """
    2. Um source válido com type existente em source_types e required_args completos.
    Deve retornar exatamente um SourceConfig com os campos corretos.
    """
    # Arrange: inserir definição de tipo
    await mongo_wrapper.config_db["source_types"].insert_one({
        "type": "weather",
        "url": "http://api.example.com",
        "required_args": ["api_key"]
    })
    # Insert válido em 'sources'
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "weather",
        "region_name": "Santo André",
        "ttl_days": 5,
        "args": {"api_key": "XYZ123"}
    })

    loader = ConfigLoader(mongo_wrapper)
    configs = await loader.load()

    assert len(configs) == 1
    cfg = configs[0]
    assert isinstance(cfg, SourceConfig)
    assert cfg.type == "weather"
    assert cfg.region_name == "Santo André"
    assert cfg.ttl_days == 5
    assert cfg.url == "http://api.example.com"
    assert cfg.args == {"api_key": "XYZ123"}

@pytest.mark.asyncio
async def test_unknown_type(mongo_wrapper, capsys):
    """
    3. Um source cujo 'type' não existe em source_types.
    Deve ser ignorado e imprimir aviso.
    """
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "nonexistent",
        "region_name": "Cidade X",
        "ttl_days": 3,
        "args": {"some_arg": "value"}
    })

    loader = ConfigLoader(mongo_wrapper)
    configs = await loader.load()

    captured = capsys.readouterr()
    out = normalize(captured.out)
    assert "Warning: Type definition for 'nonexistent' not found." in out
    assert configs == []

@pytest.mark.asyncio
async def test_missing_required_arg(mongo_wrapper, capsys):
    """
    4. Um source faltando um required_arg.
    Deve ser ignorado e imprimir aviso de argumento ausente.
    """
    await mongo_wrapper.config_db["source_types"].insert_one({
        "type": "weather",
        "url": "http://api.example.com",
        "required_args": ["api_key"]
    })
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "weather",
        "region_name": "Rio de Janeiro",
        "ttl_days": 7,
        "args": {}  # faltando 'api_key'
    })

    loader = ConfigLoader(mongo_wrapper)
    configs = await loader.load()

    captured = capsys.readouterr()
    out = normalize(captured.out)
    assert "Warning: Source 'Rio de Janeiro' is missing required args ['api_key']." in out
    assert configs == []

@pytest.mark.asyncio
async def test_extra_args(mongo_wrapper):
    """
    5. Um source com args extras além dos required_args.
    Ainda assim deve ser aceito e retornar todos os args.
    """
    await mongo_wrapper.config_db["source_types"].insert_one({
        "type": "weather",
        "url": "http://api.example.com",
        "required_args": ["api_key"]
    })
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "weather",
        "region_name": "Belo Horizonte",
        "ttl_days": 10,
        "args": {"api_key": "ABC", "extra1": "val1", "extra2": "val2"}
    })

    loader = ConfigLoader(mongo_wrapper)
    configs = await loader.load()

    assert len(configs) == 1
    cfg = configs[0]
    assert cfg.args == {"api_key": "ABC", "extra1": "val1", "extra2": "val2"}

@pytest.mark.asyncio
async def test_mixed_records(mongo_wrapper, capsys):
    """
    6. Mistura de registros válidos e inválidos.
    Apenas os válidos aparecem na lista final; avisos para os inválidos.
    """
    await mongo_wrapper.config_db["source_types"].insert_one({
        "type": "weather",
        "url": "http://api.example.com",
        "required_args": ["api_key"]
    })
    # Fonte válida
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "weather",
        "region_name": "Campinas",
        "ttl_days": 4,
        "args": {"api_key": "KEY1"}
    })
    # Fonte com tipo inexistente
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "no_type",
        "region_name": "Vitória",
        "ttl_days": 2,
        "args": {}
    })
    # Fonte faltando required_arg
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "weather",
        "region_name": "Fortaleza",
        "ttl_days": 6,
        "args": {}  # sem 'api_key'
    })

    loader = ConfigLoader(mongo_wrapper)
    configs = await loader.load()

    captured = capsys.readouterr()
    out = normalize(captured.out)
    assert "Warning: Type definition for 'no_type' not found." in out
    assert "Warning: Source 'Fortaleza' is missing required args ['api_key']." in out

    assert len(configs) == 1
    assert configs[0].region_name == "Campinas"

@pytest.mark.asyncio
async def test_required_arg_none(mongo_wrapper):
    """
    7. Um source cujo required_arg está presente, mas com valor None.
    Pelo comportamento atual, não é tratado como ausente, ou seja, o loader aceita
    e retorna um SourceConfig com args contendo None.
    """
    await mongo_wrapper.config_db["source_types"].insert_one({
        "type": "weather",
        "url": "http://api.example.com",
        "required_args": ["api_key"]
    })
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "weather",
        "region_name": "Juiz de Fora",
        "ttl_days": 8,
        "args": {"api_key": None}
    })

    loader = ConfigLoader(mongo_wrapper)
    configs = await loader.load()

    # Deve retornar um SourceConfig mesmo que api_key seja None
    assert len(configs) == 1
    cfg = configs[0]
    assert cfg.region_name == "Juiz de Fora"
    assert cfg.args == {"api_key": None}

@pytest.mark.asyncio
async def test_ttl_override(mongo_wrapper):
    """
    8. Verificar que o ttl_days definido em 'sources' é usado em SourceConfig.
    """
    await mongo_wrapper.config_db["source_types"].insert_one({
        "type": "weather",
        "url": "http://api.example.com",
        "required_args": []
    })
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "weather",
        "region_name": "Porto Alegre",
        "ttl_days": 12,
        "args": {}
    })

    loader = ConfigLoader(mongo_wrapper)
    configs = await loader.load()

    assert len(configs) == 1
    cfg = configs[0]
    assert cfg.ttl_days == 12

@pytest.mark.asyncio
async def test_concurrent_loads(mongo_wrapper):
    """
    9. Chamar load() duas vezes em paralelo; ambas devem retornar a mesma lista.
    """
    await mongo_wrapper.config_db["source_types"].insert_one({
        "type": "weather",
        "url": "http://api.example.com",
        "required_args": ["api_key"]
    })
    await mongo_wrapper.config_db["sources"].insert_one({
        "type": "weather",
        "region_name": "Brasília",
        "ttl_days": 9,
        "args": {"api_key": "Z99"}
    })

    loader = ConfigLoader(mongo_wrapper)
    task1 = loader.load()
    task2 = loader.load()
    results1, results2 = await asyncio.gather(task1, task2)

    assert results1 == results2
    assert len(results1) == 1
    assert results1[0].region_name == "Brasília"

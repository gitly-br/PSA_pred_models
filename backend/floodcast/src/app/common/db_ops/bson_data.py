from bson.json_util import dumps, loads
from bson import encode, decode

def encode_bson(data: dict) -> bytes:
    try:
        return encode(data)
    except Exception as e:
        raise ValueError(f"Erro ao codificar BSON: {e}") from e
    
def decode_bson(data: bytes) -> dict:
    try:
        return decode(data)
    except Exception as e:
        raise ValueError(f"Erro ao decodificar BSON: {e}") from e


def deserialize_json(data):
    try:
        return loads(data)
    except Exception as e:
        raise ValueError(f"Erro ao deserializar JSON: {e}") from e
    
def serialize_to_json(data: dict) -> str:
    try:
        return dumps(data)
    except Exception as e:
        raise ValueError(f"Erro ao serializar para JSON: {e}") from e

from datetime import datetime
import json
from bson import ObjectId

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()+'Z'
        elif isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

def encode_body(body):
    """
    Função para codificar variáveis datetime e ObjectId para string em um corpo JSON.
    """
    return json.loads(JSONEncoder().encode(body))
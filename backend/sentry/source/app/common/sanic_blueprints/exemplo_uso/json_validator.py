from sanic import Blueprint
from sanic.response import json
from pydantic import BaseModel
from typing import Optional
from sanic_ext import validate


class JsonValidator(BaseModel):
    id:str
    name:Optional[str] = None

json_validator = Blueprint('json_validator')

@json_validator.route('/teste_pydantic/json', methods=['GET'])
@validate(json=JsonValidator)
async def validator_json_json_validator(request, body: JsonValidator):
    try:
        return json(body.model_dump())
    
    except Exception as e:
        return json({'error' : e}, 400)
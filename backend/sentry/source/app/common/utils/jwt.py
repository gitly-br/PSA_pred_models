import datetime
from os import environ
from functools import wraps
from jwt import decode, encode

def decode_jwt_token(request, token) -> tuple[bool, dict, int, str]:  #success, payload, status, err_msg
    """Função para decodar um token jwt

    Args:
        request: 
        token: token jwt a ser decodado

    Returns:
        tuple[bool, dict, int, str]: Retorna se foi sucesso, o payload, o status e a mensagem de erro
    """

    if request.app.ctx.sett['ENV'] == 'prod':
        TOKEN_SECRET = request.app.ctx.sett['SECURE']['JWT_SECRET']
        ALGOTIRTHMS = request.app.ctx.sett['SECURE']['JWT_INT']
    else:
        TOKEN_SECRET = 'example'
        ALGOTIRTHMS = "HS256"

    try:
        decoded_token = decode(
            jwt=token, key=TOKEN_SECRET , algorithms=[ALGOTIRTHMS]
        )

        return True, decoded_token, 200, None
        
    except Exception as e:
        if 'Signature has expired' in str(e):
            return (False, {"status" : "failed", "error":"token expirado"},401, e)
        elif "Not enough segments" in str(e):
            return (False, {"status" : "failed", "error":"jwt token inválido"}, 401, e)
        elif "Signature verification failed" in str(e):
            return (False, {"status" : "failed", "error":"jwt token inválido"}, 401, e)
        elif "Invalid header string: 'utf-8' codec can't decode byte" in str(e):
            return (False, {"status" : "failed", "error":"jwt token inválido"}, 401, e)
        elif "Invalid payload padding" in str(e):
            return (False, {"status" : "failed", "error":"jwt token inválido"}, 401, e)
        else:
            return (False, {"status" : "failed", "error" : 'erro interno de servidor, tente novamente mais tarde'}, 500, e)
        

def encode_jwt_token(request, additional_payload:dict, add_expire_time_seconds:int=0)-> tuple[bool, dict, int, str]: #success, token, status, err_msg
    """Função para criar um token jwt com as informações necessárias mais adicionais de cada aplicação

    Args:
        request: 
        additional_payload (dict): informações adicionais que serão armazenadas no payload do token e serão utilizadas na aplicação

    Returns:
        tuple[bool, dict, int, str]: Retorna se foi sucesso, o token, o status e a mensagem de erro
    """
    
    if request.app.ctx.sett['ENV'] == 'prod':
        TOKEN_SECRET = request.app.ctx.sett['SECURE']['JWT_SECRET']
        ALGOTIRTHMS = request.app.ctx.sett['SECURE']['JWT_INT']
    else:
        TOKEN_SECRET = 'example'
        ALGOTIRTHMS = "HS256"
    ISS = request.app.ctx.sett['application']
    TOKEN_EXPIRE = request.app.ctx.sett['GENERAL'][ISS]['TOKEN_EXPIRE']

    try:
        encoded_token = encode(
            payload={
            'iat': datetime.datetime.utcnow(),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=TOKEN_EXPIRE) + datetime.timedelta(seconds=add_expire_time_seconds),
            'iss': ISS,
            **additional_payload
        },
            key=TOKEN_SECRET,
            algorithm=ALGOTIRTHMS
        )

        return True, encoded_token, 200, None
        
    except Exception as e:
        if 'Signature has expired' in str(e):
            return (False, {"status" : "failed", "error":"token expirado"},401, e)
        elif "Not enough segments" in str(e):
            return (False, {"status" : "failed", "error":"jwt token inválido"}, 401, e)
        elif "Signature verification failed." in str(e):
            return (False, {"status" : "failed", "error":"jwt token inválido"}, 401, e)
        elif "Invalid header string: 'utf-8' codec can't decode byte" in str(e):
            return (False, {"status" : "failed", "error":"jwt token inválido"}, 401, e)
        elif "Invalid payload padding" in str(e):
            return (False, {"status" : "failed", "error":"jwt token inválido"}, 401, e)
        else:
            return (False, {"status" : "failed", "error" : 'erro interno de servidor, tente novamente mais tarde'}, 500, e)


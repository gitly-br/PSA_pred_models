from app.common.integrations.s3_bucket.s3_bucket_ops import process_file_to_upload, process_file_to_update, delete_file_on_bucket, read_file_on_bucket


async def upload_pdf_file( credentials: dict, file: bytes, filename: str, shopping_id: int) -> tuple[bool, str, bool, str]:
    """
    Funcao para fazer upload de um arquivo pdf para um bucket storage 

    Args:
        credentials (dict): Um dicionario com as credenciais para acessar o bucket storage 
            - bucket_name (str): nome do bucket
            - response_url (str): url de resposta (usada pelo cliente para acessar o recurso)
            - url_bucket (str): url to bucket
            - key_id (str): key id para acesar o bucket
            - secret_key (str): secret key para acessar o bucket
        file (bytes): O arquivo pdf em bytes
        filename (str): Nome do arquivo
        shopping_id (int): id do shopping, o arquivo esta relacionado

    Returns:
        tuple[bool, str, bool, str]: retorna uma tupla com 4 elementos:
            - success (bool): True se o upload foi bem sucedido, False caso contrario
            - url (str): url do arquivo no bucket
            - conn_error (bool): True se houve erro de conexao, False caso contrario
            - error_message (str): mensagem de erro
    """
    success, url, conn_error, error_message = await process_file_to_upload(
        shopping_id=shopping_id,
        filename=filename,
        file=file,
        bucket_name=credentials["bucket_name"],
        response_url=credentials["response_url"],
        content_type="application/pdf",
        url_bucket=credentials["url_bucket"],
        key_id=credentials["key_id"],
        secret_key=credentials["secret_key"]
    )
    if not success:  
        return False, "", True, error_message
    return True, url, False, ""

async def update_pdf_file( credentials: dict, file: bytes, bucket_file_url: str, shopping_id: int) -> tuple[bool, str, bool, str]:
    """
    funcao para atualizar um arquivo pdf no bucket storage

    Args:
        credentials (dict): Um dicionario com as credenciais para acessar o bucket storage
            - bucket_name (str): nome do bucket
            - response_url (str): url de resposta (usada pelo cliente para acessar o recurso)
            - url_bucket (str): url to bucket
            - key_id (str): key id para acesar o bucket
            - secret_key (str): secret key para acessar o bucket
        file (bytes): O arquivo pdf em bytes
        bucket_file_url (str): A url do arquivo no bucket
        shopping_id (int): O id do shopping, o arquivo esta relacionado

    Returns:
        tuple[bool, str, bool, str]: retorna uma tupla com 4 elementos:
            - success (bool): True se o upload foi bem sucedido, False caso contrario
            - url (str): url do arquivo no bucket
            - conn_error (bool): True se houve erro de conexao, False caso contrario
            - error_message (str): mensagem de erro
    """
    success, url, conn_error, error_message = await process_file_to_update( 
        shopping_id=shopping_id,
        bucket_file_url=bucket_file_url,
        file=file,
        content_type="application/pdf",
        bucket_name=credentials["bucket_name"],
        response_url=credentials["response_url"],
        url_bucket=credentials["url_bucket"],
        key_id=credentials["key_id"],
        secret_key=credentials["secret_key"]
    )
    if not success:  
        return False, "", True, error_message
    return True, url, False, ""

async def delete_pdf_file( credentials: dict, bucket_file_url: str, shopping_id: int) -> tuple[bool, str]:
    """
    Funcao para fazer upload de um arquivo pdf para um bucket storage 

    Args:
        credentials (dict): Um dicionario com as credenciais para acessar o bucket storage 
            - bucket_name (str): nome do bucket
            - response_url (str): url de resposta (usada pelo cliente para acessar o recurso)
            - url_bucket (str): url to bucket
            - key_id (str): key id para acesar o bucket
            - secret_key (str): secret key para acessar o bucket
        file (bytes): O arquivo pdf em bytes
        filename (str): Nome do arquivo
        shopping_id (int): id do shopping, o arquivo esta relacionado
        image_ratio (float): A ratio da imagem
    Returns:
        tuple[bool, str, bool, str]: retorna uma tupla com 4 elementos:
            - success (bool): True se o upload foi bem sucedido, False caso contrario
            - url (str): url do arquivo no bucket
            - conn_error (bool): True se houve erro de conexao, False caso contrario
            - error_message (str): mensagem de erro
    """
    success, message = await delete_file_on_bucket( 
        shopping_id=shopping_id,
        bucket_file_url=bucket_file_url,
        bucket_name=credentials["bucket_name"],
        url_bucket=credentials["url_bucket"],
        key_id=credentials["key_id"],
        secret_key=credentials["secret_key"]
    )
    
    if not success:  
        return False, message
    return True, message

async def read_pdf_file( credentials: dict, bucket_file_url: str, shopping_id: int) -> tuple[bool, str | dict]:
    """
    Le um arquivo pdf do bucket storage

    Args:
        credentials (dict): Um dicionario com as credenciais para acessar o bucket storage
        bucket_file_url (str): A url do arquivo no bucket
        shopping_id (int): O shopping id

    Returns:
        tuple[bool, str | dict]: retorna uma tupla com 2 elementos:
            - success (bool): True se o upload foi bem sucedido, False caso contrario
            - payload (str | dict): Uma mensagem de erro oui um dicionario contendo:
                - content_type (str): O tipo do arquivo
                - buffer (bytes): O arquivo em bytes (io.BytesIO)
        
    """
    success, payload, conn_error, erro_message = await read_file_on_bucket( 
        shopping_id=shopping_id,
        bucket_file_url=bucket_file_url,
        bucket_name=credentials["bucket_name"],
        url_bucket=credentials["url_bucket"],
        key_id=credentials["key_id"],
        secret_key=credentials["secret_key"]
    )
    
    if not success:  
        return success, erro_message
    
    if type(payload) != dict :
        return False, "PDF nao encontrado no bucket." 
    
    return success, payload

# -------------------------------------------- #

async def upload_image_file( credentials: dict, file: bytes, filename: str, shopping_id: int, image_ratio: float, content_type: str = "image/jpg"
"image/jpg") -> tuple[bool, str, bool, str]:
    """
    funcao para atualizar uma imagem no bucket storage

    Args:
        credentials (dict): Um dicionario com as credenciais para acessar o bucket storage
            - bucket_name (str): nome do bucket
            - response_url (str): url de resposta (usada pelo cliente para acessar o recurso)
            - url_bucket (str): url to bucket
            - key_id (str): key id para acesar o bucket
            - secret_key (str): secret key para acessar o bucket
        file (bytes): A imagem em bytes
        bucket_file_url (str): A url do arquivo no bucket
        shopping_id (int): O id do shopping, o arquivo esta relacionado
        image_ratio (float): A ratio da imagem
    Returns:
        tuple[bool, str, bool, str]: retorna uma tupla com 4 elementos:
            - success (bool): True se o upload foi bem sucedido, False caso contrario
            - url (str): url do arquivo no bucket
            - conn_error (bool): True se houve erro de conexao, False caso contrario
            - error_message (str): mensagem de erro
    """
    success, url, conn_error, error_message = await process_file_to_upload(
        shopping_id=shopping_id,
        filename=filename,
        file=file,
        bucket_name=credentials["bucket_name"],
        response_url=credentials["response_url"],
        content_type=content_type,
        url_bucket=credentials["url_bucket"],
        key_id=credentials["key_id"],
        secret_key=credentials["secret_key"],
        image_ratio=image_ratio
    )
    if not success:  
        return False, "", True, error_message
    return True, url, False, ""

async def update_image_file( credentials: dict, file: bytes, bucket_file_url: str, shopping_id: int,  image_ratio: float, content_type: str = "image/jpg"
"image/jpg") -> tuple[bool, str, bool, str]:
    success, url, conn_error, error_message = await process_file_to_update( 
        shopping_id=shopping_id,
        bucket_file_url=bucket_file_url,
        file=file,
        content_type=content_type,
        bucket_name=credentials["bucket_name"],
        response_url=credentials["response_url"],
        url_bucket=credentials["url_bucket"],
        key_id=credentials["key_id"],
        secret_key=credentials["secret_key"],
        image_ratio=image_ratio
    )
    if not success:  
        return False, "", True, error_message
    return True, url, False, ""

async def delete_image_file( credentials: dict, bucket_file_url: str, shopping_id: int) -> tuple[bool, str]:
    """
    Funcao para fazer upload de uma imagem para um bucket storage 

    Args:
        credentials (dict): Um dicionario com as credenciais para acessar o bucket storage 
            - bucket_name (str): nome do bucket
            - response_url (str): url de resposta (usada pelo cliente para acessar o recurso)
            - url_bucket (str): url to bucket
            - key_id (str): key id para acesar o bucket
            - secret_key (str): secret key para acessar o bucket
        file (bytes): A imagem em bytes
        filename (str): Nome do arquivo
        shopping_id (int): id do shopping, o arquivo esta relacionado
    Returns:
        tuple[bool, str, bool, str]: retorna uma tupla com 4 elementos:
            - success (bool): True se o upload foi bem sucedido, False caso contrario
            - url (str): url do arquivo no bucket
            - conn_error (bool): True se houve erro de conexao, False caso contrario
            - error_message (str): mensagem de erro
    """
    success, message = await delete_file_on_bucket( 
        shopping_id=shopping_id,
        bucket_file_url=bucket_file_url,
        bucket_name=credentials["bucket_name"],
        url_bucket=credentials["url_bucket"],
        key_id=credentials["key_id"],
        secret_key=credentials["secret_key"]
    )
    
    if not success:  
        return False, message
    
    return True, message

async def read_image_file( credentials: dict, bucket_file_url: str, shopping_id: int) -> tuple[bool, str | dict]:
    """
    Le uma imagem do bucket storage

    Args:
        credentials (dict): Um dicionario com as credenciais para acessar o bucket storage
        bucket_file_url (str): A URL do arquivo no bucket
        shopping_id (int): O shopping id

    Returns:
        tuple[bool, str | dict]: Retorna uma tupla com 2 elementos:
            - success (bool): True se o upload foi bem sucedido, False caso contrario
            - payload (str | dict): Uma mensagem de erro oui um dicionario contendo:
                - content_type (str): O tipo do arquivo
                - buffer (bytes): O arquivo em bytes (io.BytesIO)
    """
    success, payload, conn_error, erro_message = await read_file_on_bucket( 
        shopping_id=shopping_id,
        bucket_file_url=bucket_file_url,
        bucket_name=credentials["bucket_name"],
        url_bucket=credentials["url_bucket"],
        key_id=credentials["key_id"],
        secret_key=credentials["secret_key"]
    )
    
    if not success:  
        return success, erro_message
    
    if type(payload) != dict :
        return False, "Imagem nao encontrada no bucket." 
    
    return success, payload
from app.common.utils.image_process_and_covertion import resize_and_compress
import hashlib
import aioboto3
from PIL import Image
from io import BytesIO
import re
import unicodedata

async def hash_filename(filename: str) -> str:
    """
    Funçao para gerar um hash do nome do arquivo

    Args:
        filename (str): nome do arquivo que será gerado o hash

    Returns:
        str: nome do arquivo em hash
    """
    sanitased_filename = re.sub(r'[^a-zA-Z0-9]', '', unicodedata.normalize("NFKD", filename))
    return hashlib.md5(sanitased_filename.encode()).hexdigest()

async def process_image(image: bytes, content_type: str,ratio: float) -> tuple[bool, BytesIO, None | str]:
    """
    Processa a imagem, para enviar ao bucket

    Args:
        image (bytes): A imagem que será processada
        content_type (str): o content type da imagem (ex: "image/jpeg", "image/png", "image/webp", etc)
        ratio (float): a proporção da imagem (width/height) que deve ser respeitada

    Raises:
        Exception: caso a imagem não tenha a proporção correta

    Returns:
        status: um booleano indicando se houve sucesso
        BytesIO: retorna a imagem processada (redimensionada e comprimida) em um objeto buffer
    """
    image_buffer = BytesIO(image)

    # Agora podemos usar PIL (ou Pillow) para abrir a imagem diretamente do BytesIO
    image = Image.open(image_buffer)
    # check the size ratio w/ h with a tolerance of 5% of this ratio
    w, h = image.size
    
    if abs((ratio - (w / h)) / ratio) > 0.05 and ratio != -1:
        return False, None, f"[process_image] A imagem não tem a proporção correta (widht/heigh): {ratio}"
    if  "webp" not in content_type:
        status, image, error_msg = await resize_and_compress(image, 1920, 1080, True, True)
        if not status:
            return status, image, error_msg
            
    return True, image, None

async def process_file_to_upload(shopping_id: int, filename: str, file: bytes, bucket_name: str, 
                                 response_url: str, content_type: str, url_bucket: str, key_id: str, secret_key: str,
                                 image_ratio: float = 1.0) -> tuple[bool, str, bool, str]:
    """
    Processa um arquivo para ser enviado ao bucket

    Args:
        shopping_id (int): O id do shopping
        filename (str): O nome do arquivo
        file (bytes): O arquivo em bytes
        bucket_name (str): O nome do bucket
        response_url (str): A URL de resposta (usada pelo cliente para acessar o recurso)
        content_type (str): O tipo de conteúdo do arquivo (ex: "image/jpeg", "application/pdf", etc)
        url_bucket (str): A url do bucket storage
        key_id (str): A chave de acesso ao bucket
        secret_key (str): A chave secreta de acesso ao bucket
        image_ratio (float, optional): O ration da imagem que será processada (opcional). Defaults to 1.0.

    Returns:
        tuple[bool, str, bool, str]: retorna uma tupla com 4 valores:
            - o primeiro valor é um booleano indicando se houve sucesso,
            - o segundo é a URL do arquivo
            - o terceiro é um booleano indicando se houve erro de conexão
            - o quarto é uma string com a mensagem de erro caso ocorra.
        
    """
    new_filename = filename.split('.')[0]
    extension = filename.split('.')[-1]

    # Try to connect to the bucket using aioboto3
    try:
        async with aioboto3.session.Session().client(
            's3',
            region_name='auto',
            endpoint_url=url_bucket,
            aws_access_key_id=key_id,
            aws_secret_access_key=secret_key
        ) as client:
            if "image" in content_type.lower():
                status_img, file, error_msg = await process_image(image=file, content_type=content_type, ratio=image_ratio)
                extension = 'webp'
                if not status_img:
                    return False, "", True, f"[process_file_to_upload] Error ao processar a imagem {error_msg}"
            
            resp = await client.put_object(
                Bucket=bucket_name,
                Key=f'{shopping_id}_{new_filename}.{extension}',
                Body=file,
                ContentType=content_type
            )
            
            if resp['ResponseMetadata']['HTTPStatusCode'] == 200:
                final_name = f'{response_url}/{shopping_id}_{new_filename}.{extension}'
                return True, final_name, False, ""
            else:
                return False, "", True, str(resp['ResponseMetadata']['HTTPStatusCode'])
                
    except Exception as e:
        return False, "", True, f'Error in uploading file to bucket: {str(e)}'

async def process_file_to_update(shopping_id: int, bucket_file_url: str, file: bytes, bucket_name: str, 
                                 response_url: str, content_type: str, url_bucket: str, key_id: str, 
                                 secret_key: str, image_ratio: float = 1.0) -> tuple[bool, str, bool, str]:
    """
    Funcao para processar um arquivo para ser atualizado no bucket

    Args:
        shopping_id (int): O id do shopping
        bucket_file_url (str): A URL do arquivo no bucket
        file (bytes): O arquivo em bytes
        bucket_name (str): O nome do bucket
        response_url (str): A URL de resposta (usada pelo cliente para acessar o recurso)
        content_type (str): O tipo de conteúdo do arquivo (ex: "image/jpeg", "application/pdf", etc)
        url_bucket (str): A url do bucket storage
        key_id (str): A chave de acesso ao bucket
        secret_key (str): A chave secreta de acesso ao bucket
        image_ratio (float, optional): O ratioda imagem que será processada (opcional). Defaults to 1.0.
    Returns:
        tuple[bool, str, bool, str]: retorna uma tupla com 4 valores:
            - o primeiro valor é um booleano indicando se houve sucesso,
            - o segundo é a URL do arquivo
            - o terceiro é um booleano indicando se houve erro de conexão
            - o quarto é uma string com a mensagem de erro caso ocorra.
    """
    new_filename = bucket_file_url.split('/')[-1].split('.')[0]
    extension = bucket_file_url.split('/')[-1].split('.')[1]
    status, _ = await delete_file_on_bucket(shopping_id, bucket_file_url, bucket_name, url_bucket, key_id, secret_key)
    if not status:
        return False, "", True, "[process_file_to_update] Error while trying to overwrite the file"

    if "image" in content_type.lower():
        status_img, file, error_msg = await process_image(image=file, content_type=content_type, ratio=image_ratio)
        extension = 'webp'
        if not status_img:
            return False, "", True, f"[process_file_to_upload] Error ao processar a imagem {error_msg}"

    try:
        async with aioboto3.session.Session().client('s3', region_name='auto', endpoint_url=url_bucket,
                                   aws_access_key_id=key_id, aws_secret_access_key=secret_key) as client:
            resp = await client.put_object(Bucket=bucket_name, Key=f'{shopping_id}_{new_filename}.{extension}', 
                                           Body=file, ContentType=content_type)

            if resp['ResponseMetadata']['HTTPStatusCode'] == 200:
                final_name = f'{response_url}/{shopping_id}_{new_filename}.{extension}'
                return True, final_name, False, ""
            else:
                return False, "", True, str(resp['ResponseMetadata']['HTTPStatusCode'])
    except Exception as e:
        return False, "", True, f'[process_file_to_update] Error uploading file {new_filename} to bucket: {e}'

async def delete_file_on_bucket(shopping_id: int, bucket_file_url: str, bucket_name: str, url_bucket: str, 
                            key_id: str, secret_key: str) -> tuple[bool, str]:
    """
    Deleta um arquivo do bucket

    Args:
        shopping_id (int): O id do shopping
        bucket_file_url (str): A url do arquivo no bucket
        bucket_name (str): O nome do bucket
        url_bucket (str): A url do bucket storage
        key_id (str): A chave de acesso ao bucket
        secret_key (str): A chave secreta de acesso ao bucket

    Returns:
        tuple[bool, str]: retorna uma tupla com 2 valores:
            - o primeiro valor é um booleano indicando se houve sucesso,
            - o segundo é uma string com a mensagem de erro caso ocorra.
    """
    new_filename = bucket_file_url.split('/')[-1].split('.')[0]
    extension = bucket_file_url.split('/')[-1].split('.')[1]
    try:
        async with aioboto3.session.Session().client('s3', region_name='auto', endpoint_url=url_bucket,
                                   aws_access_key_id=key_id, aws_secret_access_key=secret_key) as client:
            resp = await client.delete_object(Bucket=bucket_name, Key=f'{shopping_id}_{new_filename}.{extension}')
            if resp['ResponseMetadata']['HTTPStatusCode'] == 200:
                return True, 'Deleted'
            elif (resp['ResponseMetadata']['HTTPStatusCode'] == 204):
                return True, 'Not found'
            else:
                return False, f'[delete_file_on_bucket] Error deleting file from bucket, status_code: {resp["ResponseMetadata"]["HTTPStatusCode"]}'
    except Exception as e:
        return False, f'[delete_file_on_bucket] Error deleting file from bucket: {e}'

async def read_file_on_bucket(shopping_id: int, bucket_file_url: str, bucket_name: str, url_bucket: str, 
                            key_id: str, secret_key: str) -> tuple[bool, str, bool, str]:
    new_filename = bucket_file_url.split('/')[-1].split('.')[0]
    extension = bucket_file_url.split('/')[-1].split('.')[1]
    try:
        async with aioboto3.session.Session().client('s3', region_name='auto', endpoint_url=url_bucket,
                                   aws_access_key_id=key_id, aws_secret_access_key=secret_key) as client:
            resp = await client.get_object(Bucket=bucket_name, Key=f'{shopping_id}_{new_filename}.{extension}')
            buffer = BytesIO(await resp['Body'].read())
            
            if resp['ResponseMetadata']['HTTPStatusCode'] == 200:
                return True, {"buffer": buffer, "content_type": resp["Body"].content_type }, False, ""
            elif (resp['ResponseMetadata']['HTTPStatusCode'] == 204):
                return True, 'Not found', False, ""
            else:
                return False, "", True, f'[read_file_on_bucket] Error reading file from bucket: {e}'
            
    except Exception as e:
        return False, "", True, f'[read_file_on_bucket] Error reading file from bucket: {e}'

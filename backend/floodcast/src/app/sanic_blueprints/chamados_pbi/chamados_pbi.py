import base64
from PIL import Image
from sanic import Blueprint, response
from minio import Minio
from botocore.config import Config
import pandas as pd
import io

# Create a new Sanic blueprint
chamados_pbi_bp = Blueprint('chamados_pbi', url_prefix='/chamados_pbi')

@chamados_pbi_bp.get('/get_csv')
async def get_csv(request):

    auth_header = request.headers.get('Authorization')
    if auth_header is None or not auth_header.startswith('Basic '):
        return response.json({'error': 'Authorization header is missing or invalid'}, status=401)
    
    try:
        auth_decoded = base64.b64decode(auth_header.split(' ')[1]).decode('utf-8')
        username, password = auth_decoded.split(':', 1)
    except Exception:
        return response.json({'error': 'Invalid Authorization header format'}, status=401)
    
    if username != 'chamados_psa' or password != 'n0d817g2b307vd&@asdfGJV':
        return response.json({'error': 'Invalid username or password'}, status=401)

    # Define the S3 bucket and file key
    endpoint_minio = request.app.ctx.sett['MINIO_STORAGE']['URL_BASE']
    port_minio = request.app.ctx.sett['MINIO_STORAGE']['PORTS'][1]
    access_key = request.app.ctx.sett['MINIO_STORAGE']['CREDENTIALS']['KEY_ID']
    secret_key = request.app.ctx.sett['MINIO_STORAGE']['CREDENTIALS']['SECRET_KEY']

    # AWS S3 configuration
    S3_BUCKET_NAME = request.app.ctx.sett['MINIO_STORAGE']['CREDENTIALS']['BUCKET_NAME']
    S3_FILE_KEY = 'Ocorrencias.csv'

    try:
        # Initialize S3 client
        s3_client = Minio(
            f"{endpoint_minio}:{port_minio}",
            secure=False,
            access_key=access_key,
            secret_key=secret_key,
        )
        
        # Get the CSV file from S3
        s3_object = s3_client.get_object(S3_BUCKET_NAME, S3_FILE_KEY)
        csv_content = s3_object.read()

        df = pd.read_csv(io.BytesIO(csv_content), encoding="utf-8", sep=',', header=0)

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, 
                  sep=',', 
                  index=False)
        
        csv_data = csv_buffer.getvalue()
        
        headers = {
            "Content-Disposition": "attachment; filename=meusdados.csv"
        }
        
        # Retorna o CSV como resposta HTTP, com content_type 'text/csv'
        return response.HTTPResponse(csv_data, headers=headers, content_type="text/csv")

    except Exception as e:
        print(e, flush=True)
        return response.json({'error': str(e)}, status=500)
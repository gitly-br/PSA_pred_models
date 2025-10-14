from io import BytesIO
from PIL import Image

async def resize_and_compress(image_, max_width:int, max_height:int,
                        convert_to_webp:bool, resize_:bool)->tuple[bool, BytesIO, str]:
    """
    Redimensiona e comprime uma imagem, e retorna um buffer com a imagem

    Args:
        image_ (buffer): Imagem que será redimensionada e comprimida em um buffer
        max_width (int): Width máximo da imagem
        max_height (int): Height máximo da imagem
        convert_to_webp (bool): Flag para converter a imagem para webp
        resize_ (bool): Flag para redimensionar a imagem (caso seja maior que o maximo)

    Returns:
        tuple[bool, BytesIO, str]: 
         - o primeiro valor é um booleano indicando se houve sucesso,
         - o segundo é um buffer com a imagem.
         - terceiro é uma string com a mensagem de erro caso ocora.
    """
    # Verifica se é BytesIO, bytes ou str (path)
    if isinstance(image_, BytesIO):
        img = Image.open(image_)
    elif isinstance(image_, bytes):
        img = Image.open(BytesIO(image_))
    elif isinstance(image_, str):
        img = Image.open(image_)
    elif isinstance(image_, Image.Image):
        img = image_
    else:
        return False, None, "Tipo de imagem não suportado"
    img = image_
    # verifica se é para redimensionar, e só será redimensionado se a imagem for maior que o maximo
    if resize_:
        aspect_ratio = img.width / img.height
        if aspect_ratio >= 1: # width maior que height
            if img.width > max_width:
                new_width = max_width
                new_height = int(new_width / aspect_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else: # height maior que width
            if img.height > max_height:
                new_height = max_height
                new_width = int(new_height * aspect_ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # verificar se é para converter para webp, após salvar a imagem em webp em um buffer
    buffer = BytesIO()
    if convert_to_webp:
        img.save(buffer, format="WEBP", quality=75)
    else:
        if img.format == "JPEG":
            img.save(buffer, format="JPEG", quality=75)
        elif img.format == "PNG":
            img.save(buffer, format="PNG", compress_level=8)
        else:
            img.save(buffer, format="WEBP", quality=75) # default é converter

    buffer.seek(0)
    return True, buffer, None
import re



def euclidean_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the square of the Euclidean distance between two points in 2D space.
    """
    # Convert to Cartesian coordinates
    x1, y1 = lat1, lon1
    x2, y2 = lat2, lon2

    # Euclidean distance squared
    dist_sq = (x2 - x1)**2 + (y2 - y1)**2
    return dist_sq

def closest_point(user_lat, user_long, lat_long_list):
    """
    Returns the index of the closest point by Euclidean distance.
    """
    distances_sq = [euclidean_distance(user_lat, user_long, lat, lon) for lat, lon in lat_long_list]
    return distances_sq.index(min(distances_sq))

# # Lista de latitudes e longitudes
# lat_long_list = [(-23.6162237, -46.5686979), (-22.9035, -43.2096), (-15.7942, -47.8822)]

# # Coordenadas do usuário
# user_lat = -23.5505
# user_long = -46.6333

# # Obtendo o índice do ponto mais próximo
# closest_index = closest_point(user_lat, user_long, lat_long_list)
# print(f"O índice do ponto mais próximo é: {closest_index}")


# TODO:Tranformar isso em algo configuravel via base
def extract_country_and_language(whatsapp_id_twilio_format):
    # Dicionário com os códigos telefônicos, códigos de países e línguas
    country_codes = {
        "1": ("us", "en-us", "en"),      # EUA
        "55": ("br", "pt-br", "pt"),    # Brasil
        "52": ("mx", "es-mx", "es"),    # México
        "54": ("ar", "es-ar", "es"),    # Argentina
        "57": ("co", "es-co", "es"),    # Colômbia
        "56": ("cl", "es-cl", "es"),    # Chile
        "58": ("ve", "es-ve", "es"),    # Venezuela
        "51": ("pe", "es-pe", "es"),    # Peru
        "44": ("gb", "en-gb", "en"),    # Reino Unido
        "49": ("de", "de-de", "de"),    # Alemanha
        "33": ("fr", "fr-fr", "fr"),    # França
        "81": ("jp", "ja-jp", "ja"),    # Japão
        "82": ("kr", "ko-kr", "ko"),    # Coreia do Sul
        "86": ("cn", "zh-cn", "zh"),    # China
        "7": ("ru", "ru-ru", "ru"),     # Rússia
        "34": ("es", "es-es", "es"),    # Espanha
        "91": ("in", "hi-in", "hi"),    # Índia
        "46": ("se", "sv-se", "sv"),    # Suécia
        "2": ("ca", "en-ca", "en"),     # Canadá
        "61": ("au", "en-au", "en"),    # Austrália
        "39": ("it", "it-it", "it"),    # Itália
        "31": ("nl", "nl-nl", "nl"),    # Países Baixos (Holanda)
        "47": ("no", "nb-no", "nb"),    # Noruega
        "36": ("hu", "hu-hu", "hu"),    # Hungria
        "48": ("pl", "pl-pl", "pl"),    # Polônia
        "90": ("tr", "tr-tr", "tr"),    # Turquia
        "27": ("za", "en-za", "en"),    # África do Sul
        "64": ("nz", "en-nz", "en")     # Nova Zelândia
    }


    # Usando expressão regular para extrair o código do país
    match = re.search(r"\+([0-9]{1,2})", whatsapp_id_twilio_format)
    if not match:
        return country_codes["1"] # retorna o padrão EUA

    country_code = match.group(1)
    country_data = country_codes.get(country_code, (None, None, None))

    return country_data


def extract_ddd_from_brazilian_number(phone_number):
    # Primeiro, vamos remover qualquer caractere que não seja um número
    numbers_only = re.sub(r"[^\d]", "", phone_number)

    # Para telefones brasileiros, após o código do país (55),
    # os próximos dois dígitos representam o DDD.
    match = re.match(r"55(\d{2})", numbers_only)

    if match:
        return match.group(1)  # Retorna o DDD encontrado
    else:
        return 0  # Retorna 0 se não encontrar um padrão de DDD válido
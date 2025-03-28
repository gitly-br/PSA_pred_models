import asyncio
from datetime import datetime
import pandas as pd
from sanic.log import logger

from app.utils.aggregator import create_agg_dict

async def get_openweather_api_data(app, route, params=None):
        
    while True:
        
        token = app.ctx.sett['API_KEYS']['openweather']

        res_forecast = await app.ctx.httpx_client.get(f'http://api.openweathermap.org/data/2.5/forecast?lat=-23.667548&lon=-46.528934&appid={token}&units=metric')

        datas = res_forecast.json()

        datas['dt_request'] = datetime.now()

        # Inserir registro em mongo

        await app.ctx.mongo_obj.write_one(db_name='api_data',
            col='openweather_col',
            doc=datas)
        
        
        await asyncio.sleep(3600*1.45)

async def get_rain_distribution(df, dt_request, feature="rain_3h"):
    if feature == "rain_3h":
        rain_total = df.iloc[1:9].copy()[feature].sum()
        if rain_total == 0:
            return [0, 0, 0, 0]
        rain_night = (df.iloc[1:3].copy()[feature].sum()/rain_total)*100
        rain_morning = (df.iloc[3:5].copy()[feature].sum()/rain_total)*100
        rain_afternoon = (df.iloc[5:7].copy()[feature].sum()/rain_total)*100
        rain_evening = (df.iloc[7:9].copy()[feature].sum()/rain_total)*100
        #logger.info(f"\x1b[31mDT: {df.iloc[1:9].dt.value_counts()}\x1b[0m")
        #logger.info(f"\x1b[31mRAIN MORNING: {rain_morning}%\x1b[0m")
        #logger.info(f"\x1b[31mRAIN AFTERNOON: {rain_afternoon}%\x1b[0m")
        #logger.info(f"\x1b[31mRAIN EVENING: {rain_evening}%\x1b[0m")
        #logger.info(f"\x1b[31mRAIN TOTAL: {rain_total}\x1b[0m")
        return rain_night, rain_morning, rain_afternoon, rain_evening

async def get_OW_mongo_data_and_agg(request, agg_config, dt_request=None):

    flag_dump = False

    if dt_request is None or dt_request > datetime(2024,11,24):
        success, conn_prob, openw_data, err_msg = await request.app.ctx.mongo_obj.read_all(
            db_name='api_data',
            col='openweather_col',
            sort=[('dt_request', -1)],
            filter_={'dt_request' : {'$lte' : dt_request if dt_request is not None else datetime.now()}}
        )

        step=3

        data = openw_data[0]['list']

        flattened_data = []
        for entry in data:
            flat_entry = {
                "dt": datetime.fromtimestamp(entry.get("dt")),
                "temp": entry["main"].get("temp"),
                "feels_like": entry["main"].get("feels_like"),
                "temp_min": entry["main"].get("temp_min"),
                "temp_max": entry["main"].get("temp_max"),
                "pressure": entry["main"].get("pressure"),
                "sea_level": entry["main"].get("sea_level"),
                "grnd_level": entry["main"].get("grnd_level"),
                "humidity": entry["main"].get("humidity"),
                "temp_kf": entry["main"].get("temp_kf"),
                "weather_id": entry["weather"][0].get("id") if entry.get("weather") else None,
                "weather_main": entry["weather"][0].get("main") if entry.get("weather") else None,
                "weather_description": entry["weather"][0].get("description") if entry.get("weather") else None,
                "weather_icon": entry["weather"][0].get("icon") if entry.get("weather") else None,
                "clouds_all": entry["clouds"].get("all"),
                "wind_speed": entry["wind"].get("speed"),
                "wind_deg": entry["wind"].get("deg"),
                "wind_gust": entry["wind"].get("gust"),
                "visibility": entry.get("visibility"),
                "pop": entry.get("pop"),
                "rain_3h": entry["rain"].get("3h", 0) if "rain" in entry else 0,
                "sys_pod": entry["sys"].get("pod"),
                "dt_txt": datetime.fromisoformat(entry.get("dt_txt"))
            }
            flattened_data.append(flat_entry)

    else:
        success, conn_prob, openw_data, err_msg = await request.app.ctx.mongo_obj.read_all(db_name='api_data', col='openweather_dump_col', filter_={'dt_request' : {"$lte" : dt_request}},sort=[('dt_request', -1)])

        step=1

        flattened_data = openw_data[0]['list']
        flag_dump = True

    # Criar o DataFrame
    df = pd.DataFrame(flattened_data)

    # Verificar se tem chuva
    if not flag_dump:
        if not (500 in df['weather_id'].values or 501 in df['weather_id'].values or 502 in df['weather_id'].values or 503 in df['weather_id'].values or 504 in df['weather_id'].values or 521 in df['weather_id'].values or 522 in df['weather_id'].values or 312 in df['weather_id'].values or 314 in df['weather_id'].values or 201 in df['weather_id'].values or 202 in df['weather_id'].values or 232 in df['weather_id'].values):
            return False, None
        
    # if flag_dump:
    #     if df['accumulated'].max() < 0.1:
    #         return False, None


    agg_config_final = {}
    for i, j in agg_config.items():
        agg_config_final[i] = (j['time'], tuple(j['aggs']))

    rain_distribution = await get_rain_distribution(df, dt_request=dt_request)
    
    df_agg = df.groupby(pd.Grouper(key='dt', freq='D')).agg(
                                                  **create_agg_dict(agg_config_final, step=step)
                                                  ).reset_index()
    return True, flag_dump, df_agg, rain_distribution

def traduzir(value):
    en_br_weather={
        'light rain' : 'Chuva leve',
        'moderate rain' : 'Chuva moderada',
        'heavy rain' : 'Chuva forte',
        'clear sky': 'Céu limpo',
        'few clouds': 'Poucas nuvens',
        'scattered clouds': 'Nuvens dispersas',
        'broken clouds': 'Nuvens quebradas',
        'overcast clouds': 'Nuvens nubladas',
        'thunderstorm': 'Trovoada',
        'mist': 'Névoa',
        'snow': 'Neve'
    }

    return en_br_weather.get(value, value)


async def get_OW_mongo_data_for_dash(request, dt_request):

    if dt_request is None or dt_request > datetime(2024,11,24):
        success, conn_prob, openw_data, err_msg = await request.app.ctx.mongo_obj.read_all(
            db_name='api_data',
            col='openweather_col',
            sort=[('dt_request', -1)],
            filter_={'dt_request' : {'$lte' : dt_request if dt_request is not None else datetime.now()}}
        )

        data = openw_data[0]['list']

        flattened_data = []
        for entry in data:
            flat_entry = {
                "dt": datetime.fromtimestamp(entry.get("dt"))-timedelta(hours=3),
                "temp": entry["main"].get("temp"),
                "feels_like": entry["main"].get("feels_like"),
                "temp_min": entry["main"].get("temp_min"),
                "temp_max": entry["main"].get("temp_max"),
                "pressure": entry["main"].get("pressure"),
                "sea_level": entry["main"].get("sea_level"),
                "grnd_level": entry["main"].get("grnd_level"),
                "humidity": entry["main"].get("humidity"),
                "temp_kf": entry["main"].get("temp_kf"),
                "weather_id": entry["weather"][0].get("id") if entry.get("weather") else None,
                "weather_main": entry["weather"][0].get("main") if entry.get("weather") else None,
                "weather_description": entry["weather"][0].get("description") if entry.get("weather") else None,
                "weather_icon": entry["weather"][0].get("icon") if entry.get("weather") else None,
                "clouds_all": entry["clouds"].get("all"),
                "wind_speed": entry["wind"].get("speed"),
                "wind_deg": entry["wind"].get("deg"),
                "wind_gust": entry["wind"].get("gust"),
                "visibility": entry.get("visibility"),
                "pop": entry.get("pop"),
                "rain_3h": entry["rain"].get("3h", 0) if "rain" in entry else 0,
                "sys_pod": entry["sys"].get("pod"),
                "dt_txt": datetime.fromisoformat(entry.get("dt_txt"))
            }
            flattened_data.append(flat_entry)

    else:
        success, conn_prob, openw_data, err_msg = await request.app.ctx.mongo_obj.read_all(db_name='api_data', col='openweather_dump_col', filter_={'dt_request' : {"$lte" : dt_request}},sort=[('dt_request', -1)])


        flattened_data = openw_data[0]['list']

    # Criar o DataFrame
    df = pd.DataFrame(flattened_data)

    # Criando um novo eixo X com df/hora e descrição do clima
    df["dt_label"] = df["dt"].dt.strftime("%d/%m/%Y - %H:%M") + "<br>" + df["weather_description"].apply(str.lower).apply(traduzir) + "<br>" + df["wind_speed"].astype(str) + " m/s"

    df["pop_percent"] = df["pop"] * 100

    return df.to_dict(orient='records')



import asyncio
from datetime import datetime
import pandas as pd

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


async def get_OW_mongo_data_and_agg(request, agg_config):


    success, conn_prob, openw_data, err_msg = await request.app.ctx.mongo_obj.read_all(db_name='api_data', col='openweather_col', sort=[('dt_request', -1)])

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

    # Criar o DataFrame
    df = pd.DataFrame(flattened_data)
    agg_config_final = {}
    for i, j in agg_config.items():
        agg_config_final[i] = (j['time'], tuple(j['aggs']))
    
    df_agg = df.groupby(pd.Grouper(key='dt', freq='D')).agg(
                                                  **create_agg_dict(agg_config_final)
                                                  ).reset_index()

    print(df_agg)
from datetime import datetime
from app.utils.openweather import get_OW_mongo_data_and_agg
import joblib
import pandas as pd

async def inferencia_previsao(request, modelo:str, regiao: str, dt_request=None):

    # Pega dados do modelo

    success, conn_error, region_models, err_msg = await request.app.ctx.mongo_obj.read_one(
        db_name='models_db',
        col='models_col',
        filter_={'region_name' : regiao.upper()}
        )
    
    model_infos = {}

    for model, agg_info in region_models.get('models',{}).items():
        if model == modelo:
            model_infos[model] = agg_info
            break

    list_data = []

    
    models_agg = model_infos[modelo].get("source",[])
    for data_source, agg_info in models_agg.items():
        if agg_info != {}:
            list_data.append(await get_OW_mongo_data_and_agg(request, agg_info, datetime.fromisoformat(dt_request) if dt_request is not None else None))


    #Fazer inferencia e salvar em mongo
    # Load the model

    if list_data[0][0] == False:
        return  False, {'status' : 0, 'proba' : None, 'predict' : None, 'score' : None,'region' : regiao, 'lat' : model_infos[modelo].get('region_coord', [-23.699012, -46.4537949])[0], 'lon': model_infos[modelo].get('region_coord', [-23.699012, -46.4537949])[1], 'circle_rad' : 0, 'model' : modelo, 'obj_version':'1.0', 'dt_inference' : datetime.now()}	

    loaded_model = joblib.load(f'/source/app/utils/{modelo}.joblib')
    
    day_row = list_data[0][2].iloc[[1]]
        
    # Convert the row to a NumPy array
    input_data = day_row.drop(columns=['dt']).values

    # Make a prediction
    prediction = loaded_model.predict(input_data)
    proba = loaded_model.predict_proba(input_data)
    
    result = {'status' : 1,'proba' : proba[0][1], 'predict' : int(prediction[0]), 'score' : 0.25, 'region' : regiao, 'lat' : model_infos[modelo].get('region_coord', [-23.699012, -46.4537949])[0], 'lon': model_infos[modelo].get('region_coord', [-23.699012, -46.4537949])[1], 'circle_rad' : model_infos[modelo].get('circle_rad', 100), 'model' : modelo, 'obj_version':'1.0', 'dt_inference' : datetime.now()}	


    success, conn_error, err_msg = await request.app.ctx.mongo_obj.write_one(
        db_name='models_db',
        col='inference_col',
        doc=result
    )

    return True, result

async def inferencia_previsao_2(request, modelo:str, regiao: str, dt_request=None):

    # Pega dados do modelo

    success, conn_error, region_models, err_msg = await request.app.ctx.mongo_obj.read_one(
        db_name='models_db',
        col='models_col',
        filter_={'region_name' : regiao.upper()}
        )
    
    model_infos = {}

    list_data = []

    for model, agg_info in region_models.get('models',{}).items():

        model_infos[model] = agg_info
        models_agg = model_infos[model].get("source",[])
        

        for data_source, agg_info in models_agg.items():
            if agg_info != {}:
                weather_data = await get_OW_mongo_data_and_agg(
                                            request,
                                            agg_info,
                                            datetime.fromisoformat(dt_request) if dt_request is not None else None
                                        )
                
                list_data.append(weather_data)

        # Fazer inferencia e salvar em mongo
        # Load the model

        resp_list = []

        for weather_data in list_data:

            if weather_data[0] == False:
                resp_list.append({'status' : 0, 'proba' : None, 'predict' : None, 'score' : None,'region' : regiao, 'lat' : model_infos[model].get('region_coord', [-23.699012, -46.4537949])[0], 'lon': model_infos[model].get('region_coord', [-23.699012, -46.4537949])[1], 'circle_rad' : 0, 'model' : model, 'obj_version':'1.0', 'dt_inference' : datetime.now()})

            loaded_model = joblib.load(f'/source/app/utils/{model}.joblib')
            
            day_row = weather_data[2].iloc[[1]]
                
            # Convert the row to a NumPy array
            input_data = day_row.drop(columns=['dt']).values

            # Make a prediction
            prediction = loaded_model.predict(input_data)
            proba = loaded_model.predict_proba(input_data)
            
            result = {'status' : 1,'proba' : proba[0][1], 'predict' : int(prediction[0]), 'score' : 0.25, 'region' : regiao, 'lat' : model_infos[model].get('region_coord', [-23.699012, -46.4537949])[0], 'lon': model_infos[model].get('region_coord', [-23.699012, -46.4537949])[1], 'circle_rad' : model_infos[model].get('circle_rad', 100), 'model' : model, 'obj_version':'1.0', 'dt_inference' : datetime.now()}	


            success, conn_error, err_msg = await request.app.ctx.mongo_obj.write_one(
                db_name='models_db',
                col='inference_col',
                doc=result
            )

            resp_list.append({'modelo' : modelo, 'result' : result})

    return True, resp_list
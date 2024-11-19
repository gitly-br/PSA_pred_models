from datetime import datetime
from app.utils.openweather import get_OW_mongo_data_and_agg

async def inferencia_previsao(request, modelo, regiao: str):

    # Pega dados do modelo

    success, conn_error, region_models, err_msg = await request.app.ctx.mongo_obj.read_one(
        db_name='models_db',
        col='models_col',
        filter_={'region_name' : regiao.upper()}
        )
    
    model_infos = {}

    for model, agg_info in region_models.get('models',[]).items():
        if model == modelo:
            model_infos[model] = agg_info
            break

    list_data = []

    
    models_agg = model_infos[modelo]
    for data_source, agg_info in models_agg.items():

        if agg_info != {}:
            list_data.append(await get_OW_mongo_data_and_agg(request, agg_info))


    #Fazer inferencia e salvar em mongo

    result = {'proba' : None, 'predict' : 1, 'score' : 0.5, 'region' : regiao, 'model' : modelo, 'obj_version':'1.0', 'dt_inference' : datetime.now()}	

    success, conn_error, err_msg = await request.app.ctx.mongo_obj.write_one(
        db_name='models_db',
        col='inference_col',
        doc=result
    )

    return result
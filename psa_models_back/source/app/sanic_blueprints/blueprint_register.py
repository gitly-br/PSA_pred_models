# Este arquivo é responsável por registrar os blueprints da aplicação.
#
# O arquivo app.py chama a função register_app_blueprints(app) que registra os blueprints da aplicação.
# Importacao dos blueprints
# from app.sanic_blueprints.cadastro_x.arquivo_x import cadastro_x 
# from app.sanic_blueprints.pasta_XPTO.arquivo_XPTO import feature_XPTO
from sanic import Blueprint

from app.sanic_blueprints.modelo_1.modelo_1 import bp_modelo_1
from app.sanic_blueprints.modelo_2.modelo_2 import bp_modelo_2
from app.sanic_blueprints.modelo_3.modelo_3 import bp_modelo_3
from app.sanic_blueprints.modelo_4.modelo_4 import bp_modelo_4
from app.sanic_blueprints.modelo_5.modelo_5 import bp_modelo_5
from app.sanic_blueprints.get_dates.get_dates import bp_get_dates

route_dict ={
    "modelo_1":{
        "mock": bp_modelo_1,
        "implemented": bp_modelo_1
    }
}


def register_app_blueprints(app, settings: dict):
    for route in settings["SANIC_INIT"]["IS_MOCK_SERVER"]:
        if settings["SANIC_INIT"]["IS_MOCK_SERVER"][route]:
            app.blueprint(route_dict[route]["mock"])
        else:
            app.blueprint(route_dict[route]["implemented"])
            
    
    app.blueprint(bp_modelo_2)
    app.blueprint(bp_modelo_3)
    app.blueprint(bp_modelo_4)
    app.blueprint(bp_modelo_5)
    app.blueprint(bp_get_dates)
    # app.blueprint(feature_XPTO)

# Este arquivo é responsável por registrar os blueprints da aplicação.
#
# O arquivo app.py chama a função register_app_blueprints(app) que registra os blueprints da aplicação.
# Importacao dos blueprints
# from app.sanic_blueprints.cadastro_x.arquivo_x import cadastro_x
# from app.sanic_blueprints.pasta_XPTO.arquivo_XPTO import feature_XPTO
from sanic import Blueprint

from app.sanic_blueprints.get_dates.get_dates import bp_get_dates
from app.sanic_blueprints.home.home import bp_home
from app.sanic_blueprints.forecast.forecast import bp_forecast
from app.sanic_blueprints.chamados_pbi.chamados_pbi import chamados_pbi_bp
from app.sanic_blueprints.region.region import bp_region


def register_app_blueprints(app, settings: dict):
    app.blueprint(bp_get_dates)
    app.blueprint(bp_home)
    app.blueprint(bp_forecast)
    app.blueprint(chamados_pbi_bp)
    app.blueprint(bp_region)
    # app.blueprint(feature_XPTO)

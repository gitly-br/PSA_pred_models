import streamlit as st
from datetime import date, datetime, timedelta
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from pages.home.utils import week_day_portuguese
import logging
from app import get_forecast

logging.basicConfig(level=logging.INFO)

REGION_DICT = {
        "all": "todo o município",
        "tamanduatei": "bacia do tamanduateí",
        "guarara": "sub-bacia do guarará",
        "meninos": "bacia dos meninos",
        "oratorio": "bacia do oratório"
}

st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")

# Remove espaço em branco no topo
st.markdown("""
    <style>
    header.stAppHeader {
        background-color: transparent;
    }
    section.stMain .block-container {
        padding-top: 0rem;
        z-index: 1;
    }
    </style>""", unsafe_allow_html=True)
st_autorefresh(interval=300000, key="datarefresh_models")

# Define as cores com base nos dados
def get_color(value):
    if value is None:
        return (0, 0, 0, 0)
    if value <= 0.5:
        return (182, 226, 161, abs(value - 0.5) + 0.4)
    else:
        return (253, 138, 138, abs(value - 0.5) + 0.4)

forecast = get_forecast().json()
today = forecast.get("today", None)
model_results = {}
for region, results in today.items():
    if not region in model_results:
        model_results[region] = {}
    for model_name, results in today[region]["models"].items():
        model_results[region][model_name] = results["proba"]


predict_date = datetime.strptime(st.session_state.predict_date, '%d/%m/%Y').date()
predict_week_day = week_day_portuguese[predict_date.weekday()]
st.markdown(
        f"<h1>Previsões detalhadas de {predict_week_day} ({predict_date})</h1>",
        unsafe_allow_html=True
        )

for region, models in model_results.items():
    st.markdown(
            f"<br><h4>Modelos de {REGION_DICT[region]}</h4>",
            unsafe_allow_html=True
            )
    for model_name, proba in models.items():
        st.markdown(
            f"""<div style=' display: flex; align-items: center;'>
                    <div style='background-color:rgba{str(get_color(proba))}; width:20px; height:20px; border-radius:50%;'></div>
                    <div> {model_name.upper()}: {int(proba*100)}%</div>
                </div>""",
            unsafe_allow_html=True
        )

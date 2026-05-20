import streamlit as st
from datetime import date, datetime, timedelta, timezone
import pandas as pd
import json
from streamlit_folium import folium_static
import folium
import requests
from os import environ
from app import get_forecast, get_forecast_input
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from pages.home.utils import get_color_distribution, get_map_color, get_flood_color, get_color, plot_gauge, plot_weather_forecast, week_day_portuguese
from streamlit_theme import st_theme
from authenticator import authenticator

REGION_NAMES = ("tamanduatei", "guarara", "oratorio", "meninos")

try:
    st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")
except:
    pass

st.session_state.tema = st_theme()

@st.dialog("Erro")
def not_found_dialog():
    st.session_state.err_text = "Não há resultados para a data selecionada"
    st.error(st.session_state.err_text)

@st.dialog("Erro")
def generic_error_dialog():
    st.session_state.err_text = "Houve um erro ao coletar os resultados"
    st.error(st.session_state.err_text)

@st.cache_data
def load_geojson(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

if '' not in st.session_state:
    st.session_state.map_theme = 'Cartodb Positron'

def set_fallback_data():
    st.session_state.fallback = True
    st.session_state.data = {
        "proba": 1.0,
        "explanation": "Não há resultados para a data selecionada",
        "rain_today": {"morning": 1.0, "afternoon": 1.0, "evening": 1.0, "night": 1.0},
        "forecast_summary": {"point_count": 0, "total_mm": 0.0, "max_point_total_mm": 0.0, "min_point_total_mm": 0.0},
        "models": {},
    }
    st.session_state.data_tomorrow = st.session_state.data.copy()
    st.session_state.region_data = {region: {"proba": 1.0, "explanation": "Não há resultados para a data selecionada"} for region in REGION_NAMES}

def load_dashboard_data(date_str: str):
    response = get_forecast(date_str, region_name="all")
    if response.status_code == 404:
        set_fallback_data()
        return response
    if response.status_code != 200:
        set_fallback_data()
        return response

    st.session_state.fallback = False
    st.session_state.data = response.json()
    st.session_state.region_data = {}

    for region in REGION_NAMES:
        region_response = get_forecast(date_str, region_name=region)
        if region_response.status_code == 200:
            st.session_state.region_data[region] = region_response.json()

    for region in REGION_NAMES:
        st.session_state.region_data.setdefault(region, {"proba": 0.0, "explanation": "Dados indisponíveis"})

    next_date = (datetime.strptime(date_str, "%Y-%m-%d").date() + timedelta(days=1)).strftime("%Y-%m-%d")
    tomorrow_response = get_forecast(next_date, region_name="all")
    if tomorrow_response.status_code == 200:
        st.session_state.data_tomorrow = tomorrow_response.json()
    else:
        st.session_state.data_tomorrow = {"proba": 0.0, "explanation": "Dados indisponíveis", "rain_today": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0, "night": 0.0}}

    st.session_state.data_input = get_forecast_input(date_str)
    return response

def change_theme():
    if st.session_state.map_theme == 'OpenStreetMap':
        st.session_state.map_theme = 'OpenStreetMap'
    else:
        st.session_state.map_theme = 'Cartodb Positron'

def on_date_change():
    st.session_state.previous_selected_date = st.session_state.selected_date
    date_str = st.session_state.selected_date.strftime('%Y-%m-%d')
    response = get_forecast(date_str, region_name="all")
    if response.status_code == 404:
        set_fallback_data()
        not_found_dialog()
    elif response.status_code != 200:
        set_fallback_data()
        generic_error_dialog()
    else:
        load_dashboard_data(date_str)

if 'data' not in st.session_state:
    load_dashboard_data(st.session_state.selected_date.strftime('%Y-%m-%d'))

if 'data_input' not in st.session_state:
    st.session_state.data_input = get_forecast_input(st.session_state.selected_date.strftime('%Y-%m-%d'))

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

st_autorefresh(interval=300000, key="datarefresh_home")

st.markdown(
    f"""
    <div style='display: flex; justify-content: space-between; align-items: center;'>
        <div>
            <h1 style='margin: 0; color:rgba(17, 28, 153, 255)'>Sistema de Predição de Alagamentos e Inundações</h1>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div style='text-align: right;'>
        <p style='margin: 0;'>Previsão feita em: {st.session_state.predict_date}.</p>
        <p style='margin: 0;'>Todas as previsões são feitas a partir das 0h do dia selecionado.</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("<h3 style='color:rgba(219, 116, 7, 255);'>Modelo de Santo André:</h3>", unsafe_allow_html=True)

col1, col2, col3, _, col4 = st.columns([3, 7, 5, 1, 11], vertical_alignment='center')

with col1:

    st.date_input(
        'Data escolhida:', 
        value=datetime.now(timezone(timedelta(hours=-3))).date(), 
        min_value=datetime(2017, 10, 6),
        format="DD/MM/YYYY",
        key="selected_date",
        on_change=on_date_change
    )
    
    # Exibe os dados apenas se existirem
    if st.session_state.data:
        today = st.session_state.data
        tomorrow = st.session_state.data_tomorrow
        region_data = st.session_state.region_data

rain_color_distribution = get_color_distribution(today['rain_today'])

# RAIN DISTRIBUTION
with col2:
    with st.container(border=True):
        st.markdown(
        f"""
        <div style='background-color: rgba{str(get_color(today['proba'], 0.3))}; display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 10px; padding: 10px; border-radius: 10px;'>
            <div style='display: flex; flex-direction: row; align-items: center; justify-content: center; gap: 10px;'>
                <p style='font-size: 20px; font-family: "Source Sans Pro", sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;'>
                    {week_day_portuguese[datetime.strptime(st.session_state.predict_date, '%d/%m/%Y').weekday()]}<br>{st.session_state.predict_date}
                </p>
            </div>
            <div style='display: flex; flex-direction: row; justify-content: space-evenly; gap: 20px;'>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Madrugada</p>
                    <div style='background-color: rgba{str(rain_color_distribution['night'])}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Manhã</p>
                    <div style='background-color: rgba{str(rain_color_distribution['morning'])}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Tarde</p>
                    <div style='background-color: rgba{str(rain_color_distribution['afternoon'])}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Noite</p>
                    <div style='background-color: rgba{str(rain_color_distribution['evening'])}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    with st.container(border=True):
        st.markdown(
        f"""
        <div style='background-color: rgba{str(get_color(tomorrow['proba'], 0.3))}; display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 10px; padding: 10px; border-radius: 10px;'>
            <div style='display: flex; flex-direction: row; align-items: center; justify-content: center; gap: 10px;'>
                <p style='font-size: 20px; font-family: "Source Sans Pro", sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;'>
                    {week_day_portuguese[datetime.strptime(st.session_state.next_predict_date, '%d/%m/%Y').weekday()]}<br>{st.session_state.next_predict_date}
                </p>
            </div>
            <div style='display: flex; flex-direction: row; justify-content: space-evenly; gap: 20px;'>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px; color: rgba{str(get_color(tomorrow['proba'], 0))};'>----</p>
                    <div style='background-color: rgba{str(get_color(tomorrow['proba']))}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# Caixa de prediçao + explicador
with col4:
    with st.container(border=True):
        if st.session_state.fallback:
            st.markdown(f"""
                <div style=display: flex; justify-content: center; align-items: center;'> 
                    <p style='text-align: center; font-size: 20px; font-family: 'Source Sans Pro', sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2; color='red';'>
                        {st.session_state.err_text}
                    </p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        else:
            st.markdown(f""" 
            <div style=display: flex; justify-content: center; align-items: center;'> 
                <p style='text-align: center; font-size: 20px; font-family: 'Source Sans Pro', sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;'>
                    <b>{today['proba']*100:.0f}%</b> de possibilidade em {st.session_state.predict_date}
                </p>
                <p style='text-align: center; font-size: 16px; font-family: 'Source Sans Pro', sans-serif; font-weight: 400; text-align: center; margin: 10px 0; line-height: 1.2;'>
                    <i>{today['explanation']}</i>
                </p>
            </div>
            """, 
            unsafe_allow_html=True
            )

    with st.container(border=True):
        if st.session_state.fallback:
            st.markdown(f"""
                <div style=display: flex; justify-content: center; align-items: center;'> 
                    <p style='text-align: center; font-size: 20px; font-family: 'Source Sans Pro', sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2; color='red';'>
                        {st.session_state.err_text}
                    </p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        else:
            st.markdown(f""" 
            <div style=display: flex; justify-content: center; align-items: center;'> 
                <p style='text-align: center; font-size: 20px; font-family: 'Source Sans Pro', sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;'>
                    <b>{tomorrow['proba']*100:.0f}%</b> de possibilidade em {st.session_state.next_predict_date}
                </p>
                <p style='text-align: center; font-size: 16px; font-family: 'Source Sans Pro', sans-serif; font-weight: 400; text-align: center; margin: 10px 0; line-height: 1.2;'>
                    <i>{tomorrow['explanation']}</i>
                </p>
            </div>
            """, 
            unsafe_allow_html=True
            )

st.divider()
st.markdown("<h3 style='color:rgba(219, 116, 7, 255);'>Modelo de Bacias:</h3>", unsafe_allow_html=True)

# Seleção de data
st.session_state.date_prev = st.segmented_control(
    "Seleção de previsão",
    [st.session_state.predict_date],
    selection_mode="single",
    default=st.session_state.predict_date,
    label_visibility='collapsed'
)

col_1, col_2 = st.columns([7, 7])

# Mapa
with col_1:

    # Dados GeoJSON simples (exemplo)
    geojson_data = load_geojson('assets/sub-bacias.geojson')
    geojson_alagaveis_data = load_geojson('assets/Areas_alagaveis.geojson')
    geojson_eixos_data = load_geojson('assets/Eixo_logradouros.geojson')
    geojson_viadutos_data = load_geojson('assets/Viadutos.geojson')
    geojson_vias_data = load_geojson('assets/Vias_principais.geojson')

    # Criar o mapa

    m = folium.Map(location=[-23.671165, -46.515248], zoom_start=12, control_scale=True)	
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, Maxar, Earthstar Geographics",
        name="Esri World Imagery",
        show=False
    ).add_to(m)
    
    # Adicionar camada GeoJSON com popup
    folium.GeoJson(
        geojson_data,
        name="Bacias Hidrográficas",
        tooltip=folium.GeoJsonTooltip(fields=["NOM_SUB_BA", "NOM_BACIA"]),
        popup=folium.GeoJsonPopup(fields=["NOM_SUB_BA", "NOM_BACIA"]),
        style_function=lambda feature: {
            "fillColor": get_map_color(feature['properties'].get('MODELO')),
            "fillOpacity": 0.4,
            'color': 'black',
            'weight': 0.5
        }
    ).add_to(m)

    folium.GeoJson(
        geojson_alagaveis_data,
        name="Áreas Alagáveis",
        tooltip=folium.GeoJsonTooltip(fields=["fid"]),
        popup=folium.GeoJsonPopup(fields=["fid"]),
        style_function=lambda feature: {
            "fillColor": get_flood_color(region_data.get(feature['properties'].get("MODELO", ""), {}).get("proba", None)),
            "fillOpacity": 0.7,
            "color": get_flood_color(region_data.get(feature['properties'].get("MODELO", ""), {}).get("proba", None)),
            'weight': (0.5 + region_data.get(feature['properties'].get("MODELO", ""), {}).get("proba", 0)) * 2
        }

    ).add_to(m)

    folium.LayerControl().add_to(m)

    # Exibir no Streamlit
    folium_static(m, width=None, height=500*0.82)
    
# Gauges para subregioes
with col_2:
    # Exibe a lista ao lado direito

    with st.container(border=True):
        st.markdown("""<div style='display: flex; justify-content: center; align-items: center;'>
                            <h5 style='text-align: center;'>Possibilidade de Alagamento ou Inundação</h5>
                        </div>""",
                    unsafe_allow_html=True)
    
    a1, a2 = st.columns([1, 1])
    with a1:
        with st.container(border=True):
            plot_gauge(region_data['tamanduatei']['proba'], "Bacia do Tamanduateí Central", "tamanduatei", {'l':10, 'b':20, 't':50})
    with a2:
        with st.container(border=True):
            plot_gauge(region_data['guarara']['proba'], "Sub-bacia do Guarará", "guarara", {'l':10, 'b':20, 't':50})
        
    b1, b2 = st.columns([1, 1])
    with b1:
        with st.container(border=True):
            plot_gauge(region_data['oratorio']['proba'], "Bacia do Oratório", "oratorio", {'l':10, 'b':20, 't':50})
    with b2:
        with st.container(border=True):
            plot_gauge(region_data['meninos']['proba'], "Bacia dos Meninos", "meninos", {'l':10, 'b':20, 't':50})


if not st.session_state.fallback:
    plot_weather_forecast(st.session_state.data_input)

# except Exception as e:
#     if isinstance(e, NameError):
#         with st.spinner("Carregando dados inicias..."):
#             st.session_state.data = get_forecast(st.session_state.selected_date.strftime('%Y-%m-%d'))
#             st.session_state.input = get_forecast_input(st.session_state.selected_date.strftime('%Y-%m-%d'))
#         st.rerun()
#     else:
#         st.error(f"An unexpected error occurred: {e}")

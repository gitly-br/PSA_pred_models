import streamlit as st
from datetime import date, datetime, timedelta
import pandas as pd
import json
from streamlit_folium import folium_static
import folium
import requests
from os import environ
from app import call_models, get_forecast
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from pages.home.utils import get_color_distribution, get_map_color, get_flood_color, get_color, get_rain_distribution, plot_gauge, plot_weather_forecast, week_day_portuguese, get_shap_importance
from streamlit_theme import st_theme


st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")

st.session_state.tema = st_theme()

@st.cache_data
def load_geojson(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

if 'map_theme' not in st.session_state:
    st.session_state.map_theme = 'Cartodb Positron'


def change_theme():
    if st.session_state.map_theme == 'OpenStreetMap':
        st.session_state.map_theme = 'OpenStreetMap'
    else:
        st.session_state.map_theme = 'Cartodb Positron'

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

# Título principal

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
        <p style='margin: 0;'>Data e hora da última atualização dos modelos: {st.session_state.predict_date} 00:00</p>
        <p style='margin: 0;'>Data e hora da próxima dos modelos: {st.session_state.next_predict_date} 00:00</p>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("<h3 style='color:rgba(219, 116, 7, 255);'>Modelo de Santo André:</h3>", unsafe_allow_html=True)

col1, col2, space2, col3 = st.columns([3, 8, 1, 14], vertical_alignment='center')

with col1:

    date_aux = st.date_input(
        'Data Base', 
        value=datetime.now()-timedelta(days=1), 
        min_value=datetime(2017, 10, 6),
        format="DD/MM/YYYY",
    )
    
    st.session_state.selected_date = date_aux
    
    # Botão para atualizar os dados
    if st.button("Atualizar Predição"):
        with st.spinner("Carregando dados..."):
            st.session_state.data = call_models(st.session_state.selected_date.strftime('%Y-%m-%d'))
            st.session_state.forecast = get_forecast(st.session_state.selected_date.strftime('%Y-%m-%d'))

    # Exibe os dados apenas se existirem
    if st.session_state.data:
        data_list_summary = {}
        data_list_detailed = {}
        for json_response in st.session_state.data['data']:
            data_list_summary[json_response['regiao']] = json_response['summary']
            data_list_detailed[json_response['regiao']] = json_response['detailed']

st.session_state.rain_distribution = get_rain_distribution(data_list_detailed)
proba_rain_distribution = get_color_distribution(data_list_summary['SA']['proba'], st.session_state.rain_distribution["SA"])

with col2:
    with st.container(border=True):
        # plot_gauge(0.123, "Amanhã", {'l':10, 'b':20, 't':50})
        st.markdown(
        f"""
        <div style='background-color: rgba{str(get_color(data_list_summary['SA']['proba'], 0.3))}; display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 10px; padding: 10px; border-radius: 10px;'>
            <div style='display: flex; flex-direction: row; align-items: center; justify-content: center; gap: 10px;'>
                <p style='font-size: 20px; font-family: "Source Sans Pro", sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;'>
                    {week_day_portuguese[datetime.strptime(st.session_state.predict_date, '%d/%m/%Y').weekday()]}<br>{st.session_state.predict_date}
                </p>
            </div>
            <div style='display: flex; flex-direction: row; justify-content: space-evenly; gap: 20px;'>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Madrugada</p>
                    <div style='background-color: rgba{str(proba_rain_distribution['madrugada'])}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Manhã</p>
                    <div style='background-color: rgba{str(proba_rain_distribution['manha'])}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Tarde</p>
                    <div style='background-color: rgba{str(proba_rain_distribution['tarde'])}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Noite</p>
                    <div style='background-color: rgba{str(proba_rain_distribution['noite'])}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


with col3:
    with st.container(border=True):
        st.markdown(f"<div style=display: flex; justify-content: center; align-items: center;'><h5 style='text-align: center;'>{data_list_summary['SA']['proba']*100:.1f}% de Possibilidade de Alagamento ou Inundação</h5><p style='text-align: center; font-size: 18px; font-family: 'Source Sans Pro', sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;'>Em Santo André em {st.session_state.predict_date}</p></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(f"<div style=display: flex; justify-content: center; align-items: center;'><p style='text-align: center; font-size: 18px; font-family: 'Source Sans Pro', sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;>Explicabilidade: {get_shap_importance(data_list_detailed['SA'])} </p></div>", unsafe_allow_html=True)


st.divider()
st.markdown("<h3 style='color:rgba(219, 116, 7, 255);'>Modelo de Bacias:</h3>", unsafe_allow_html=True)

# Seleção de data
today_date:str  = datetime.now().strftime('%d/%m/%Y')

st.session_state.date_prev = st.segmented_control(
    "Seleção de previsão",
    [today_date],
    selection_mode="single",
    default=today_date,
    label_visibility='collapsed'
)

col_1, col_2 = st.columns([7, 7])

with col_1:

    # Dados GeoJSON simples (exemplo)
    geojson_data = load_geojson('assets/sub-bacias.geojson')
    geojson_alagaveis_data = load_geojson('assets/Areas_alagaveis.geojson')
    geojson_eixos_data = load_geojson('assets/Eixo_logradouros.geojson')
    geojson_viadutos_data = load_geojson('assets/Viadutos.geojson')
    geojson_vias_data = load_geojson('assets/Vias_principais.geojson')

    # Criar o mapa

    m = folium.Map(location=[-23.671165, -46.515248], zoom_start=12, control_scale=True)	

    # folium.GeoJson(
    #     geojson_eixos_data,
    #     name="fid",
    #     popup=folium.GeoJsonPopup(fields=["DSC_LOGRAD"]),
    #     style_function=lambda feature: {
    #         'color': 'gray',
    #         'weight': 0.5,
    #         'opacity': 0.5
    #     }
    # ).add_to(m)

    # folium.GeoJson(
    #     geojson_viadutos_data,
    #     name="fid",
    #     popup=folium.GeoJsonPopup(fields=["ID"]),
    #     style_function=lambda feature: {
    #         'color': 'gray',
    #         'weight': 0.5,
    #         'opacity': 0.5
    #     }
    # ).add_to(m)

    # folium.GeoJson(
    #     geojson_vias_data,
    #     name="fid",
    #     popup=folium.GeoJsonPopup(fields=["ID"]),
    #     style_function=lambda feature: {
    #         'color': 'gray',
    #         'weight': 0.5,
    #         'opacity': 0.5
    #     }
    # ).add_to(m)
     
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
            "fillColor": get_flood_color(data_list_summary.get(feature['properties'].get('MODELO', ""), {}).get('proba')),
            "fillOpacity": 0.7,
            'color': get_flood_color(data_list_summary.get(feature['properties'].get('MODELO', ""), {}).get('proba')),
            'weight': (0.5 + data_list_summary.get(feature['properties'].get('MODELO', ""), {}).get('proba', 0)) * 4
        }

    ).add_to(m)

    folium.LayerControl().add_to(m)

    # Exibir no Streamlit
    folium_static(m, width=None, height=500*0.82)
    

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
            plot_gauge(data_list_summary['TAMCENTRAL']['proba'], "Bacia do Tamanduateí Central", "TAMCENTRAL", {'l':10, 'b':20, 't':50})
    with a2:
        with st.container(border=True):
            plot_gauge(data_list_summary['GUARARA']['proba'], "Sub-bacia do Guarará", "GUARARA", {'l':10, 'b':20, 't':50})
        
    b1, b2 = st.columns([1, 1])
    with b1:
        with st.container(border=True):
            plot_gauge(data_list_summary['ORATORIO']['proba'], "Bacia do Oratório", "ORATORIO", {'l':10, 'b':20, 't':50})
    with b2:
        with st.container(border=True):
            plot_gauge(data_list_summary['MENINOS']['proba'], "Bacia dos Meninos", "MENINOS", {'l':10, 'b':20, 't':50})

plot_weather_forecast(st.session_state.forecast)
import streamlit as st
from datetime import date, datetime, timedelta
import pandas as pd
import json
from streamlit_folium import folium_static
import folium
import requests
from os import environ
from app import call_region_api
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from pages.home.utils import get_color_distribution, get_map_color, get_flood_color, get_color, get_rain_distribution, plot_gauge, week_day_portuguese
try:
    st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")
except:
    pass


# Hardcode theme for now
if 'tema' not in st.session_state:
    st.session_state.tema = {'base': 'light'}

@st.cache_data
def load_geojson(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

if 'map_theme' not in st.session_state:
    st.session_state.map_theme = 'Cartodb Positron'

if 'data' not in st.session_state or st.session_state.data is None:
    with st.spinner("Carregando dados iniciais..."):
        st.session_state.data = call_region_api()

if st.session_state.data:
    data_list_summary = st.session_state.data['today']
    flag_not_rain_predict =  data_list_summary['all'] is not None

    if flag_not_rain_predict:
        st.session_state.rain_distribution = get_rain_distribution(data_list_summary['all'])
        proba_rain_distribution = get_color_distribution(data_list_summary['all'].get('proba', 0), st.session_state.rain_distribution)
else:
    # Handle the case where data is still not available (e.g., API error)
    st.warning("Não foi possível carregar os dados. Por favor, tente novamente.")
    st.stop() # Stop execution to prevent further errors

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
            st.session_state.data = call_region_api()

    # Exibe os dados apenas se existirem
    if st.session_state.data:
        data_list_summary = st.session_state.data['today']

with col2:
    with st.container(border=True):
        # plot_gauge(0.123, "Amanhã", {'l':10, 'b':20, 't':50})
        st.markdown(
        f"""
        <div style='background-color: rgba{str(get_color(data_list_summary['all']['proba'], 0.3) if flag_not_rain_predict else (171, 171, 171, 0.45))}; display: flex; flex-direction: column; align-items: center; justify-content: center; margin-bottom: 10px; padding: 10px; border-radius: 10px;'>
            <div style='display: flex; flex-direction: row; align-items: center; justify-content: center; gap: 10px;'>
                <p style='font-size: 20px; font-family: "Source Sans Pro", sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;'>
                    {week_day_portuguese[datetime.strptime(st.session_state.predict_date, '%d/%m/%Y').weekday()]}<br>{st.session_state.predict_date}
                </p>
            </div>
            <div style='display: flex; flex-direction: row; justify-content: space-evenly; gap: 20px;'>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Madrugada</p>
                    <div style='background-color: rgba{str(proba_rain_distribution['night'] if flag_not_rain_predict else (171, 171, 171, 0.60))}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Manhã</p>
                    <div style='background-color: rgba{str(proba_rain_distribution['morning'] if flag_not_rain_predict else (171, 171, 171, 0.60))}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Tarde</p>
                    <div style='background-color: rgba{str(proba_rain_distribution['afternoon'] if flag_not_rain_predict else (171, 171, 171, 0.60))}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
                <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;'>
                    <p style='font-size: 16px; font-family: "Source Sans Pro", sans-serif; font-weight: 500; text-align: center; margin-bottom: 5px;'>Noite</p>
                    <div style='background-color: rgba{str(proba_rain_distribution['evening'] if flag_not_rain_predict else (171, 171, 171, 0.60))}; width: 45px; height: 45px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


with col3:
    with st.container(border=True):
        if flag_not_rain_predict:
            st.markdown(f"<div style=display: flex; justify-content: center; align-items: center;'><h5 style='text-align: center;'>{data_list_summary['all']['proba']*100:.1f}% de Possibilidade de Alagamento ou Inundação</h5><p style='text-align: center; font-size: 18px; font-family: 'Source Sans Pro', sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;'>Em Santo André em {st.session_state.predict_date}</p></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style=display: flex; justify-content: center; align-items: center;'><h5 style='text-align: center;'>Sem previsão de alagamento ou inundação</h5><p style='text-align: center; font-size: 18px; font-family: 'Source Sans Pro', sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;'>Em Santo André em {st.session_state.predict_date}</p></div>", unsafe_allow_html=True)

    if flag_not_rain_predict:
        with st.container(border=True):
            st.markdown(f"<div style=display: flex; justify-content: center; align-items: center;'><p style='text-align: center; font-size: 18px; font-family: 'Source Sans Pro', sans-serif; font-weight: 600; text-align: center; margin: 10px 0; line-height: 1.2;>Explicabilidade: {data_list_summary['all']['explanation']} </p></div>", unsafe_allow_html=True)


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
            "fillColor": get_flood_color(data_list_summary.get(feature['properties'].get('MODELO', ""), {}).get('proba'))  if flag_not_rain_predict else "grey",
            "fillOpacity": 0.7,
            'color': get_flood_color(data_list_summary.get(feature['properties'].get('MODELO', ""), {}).get('proba')) if flag_not_rain_predict else "grey",
            'weight': (0.5 + data_list_summary.get(feature['properties'].get('MODELO', ""), {}).get('proba', 0)) * 4 if flag_not_rain_predict else 1
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
            plot_gauge(data_list_summary['tamanduatei']['proba'] if flag_not_rain_predict else 0, "Bacia do Tamanduateí Central", "TAMCENTRAL", {'l':10, 'b':20, 't':50}, flag_not_rain_predict)
    with a2:
        with st.container(border=True):
            plot_gauge(data_list_summary['guarara']['proba'] if flag_not_rain_predict else 0, "Sub-bacia do Guarará", "GUARARA", {'l':10, 'b':20, 't':50}, flag_not_rain_predict)
        
    b1, b2 = st.columns([1, 1])
    with b1:
        with st.container(border=True):
            plot_gauge(data_list_summary['oratorio']['proba'] if flag_not_rain_predict else 0, "Bacia do Oratório", "ORATORIO", {'l':10, 'b':20, 't':50}, flag_not_rain_predict)
    with b2:
        with st.container(border=True):
            plot_gauge(data_list_summary['meninos']['proba'] if flag_not_rain_predict else 0, "Bacia dos Meninos", "MENINOS", {'l':10, 'b':20, 't':50}, flag_not_rain_predict)

import streamlit as st
from datetime import datetime
import pandas as pd
import json
from streamlit_folium import folium_static
import folium
import requests
from os import environ
from app import call_models
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go

st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")

# Define as cores com base nos dados
def get_color(value):
    if value is None:
        return (0, 0, 0, 0)
    if value <= 0.5:
        return (182, 226, 161, abs(value - 0.5) + 0.4)
    else:
        return (253, 138, 138, abs(value - 0.5) + 0.4)

def plot_gauge(value, title, margin_dict:dict = {'l':10, 'b':20, 't':50}):
    if value >= 0.75:
        color = "red"
    elif 0.75 > value >= 0.45:
        color = "orange"
    else:
        color = "green"

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        number={'valueformat': '.0%'},  # Adiciona o símbolo de porcentagem
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title},
        gauge = {
            'axis': {'range': [None, 1], 'tickformat': ".0%"},
            'bar': {'color': color, 'thickness': 1, 'line' : {'width' : 1}},
        }
    ))
    config = {'displayModeBar': False}

    fig.update_layout(margin_autoexpand=True)
    fig.update_layout(
        height=140,  # Altura
        margin=margin_dict  # Margens menores
    )
    st.plotly_chart(fig, use_container_width=True, **{'config':config})



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
            <h1 style='margin: 0;'>Sistema de Predição de Alagamentos e Inundações</h1>
        </div>
        <div style='text-align: right;'>
            <p style='margin: 0;'>Data e hora da última atualização dos modelos: {st.session_state.predict_date} 00:00</p>
            <p style='margin: 0;'>Data e hora da próxima dos modelos: {st.session_state.next_predict_date} 00:00</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown("<h3 style='color:green;'>Modelo de Santo André:</h3>", unsafe_allow_html=True)


col1, space, col2, space2, col3 = st.columns([3, 1, 3, 1, 15], vertical_alignment='center')

with col1:

    date_aux = st.date_input(
        'Data Base', 
        value=datetime.now(), 
        min_value=datetime(2017, 10, 6),
        format="DD/MM/YYYY",
    )
    
    st.session_state.selected_date = date_aux
    
    # Botão para atualizar os dados
    if st.button("Atualizar Predição"):
        with st.spinner("Carregando dados..."):
            st.session_state.data = call_models(st.session_state.selected_date.strftime('%Y-%m-%d'))

    # Exibe os dados apenas se existirem
    if st.session_state.data:
        data_list_summary = {}
        for json_response in st.session_state.data['data']:
            data_list_summary[json_response['regiao']] = json_response['summary']
        
        


with col2:
    with st.container(border=True):
        # plot_gauge(0.123, "Amanhã", {'l':10, 'b':20, 't':50})
        st.markdown(
        f"""
        <div style='display: flex; flex-direction: column; align-items: center; justify-content: center;margin-bottom: 10px;'>
            <p style='font-size: 20px; font-family: "Source Sans Pro", sans-serif; font-weight: 600; text-align: center; color: #333; margin: 10px 0; line-height: 1.2;'>Amanhã<br>{st.session_state.next_predict_date}</p>
            <div style='background-color: rgba{str(get_color(data_list_summary['SA']['proba']))}; width: 60px; height: 60px; border-radius: 50%; display: flex; justify-content: center; align-items: center;'>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


with col3:
    with st.container(border=True):
        st.markdown(f"<div style=display: flex; justify-content: center; align-items: center;'><h5 style='text-align: center;'>{data_list_summary['SA']['proba']*100:.1f}% de Possibilidade de Alagamento ou Inundação em Santo André em<br>{st.session_state.next_predict_date}</h5></div>", unsafe_allow_html=True)

st.divider()
st.markdown("<h3 style='color:green;'>Modelo de Bacias:</h3>", unsafe_allow_html=True)
st.session_state.date_prev = st.segmented_control(
    "Seleção de previsão",
    ["Amanhã"],
    selection_mode="single",
    default="Amanhã",
    label_visibility='collapsed'
)

col_1, col_2 = st.columns([7, 7])

with col_1:

    # Dados GeoJSON simples (exemplo)
    with open('assets/sub-bacias.geojson') as f:
        geojson_data = json.load(f)

    # Criar o mapa
    m = folium.Map(location=[-23.671165, -46.515248], zoom_start=12, height="82%", tiles="Cartodb Positron", control_scale=True)	

    # Adicionar camada GeoJSON com popup
    folium.GeoJson(
        geojson_data,
        name="NOM_BACIA",
        tooltip=folium.GeoJsonTooltip(fields=["NOM_SUB_BA", "NOM_BACIA"]),
        popup=folium.GeoJsonPopup(fields=["NOM_SUB_BA", "NOM_BACIA"]),
        style_function= lambda feature: {
            "fillColor" : "green"
            if "guarará" == feature['properties']['NOM_SUB_BA'].lower() else 
            "orange" if "meninos" == feature["properties"]['NOM_BACIA'].lower() else
            "blue" if "oratório" == feature["properties"]['NOM_BACIA'].lower() else
            "#12b6fc" if "tamanduateí central" == feature["properties"]['NOM_BACIA'].lower() else
            "yellow",
            'color' : 'black',
            'weight': 0.5
        }
    ).add_to(m)

    # Exibir no Streamlit
    folium_static(m, width=None)

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
            plot_gauge(data_list_summary['TAMCENTRAL']['proba'], "Bacia do Tamanduateí Central", {'l':10, 'b':20, 't':50})
    with a2:
        with st.container(border=True):
            plot_gauge(data_list_summary['GUARARA']['proba'], "Sub-bacia do Guarará", {'l':10, 'b':20, 't':50})
        
    b1, b2 = st.columns([1, 1])
    with b1:
        with st.container(border=True):
            plot_gauge(data_list_summary['ORATORIO']['proba'], "Bacia do Oratório", {'l':10, 'b':20, 't':50})
    with b2:
        with st.container(border=True):
            plot_gauge(data_list_summary['MENINOS']['proba'], "Bacia dos Meninos", {'l':10, 'b':20, 't':50})
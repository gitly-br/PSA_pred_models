import streamlit as st
import requests
import pandas as pd
from os import environ
from streamlit_folium import folium_static
import folium
import json
from datetime import date, datetime, timedelta
from authenticator import authenticator
from streamlit_theme import st_theme

api_url = environ.get('API_URL', 'http://localhost:8080')
DEFAULT_SELECTED_DATE = date(2026, 5, 19)

def get_forecast(date: str = "", region_name: str = "all"):
    api_url_i = f"{api_url}/region/{region_name}"
    if date != "":
        api_url_i = f"{api_url_i}?date={date}"

    response_i = requests.get(api_url_i)
    return response_i

def get_forecast_input(date: str=""):
    if date == "":
        api_url_i = f"{api_url}/forecast-data/santoandre/openweather"
    else:
        api_url_i = f"{api_url}/forecast-data/santoandre/openweather?date={date}"

    response_i = requests.get(api_url_i)
    return response_i.json()

@st.dialog("Links Úteis")
def links_uteis():
    st.markdown("[Defesa Civil - Santo André](https://portais.santoandre.sp.gov.br/defesacivil)")
    st.markdown("[Centro de Resiliência](https://portais.santoandre.sp.gov.br/defesacivil/centro-de-resiliencia/)")
    st.markdown("[Banco de Desenvolvimento da América Latina e Caribe - CAF](https://www.caf.com/pt/)")

@st.dialog("Carregando...")
def loading_dialog():
    with st.spinner("Carregando dados, aguarde..."):
        date_str = st.session_state.selected_date.strftime('%Y-%m-%d')
        st.session_state.data = get_forecast(date_str).json()
        st.session_state.data_input = get_forecast_input(date_str)
        st.rerun()

try:
    st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")
except Exception as e:
    print(f"Error: {e}")


# Função para verificar as credenciais

if 'tema' not in st.session_state or st.session_state.tema is None:
    st.session_state.tema = st_theme()

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = DEFAULT_SELECTED_DATE

st.session_state.predict_date = st.session_state.selected_date.strftime('%d/%m/%Y')
st.session_state.next_predict_date = (st.session_state.selected_date + timedelta(days=1)).strftime('%d/%m/%Y')

if 'data' not in st.session_state:
    response = get_forecast(st.session_state.selected_date.strftime('%Y-%m-%d'))
    if response.status_code == 200:
        st.session_state.data = response.json()
        st.session_state.fallback = False
    else:
        st.session_state.data = None
        st.session_state.fallback = True

if 'data_tomorrow' not in st.session_state:
    next_date = (st.session_state.selected_date + timedelta(days=1)).strftime('%Y-%m-%d')
    tomorrow_response = get_forecast(next_date, region_name='all')
    if tomorrow_response.status_code == 200:
        st.session_state.data_tomorrow = tomorrow_response.json()
    else:
        st.session_state.data_tomorrow = {"proba": 0.0, "explanation": "Dados indisponíveis", "rain_today": {"morning": 0.0, "afternoon": 0.0, "evening": 0.0, "night": 0.0}}

if 'data_input' not in st.session_state:
    response = get_forecast_input(st.session_state.selected_date.strftime('%Y-%m-%d'))
    st.session_state.data_input = response

if 'authentication_status' not in st.session_state:
    st.session_state.authentication_status = None  # Armazena o status de autenticação
if 'logout' not in st.session_state:
    st.session_state.logout = None  # Armazena o status de autenticação

# --- widget login -------------
try:
    authenticator.login("main")
except Exception as e:
    st.error(e)

if st.session_state.authentication_status:
    pages = [
            st.Page("pages/home/home.py", title="Home"),
            st.Page("pages/models/models.py", title="Modelos Detalhados"),
            st.Page("pages/chamados/chamados.py", title="Mapa de Ocorrências"),
    ]

    # SIDEBAR START
    pg = st.navigation(pages)
    try:
        pg.run()
    except Exception as e:
        st.error(e)

    # Remove espaço em branco no topo
    st.markdown("""
        <style>
        header.stAppHeader {
            background-color: transparent;
        }
        section.stMain .block-container {8
            padding-top: 0rem;
            z-index: 1;
        }
        </style>""", unsafe_allow_html=True)

    st.sidebar.image("static/Group_Custom.png")
    st.sidebar.markdown(
        "<h2>Informações Gerais</h2>", 
        unsafe_allow_html=True
    )
    st.sidebar.markdown("[Formulário para Registro de Ocorrências](https://forms.gle/yUxpb68E5cjj1YdHA)")
    st.sidebar.markdown("[Ajuda](https://gitly.notion.site/Ajuda-PSA-Dashboard-185ad90ac24c802b80faee77754fb4cf?pvs=4)")

    st.sidebar.button("Links Úteis", on_click=links_uteis, use_container_width=True)
    st.sidebar.markdown(
        f"""
        <style>

            .image-container {{
                width: 80px; /* Largura da imagem */
                height: 80px; /* Altura da imagem */
                background-image: url('logo_transparent_cropado.png'); /* Substitua pelo caminho do seu arquivo */
                background-size: cover;
                background-repeat: no-repeat;
                background-position: center;
            }}

            .text-container {{
                font-size: 22px; /* Tamanho da fonte */
                font-weight: bold; /* Texto em negrito */
            }}
        </style>

        <div data-testid="stSidebarNav" style="gap: 20px; display: flex; align-items: center; justify-content: center;margin-bottom: 20px;">
            <a href="https://www.gitly.com.br/"><img src="./app/static/gitly.png" width="75"></a>
            <div class="text-container">V 2.9</div>
        </div>
        """,
        unsafe_allow_html=True,
    
    )

    authenticator.logout(button_name="Logout", location="sidebar")
    # SIDEBAR STOP
        

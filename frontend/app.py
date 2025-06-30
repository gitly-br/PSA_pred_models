
import streamlit as st
import requests
import pandas as pd
from os import environ
from streamlit_folium import folium_static
import folium
import json
from datetime import datetime, timedelta
from datetime import datetime, timedelta

api_url = environ.get('API_URL', 'http://localhost:8000')

def call_region_api(region="santoandre"):
    api_url_i = f"{api_url}/region/{region}"
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
        st.session_state.data = call_region_api()
        st.rerun()

try:
    st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")
except:
    pass


# Função para verificar as credenciais

# if 'tema' not in st.session_state or st.session_state.tema is None:
#     st.session_state.tema = st_theme()

# def check_credentials(username, password):
#     # Substitua pela lógica de autenticação real
#     return username in ["psa_defesa_civil", 'admin'] and password in ["PSA@D3fes4", 'admin123']

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date() - timedelta(days=1)

st.session_state.predict_date = (st.session_state.selected_date + timedelta(days=1)).strftime('%d/%m/%Y')
st.session_state.next_predict_date = (st.session_state.selected_date + timedelta(days=2)).strftime('%d/%m/%Y')

if 'data' not in st.session_state:
    st.session_state.data = None  # Armazena os dados retornados da API

    pages = [
            st.Page("pages/home/home.py", title="Home"),
            st.Page("pages/models/models.py", title="Modelos Detalhados"),
            st.Page("pages/chamados/chamados.py", title="Mapa de Ocorrências"),
    ]

    pg = st.navigation(pages)
    pg.run()

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

    # st.sidebar.markdown(f"""
    #     <div style="text-align: center;">
    #         <a href="https://portais.santoandre.sp.gov.br/defesacivil">
    #         <img src="./app/static/PSA.png" width="150">
    #         </a>
    #     </div>
    #     """, unsafe_allow_html=True)
    # st.sidebar.markdown(f"""
    #     <div style="margin-bottom:20px; text-align: center; display: flex; justify-content: space-around; gap: 20px; align-items: center;">
    #         <a href="https://www.caf.com/pt/">
    #         <img src="./app/static/CAF.png" width="100">
    #         </a>
    #         <a href="https://portais.santoandre.sp.gov.br/defesacivil">
    #         <img src="./app/static/logo-DFSA.png" width="100">
    #         </a>
    #     </div>
    #     """, unsafe_allow_html=True)
    
    st.sidebar.image("static/Group_Dark.png" if st.session_state.tema['base'] == 'dark' else "static/Group_Custom.png")
    st.sidebar.markdown(
        "<h2>Informações Gerais</h2>", 
        unsafe_allow_html=True
    )
    st.sidebar.markdown("[Formulário para Registro de Ocorrências](https://forms.gle/yUxpb68E5cjj1YdHA)")
    st.sidebar.markdown("[Ajuda](https://gitly.notion.site/Ajuda-PSA-Dashboard-185ad90ac24c802b80faee77754fb4cf?pvs=4)")

    st.sidebar.button("Links Úteis", on_click=links_uteis, use_container_width=True)
    
    
    ### DENTRO DE STYLE PARA CASO PRECISE IMPROVISAR FOOTER
    # [data-testid="stSidebarNav"] + div {{
    #     position: relative;
    #     bottom: 0;
    #     height: 10%;
    #     display: flex;
    #     flex-direction: row; /* Organiza imagem e texto lado a lado */
    #     align-items: center; /* Centraliza verticalmente */
    #     gap: 10px; /* Espaço entre a imagem e o texto */
    # }}

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
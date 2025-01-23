
import streamlit as st
import requests
import pandas as pd
from os import environ
from streamlit_folium import folium_static
import folium
import json
from datetime import datetime, timedelta

api_url = environ.get('API_URL___', 'http://psa_models_back:8000')

def call_models(dt_begin=None):
    # Conteúdo da primeira aba (Visualização)
    responses = []
    for i in range(1, 6):
        api_url_i = f"{api_url}/modelo_{i}"
        response_i = requests.post(api_url_i, json={'dt_request': dt_begin})
        responses.append(response_i)

    
    for response in responses:
        if response.status_code != 200:
            st.error(f"Falha ao conectar à API: Código de status {response.status_code}")
            st.stop()


    json_responses = [response.json() for response in responses]

    return json_responses

# Função para verificar as credenciais


def check_credentials(username, password):
    # Substitua pela lógica de autenticação real
    return username == "psa_defesa_civil" and password == "PSA@D3fes4"

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date()

st.session_state.predict_date = (st.session_state.selected_date + timedelta(days=1)).strftime('%d/%m/%Y')
st.session_state.next_predict_date = (st.session_state.selected_date + timedelta(days=2)).strftime('%d/%m/%Y')


# Inicializa o estado da sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'data' not in st.session_state:
    st.session_state.data = None  # Armazena os dados retornados da API

# Tela de login
if not st.session_state.logged_in:
    
    st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")
    col1, col2, col3 = st.columns([3, 3, 3])
    
    with col2:
        st.title("Login")

        username = st.text_input("Usuário")
        password = st.text_input("Senha", type='password')

        if st.button("Entrar"):
            if check_credentials(username, password):
                st.session_state.logged_in = True
                st.success("Login realizado com sucesso")
                st.session_state.data = call_models(datetime.now().strftime('%Y-%m-%d'))
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos")
else:
    
    pages = [
            st.Page("home.py", title="Home"),
            st.Page("models.py", title="Modelos Detalhados"),
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

    st.sidebar.image("PSA.png")
    st.sidebar.title("Sistema de Previsão de Alagamentos")
    st.sidebar.markdown("[Formulário para registro de ocorrência](https://forms.gle/yUxpb68E5cjj1YdHA)")
    st.sidebar.markdown("[Dúvidas](YdHA)")
    st.sidebar.markdown(
        f"""
        <style>
            [data-testid="stSidebarNav"] + div {{
                position: relative;
                bottom: 0;
                height: 80%;
                display: flex;
                flex-direction: row; /* Organiza imagem e texto lado a lado */
                align-items: center; /* Centraliza verticalmente */
                gap: 10px; /* Espaço entre a imagem e o texto */
            }}

            .image-container {{
                width: 80px; /* Largura da imagem */
                height: 80px; /* Altura da imagem */
                background-image: url('logo_transparent_cropado.png'); /* Substitua pelo caminho do seu arquivo */
                background-size: cover;
                background-repeat: no-repeat;
                background-position: center;
            }}

            .text-container {{
                font-size: 20px; /* Tamanho da fonte */
                font-weight: bold; /* Texto em negrito */
                color: #000; /* Cor do texto */
            }}
        </style>

        <div data-testid="stSidebarNav">
            <div class="image-container"></div>
            <div class="text-container">V 2.0</div>
        </div>
        """,
        unsafe_allow_html=True,
    
    )
        

        # st.markdown('<br><h4>Bacia Tamanduateí (24h)</h4>',unsafe_allow_html=True)

        # for idx, row in df.iterrows():
        #     if row['regiao'] == 'tam':

        #         if row['status'] == 0:
        #             st.markdown(
        #                 f"""<div style=' display: flex; align-items: center;'>
        #                         <div style='background-color:rgba{str(get_color(row['valor']))}; width:20px; height:20px; border-radius:50%;'></div>
        #                         <div style='margin-left: 20px;'>Sem previsão de chuvas moderadas ou fortes</div>
        #                     </div>""",
        #                 unsafe_allow_html=True
        #             )
        #             break
        #         else:
        #             st.markdown(
        #                 f"""<div style=' display: flex; align-items: center;'>
        #                         <div style='background-color:rgba{str(get_color(row['valor']))}; width:20px; height:20px; border-radius:50%;'></div>
        #                         <div style='margin-left: 20px;'>Chance de alagar: {row['valor']*100:.1f}%</div>
        #                         <div>Modelo: {row['model']}</div>
        #                         <div>Ultima atualização: {(datetime.fromisoformat(row['dt_inference'].replace('Z','')) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')}</div>
        #                     </div>""",
        #                 unsafe_allow_html=True
        #             )

# footer="""<style>
# a:link , a:visited{
# color: blue;
# background-color: transparent;
# text-decoration: underline;
# }

# a:hover,  a:active {
# color: red;
# background-color: transparent;
# text-decoration: underline;
# }

# .footer {
# position: fixed;
# left: 0;
# bottom: 0;
# width: 100%;
# background-color: white;
# color: black;
# text-align: center;
# }
# </style>
# <div class="footer">
# <p></p>
# </div>
# """
# st.markdown(footer,unsafe_allow_html=True)
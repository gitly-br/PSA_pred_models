
import streamlit as st
import requests
import pandas as pd
from os import environ
from streamlit_folium import folium_static
import folium
import json
from datetime import datetime, timedelta
from streamlit_theme import st_theme

api_url = environ.get('API_URL_', 'http://psa_models_back:8000')

def call_models(dt_begin=None):
        
    api_url_i = f"{api_url}/home"
    response_i = requests.post(api_url_i, json={'dt_request': dt_begin})

    return response_i.json()

# Função para verificar as credenciais


def check_credentials(username, password):
    # Substitua pela lógica de autenticação real
    return username == "psa_defesa_civil" and password == "PSA@D3fes4"

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date() - timedelta(days=1)

st.session_state.predict_date = (st.session_state.selected_date + timedelta(days=1)).strftime('%d/%m/%Y')
st.session_state.next_predict_date = (st.session_state.selected_date + timedelta(days=2)).strftime('%d/%m/%Y')

@st.dialog("Links Úteis")
def links_uteis():
    st.markdown("[Defesa Civil - Santo André](https://portais.santoandre.sp.gov.br/defesacivil)")
    st.markdown("[Centro de Resiliência](https://portais.santoandre.sp.gov.br/defesacivil/centro-de-resiliencia/)")
    st.markdown("[Banco de Desenvolvimento da América Latina e Caribe - CAF](https://www.caf.com/pt/)")


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
            st.Page("previsao.py", title="Previsão"),
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
    
    st.sidebar.image("static/Group_Dark.png" if st_theme()['base'] == 'dark' else "static/Group_Custom.png")
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

        <div data-testid="stSidebarNav" style="gap: 20px; display: flex; align-items: center; justify-content: center;">
            <a href="https://www.gitly.com.br/"><img src="./app/static/gitly.png" width="75"></a>
            <div class="text-container">V 2.2</div>
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
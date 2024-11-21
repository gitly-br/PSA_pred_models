from datetime import datetime, timedelta
import streamlit as st
import requests
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from streamlit_autorefresh import st_autorefresh


# Função para verificar as credenciais

st.set_page_config(layout='wide')
st_autorefresh(interval=300000, key="datarefresh")

def check_credentials(username, password):
    # Substitua pela lógica de autenticação real
    return username == "usuario" and password == "senha"


# Inicializa o estado da sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Tela de login
if not st.session_state.logged_in:
    st.title("Login")

    username = st.text_input("Usuário")
    password = st.text_input("Senha", type='password')

    if st.button("Entrar"):
        if check_credentials(username, password):
            st.session_state.logged_in = True
            st.success("Login realizado com sucesso")
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")
else:

    col_1, space_, col_2 = st.columns([11, 1, 4])

    with col_1:
        # Título principal após o login
        st.title("Predição de alagamentos")

        # Conteúdo da primeira aba (Visualização)
        # URL da API
        api_url = "http://psa_models_back:8000/modelo_1"  # Substitua pela URL da sua API

        # Faz a requisição à API
        response = requests.post(api_url)

        if response.status_code == 200:
            json_response = response.json()

            # Verifica se o status é 'success' e extrai os dados do campo 'data'
            if json_response.get('status') == 'success':
                data = json_response.get('data', {})

                # Cria um DataFrame a partir dos dados
                df = pd.DataFrame([data])

                # Renomeia as colunas conforme necessário
                df.rename(columns={'region': 'regiao',
                          'score': 'valor'}, inplace=True)

                # Define as cores com base nos dados
                def get_color(value):
                    if value <= 0.3:
                        return (255, 237, 160, 160)  # Cor para valores baixos
                    elif value <= 0.7:
                        return (254, 178, 76, 160)  # Cor para valores médios
                    else:
                        return (240, 59, 32, 160)  # Cor para valores altos

                def get_hex_color(value):
                    if value <= 0.3:
                        return '#ffeda0'
                    elif value <= 0.7:
                        return '#feb24c'
                    else:
                        return '#f03b20'

                df['cor'] = df['valor'].apply(get_color)

                # Plota o mapa
                st.map(df, latitude="lat", longitude="lon",
                       size="circle_rad", color="cor", height=600)
            else:
                st.error("Falha ao obter dados da API: Status não é 'success'")
                st.stop()
        else:
            st.error(
                f"Falha ao conectar à API: Código de status {response.status_code}")
            st.stop()

    with col_2:
        # Exibe a lista ao lado direito
        st.header("Regiões")
        for idx, row in df.iterrows():
            st.markdown(
                f"""<div style='margin-left: 10px; display: flex; align-items: center;'>
                        <strong>Santo André</strong></div>
                        <div style='background-color:{get_hex_color(row['valor'])}; width:20px; height:20px; border-radius:50%; margin-left: 30px;'>
                        <div style='margin-left: 45px;'>
                        {row['valor']*100}%
                        </div>
                        </div>
                        <div style='margin-left: 30px;'>
                            Modelo: {row['model']}
                        </div>
                        <div style='margin-left: 30px;'>
                            Ultima atualização: {(datetime.fromisoformat(row['dt_inference'].replace('Z','')) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')}
                        </div>
                        
                        """,
                unsafe_allow_html=True
            )

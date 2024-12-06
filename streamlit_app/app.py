from datetime import datetime, timedelta
import streamlit as st
import requests
import pandas as pd
from streamlit_autorefresh import st_autorefresh
from os import environ


api_url = environ.get('API_URL', 'http://psa_models_back:8000')

# Função para verificar as credenciais

st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")

st_autorefresh(interval=300000, key="datarefresh")

def check_credentials(username, password):
    # Substitua pela lógica de autenticação real
    return username == "psa_defesa_civil" and password == "PSA@D3fes4"

if 'selected_date' not in st.session_state:
    st.session_state.selected_date = datetime.now().date() + timedelta(days=1)

st.session_state.predict_date = st.session_state.selected_date.strftime('%d/%m/%Y')

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

# Inicializa o estado da sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if 'data' not in st.session_state:
    st.session_state.data = None  # Armazena os dados retornados da API

# Tela de login
if not st.session_state.logged_in:

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
    
    st.sidebar.image("PSA.png")
    st.sidebar.title("Sistema de Previsão de Alagamentos")
    st.sidebar.markdown("[Formulário para registro de ocorrência](https://forms.gle/yUxpb68E5cjj1YdHA)")

    
    # Título principal
    st.title("Predição de Alagamentos")
    col1, space, col2 = st.columns([5, 1, 6])

    with col1:

        date_aux = st.date_input(
            'Data', 
            value=datetime.now()+timedelta(days=1), 
            min_value=datetime(2017, 10, 7),
            format="DD/MM/YYYY",
        )
        
        st.session_state.selected_date = date_aux + (timedelta(days=1) if date_aux > datetime(2024, 11, 24).date() else timedelta(days=0))
        
        # Botão para atualizar os dados
        if st.button("Atualizar"):
            with st.spinner("Carregando dados..."):
                st.session_state.data = call_models(st.session_state.selected_date.strftime('%Y-%m-%d'))

        # Exibe os dados apenas se existirem
        if st.session_state.data:
            data_list = []
            for json_response in st.session_state.data:
                if json_response.get('status') == 'success':
                    data_list.append(json_response.get('data', {}))
                else:
                    data_list.append(json_response.get('data', {}))

            df = pd.DataFrame(data_list)
            df.rename(columns={'region': 'regiao', 'proba': 'valor'}, inplace=True)

            # Define as cores com base nos dados
            def get_color(value):
                if value is None:
                    return (0, 0, 0, 0)
                if value <= 0.5:
                    return (182, 226, 161, abs(value - 0.5) + 0.4)
                else:
                    return (253, 138, 138, abs(value - 0.5) + 0.4)

            df_map = df.copy()
            df_map['cor'] = df_map['valor'].apply(get_color)

            new_row = {
                'circle_rad': 0, 
                'valor': 0, 
                'cor': (0, 0, 0, 0), 
                'lat': -23.656825, 
                'lon': -46.533353, 
                'status': 1
            }
            df_map = pd.concat([df_map, pd.DataFrame([new_row])], ignore_index=True)

            df_maps = df_map[df_map['status'] == 1]


    with col2:
        st.markdown("<h2>Período considerado na predição</h2>", unsafe_allow_html=True)
        st.text(f"De {st.session_state.predict_date} 00:00  -  {st.session_state.predict_date} 23:59")
    
    col_1, space_, col_2 = st.columns([9, 1, 6])

    with col_1:

            # Plota o mapa
            st.map(df_maps, latitude="lat", longitude="lon",
                   size="circle_rad", color="cor", height=600, zoom=13)

    with col_2:
        # Exibe a lista ao lado direito
        st.header("Região Considerada no Modelo")

        st.markdown('<h4>Santo André (24h)</h4>',unsafe_allow_html=True)
        for idx, row in df.iterrows():
            if row['regiao'] == 'SA':
                if row['status'] == 0:
                    st.markdown(
                        f"""<div style=' display: flex; align-items: center;'>
                                <div style='background-color:rgba{str(get_color(row['valor']))}; width:20px; height:20px; border-radius:50%;'></div>
                                <div style='margin-left: 20px;'>Sem previsão de chuvas moderadas ou fortes</div>
                            </div>""",
                        unsafe_allow_html=True
                    )
                    break
                else:
                    st.markdown(
                        f"""<div style=' display: flex; align-items: center;'>
                                <div style='background-color:rgba{str(get_color(row['valor']))}; width:20px; height:20px; border-radius:50%;'></div>
                                <div style='margin-left: 20px;'>Chance de alagar: {row['valor']*100:.1f}%</div>
                                <div>Modelo: {row['model']}</div>
                                <div>Ultima atualização: {(datetime.fromisoformat(row['dt_inference'].replace('Z','')) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')}</div>
                            </div>""",
                        unsafe_allow_html=True
                    )

        st.markdown('<br><h4>Bacia Tamanduateí (24h)</h4>',unsafe_allow_html=True)

        for idx, row in df.iterrows():
            if row['regiao'] == 'tam':

                if row['status'] == 0:
                    st.markdown(
                        f"""<div style=' display: flex; align-items: center;'>
                                <div style='background-color:rgba{str(get_color(row['valor']))}; width:20px; height:20px; border-radius:50%;'></div>
                                <div style='margin-left: 20px;'>Sem previsão de chuvas moderadas ou fortes</div>
                            </div>""",
                        unsafe_allow_html=True
                    )
                    break
                else:
                    st.markdown(
                        f"""<div style=' display: flex; align-items: center;'>
                                <div style='background-color:rgba{str(get_color(row['valor']))}; width:20px; height:20px; border-radius:50%;'></div>
                                <div style='margin-left: 20px;'>Chance de alagar: {row['valor']*100:.1f}%</div>
                                <div>Modelo: {row['model']}</div>
                                <div>Ultima atualização: {(datetime.fromisoformat(row['dt_inference'].replace('Z','')) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')}</div>
                            </div>""",
                        unsafe_allow_html=True
                    )
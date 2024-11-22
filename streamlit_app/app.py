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



# Inicializa o estado da sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

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
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos")
else:
    
    st.sidebar.image("PSA.png")
    st.sidebar.title("Sistema de Previsão de Alagamentos")
    st.sidebar.markdown("[Formulário para registro de ocorrência](https://forms.gle/yUxpb68E5cjj1YdHA)")

    col_1, space_, col_2 = st.columns([9, 1, 6])

    with col_1:
        # Título principal após o login
        st.title("Predição de Alagamentos")

        # Conteúdo da primeira aba (Visualização)
        responses = []
        for i in range(1, 6):
            api_url_i = f"{api_url}/modelo_{i}"
            response_i = requests.post(api_url_i)
            responses.append(response_i)

        success=True
        for response in responses:
            if response.status_code != 200:
                st.error(f"Falha ao conectar à API: Código de status {response.status_code}")
                st.stop()


        json_responses = [response.json() for response in responses]


        data_list = []
        for json_response in json_responses:
            if json_response.get('status') == 'success':
                data_list.append(json_response.get('data', {}))
            else:
                data_list.append(json_response.get('data', {}))

        df = pd.DataFrame(data_list)

        if success:

            # Verifica se o status é 'success' e extrai os dados do campo 'data'

                # Cria um DataFrame a partir dos dados
                df = pd.DataFrame(data_list)

                # Renomeia as colunas conforme necessário
                df.rename(columns={'region': 'regiao',
                          'proba': 'valor'}, inplace=True)

                # Define as cores com base nos dados
                def get_color(value):
                    if value is None:
                        return (0,0,0,0)
                    if value <= 0.5:
                        return (182, 226, 161, abs(value-0.5)+0.4) 
                    else:
                        return (253, 138, 138, abs(value-0.5)+0.4)  # Cor para valores altos

                def get_hex_color(value):
                    if value <= 0.5:
                        return '#B6E2A1'
                    elif value <= 0.7:
                        return '#fd8a8a'

                df_map = df.copy()

                df_map['cor'] = df_map['valor'].apply(get_color)

                new_row = {'circle_rad': 0, 'valor': 0, 'cor': (0,0,0,0), 'lat' : -23.656825, 'lon' : -46.533353, 'status':1}
                df_map = pd.concat([df_map, pd.DataFrame([new_row])], ignore_index=True)

                df_maps = df_map[df_map['status'] == 1]
                
                
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
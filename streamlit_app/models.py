import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from streamlit_autorefresh import st_autorefresh

from app import call_models

st.set_page_config(layout='wide', page_title="Sistema de Previsão de Alagamentos", page_icon="🌧️")


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
st_autorefresh(interval=300000, key="datarefresh_models")

# Define as cores com base nos dados
def get_color(value):
    if value is None:
        return (0, 0, 0, 0)
    if value <= 0.5:
        return (182, 226, 161, abs(value - 0.5) + 0.4)
    else:
        return (253, 138, 138, abs(value - 0.5) + 0.4)

date_aux = st.date_input(
        'Data', 
        value=datetime.now()-timedelta(days=1), 
        min_value=datetime(2017, 10, 6),
        format="DD/MM/YYYY",
    )
    
st.session_state.selected_date = date_aux

# Botão para atualizar os dados
if st.button("Atualizar"):
    with st.spinner("Carregando dados..."):
        st.session_state.data = call_models(st.session_state.selected_date.strftime('%Y-%m-%d'))

# Exibe os dados apenas se existirem
if st.session_state.data:
    data_list = []
    for json_response in st.session_state.data['data']:
        for model in json_response['detailed']:
            data_list.append(model['result'])

    st.session_state.df = pd.DataFrame(data_list)
    st.session_state.df.rename(columns={'region': 'regiao', 'proba': 'valor'}, inplace=True)


st.markdown('<br><h4>Santo André (24h)</h4>',unsafe_allow_html=True)

for idx, row in st.session_state.df.iterrows():
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
                        <div style='margin-left: 20px;'> - Possibilidade de Alagamento ou Inundação : {row['valor']*100:.1f}% </div>
                        <div> - Modelo: {row['model']}</div>
                        <div> - Última atualização: {(datetime.fromisoformat(row['dt_inference'].replace('Z','')) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')}</div>
                    </div>""",
                unsafe_allow_html=True
            )

st.markdown('<br><h4>Bacia Tamanduateí Central(24h)</h4>',unsafe_allow_html=True)

for idx, row in st.session_state.df.iterrows():
    if row['regiao'] == 'TAMCENTRAL':

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
                        <div style='margin-left: 20px;'>Possibilidade de Alagamento ou Inundação : {row['valor']*100:.1f}% </div>
                        <div> - Modelo: {row['model']}</div>
                        <div> - Última atualização: {(datetime.fromisoformat(row['dt_inference'].replace('Z','')) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')}</div>
                    </div>""",
                unsafe_allow_html=True
            )

st.markdown('<br><h4>Bacia dos Meninos(24h)</h4>',unsafe_allow_html=True)

for idx, row in st.session_state.df.iterrows():
    if row['regiao'] == 'MENINOS':

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
                        <div style='margin-left: 20px;'>Possibilidade de Alagamento ou Inundação : {row['valor']*100:.1f}% </div>
                        <div> - Modelo: {row['model']}</div>
                        <div> - Última atualização: {(datetime.fromisoformat(row['dt_inference'].replace('Z','')) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')}</div>
                    </div>""",
                unsafe_allow_html=True
            )

# with col2:
st.markdown('<br><h4>Bacia do Oratório(24h)</h4>',unsafe_allow_html=True)

for idx, row in st.session_state.df.iterrows():
    if row['regiao'] == 'ORATORIO':

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
                        <div style='margin-left: 20px;'>Possibilidade de Alagamento ou Inundação : {row['valor']*100:.1f}% </div>
                        <div> - Modelo: {row['model']}</div>
                        <div> - Última atualização: {(datetime.fromisoformat(row['dt_inference'].replace('Z','')) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')}</div>
                    </div>""",
                unsafe_allow_html=True
            )

st.markdown('<br><h4>Sub-bacia do Guarará(24h)</h4>',unsafe_allow_html=True)

for idx, row in st.session_state.df.iterrows():
    if row['regiao'] == 'GUARARA':

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
                        <div style='margin-left: 20px;'>Possibilidade de Alagamento ou Inundação : {row['valor']*100:.1f}% </div>
                        <div> - Modelo: {row['model']}</div>
                        <div> - Última atualização: {(datetime.fromisoformat(row['dt_inference'].replace('Z','')) - timedelta(hours=3)).strftime('%d/%m/%Y %H:%M')}</div>
                    </div>""",
                unsafe_allow_html=True
            )

        
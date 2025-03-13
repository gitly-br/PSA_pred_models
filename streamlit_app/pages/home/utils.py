import streamlit as st
import plotly.graph_objects as go
from streamlit_theme import st_theme

week_day_portuguese = {
    0: 'Segunda-feira',
    1: 'Terça-feira',
    2: 'Quarta-feira',
    3: 'Quinta-feira',
    4: 'Sexta-feira',
    5: 'Sábado',
    6: 'Domingo'
}

# Define as cores com base nos dados
def get_color(value):
    if value is None:
        return (0, 0, 0, 0)
    if value < 0.45:
        return (182, 226, 161, abs(value - 0.5) + 0.4)
    elif 0.45 <= value < 0.75 :
        return (235, 189, 23, 255)
    else :
        return (253, 138, 138, 255)
    
def get_map_color(value):
    if value is None:
        return "white"
    if value == "TAMCENTRAL":
        return "#1676ba"
    elif value == "GUARARA":
        return "#3607b8"
    elif value == "ORATORIO":
        return "blue"
    elif value == "MENINOS":
        return "#b63eed"
    else:
        return "white"

def get_map_color_rgba(value):
    if value is None:
        return "white"
    if value == "TAMCENTRAL":
        return "rgba(22, 118, 186, 0.2)"
    elif value == "GUARARA":
        return "rgba(54, 7, 184, 0.2)"
    elif value == "ORATORIO":
        return "rgba(0, 0, 255, 0.2)"
    elif value == "MENINOS":
        return "rgba(182, 62, 237, 0.2)"
    else:
        return "white"

def get_flood_color(value):
    if value is None:
        return "white"
    if value >= 0.75:
        return "red"
    elif 0.75 > value >= 0.45:
        return "orange"
    else:
        return "#31993a"


def plot_gauge(value, title, model: str ,margin_dict:dict = {'l':10, 'b':20, 't':50}):
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        number={'valueformat': '.0%', 'font' : {'color' : 'black' if st.session_state.tema['base'] == 'light' else 'white'}},  # Adiciona o símbolo de porcentagem
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font' : {'color' : 'black' if st.session_state.tema['base'] == 'light' else 'white'}},
        gauge = {
            'axis': {'range': [None, 1], 'tickformat': ".0%", 'tickfont' : {'color' : 'black' if st.session_state.tema['base'] == 'light' else 'white'}},
            'bar': {'color': get_flood_color(value), 'thickness': 1, 'line' : {'width' : 1}},
            'bgcolor' : 'white' if st.session_state.tema['base'] == 'light' else 'black',
            
        }
    ))
    config = {'displayModeBar': False,'paper_bgcolor' : get_map_color_rgba(model)}

    fig.update_layout(paper_bgcolor = get_map_color_rgba(model), margin_autoexpand=True)
    fig.update_layout(
        height=140,  # Altura
        margin=margin_dict,  # Margens menores
    )
    st.plotly_chart(fig, use_container_width=True, **{'config':config})
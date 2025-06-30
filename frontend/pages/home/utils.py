import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

phenomenon_portuguese = {
    'temp': 'temperatura',
    'pressure': 'pressão atmosférica',
    'humidity': 'umidade',
    'wind_speed': 'velocidade do Vento',
    'rain': 'chuva',
    'clouds': 'nuvens'
}

measure_portuguese = {
    'mean': 'média',
    'min': 'mínimo',
    'max': 'máximo',
    'delta': 'variação'
}


def get_rain_distribution(models_summary):
    rain_distribution = models_summary["rain_today"]
    return rain_distribution

# Define as cores com base nos dados
def get_color(value, alpha=1):
    if value is None:
        return (0, 0, 0, 0)
    if value < 0.45:
        return (182, 226, 161, alpha)
    elif 0.45 <= value < 0.75 :
        return (235, 189, 23, alpha)
    else :
        return (253, 138, 138, alpha)
    
def get_color_distribution(proba, rain_distribution):
    rain_colors = {}
    max_value = max(rain_distribution.values())

    for key, value in rain_distribution.items():
        if value < 0.45:
            rain_colors[key] = (182, 226, 161, 1)
        elif 0.45 <= value < 0.75:
            rain_colors[key] = (235, 189, 23, 1)
        else:
            rain_colors[key] = (253, 138, 138, 1)
    
    return rain_colors
    
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


def plot_gauge(value, title, model: str ,margin_dict:dict = {'l':10, 'b':20, 't':50}, is_rain: bool = False):
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value if is_rain else 0,
        number={'valueformat': '.0%', 'font' : {'color' : 'black' if st.session_state.tema['base'] == 'light' else 'white'}},  # Adiciona o símbolo de porcentagem
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font' : {'color' : 'black' if st.session_state.tema['base'] == 'light' else 'white'}},
        gauge = {
            'axis': {'range': [None, 1], 'tickformat': ".0%", 'tickfont' : {'color' : 'black' if st.session_state.tema['base'] == 'light' else 'white'}},
            'bar': {'color': get_flood_color(value) if is_rain else "grey", 'thickness': 1, 'line' : {'width' : 1}},
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





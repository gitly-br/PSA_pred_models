import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from streamlit_theme import st_theme
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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

PERIOD_KEYS = ("night", "morning", "afternoon", "evening")


def validate_probability(value):
    if value is None:
        return None
    try:
        probability = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= probability <= 1.0:
        return probability
    return None


def format_probability(value):
    probability = validate_probability(value)
    if probability is None:
        return "contrato inválido"
    return f"{probability * 100:.0f}%"


def collect_probability_contract_errors(payloads):
    errors = []
    for label, payload in payloads:
        if not payload:
            continue
        value = payload.get("proba")
        if value is not None and validate_probability(value) is None:
            errors.append(f"{label}.proba={value!r}")
    return errors


def get_period_rain_distribution(hourly_data):
    distribution = {key: 0.0 for key in PERIOD_KEYS}
    sao_paulo_tz = ZoneInfo("America/Sao_Paulo")
    if not isinstance(hourly_data, (list, tuple)):
        return distribution

    for index, hour_data in enumerate(hourly_data[:24]):
        if not isinstance(hour_data, dict):
            continue
        try:
            rain = float(hour_data.get("rain") or hour_data.get("precipitation_mm") or 0.0)
        except (TypeError, ValueError):
            rain = 0.0

        if "dt" in hour_data:
            try:
                hour = datetime.fromtimestamp(float(hour_data["dt"]), timezone.utc).astimezone(sao_paulo_tz).hour
            except (TypeError, ValueError, OSError):
                hour = index
        else:
            hour = index

        if hour < 6:
            distribution["night"] += rain
        elif hour < 12:
            distribution["morning"] += rain
        elif hour < 18:
            distribution["afternoon"] += rain
        else:
            distribution["evening"] += rain

    return distribution

# Define as cores com base nos dados
def get_color(value, alpha=1):
    value = validate_probability(value)
    if value is None:
        return (0, 0, 0, 0)
    if value < 0.25:
        return (182, 226, 161, alpha)
    elif 0.25 <= value < 0.5:
        return (235, 189, 23, alpha)
    else :
        return (253, 138, 138, alpha)
    
def get_color_distribution(rain_distribution):
    rain_color_distribution = rain_distribution.copy()
    for key, value in rain_color_distribution.items():
        if value < 5.0:
            rain_color_distribution[key] = (182, 226, 161, 1)
        elif 5.0 <= value < 10.0:
            rain_color_distribution[key] = (235, 189, 23, 1)
        else:
            rain_color_distribution[key] = (253, 138, 138, 1)
    
    return rain_color_distribution
    
def get_map_color(value):
    if value is None:
        return "white"
    if value == "tamanduatei":
        return "#1676ba"
    elif value == "guarara":
        return "#3607b8"
    elif value == "oratorio":
        return "blue"
    elif value == "meninos":
        return "#b63eed"
    else:
        return "white"

def get_map_color_rgba(value):
    if value is None:
        return "white"
    if value == "tamanduatei":
        return "rgba(22, 118, 186, 0.2)"
    elif value == "guarara":
        return "rgba(54, 7, 184, 0.2)"
    elif value == "oratorio":
        return "rgba(0, 0, 255, 0.2)"
    elif value == "meninos":
        return "rgba(182, 62, 237, 0.2)"
    else:
        return "white"

def get_flood_color(value):
    value = validate_probability(value)
    if value is None:
        return "grey"
    if value >= 0.5:
        return "red"
    elif 0.5 > value >= 0.25:
        return "orange"
    else:
        return "#31993a"


def plot_gauge(value, title, model: str ,margin_dict:dict = {'l':10, 'b':20, 't':50}):
    value = validate_probability(value)
    
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = value,
        number={'valueformat': '.0%', 'font' : {'color' : 'black'}},  # Adiciona o símbolo de porcentagem
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': title, 'font' : {'color' : 'black'}},
        gauge = {
            'axis': {'range': [None, 1], 'tickformat': ".0%", 'tickfont' : {'color' : 'black'}},
            'bar': {'color': get_flood_color(value) if value else "grey", 'thickness': 1, 'line' : {'width' : 1}},
            'bgcolor' : 'white',
            
        }
    ))
#    fig = go.Figure(go.Indicator(
#        mode = "gauge+number",
#        value = value if is_rain else 0,
#        number={'valueformat': '.0%', 'font' : {'color' : 'black' if st.session_state.tema['base'] == 'light' else 'white'}},  # Adiciona o símbolo de porcentagem
#        domain = {'x': [0, 1], 'y': [0, 1]},
#        title = {'text': title, 'font' : {'color' : 'black' if st.session_state.tema['base'] == 'light' else 'white'}},
#        gauge = {
#            'axis': {'range': [None, 1], 'tickformat': ".0%", 'tickfont' : {'color' : 'black' if st.session_state.tema['base'] == 'light' else 'white'}},
#            'bar': {'color': get_flood_color(value) if is_rain else "grey", 'thickness': 1, 'line' : {'width' : 1}},
#            'bgcolor' : 'white' if st.session_state.tema['base'] == 'light' else 'black',
#            
#        }
#    ))
    config = {'displayModeBar': False,'paper_bgcolor' : get_map_color_rgba(model)}

    fig.update_layout(paper_bgcolor = get_map_color_rgba(model), margin_autoexpand=True)
    fig.update_layout(
        height=140,  # Altura
        margin=margin_dict,  # Margens menores
    )
    st.plotly_chart(fig, use_container_width=True, **{'config':config})



def plot_weather_forecast(hourly_data):
    # Transforma o JSON em DataFrame
    for i in range(len(hourly_data)):
        hourly_data[i]["dt_label"] = f"{i:02}h"
    df_hourly = pd.DataFrame(hourly_data).head(24)

    df_hourly['pop'] = df_hourly['pop'].astype('float')
    df_hourly['normalized_pop'] = df_hourly['pop'] * df_hourly['rain'].max()

    # Criando a figura com eixo Y secundário
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Adicionando a chuva como barra
    fig.add_trace(
        go.Bar(
            x=df_hourly["dt_label"],
            y=df_hourly["rain"],
            name="Precipitação horária",
            # marker_color=,
            marker={"color" : 'rgba(0, 0, 255, 0.5)'},
            hovertemplate="<b>Precipitação:</b> %{y:.1f} mm<extra></extra>",
            text=df_hourly["pop"].astype(str) + "%<br>" + df_hourly["rain"].astype(str) + " mm",  # Exibe o valor numérico
            textposition="outside",  # Posiciona o texto acima da barra
            texttemplate="%{text}",
        ),
        secondary_y=True,
    )

    # Adicionando a temperatura como Scatter
    fig.add_trace(
        go.Scatter(
            x=df_hourly["dt_label"],  
            y=df_hourly["temp"],
            name="Temperatura",
            mode='lines+markers+text',  # Adicionando o texto diretamente no Scatter
            hovertemplate="<b>Temperatura:</b> %{y:.1f}°C <extra></extra>",
            text=df_hourly["temp"],  # Exibe o valor numérico
            textposition="top center",  # Posiciona o texto acima
            texttemplate="%{text:.1f}°C",  # Formato do texto
            marker=dict(size=8, color='red'),  # Para destacar melhor
            line=dict(width=2, color='red'),  # Linha vermelha para destacar
        ),
        secondary_y=False,
    )


    # Configurando eixos Y
    fig.update_yaxes(title_text="<b>Temperatura (°C)</b>", secondary_y=False, range=[df_hourly["temp"].min() - 2, df_hourly["temp"].max() + 2])  # Dynamic Range
    fig.update_yaxes(title_text="<b>Volume de chuva (mm)</b>", secondary_y=True, range=[0, df_hourly["rain"].max() * 1.2], showgrid=False)  # Dynamic Range

    # Configuração final do layout
    fig.update_layout(
        title_text="Previsão do Tempo <br><sup>Dados fornecidos por OpenWeather</sup>",
        barmode='group',  # Barras agrupadas lado a lado
        hovermode="x unified",  # Melhora a interação no hover
        xaxis=dict(
            title="<b></b>",
            tickangle=0,  # rotulo na horizontal
            tickmode="array",
            tickvals=df_hourly["dt_label"],
            ticktext=df_hourly["dt_label"]
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

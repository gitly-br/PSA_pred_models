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


def get_shap_importance(region_models) -> str:
    most_important = ''
    most_important_value = 0

    for model in region_models:
        if model['result'].get('shap') is not None:
            for value, feature in model['result']['shap']:
                if abs(value) > most_important_value:
                    most_important = feature
                    most_important_value = abs(value)

    features = most_important.split('_')
    phenomenon = features[0].lower()
    measure = features[-1].lower()

    return f'A "{measure_portuguese[measure]} de {phenomenon_portuguese[phenomenon]}" é a variável que mais influenciou esta precição'


def get_rain_distribution(models_summary):
    rain_distribution = models_summary["SA"]["time_of_day"]
    print(rain_distribution)
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
        if value < 45:
            rain_colors[key] = (182, 226, 161, 1)
        elif 45 <= value < 75:
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



def plot_weather_forecast(df_json):

    # Transforma o JSON em DataFrame
    df_aux = pd.DataFrame(df_json)

    # Seleciona os primeiros 24 registros e ordena pelo campo 'dt' em ordem crescente
    df = df_aux.sort_values(by="dt").head(9)
    df['pop'] = df['pop'].astype('float')
    df['normalized_pop'] = df['pop'] * df['rain_3h'].max()

    # Criando a figura com eixo Y secundário
    fig = make_subplots(specs=[[{"secondary_y": True}]])


    # Adicionando a chuva como barra
    fig.add_trace(
        go.Bar(
            x=df["dt_label"],
            y=df["rain_3h"],
            name="Chuva acum. 3h",
            # marker_color=,
            marker={"color" : 'rgba(0, 0, 255, 0.5)'},
            hovertemplate="<b>Chuva acum. 3h:</b> %{y:.1f} mm<extra></extra>",
            text=df["pop_percent"].astype(str) + "%<br>" + df["rain_3h"].astype(str) + " mm",  # Exibe o valor numérico
            textposition="outside",  # Posiciona o texto acima da barra
            texttemplate="%{text}",
        ),
        secondary_y=True,
    )

    # Adicionando a probabilidade de precipitação como uma barra mais fina
    # fig.add_trace(
    #     go.Bar(
    #         x=df["dt_label"],
    #         y=df["normalized_pop"],
    #         name="Probabilidade de chuva",
    #         marker={"color" : 'rgba(0, 0, 255, 0.2)'},
    #         hovertemplate="<b>Probabilidade de chuva:</b> %{text}<extra></extra>",
    #         text=df["pop_percent"].astype(str)+"%",  # Exibe o valor numérico
    #         textposition="outside",  # Posiciona o texto acima da barra
    #     ),
    #     secondary_y=True,
    # )

    # Adicionando a temperatura como Scatter
    fig.add_trace(
        go.Scattergl(
            x=df["dt_label"],  
            y=df["temp"],
            name="Temperatura",
            mode='lines+markers+text',  # Adicionando o texto diretamente no Scatter
            hovertemplate="<b>Temperatura:</b> %{y:.1f}°C <extra></extra>",
            text=df["temp"],  # Exibe o valor numérico
            textposition="top center",  # Posiciona o texto acima
            texttemplate="%{text:.1f}°C",  # Formato do texto
            marker=dict(size=8, color='red'),  # Para destacar melhor
            line=dict(width=2, color='red'),  # Linha vermelha para destacar
        ),
        secondary_y=False,
    )


    # Configurando eixos Y
    fig.update_yaxes(title_text="<b>Temperatura (°C)</b>", secondary_y=False, range=[df["temp"].min() - 2, df["temp"].max() + 2])  # Dynamic Range
    fig.update_yaxes(title_text="<b>Volume de chuva (mm)</b>", secondary_y=True, range=[0, df["rain_3h"].max() * 1.2])  # Dynamic Range

    # Configuração final do layout
    fig.update_layout(
        title_text="Previsão do Tempo <br><sup>Dados fornecidos por OpenWeather</sup>",
        barmode='group',  # Barras agrupadas lado a lado
        hovermode="x unified",  # Melhora a interação no hover
        xaxis=dict(
            title="<b></b>",
            tickangle=0,  # rotulo na horizontal
            tickmode="array",
            tickvals=df["dt_label"],
            ticktext=df["dt_label"]
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

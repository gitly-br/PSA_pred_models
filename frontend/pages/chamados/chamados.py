import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval
# components.iframe(
#     "https://app.powerbi.com/view?r=eyJrIjoiMTVhZjNkZTAtNDY1OS00MDEwLTk1NWYtNDk5ZTBlZDYxMzY4IiwidCI6ImUwM2ZhYzdmLTdhOTktNDdhMS1hYTY5LTAzMmFjNDg4ZTcxNCJ9",
#     scrolling=False,
#     height=750,
# )

height = streamlit_js_eval(js_expressions='screen.height', key = 'SCR')

st.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 0rem;
                    padding-left: 5rem;
                    padding-right: 5rem;
                }
        </style>
        """, unsafe_allow_html=True)

components.iframe(
    "https://app.powerbi.com/view?r=eyJrIjoiYzg4YmFjYWEtNzVjNi00NDNmLThkYmMtNGVlNWNlNzJkN2ZiIiwidCI6ImUwM2ZhYzdmLTdhOTktNDdhMS1hYTY5LTAzMmFjNDg4ZTcxNCJ9",
    scrolling=False,
    height=int(height * 0.75),
)

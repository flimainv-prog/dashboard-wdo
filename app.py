import streamlit as st
import pandas as pd
from datetime import time
import base64
from pathlib import Path
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

from tab_grafico import render_grafico
from tab_backtest import render_backtest
from tab_heatmap import render_heatmap

from helpers import (
    BRT, gerar_dias_uteis, fetch_di_variacao, checar_e_enviar_alerta_di,
    VERDE_TICKERS, VERMELHA_TICKERS, ativos, fetch_mxn_brl, ultimo_candle_real
)

st.set_page_config(page_title="Trend Axis WDO", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

bg_file = Path(__file__).with_name("fundo.png")
if bg_file.exists():
    try:
        with open(bg_file, "rb") as img_file:
            img_b64 = base64.b64encode(img_file.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{ background: transparent !important; }}
            .stApp::before {{
                content: ""; position: fixed; inset: 0;
                background-image: url("data:image/png;base64,{img_b64}");
                background-repeat: no-repeat; background-position: center center;
                background-size: cover; filter: blur(10px) brightness(0.3);
                z-index: -1; pointer-events: none;
            }}
            </style>
            """, unsafe_allow_html=True
        )
    except Exception:
        pass

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Orbitron:wght@700&display=swap');
* { font-family: 'Inter', sans-serif; }
[data-testid="stStatusWidget"] { visibility: hidden !important; }
.block-container { padding-top: 1rem !important; margin-top: -4rem !important; padding-bottom: 0px !important; margin-bottom: 0px !important; max-width: 100% !important; padding-left: 2rem !important; padding-right: 2rem !important; }
[data-testid="stSidebar"] { display: flex !important; visibility: visible !important; opacity: 1 !important; transform: none !important; min-width: 170px !important; max-width: 170px !important; width: 170px !important; background-color: rgba(11, 15, 25, 0.7) !important; backdrop-filter: blur(12px); border-right: 1px solid rgba(255,255,255,0.05); }
[data-testid="stSidebar"][aria-expanded="false"] { display: flex !important; visibility: visible !important; opacity: 1 !important; transform: none !important; min-width: 170px !important; max-width: 170px !important; width: 170px !important; }
[data-testid="collapsedControl"] { display: block !important; visibility: visible !important; opacity: 1 !important; }
[data-testid="stSidebar"] label p { font-size: 11px !important; color: #94A3B8 !important; margin-bottom: -5px !important; }
[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stTimeInput { margin-bottom: -5px !important; }
[data-testid="stSidebar"] .stButton > button { font-size: 11px !important; font-weight: 600 !important; padding: 4px 8px !important; border-radius: 6px !important; background: rgba(16, 185, 129, 0.15) !important; border: 1px solid rgba(16, 185, 129, 0.4) !important; color: #10B981 !important; transition: 0.3s; margin-top: 5px; }
[data-testid="stSidebar"] .stButton > button:hover { background: rgba(16, 185, 129, 0.3) !important; border: 1px solid #10B981 !important; color: #ffffff !important; }
#MainMenu {visibility: hidden;} header {visibility: hidden;}
.stTabs [data-baseweb="tab-list"] { gap: 10px; margin-bottom: -5px; margin-top: -15px; }
.stTabs [data-baseweb="tab"] { padding-top: 0px; padding-bottom: 5px; }
.modern-title { font-family: 'Orbitron', sans-serif; font-size: 2.0rem; background: -webkit-linear-gradient(45deg, #38BDF8, #10B981); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: -15px; margin-top: 0px; text-transform: uppercase; letter-spacing: 2px; }
.title-date { font-family: 'Inter', sans-serif; font-size: 2.0rem; color: #94A3B8; -webkit-text-fill-color: #94A3B8; letter-spacing: 0px; text-transform: none; }
.prob-box { background-color: rgba(15, 23, 42, 0.7); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 6px 15px; display: flex; width: 100%; align-items: center; }
.di-alerta-1 { border-right: 2px solid rgba(255,255,255,0.1); padding-right: 15px; margin-right: 15px; animation: blink-yellow 2s infinite; }
.di-alerta-2 { border-right: 2px solid rgba(255,255,255,0.1); padding-right: 15px; margin-right: 15px; animation: blink-red 1s infinite; }
.leilao-box { background-color: rgba(15, 23, 42, 0.7); border-left: 4px solid #F59E0B; padding: 5px 15px; margin-bottom: 5px; }
.leilao-pulse { animation: pulse 2s infinite; }
@keyframes pulse { 0% { opacity: 0.8; } 50% { opacity: 1; } 100% { opacity: 0.8; } }
.bt-card { background-color: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
.bt-card-title { color: #94A3B8; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }
.bt-card-value { color: #F8FAFC; font-size: 28px; font-weight: bold; font-family: 'Orbitron', sans-serif; }
.bt-win { color: #10B981; }
.bt-loss { color: #EF4444; }
.stPlotlyChart > div { height: 70vh !important; min-height: 400px !important; }
.stPlotlyChart > div > div { height: 100% !important; }
.js-plotly-plot, .js-plotly-plot .plot-container { height: 100% !important; }
.js-plotly-plot .svg-container { height: 100% !important; }
@media (max-width: 768px) { .stPlotlyChart > div { height: 60vh !important; min-height: 300px !important; } }
</style>
""", unsafe_allow_html=True)

st_autorefresh(interval=60000, key="data_refresh")
datas_disponiveis = gerar_dias_uteis()

with st.spinner(""):
    di_34 = fetch_di_variacao("BMFBOVESPA:DI1F2034", "DI1F34")
    di_35 = fetch_di_variacao("BMFBOVESPA:DI1F2035", "DI1F35")

cor_34 = "#10B981" if di_34 >= 0 else "#EF4444"
cor_35 = "#10B981" if di_35 >= 0 else "#EF4444"

st.markdown("""
<style>
    div[data-testid="column"] { display: flex; flex-direction: column; justify-content: center; }
</style>
""", unsafe_allow_html=True)

c_tit, c_fd1, c_di34, c_di35, c_dados = st.columns([2.5, 1.2, 0.8, 0.8, 4.5])

with c_tit:
    st.markdown(f"""
    <h1 class='modern-title' style='text-align: left; display: flex; align-items: center; margin-top: 0px; padding-top: 0px; font-size: 2.5rem;'>
        TREND AXIS
        <span id='digital-clock' class='title-date' style='margin-left: 15px; font-size: 1.5rem; color: #94A3B8;'>| --:--:--</span>
    </h1>
    """, unsafe_allow_html=True)

with c_fd1:
    with st.popover("📅 Período", use_container_width=True):
        start_date = st.selectbox(
            "📅 Início",
            options=datas_disponiveis,
            format_func=lambda d: "Hoje" if str(d) == str(pd.Timestamp.now(tz=BRT).date()) else pd.to_datetime(d).strftime("%d/%m/%y"),
            index=0
        )
        start_time = st.time_input("🕐 Hora Início", value=time(0, 0))
        st.markdown("<hr style='margin: 10px 0px; opacity: 0.2;'>", unsafe_allow_html=True)
        end_date = st.selectbox(
            "📅 Fim",
            options=datas_disponiveis,
            format_func=lambda d: "Hoje" if str(d) == str(pd.Timestamp.now(tz=BRT).date()) else pd.to_datetime(d).strftime("%d/%m/%y"),
            index=0
        )
        end_time = st.time_input("🕐 Hora Fim", value=time(23, 59))

animacao_34 = checar_e_enviar_alerta_di("DI34", di_34)
animacao_35 = checar_e_enviar_alerta_di("DI35", di_35)

with c_di34:
    st.markdown(f"""
    <div style='text-align: center; background-color: #1E293B; padding: 10px; border-radius: 8px; {animacao_34}'>
        <div style='color: #94A3B8; font-size: 12px; font-weight: 600;'>DI1F34</div>
        <div style='color: {cor_34}; font-size: 18px; font-weight: bold;'>{di_34:+.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

with c_di35:
    st.markdown(f"""
    <div style='text-align: center; background-color: #1E293B; padding: 10px; border-radius: 8px; {animacao_35}'>
        <div style='color: #94A3B8; font-size: 12px; font-weight: 600;'>DI1F35</div>
        <div style='color: {cor_35}; font-size: 18px; font-weight: bold;'>{di_35:+.2f}%</div>
    </div>
    """, unsafe_allow_html=True)

placeholder_dados = c_dados.empty()

start_dt = pd.Timestamp(f"{start_date} {start_time}").tz_localize(BRT)
end_dt = pd.Timestamp(f"{end_date} {end_time}").tz_localize(BRT)

if start_dt > end_dt:
    start_dt, end_dt = end_dt, start_dt

# --- RELÓGIO JS E AUTO-REFRESH ---
components.html("""
<script>
function updateClock() {
    const now = new Date();
    const options = {
        timeZone: 'America/Sao_Paulo',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    };
    const timeString = now.toLocaleTimeString('pt-BR', options);
    const clockElement = window.parent.document.querySelector('#digital-clock');
    if (clockElement) {
        clockElement.innerText = '| ' + timeString;
    }
}
setInterval(updateClock, 1000);
updateClock();

// CORREÇÃO: Auto-refresh nativo a cada 60 segundos (substitui a biblioteca com erro)
setTimeout(function(){
    window.parent.location.reload();
}, 60000);
</script>
""", height=0)

tab1, tab2, tab3 = st.tabs(["📈 Gráfico", "🎯 Backtest de Correlação", "🔥 Mapa de Calor Abertura"])

with tab1:
    render_grafico(start_dt, end_dt, placeholder_dados)

with tab2:
    render_backtest(start_dt, end_dt)

with tab3:
    render_heatmap(start_dt, end_dt)

def main():
    pass

if __name__ == "__main__":
    main()

# app.py
import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, time
import time as time_mod
import pytz
import base64
import os
import glob
import requests
import re
import urllib.request
import json
import streamlit.components.v1 as components
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import datetime

# --- ABAS ---
from tab_grafico import render_grafico
from tab_backtest import render_backtest
from tab_heatmap import render_heatmap

# --- HELPERS ---
from helpers import (
    VERDE_TICKERS, VERMELHA_TICKERS, TODOS_TICKERS, BRT,
    get_historico_base, get_dados_recentes, ativos, fetch_mxn_brl,
    gerar_dias_uteis, ultimo_candle_real, fetch_di_variacao, checar_e_enviar_alerta_di
)

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Trend Axis WDO",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. SISTEMA DE BACKGROUND E OCULTAÇÃO DO "RUNNING" ---
bg_file = Path(__file__).with_name("fundo.png")
if bg_file.exists():
    try:
        with open(bg_file, "rb") as img_file:
            img_b64 = base64.b64encode(img_file.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: transparent !important;
            }}
            .stApp::before {{
                content: "";
                position: fixed;
                inset: 0;
                background-image: url("data:image/png;base64,{img_b64}");
                background-repeat: no-repeat;
                background-position: center center;
                background-size: cover;
                filter: blur(10px) brightness(0.3);
                z-index: -1;
                pointer-events: none;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    except Exception:
        pass

# --- 3. CSS AVANÇADO E COMPACTAÇÃO ---
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Orbitron:wght@700&display=swap');
* {{ font-family: 'Inter', sans-serif; }}
[data-testid="stStatusWidget"] {{ visibility: hidden !important; }}
.block-container {{
    padding-top: 1rem !important;
    margin-top: -4rem !important;
    padding-bottom: 0px !important;
    margin-bottom: 0px !important;
    max-width: 100% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}}
[data-testid="stSidebar"] {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    transform: none !important;
    min-width: 170px !important;
    max-width: 170px !important;
    width: 170px !important;
    background-color: rgba(11, 15, 25, 0.7) !important;
    backdrop-filter: blur(12px);
    border-right: 1px solid rgba(255,255,255,0.05);
}}
[data-testid="stSidebar"][aria-expanded="false"] {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    transform: none !important;
    min-width: 170px !important;
    max-width: 170px !important;
    width: 170px !important;
}}
[data-testid="collapsedControl"] {{
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
}}
[data-testid="stSidebar"] label p {{ font-size: 11px !important; color: #94A3B8 !important; margin-bottom: -5px !important; }}
[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stTimeInput {{ margin-bottom: -5px !important; }}
[data-testid="stSidebar"] .stButton > button {{
    font-size: 11px !important; font-weight: 600 !important; padding: 4px 8px !important;
    border-radius: 6px !important; background: rgba(16, 185, 129, 0.15) !important;
    border: 1px solid rgba(16, 185, 129, 0.4) !important; color: #10B981 !important;
    transition: 0.3s; margin-top: 5px;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(16, 185, 129, 0.3) !important;
    border: 1px solid #10B981 !important;
    color: #ffffff !important;
}}
#MainMenu {{visibility: hidden;}} header {{visibility: hidden;}}
.stTabs [data-baseweb="tab-list"] {{ gap: 10px; margin-bottom: -5px; margin-top: -15px; }}
.stTabs [data-baseweb="tab"] {{ padding-top: 0px; padding-bottom: 5px; }}
.modern-title {{ font-family: 'Orbitron', sans-serif; font-size: 2.0rem; background: -webkit-linear-gradient(45deg, #38BDF8, #10B981); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: -15px; margin-top: 0px; text-transform: uppercase; letter-spacing: 2px; }}
.title-date {{ font-family: 'Inter', sans-serif; font-size: 2.0rem; color: #94A3B8; -webkit-text-fill-color: #94A3B8; letter-spacing: 0px; text-transform: none; }}
.prob-box {{ background-color: rgba(15, 23, 42, 0.7); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 6px 15px; display: flex; width: 100%; align-items: center; margin-top: -10px; margin-bottom: 5px; }}
@keyframes blink-yellow {{ 0% {{ opacity: 1; box-shadow: 0 0 5px #F59E0B; }} 50% {{ opacity: 0.5; box-shadow: none; }} 100% {{ opacity: 1; box-shadow: 0 0 5px #F59E0B; }} }}
@keyframes blink-red {{ 0% {{ opacity: 1; box-shadow: 0 0 15px #EF4444; transform: scale(1); }} 50% {{ opacity: 0.7; box-shadow: none; transform: scale(0.98); }} 100% {{ opacity: 1; box-shadow: 0 0 15px #EF4444; transform: scale(1); }} }}
.di-alerta-1 {{ border-right: 2px solid rgba(255,255,255,0.1); padding-right: 15px; margin-right: 15px; animation: blink-yellow 2s infinite; }}
.di-alerta-2 {{ border-right: 2px solid rgba(255,255,255,0.1); padding-right: 15px; margin-right: 15px; animation: blink-red 1s infinite; }}
.leilao-box {{ background-color: rgba(15, 23, 42, 0.7); border-left: 4px solid #F59E0B; padding: 5px 15px; margin-bottom: 5px; }}
.leilao-pulse {{ animation: pulse 2s infinite; }}
@keyframes pulse {{ 0% {{ opacity: 0.8; }} 50% {{ opacity: 1; }} 100% {{ opacity: 0.8; }} }}
.bt-card {{ background-color: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
.bt-card-title {{ color: #94A3B8; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 5px; }}
.bt-card-value {{ color: #F8FAFC; font-size: 28px; font-weight: bold; font-family: 'Orbitron', sans-serif; }}
.bt-win {{ color: #10B981; }}
.bt-loss {{ color: #EF4444; }}
.stPlotlyChart > div {{ height: 70vh !important; min-height: 400px !important; }}
.stPlotlyChart > div > div {{ height: 100% !important; }}
.js-plotly-plot, .js-plotly-plot .plot-container {{ height: 100% !important; }}
.js-plotly-plot .svg-container {{ height: 100% !important; }}
@media (max-width: 768px) {{
    .stPlotlyChart > div {{ height: 60vh !important; min-height: 300px !important; }}
}}
</style>
""", unsafe_allow_html=True)

# --- 4. CESTAS GLOBAIS ---
VERDE_TICKERS = ['DX-Y.NYB', 'GC=F', 'SI=F', '^TNX', '^FVX', '^IRX', 'ZB=F', 'USDCAD=X', 'USDJPY=X', 'USDCHF=X', 'USDSEK=X', 'USDMXN=X', 'USDZAR=X', 'USDTRY=X', 'CL=F', 'NG=F']
VERMELHA_TICKERS = ['SPY', 'QQQ', 'EWZ', 'EEM', 'GLD', 'TLT', 'EURUSD=X', 'GBPUSD=X', 'AUDUSD=X', 'NZDUSD=X', '^GSPC', '^IXIC', '^BVSP', '^HSI', '^N225', '^FTSE', 'HG=F', 'BTC-USD']
TODOS_TICKERS = list(set(VERDE_TICKERS + VERMELHA_TICKERS + ['USDMXN=X', 'USDBRL=X']))
EMAIL_REMETENTE = "nois.rco@gmail.com"
SENHA_APP = ".Lj0882*"
EMAIL_DESTINO = "flima.jur@gmail.com"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

@st.cache_data(ttl=3600, max_entries=1)
def get_historico_base():
    agora = pd.Timestamp.now(tz=BRT)
    str_start = (agora - timedelta(days=22)).strftime('%Y-%m-%d')
    str_end = agora.strftime('%Y-%m-%d')
    try:
        raw = yf.download(TODOS_TICKERS, start=str_start, end=str_end, interval="5m", progress=False, group_by='ticker', threads=False)
        if not raw.empty and isinstance(raw.columns, pd.MultiIndex):
            raw.index = raw.index.tz_convert(BRT) if raw.index.tz is not None else raw.index.tz_localize('UTC').tz_convert(BRT)
            return raw
    except:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=60, max_entries=1, show_spinner=False)
def get_dados_recentes():
    agora = pd.Timestamp.now(tz=BRT)
    str_start = (agora - timedelta(days=2)).strftime('%Y-%m-%d')
    str_end = (agora + timedelta(days=2)).strftime('%Y-%m-%d')
    try:
        raw = yf.download(TODOS_TICKERS, start=str_start, end=str_end, interval="5m", progress=False, group_by='ticker', threads=False)
        if not raw.empty and isinstance(raw.columns, pd.MultiIndex):
            raw.index = raw.index.tz_convert(BRT) if raw.index.tz is not None else raw.index.tz_localize('UTC').tz_convert(BRT)
            return raw
    except:
        pass
    return pd.DataFrame()

def get_cached_market_data():
    hist = get_historico_base()
    rec = get_dados_recentes()
    if hist.empty:
        return rec
    if rec.empty:
        return hist
    df = pd.concat([hist, rec])
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

def get_market_data(start_dt, end_dt):
    return get_cached_market_data()

def gerar_dias_uteis():
    hoje = pd.Timestamp.now(tz=BRT).date()
    inicio_mes = pd.Timestamp(year=hoje.year, month=hoje.month, day=1).date()
    dias_uteis = pd.date_range(start=inicio_mes, end=hoje, freq='B')
    lista_dias = [dia.strftime('%Y-%m-%d') for dia in dias_uteis]
    return lista_dias[::-1]

def ultimo_candle_real():
    agora = pd.Timestamp.now(tz=BRT)
    m = agora.replace(second=0, microsecond=0)
    return m - timedelta(minutes=m.minute % 5)

def checar_e_enviar_alerta_di(*args, **kwargs):
    return None

def fetch_di_variacao(ticker_tv="BMFBOVESPA:DI1F2034", ticker_advfn="DI1F34"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        url_b3 = f"https://cotacao.b3.com.br/mds/api/v1/DerivativeQuotation/{ticker_advfn.upper()}"
        headers_b3 = headers.copy()
        headers_b3["Origin"] = "https://www.b3.com.br"
        headers_b3["Referer"] = "https://www.b3.com.br/"
        resp = requests.get(url_b3, headers=headers_b3, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            sctn = data.get("Sctn", [])
            if sctn:
                scty_qtn = sctn[0].get("Data", [])[0].get("SctyQtn", {})
                var_pts = float(scty_qtn.get("VartnPts", 0))
                prev_close = float(scty_qtn.get("PrvsDayClsPric", 1))
                if prev_close > 0:
                    pct_change = (var_pts / prev_close) * 100
                    return round(pct_change, 2)
    except:
        pass

    try:
        url_tv = "https://scanner.tradingview.com/brazil/scan"
        payload = {"symbols": {"tickers": [ticker_tv]}, "columns": ["change"]}
        resp = requests.post(url_tv, json=payload, headers=headers, timeout=4)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data and len(data[0].get("d", [])) > 0:
                val = float(data[0]["d"][0])
                if -15.0 <= val <= 15.0:
                    return round(val, 2)
    except:
        pass

    try:
        url_si = f"https://statusinvest.com.br/juros-futuros/{ticker_advfn.lower()}"
        resp = requests.get(url_si, headers=headers, timeout=4)
        if resp.status_code == 200:
            match = re.search(r'title="Variação do valor"[^>]*>([+-]?\d+(?:[.,]\d+)?)%', resp.text)
            if match:
                val = float(match.group(1).replace(',', '.'))
                if -15.0 <= val <= 15.0:
                    return round(val, 2)
    except:
        pass

    return 0.0

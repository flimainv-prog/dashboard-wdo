# helpers.py
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import pytz
import requests
import re
from pathlib import Path

BRT = pytz.timezone('America/Sao_Paulo')

VERDE_TICKERS = [
    'DX-Y.NYB', 'GC=F', 'SI=F', '^TNX', '^FVX', '^IRX', 'ZB=F',
    'USDCAD=X', 'USDJPY=X', 'USDCHF=X', 'USDSEK=X', 'USDMXN=X',
    'USDZAR=X', 'USDTRY=X', 'CL=F', 'NG=F'
]

VERMELHA_TICKERS = [
    'SPY', 'QQQ', 'EWZ', 'EEM', 'GLD', 'TLT', 'EURUSD=X', 'GBPUSD=X',
    'AUDUSD=X', 'NZDUSD=X', '^GSPC', '^IXIC', '^BVSP', '^HSI', '^N225',
    '^FTSE', 'HG=F', 'BTC-USD'
]

TODOS_TICKERS = list(set(VERDE_TICKERS + VERMELHA_TICKERS + ['USDMXN=X', 'USDBRL=X']))

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
}

@st.cache_data(ttl=3600, max_entries=1)
def get_historico_base():
    agora = pd.Timestamp.now(tz=BRT)
    str_start = (agora - timedelta(days=22)).strftime('%Y-%m-%d')
    str_end = agora.strftime('%Y-%m-%d')
    try:
        raw = yf.download(
            TODOS_TICKERS,
            start=str_start,
            end=str_end,
            interval="5m",
            progress=False,
            group_by='ticker',
            threads=False
        )
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
        raw = yf.download(
            TODOS_TICKERS,
            start=str_start,
            end=str_end,
            interval="5m",
            progress=False,
            group_by='ticker',
            threads=False
        )
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

def ativos(tickers_list, start_dt, end_dt, threshold=0.003, modo='alta'):
    raw_data = get_market_data(start_dt, end_dt)
    if raw_data.empty:
        return pd.Series(dtype=float)

    start_naive = start_dt.replace(tzinfo=None)
    end_naive = end_dt.replace(tzinfo=None)

    series_list = []
    ativos_validos = 0

    for ticker in tickers_list:
        try:
            if ticker not in raw_data.columns.levels[0]:
                continue

            ticker_df = raw_data[ticker]
            col_name = 'Close' if 'Close' in ticker_df.columns else 'close' if 'close' in ticker_df.columns else None
            if not col_name:
                continue

            s_full = ticker_df[col_name].dropna()
            if s_full.empty:
                continue

            s_full.index = s_full.index.tz_localize(None)

            s_before = s_full[s_full.index <= start_naive]
            ref_val = float(s_before.iloc[-1]) if not s_before.empty else float(s_full.iloc[0])

            s_window = s_full[(s_full.index >= start_naive) & (s_full.index <= end_naive)]
            if s_window.empty or ref_val == 0:
                continue

            s_window = s_window.resample('5min').last().dropna()
            if s_window.empty:
                continue

            s_window.index = s_window.index.tz_localize(BRT)
            series_list.append(100 * (s_window - ref_val) / abs(ref_val))
            ativos_validos += 1
        except:
            continue

    if not series_list or ativos_validos == 0:
        return pd.Series(dtype=float)

    df = pd.concat(series_list, axis=1)

    if modo == 'baixa':
        return ((df < -threshold).sum(axis=1).astype(float) / ativos_validos) * 100.0

    return ((df > threshold).sum(axis=1).astype(float) / ativos_validos) * 100.0

def fetch_mxn_brl(start_dt, end_dt):
    raw_data = get_market_data(start_dt, end_dt)

    if raw_data.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float), 0.0, 0.0

    try:
        fake_series = pd.Series(dtype=float)

        if 'USDMXN=X' not in raw_data.columns.levels[0] or 'USDBRL=X' not in raw_data.columns.levels[0]:
            return fake_series, fake_series, 1.0, 1.0

        mxn_df = raw_data['USDMXN=X']
        brl_df = raw_data['USDBRL=X']

        mxn_col = 'Close' if 'Close' in mxn_df.columns else 'close'
        brl_col = 'Close' if 'Close' in brl_df.columns else 'close'

        mxn = mxn_df[mxn_col].dropna()
        brl = brl_df[brl_col].dropna()

        if mxn.empty or brl.empty:
            return fake_series, fake_series, 1.0, 1.0

        mxn.index = mxn.index.tz_localize(None)
        brl.index = brl.index.tz_localize(None)

        start_naive = start_dt.replace(tzinfo=None)
        end_naive = end_dt.replace(tzinfo=None)
        anchor_time = start_naive.replace(hour=0, minute=0, second=0, microsecond=0)

        mxn_before = mxn[mxn.index <= anchor_time]
        mxn_ref = float(mxn_before.iloc[-1]) if not mxn_before.empty else float(mxn.iloc[0])

        brl_before = brl[brl.index <= anchor_time]
        brl_ref = float(brl_before.iloc[-1]) if not brl_before.empty else float(brl.iloc[0])

        mxn = mxn[(mxn.index >= start_naive) & (mxn.index <= end_naive)]
        brl = brl[(brl.index >= start_naive) & (brl.index <= end_naive)]

        if mxn.empty or brl.empty:
            return fake_series, fake_series, mxn_ref, brl_ref

        full_idx = pd.date_range(start_naive, end_naive, freq='5min')

        mxn_resampled = mxn.resample('5min').last().reindex(full_idx).dropna()
        brl_resampled = brl.resample('5min').last().reindex(full_idx).dropna()

        if mxn_resampled.empty or brl_resampled.empty:
            return fake_series, fake_series, mxn_ref, brl_ref

        mxn_resampled.index = mxn_resampled.index.tz_localize(BRT)
        brl_resampled.index = brl_resampled.index.tz_localize(BRT)

        return mxn_resampled, brl_resampled, mxn_ref, brl_ref

    except:
        return pd.Series(dtype=float), pd.Series(dtype=float), 0.0, 0.0

def fetch_di_variacao(ticker_tv="BMFBOVESPA:DI1F2034", ticker_advfn="DI1F34"):
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

def checar_e_enviar_alerta_di(*args, **kwargs):
    return None

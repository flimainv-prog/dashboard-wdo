import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import pytz
import requests
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
import concurrent.futures

BRT = pytz.timezone('America/Sao_Paulo')
VERDE_TICKERS = [
    'DX-Y.NYB', 'USDCAD=X', 'USDJPY=X', 'USDCHF=X', 'USDSEK=X', 
    'USDMXN=X', 'USDZAR=X', 'USDTRY=X', 
    'TLT', 'ZB=F'
]

VERMELHA_TICKERS = [
    'SPY', 'QQQ', 'EWZ', 'EEM', '^GSPC', '^IXIC', '^BVSP', '^HSI', '^N225', '^FTSE',
    'EURUSD=X', 'GBPUSD=X', 'AUDUSD=X', 'NZDUSD=X',
    'HG=F', 'CL=F', 'NG=F', 'GC=F', 'GLD', 'SI=F',
    'BTC-USD',
    '^TNX', '^FVX', '^IRX'
]
TODOS_TICKERS = list(set(VERDE_TICKERS + VERMELHA_TICKERS + ['USDMXN=X', 'USDBRL=X']))

try:
    FMP_API_KEY = st.secrets["FMP_API_KEY"]
    SENHA_APP = st.secrets["SENHA_EMAIL"]
except Exception:
    FMP_API_KEY = "9X2sZMl2ELpHgGRIPhN3asKUdzIJt0q4"
    SENHA_APP = ".Lj0882*"

EMAIL_REMETENTE = "nois.rco@gmail.com"
EMAIL_DESTINO = "flima.jur@gmail.com"

def mapear_ticker_fmp(ticker_yf):
    t = ticker_yf.upper()
    if t.endswith('=X'): return t.replace('=X', '')
    if t == 'DX-Y.NYB': return 'USDX'
    if t == 'GC=F': return 'GCUSD'
    if t == 'SI=F': return 'SIUSD'
    if t == 'CL=F': return 'CLUSD'
    if t == 'NG=F': return 'NGUSD'
    if t == 'HG=F': return 'HGUSD'
    if t == 'ZB=F': return 'ZBUSD'
    if t == 'BTC-USD': return 'BTCUSD'
    if t.startswith('^'): return t.replace('^', '%5E')
    return t

def fetch_single_ticker_fmp(ticker, interval, start_date, end_date):
    fmp_ticker = mapear_ticker_fmp(ticker)
    url = f"https://financialmodelingprep.com/api/v3/historical-chart/{interval}/{fmp_ticker}?from={start_date}&to={end_date}&apikey={FMP_API_KEY}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                df_temp = pd.DataFrame(data)
                df_temp['date'] = pd.to_datetime(df_temp['date'])
                df_temp.set_index('date', inplace=True)
                df_temp.sort_index(inplace=True)
                df_temp = df_temp.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
                
                if 'Close' in df_temp.columns:
                    df_temp = df_temp[['Open', 'High', 'Low', 'Close', 'Volume']]
                    df_temp.columns = pd.MultiIndex.from_product([[ticker], df_temp.columns])
                    df_temp.index = df_temp.index.tz_localize('America/New_York').tz_convert(BRT)
                    return df_temp
            else:
                # Mostra na tela se a API responder, mas não mandar dados
                st.sidebar.error(f"FMP retornou VAZIO para {ticker}. Verifique se o ticker {fmp_ticker} existe no FMP.")
        else:
            # Mostra na tela se a API bloquear o acesso (ex: chave inválida ou sem permissão)
            st.sidebar.error(f"Erro FMP {ticker}: HTTP {resp.status_code} - {resp.text[:100]}")
    except Exception as e:
        # Mostra na tela se der timeout ou erro de internet
        st.sidebar.error(f"Timeout/Conexão FMP para {ticker}: {e}")
    return None

def fetch_fmp_data(tickers, interval="5min", days_back=5):
    agora = pd.Timestamp.now(tz=BRT)
    start_date = (agora - timedelta(days=days_back)).strftime('%Y-%m-%d')
    end_date = (agora + timedelta(days=1)).strftime('%Y-%m-%d')
    
    df_list = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fetch_single_ticker_fmp, ticker, interval, start_date, end_date): ticker for ticker in tickers}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                df_list.append(result)
            
    if df_list:
        return pd.concat(df_list, axis=1)
    return pd.DataFrame()

@st.cache_data(ttl=3600, max_entries=1)
def get_historico_base():
    return fetch_fmp_data(TODOS_TICKERS, interval="5min", days_back=7)

@st.cache_data(ttl=60, max_entries=1, show_spinner=False)
def get_dados_recentes():
    return fetch_fmp_data(TODOS_TICKERS, interval="5min", days_back=3)

def get_cached_market_data():
    hist = get_historico_base()
    rec = get_dados_recentes()
    
    if hist.empty and rec.empty:
        st.cache_data.clear()
        return pd.DataFrame()
        
    if hist.empty: return rec
    if rec.empty: return hist
    
    df = pd.concat([hist, rec])
    df = df[~df.index.duplicated(keep='last')]
    return df.sort_index()

def get_market_data(start_dt, end_dt):
    df = get_cached_market_data()
    if df.empty:
        st.cache_data.clear()
    return df

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
        fake_idx = pd.date_range(start_dt, end_dt, freq='5min')
        return pd.Series(0.0, index=fake_idx)

    start_naive, end_naive = start_dt.replace(tzinfo=None), end_dt.replace(tzinfo=None)
    full_idx = pd.date_range(start_naive, end_naive, freq='5min')
    
    dias_para_domingo = (start_naive.weekday() + 1) % 7
    if start_naive.weekday() == 6 and start_naive.hour >= 18:
        anchor_time = start_naive.replace(hour=18, minute=0, second=0, microsecond=0)
    else:
        anchor_time = (start_naive - timedelta(days=dias_para_domingo)).replace(hour=18, minute=0, second=0, microsecond=0)

    PESOS = {
        'DX-Y.NYB': 3.0, '^TNX': 3.0, 'SPY': 3.0, '^GSPC': 3.0,
        'QQQ': 2.0, '^IXIC': 2.0, 'GC=F': 2.0, 'CL=F': 2.0,
        'EURUSD=X': 2.0, 'USDJPY=X': 2.0, '^FVX': 2.0,
        'USDCAD=X': 1.5, 'USDCHF=X': 1.5, 'BTC-USD': 1.5
    }

    series_dict = {}
    peso_total = 0.0

    for ticker in tickers_list:
        if ticker in raw_data.columns.levels[0]:
            try:
                ticker_df = raw_data[ticker]
                col_name = 'Close' if 'Close' in ticker_df.columns else 'close' if 'close' in ticker_df.columns else None
                if not col_name: continue
                
                s_full = ticker_df[col_name].dropna()
                if s_full.empty: continue
                
                s_full.index = s_full.index.tz_localize(None)
                s_before = s_full[s_full.index <= anchor_time]
                ref_val = float(s_before.iloc[-1]) if not s_before.empty else float(s_full.iloc[0])

                s_window = s_full[(s_full.index >= start_naive) & (s_full.index <= end_naive)]

                if not s_window.empty and ref_val != 0:
                    s_window = s_window.resample('5min').last().reindex(full_idx).ffill()
                    s_window.index = s_window.index.tz_localize(BRT)
                    
                    volatilidade = s_full.pct_change().std()
                    if pd.isna(volatilidade) or volatilidade == 0:
                        volatilidade = 0.0005
                        
                    limiar_dinamico = (volatilidade * 100) * 2.0 
                    var_pct = 100 * (s_window - ref_val) / abs(ref_val)
                    peso_ativo = PESOS.get(ticker, 1.0)
                    
                    series_dict[ticker] = {
                        'var_pct': var_pct,
                        'limiar': limiar_dinamico,
                        'peso': peso_ativo
                    }
                    peso_total += peso_ativo
            except Exception:
                continue

    if not series_dict or peso_total == 0:
        fake_idx = pd.date_range(start_dt, end_dt, freq='5min')
        return pd.Series(0.0, index=fake_idx)

    resultado_final = pd.Series(0.0, index=full_idx).tz_localize(BRT)
    
    for ticker, dados in series_dict.items():
        var_pct = dados['var_pct']
        limiar = dados['limiar']
        peso = dados['peso']
        
        if modo == 'baixa':
            voto = (var_pct < -limiar).astype(float) * peso
        else:
            voto = (var_pct > limiar).astype(float) * peso
            
        resultado_final += voto

    return (resultado_final / peso_total) * 100.0

def fetch_mxn_brl(start_dt, end_dt):
    raw_data = get_market_data(start_dt, end_dt)
    fake_idx = pd.date_range(start_dt, end_dt, freq='5min')
    fake_series = pd.Series(1.0, index=fake_idx)
    
    if raw_data.empty:
        return fake_series, fake_series, 1.0, 1.0

    try:
        has_mxn = 'USDMXN=X' in raw_data.columns.levels[0]
        has_brl = 'USDBRL=X' in raw_data.columns.levels[0]
        
        if not has_mxn or not has_brl:
            return fake_series, fake_series, 1.0, 1.0
            
        mxn_df = raw_data['USDMXN=X']
        brl_df = raw_data['USDBRL=X']
        
        mxn_col = 'Close' if 'Close' in mxn_df.columns else 'close'
        brl_col = 'Close' if 'Close' in brl_df.columns else 'close'
        
        mxn = mxn_df[mxn_col].dropna()
        brl = brl_df[brl_col].dropna()
        
        if mxn.empty or brl.empty:
            return fake_series, fake_series, 1.0, 1.0

        mxn.index, brl.index = mxn.index.tz_localize(None), brl.index.tz_localize(None)

        start_naive, end_naive = start_dt.replace(tzinfo=None), end_dt.replace(tzinfo=None)
        anchor_time = start_naive.replace(hour=0, minute=0, second=0, microsecond=0)

        mxn_before = mxn[mxn.index <= anchor_time]
        mxn_ref = float(mxn_before.iloc[-1]) if not mxn_before.empty else float(mxn.iloc[0])

        brl_before = brl[brl.index <= anchor_time]
        brl_ref = float(brl_before.iloc[-1]) if not brl_before.empty else float(brl.iloc[0])

        mxn = mxn[(mxn.index >= start_naive) & (mxn.index <= end_naive)]
        brl = brl[(brl.index >= start_naive) & (brl.index <= end_naive)]

        full_idx = pd.date_range(start_naive, end_naive, freq='5min')
        mxn_resampled = mxn.resample('5min').last().reindex(full_idx).ffill()
        brl_resampled = brl.resample('5min').last().reindex(full_idx).ffill()

        mxn_resampled.index, brl_resampled.index = mxn_resampled.index.tz_localize(BRT), brl_resampled.index.tz_localize(BRT)
        return mxn_resampled, brl_resampled, mxn_ref, brl_ref
    except Exception:
        return fake_series, fake_series, 1.0, 1.0

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
    except: pass

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
    except: pass

    try:
        url_si = f"https://statusinvest.com.br/juros-futuros/{ticker_advfn.lower()}"
        resp = requests.get(url_si, headers=headers, timeout=4)
        if resp.status_code == 200:
            match = re.search(r'title=\"Variação do valor\"[^>]*>.*?<b[^>]*>([+-]?[\d,\.]+)%</b>', resp.text, re.DOTALL)
            if match:
                val = float(match.group(1).replace('.', '').replace(',', '.'))
                return round(val, 2)
    except: pass

    try:
        url_advfn = f"https://br.advfn.com/bolsa-de-valores/bmf/{ticker_advfn.upper()}/cotacao"
        resp = requests.get(url_advfn, headers=headers, timeout=4)
        if resp.status_code == 200:
            match = re.search(r'Varia[çc][aã]o\s*do\s*Dia\s*%.*?<td[^>]*>\s*([+-]?[\d,\.]+)', resp.text, re.IGNORECASE | re.DOTALL)
            if match:
                val = float(match.group(1).replace('.', '').replace(',', '.'))
                return round(val, 2)
    except: pass

    return 0.0

def checar_e_enviar_alerta_di(di_nome, valor_atual):
    nivel_alerta = 0
    if abs(valor_atual) >= 2.0:
        nivel_alerta = 2
    elif abs(valor_atual) >= 1.5:
        nivel_alerta = 1
    if nivel_alerta == 0:
        return ""
        
    chave_alerta = f"alerta_enviado_{di_nome}_{nivel_alerta}"
    if chave_alerta not in st.session_state:
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_REMETENTE
            msg['To'] = EMAIL_DESTINO
            msg['Subject'] = f"🚨 ALERTA {di_nome}: Variação de {valor_atual}%"
            corpo = f"O contrato {di_nome} atingiu uma variação crítica de {valor_atual}%.\nNível de Alerta: {'MÁXIMO (>2.0%)' if nivel_alerta == 2 else 'ATENÇÃO (>1.5%)'}"
            msg.attach(MIMEText(corpo, 'plain'))
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(EMAIL_REMETENTE, SENHA_APP)
            server.send_message(msg)
            server.quit()
            st.session_state[chave_alerta] = True
        except Exception:
            pass
            
    if nivel_alerta == 2:
        return "animation: pulse 1s infinite; border: 2px solid #EF4444; box-shadow: 0 0 15px #EF4444;"
    else:
        return "animation: pulse 2s infinite; border: 2px solid #F59E0B; box-shadow: 0 0 10px #F59E0B;"

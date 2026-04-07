import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import time

from helpers import (
    ativos, fetch_mxn_brl, ultimo_candle_real, BRT, VERDE_TICKERS, VERMELHA_TICKERS
)

def render_grafico(start_dt, end_dt, placeholder_dados):
    with st.spinner("Processando Inteligência de Gráfico..."):
        verde_count = ativos(VERDE_TICKERS, start_dt, end_dt, modo='alta')
        vermelha_count = ativos(VERMELHA_TICKERS, start_dt, end_dt, modo='baixa')
        mxn_bruto, brl_bruto, mxn_ref, brl_ref = fetch_mxn_brl(start_dt, end_dt)

    if verde_count.empty or vermelha_count.empty or mxn_bruto.empty:
        motivos = []
        hoje = pd.Timestamp.now(tz=BRT).date()
        if end_dt.date() > hoje:
            motivos.append("datas futuras (yfinance não tem dados reais)")
        if start_dt.weekday() >= 5 or end_dt.weekday() >= 5:
            motivos.append("fins de semana/feriados (sem negociações)")
        if (end_dt - start_dt).total_seconds() < 3600:
            motivos.append("período muito curto")
        motivo_str = "; ".join(motivos) if motivos else "erro na API ou período sem negociações"
        st.warning(f"⚠️ Dados insuficientes para montar o gráfico ({motivo_str}). Tente datas recentes úteis (seg-sex, últimos 5-10 dias, 9h-17h) no popover.")
        
        fig_placeholder = go.Figure()
        fig_placeholder.add_annotation(
            text="Aguardando dados válidos...\nSugestão: Use datas recentes (ex: 25/03/2024 a 29/03/2024, 9h-17h)",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False, font_size=14, font_color="#94A3B8"
        )
        fig_placeholder.update_layout(height=400, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_placeholder, use_container_width=True)
        return

    agora_idx = pd.Timestamp(ultimo_candle_real())
    if end_dt > agora_idx:
        verde_count = verde_count[verde_count.index <= agora_idx]
        vermelha_count = vermelha_count[vermelha_count.index <= agora_idx]
        mxn_bruto = mxn_bruto[mxn_bruto.index <= agora_idx]
        brl_bruto = brl_bruto[brl_bruto.index <= agora_idx]

    if not mxn_bruto.dropna().empty:
        mxn_df = pd.DataFrame(mxn_bruto, columns=['Close'])
        delta = mxn_df['Close'].diff()
        gain, loss = delta.where(delta > 0, 0.0), -delta.where(delta < 0, 0.0)
        avg_gain = gain.ewm(alpha=1/14, min_periods=1, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, min_periods=1, adjust=False).mean()
        mxn_df['RSI_14'] = 100 - (100 / (1 + (avg_gain / avg_loss)))
        
        exp1 = mxn_df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = mxn_df['Close'].ewm(span=26, adjust=False).mean()
        ppo_line = ((exp1 - exp2) / exp2) * 100 
        mxn_df['PPO_Hist'] = ppo_line - ppo_line.ewm(span=9, adjust=False).mean()
        
        pct_mxn = (((mxn_bruto - mxn_ref) / mxn_ref) * 100) if mxn_ref != 0 else (mxn_bruto * 0)
        pct_brl = (((brl_bruto - brl_ref) / brl_ref) * 100) if brl_ref != 0 else (brl_bruto * 0) 
        
        ppo_hist = mxn_df['PPO_Hist'].fillna(0)
        rastro_azul = ((pct_mxn * 40) * (1 + (ppo_hist * 10))).round(0)
        linha_cinza = (pct_mxn * 40).round(0) 
        linha_ambar = (pct_brl * 40).round(0) 
        
        rsi_atual_mxn, ppo_atual = mxn_df['RSI_14'].iloc[-1], ppo_hist.iloc[-1]
    else:
        rastro_azul = pd.Series(0, index=verde_count.index)
        linha_cinza = pd.Series(0, index=verde_count.index)
        linha_ambar = pd.Series(0, index=verde_count.index)
        rsi_atual_mxn, ppo_atual = 50, 0

    verde_atual = verde_count.iloc[-1] if not verde_count.empty else 0
    verm_atual = vermelha_count.iloc[-1] if not vermelha_count.empty else 0
    azul_atual = rastro_azul.iloc[-1] if not rastro_azul.empty else 0
    spread = verde_atual - verm_atual 
    
    cor_spread = "#10B981" if spread > 0 else "#EF4444" if spread < 0 else "#94A3B8"
    prob_alta = min(max(50.0 + min(max(spread * 0.4, -30), 30) + (10 if ppo_atual > 0.01 else -10 if ppo_atual < -0.01 else 0) + (10 if rsi_atual_mxn > 55 else -10 if rsi_atual_mxn < 45 else 0), 5), 95)
    prob_baixa = 100 - prob_alta
    
    trava_alerta = ""
    if rsi_atual_mxn >= 70: 
        trava_alerta = "⚠️ TRAVA: COMPRA EXAUSTA"
        prob_alta = min(prob_alta, 40) 
    elif rsi_atual_mxn <= 30: 
        trava_alerta = "⚠️ TRAVA: VENDA EXAUSTA"
        prob_baixa = min(prob_baixa, 40)

    limite_forte, limite_normal = 30, 10
    limite_leilao = 35 
    
    if spread >= limite_forte: status_color, status_text = "#10B981", "🟢 FORTE PRESSÃO COMPRADORA"
    elif spread >= limite_normal: status_color, status_text = "#34D399", "🟢 PRESSÃO COMPRADORA"
    elif spread <= -limite_forte: status_color, status_text = "#EF4444", "🔴 FORTE PRESSÃO VENDEDORA"
    elif spread <= -limite_normal: status_color, status_text = "#F87171", "🔴 PRESSÃO VENDEDORA"
    else: status_color, status_text = "#94A3B8", "⚪ CONSOLIDAÇÃO / NEUTRO"

    agora = pd.Timestamp.now(tz=BRT).time()
    inicio_leilao = time(8, 55)
    fim_leilao = time(9, 0)
    alerta_leilao_html = "" 

    if inicio_leilao <= agora <= fim_leilao:
        if spread >= limite_leilao and azul_atual > 0:
            alerta_leilao_html = f"<div class='leilao-box' style='border-left-color: #10B981;'><span class='leilao-pulse' style='color: #10B981; font-weight: bold; font-size: 15px;'>⏳ LEILÃO (08:55): ✅ COMPRA HABILITADA (Spread: {spread:+.0f} | Azul: {azul_atual:+.0f})</span></div>"
        elif spread <= -limite_leilao and azul_atual < 0:
            alerta_leilao_html = f"<div class='leilao-box' style='border-left-color: #EF4444;'><span class='leilao-pulse' style='color: #EF4444; font-weight: bold; font-size: 15px;'>⏳ LEILÃO (08:55): 🚨 VENDA HABILITADA (Spread: {spread:+.0f} | Azul: {azul_atual:+.0f})</span></div>"
        else:
            alerta_leilao_html = f"<div class='leilao-box' style='border-left-color: #94A3B8;'><span style='color: #94A3B8; font-size: 14px;'>⏳ LEILÃO (08:55): </span><span style='color: #94A3B8; font-weight: bold; font-size: 15px;'>Aguardando spread (+{limite_leilao} ou -{limite_leilao}) e Azul a favor</span></div>"

    prob_max = max(prob_alta, prob_baixa)
    dir_color = "#10B981" if prob_alta > prob_baixa else "#EF4444"
    dir_text = "ALTA" if prob_alta > prob_baixa else "BAIXA"

    with placeholder_dados:
        if alerta_leilao_html:
            st.markdown(alerta_leilao_html, unsafe_allow_html=True)
        if trava_alerta:
            st.markdown(f"<div style='background-color: rgba(245, 158, 11, 0.2); border-left: 4px solid #F59E0B; padding: 5px 15px; margin-bottom: 5px; color: #F59E0B; font-weight: bold;'>{trava_alerta}</div>", unsafe_allow_html=True)
            
        st.markdown(f"<div style='margin-bottom: 5px;'><span style='color: {status_color}; font-weight: bold; font-size: 18px;'>{status_text}</span></div>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style='display: flex; justify-content: space-around; align-items: center; background: rgba(15, 23, 42, 0.6); border-radius: 8px; padding: 5px 10px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 2px 4px rgba(0,0,0,0.2);'>
            <div style='text-align: center;'><span style='color: #94A3B8; font-size: 10px;'>VERDE</span><br><span style='color: #10B981; font-weight: bold; font-size: 15px;'>🟢 {verde_atual:.0f}</span></div>
            <div style='text-align: center;'><span style='color: #94A3B8; font-size: 10px;'>VERMELHA</span><br><span style='color: #EF4444; font-weight: bold; font-size: 15px;'>🔴 {verm_atual:.0f}</span></div>
            <div style='text-align: left;'><span style='color: #94A3B8; font-size: 10px;'>Δ</span><br><span style='color: {cor_spread}; font-weight: bold; font-size: 15px;'>Δ {spread:+.0f}</span></div>
            <div style='text-align: center;'><span style='color: #94A3B8; font-size: 10px;'>AZUL</span><br><span style='color: #38BDF8; font-weight: bold; font-size: 15px;'>🔵 {azul_atual:+.0f}</span></div>
            <div style='text-align: center; border-left: 1px solid rgba(255,255,255,0.1); padding-left: 10px;'><span style='color: #94A3B8; font-size: 10px;'>PROB WDO</span><br><span style='color: {dir_color}; font-weight: bold; font-size: 15px;'>{prob_max:.0f}% {dir_text}</span></div>
        </div>
        """, unsafe_allow_html=True)

    common_idx = verde_count.index.intersection(vermelha_count.index)
    delta_series = (verde_count[common_idx] - vermelha_count[common_idx]).round(0).astype(int)
    
    fig = go.Figure()
    
    if not verde_count.empty:
        fig.add_trace(go.Scatter(
            x=common_idx,
            y=verde_count[common_idx],
            customdata=delta_series,
            mode='lines',
            name='📊 Spread',
            line=dict(color='rgba(0,0,0,0)', width=0),
            showlegend=False,
            hovertemplate='📊 Spread: %{customdata:.0f}<extra></extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=common_idx,
            y=vermelha_count[common_idx],
            mode='lines+markers',
            name='🔴 Vermelha',
            line=dict(color='#EF4444', width=3, shape='spline', smoothing=1.1),
            marker=dict(size=5, symbol='circle'),
            fill='tozeroy',
            fillcolor='rgba(239, 68, 68, 0.05)',
            hovertemplate='%{y:.0f}<extra></extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=common_idx,
            y=verde_count[common_idx],
            mode='lines+markers',
            name='🟢 Verde',
            line=dict(color='#10B981', width=3, shape='spline', smoothing=1.1),
            marker=dict(size=5, symbol='circle'),
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.05)',
            hovertemplate='%{y:.0f}<extra></extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=linha_cinza.index,
            y=linha_cinza,
            mode='lines',
            name='⚪ (Fluxo Base)',
            line=dict(color='rgba(148, 163, 184, 0.6)', width=1.2, dash='solid', shape='spline', smoothing=0.6),
            hoverinfo='skip'
        ))
        
        fig.add_trace(go.Scatter(
            x=linha_ambar.index,
            y=linha_ambar,
            mode='lines',
            name='🟠 (WDO)',
            line=dict(color='#F59E0B', width=1.2, dash='solid', shape='spline', smoothing=0.6),
            hoverinfo='skip'
        ))
        
        fig.add_trace(go.Scatter(
            x=rastro_azul.index,
            y=rastro_azul,
            mode='lines+markers',
            name='🔵',
            line=dict(color='#38BDF8', width=2.0, shape='spline', smoothing=0.8, dash='dot'),
            marker=dict(size=5, symbol='circle'),
            yaxis='y2',
            hovertemplate='%{y:.0f}<extra></extra>'
        ))

    all_vals = pd.concat([
        verde_count[common_idx],
        vermelha_count[common_idx],
        linha_cinza.reindex(common_idx),
        linha_ambar.reindex(common_idx),
        rastro_azul.reindex(common_idx)
    ], axis=0).dropna()
    
    if not all_vals.empty:
        y_max = all_vals.max()
        y_min = all_vals.min()
        padding = max((y_max - y_min) * 0.08, 5)
    else:
        y_max, y_min, padding = 10, -10, 5

    fig.update_layout(
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor="#1E293B",
            font_color="white",
            bordercolor="rgba(255,255,255,0.2)",
            align="left"
        ),
        height=600,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.05,
            xanchor="center",
            x=0.5,
            font=dict(color="white", size=13),
            bgcolor="rgba(0,0,0,0)"
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=50, b=20),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.1)',
            automargin=True,
            showticklabels=True,
            hoverformat='%H:%M',
            showspikes=True,
            spikemode='across',
            spikecolor='rgba(255,255,255,0.12)',
            spikethickness=0.3,
            spikesnap='cursor'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.1)',
            side='right',
            automargin=True,
            range=[y_min - padding, y_max + padding]
        ),
        yaxis2=dict(
            title=dict(text="Rastro Azul", font=dict(color="#F8FAFC")),
            overlaying='y',
            side='right',
            showticklabels=True,
            tickfont=dict(color="#F8FAFC", size=12),
            range=[
                (rastro_azul.min() * 1.2 if not rastro_azul.empty else -75),
                (rastro_azul.max() * 1.2 if not rastro_azul.empty else 75)
            ]
        ),
    )
    
    st.plotly_chart(
        fig,
        use_container_width=True,
        theme=None,
        config={
            'displayModeBar': True,
            'scrollZoom': False,
            'displaylogo': False
        }
    )

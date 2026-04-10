import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import time

from helpers import (
    ativos, fetch_mxn_brl, ultimo_candle_real, BRT, VERDE_TICKERS, VERMELHA_TICKERS,
    fetch_di_variacao, gerar_dias_uteis
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
            motivos.append("datas futuras")
        if start_dt.weekday() >= 5 or end_dt.weekday() >= 5:
            motivos.append("fim de semana/feriado")
        if (end_dt - start_dt).total_seconds() < 3600:
            motivos.append("período muito curto")

        motivo_str = "; ".join(motivos) if motivos else "sem dados no período selecionado"

        st.warning(
            f"Dados insuficientes para montar o gráfico ({motivo_str}). "
            "Use datas úteis recentes no período de mercado."
        )

        fig_placeholder = go.Figure()
        fig_placeholder.add_annotation(
            text="Aguardando dados válidos...\nSelecione um período útil com mercado aberto.",
            x=0.5, y=0.5, xref="paper", yref="paper",
            showarrow=False, font=dict(size=16, color="white")
        )
        fig_placeholder.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig_placeholder, use_container_width=True, config={'displayModeBar': False})
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
        ppo_hist = (ppo_line - ppo_line.ewm(span=9, adjust=False).mean()).fillna(0)

        pct_mxn = (((mxn_bruto - mxn_ref) / mxn_ref) * 100) if mxn_ref != 0 else (mxn_bruto * 0)
        pct_brl = (((brl_bruto - brl_ref) / brl_ref) * 100) if brl_ref != 0 else (brl_bruto * 0)

        rastro_azul = ((pct_mxn * 40) * (1 + (ppo_hist * 10))).round(0)
        linha_cinza = (pct_mxn * 40).round(0)
        linha_ambar = (pct_brl * 40).round(0)

        rsi_atual_mxn = mxn_df['RSI_14'].iloc[-1]
        ppo_atual = ppo_hist.iloc[-1]
    else:
        rastro_azul = pd.Series(0, index=verde_count.index)
        linha_cinza = pd.Series(0, index=verde_count.index)
        linha_ambar = pd.Series(0, index=verde_count.index)
        rsi_atual_mxn = 50
        ppo_atual = 0

    verde_atual = verde_count.iloc[-1] if not verde_count.empty else 0
    verm_atual = vermelha_count.iloc[-1] if not vermelha_count.empty else 0
    azul_atual = rastro_azul.iloc[-1] if not rastro_azul.empty else 0
    spread = verde_atual - verm_atual
    cor_spread = "#10B981" if spread > 0 else "#EF4444" if spread < 0 else "#F59E0B"

    status_text = "DADOS OK" if not verde_count.empty else "SEM DADOS"
    status_color = "#10B981" if not verde_count.empty else "#EF4444"
    trava_alerta = "OK" if not verde_count.empty else "N/A"

    with st.container():
        c_status, c_info = st.columns([1.2, 4.8])

        with c_status:
            st.markdown(
                f"""
                <div class='prob-box' style='justify-content: center; height: 100%; border-color: {status_color}40;'>
                    <span style='color: {status_color}; font-weight: bold; font-size: 14px; text-align: center;'>{status_text}</span>
                </div>
                """,
                unsafe_allow_html=True
            )

        with c_info:
            st.markdown(
                f"""
                <div style='display: flex; justify-content: space-around; align-items: center; background: rgba(15, 23, 42, 0.6); border-radius: 8px; padding: 5px 10px; border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 2px 4px rgba(0,0,0,0.2);'>
                    <div style='text-align: center;'><span style='color: #94A3B8; font-size: 10px;'>VERDE</span><br><span style='color: #10B981; font-weight: bold; font-size: 15px;'>🟢 {verde_atual:.0f}</span></div>
                    <div style='text-align: center;'><span style='color: #94A3B8; font-size: 10px;'>VERMELHA</span><br><span style='color: #EF4444; font-weight: bold; font-size: 15px;'>🔴 {verm_atual:.0f}</span></div>
                    <div style='text-align: center;'><span style='color: #94A3B8; font-size: 10px;'>AZUL</span><br><span style='color: #38BDF8; font-weight: bold; font-size: 15px;'>🔵 {azul_atual:.0f}</span></div>
                    <div style='text-align: center;'><span style='color: #94A3B8; font-size: 10px;'>Δ</span><br><span style='color: {cor_spread}; font-weight: bold; font-size: 15px;'>Δ {spread:+.0f}</span></div>
                    <div style='text-align: center;'><span style='color: #94A3B8; font-size: 10px;'>TRAVA</span><br><span style='color: #F59E0B; font-weight: bold; font-size: 15px;'>{trava_alerta}</span></div>
                </div>
                """,
                unsafe_allow_html=True
            )

    common_idx = verde_count.index.intersection(vermelha_count.index).intersection(rastro_azul.index)
    if common_idx.empty:
        st.warning("Sem dados em comum para desenhar o gráfico.")
        return

    verde_count = verde_count.loc[common_idx]
    vermelha_count = vermelha_count.loc[common_idx]
    rastro_azul = rastro_azul.loc[common_idx]
    linha_cinza = linha_cinza.reindex(common_idx)
    linha_ambar = linha_ambar.reindex(common_idx)

    delta_series = (verde_count - vermelha_count).round(0).astype(int)

    all_vals = pd.concat([
        verde_count,
        vermelha_count,
        linha_cinza,
        linha_ambar,
        rastro_azul
    ], axis=0).dropna()

    if not all_vals.empty:
        y_max = all_vals.max()
        y_min = all_vals.min()
        padding = max((y_max - y_min) * 0.08, 5)
    else:
        y_max, y_min, padding = 10, -10, 5

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=common_idx,
        y=verde_count,
        customdata=delta_series,
        mode='lines+markers',
        name='🟢 Verde',
        line=dict(color='#10B981', width=3, shape='spline', smoothing=1.1),
        marker=dict(size=5, symbol='circle'),
        fill='tozeroy',
        fillcolor='rgba(16, 185, 129, 0.05)',
        hovertemplate='%{x|%H:%M} — %{y:.0f}<extra></extra>'
    ))

    fig.add_trace(go.Scatter(
        x=common_idx,
        y=vermelha_count,
        mode='lines+markers',
        name='🔴 Vermelha',
        line=dict(color='#EF4444', width=3, shape='spline', smoothing=1.1),
        marker=dict(size=5, symbol='circle'),
        fill='tozeroy',
        fillcolor='rgba(239, 68, 68, 0.05)',
        hovertemplate='%{x|%H:%M} — %{y:.0f}<extra></extra>'
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
        hovertemplate='Azul: %{y:.0f}<extra></extra>'
    ))

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
            tickfont=dict(color="#F8FAFC", size=12),
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
            side='left',
            automargin=True,
            showticklabels=True,
            tickfont=dict(color="#F8FAFC", size=12),
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

# tab_grafico.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import time
from helpers import (
    ativos, fetch_mxn_brl, ultimo_candle_real, BRT, VERDE_TICKERS, VERMELHA_TICKERS,
    fetch_di_variacao, gerar_dias_uteis
)

def render_grafico(start_dt, end_dt, placeholder_dados):
    # --- PROCESSAMENTO DOS DADOS PARA O GRÁFICO (Variável pela Sidebar) ---
    with st.spinner("Processando Inteligência de Gráfico..."):
        verde_count = ativos(VERDE_TICKERS, start_dt, end_dt, modo='alta')
        vermelha_count = ativos(VERMELHA_TICKERS, start_dt, end_dt, modo='alta')
        mxn_bruto, brl_bruto, mxn_ref, brl_ref = fetch_mxn_brl(start_dt, end_dt)

    # Se não houver dados reais, não tenta montar linhas planas
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

    # Usa apenas a interseção real dos índices
    common_idx = verde_count.index.intersection(vermelha_count.index)

    if common_idx.empty:
        st.warning("Sem dados em comum para desenhar o gráfico.")
        return

    verde_count = verde_count.loc[common_idx]
    vermelha_count = vermelha_count.loc[common_idx]

    # Se a série ficar constante, não desenha linha falsa
    if verde_count.nunique() <= 1 and vermelha_count.nunique() <= 1:
        st.warning("Os dados retornaram constantes neste período. Selecione outro intervalo.")
        return

    delta_series = (verde_count - vermelha_count).round(0).astype(int)

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

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
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
            automargin=True
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

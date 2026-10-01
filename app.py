import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import extra_streamlit_components as stx
import os
from datetime import datetime

st.set_page_config(page_title="Gestão Financeira", layout="wide")

# --- GERENCIADOR DE COOKIES ---
cookie_manager = stx.CookieManager()

def check_credentials(username, password):
    correct_user = os.getenv("APP_USER", "admin")
    correct_pass = os.getenv("APP_PASSWORD", "senha123")
    return username == correct_user and password == correct_pass

auth_cookie = cookie_manager.get('auth_financas')

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = True if auth_cookie == "logged" else False

if not st.session_state["logged_in"]:
    st.title("🔒 Acesso Restrito - Gestão Financeira")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("form_login"):
            usuario = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            btn_entrar = st.form_submit_button("Entrar")
            if btn_entrar:
                if check_credentials(usuario, senha):
                    st.session_state["logged_in"] = True
                    cookie_manager.set('auth_financas', 'logged', key='set_auth')
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    st.stop()

# --- CONEXÃO BANCO DE DADOS ---
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "secret"),
        port=os.getenv("DB_PORT", "5432")
    )

def get_categorias():
    try:
        conn = get_connection()
        df_cat = pd.read_sql_query("SELECT nome FROM categorias ORDER BY nome ASC", conn)
        conn.close()
        return df_cat['nome'].tolist()
    except:
        return ["Moradia", "Alimentação", "Transporte", "Lazer", "Saúde", "Investimentos", "Outros"]

# Logout
if st.sidebar.button("Sair (Logout)"):
    st.session_state["logged_in"] = False
    cookie_manager.delete('auth_financas', key='del_auth')
    st.rerun()

st.title("📊 Gestão Financeira Pessoal")

# --- BARRA LATERAL: TRANSAÇÃO E CATEGORIA ---
st.sidebar.header("Adicionar Transação")
lista_categorias = get_categorias()
lista_formas_pagamento = ["PIX", "Cartão de Crédito", "Cartão de Débito", "Dinheiro", "Boleto", "Transferência"]

with st.sidebar.form("form_transacao", clear_on_submit=True):
    data = st.date_input("Data", datetime.now())
    tipo = st.selectbox("Tipo", ["Despesa", "Receita"])
    categoria = st.selectbox("Categoria", lista_categorias)
    forma_pagamento = st.selectbox("Forma de Pagamento", lista_formas_pagamento)
    valor = st.number_input("Valor (R$)", min_value=0.01, format="%.2f")
    descricao = st.text_input("Descrição")
    btn_salvar = st.form_submit_button("Salvar Registro")

if btn_salvar:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO transacoes (data, tipo, categoria, valor, descricao, forma_pagamento) VALUES (%s, %s, %s, %s, %s, %s)",
            (data, tipo, categoria, valor, descricao, forma_pagamento)
        )
        conn.commit()
        cur.close()
        conn.close()
        st.sidebar.success("Transação salva!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erro ao salvar: {e}")

st.sidebar.divider()
st.sidebar.header("Nova Categoria")
with st.sidebar.form("form_categoria", clear_on_submit=True):
    nova_cat = st.text_input("Nome da Categoria")
    btn_cat = st.form_submit_button("Adicionar Categoria")

if btn_cat and nova_cat.strip() != "":
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO categorias (nome) VALUES (%s) ON CONFLICT DO NOTHING", (nova_cat.strip(),))
        conn.commit()
        cur.close()
        conn.close()
        st.sidebar.success(f"Categoria '{nova_cat}' adicionada!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erro ao criar categoria: {e}")

# PERÍODO DE ANÁLISE
st.sidebar.divider()
st.sidebar.header("📅 Período de Análise")
ano_atual = datetime.now().year
mes_atual = datetime.now().month

ano_selecionado = st.sidebar.selectbox("Ano", list(range(ano_atual - 2, ano_atual + 3)), index=2)
meses_nome = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
mes_selecionado_nome = st.sidebar.selectbox("Mês", meses_nome, index=mes_atual - 1)
mes_selecionado = meses_nome.index(mes_selecionado_nome) + 1

# ABAS DO APP
tab_dash, tab_patrimonio, tab_editar = st.tabs(["Dashboard", "🏦 Saldo & Patrimônio", "✏️ Editar Transações"])

# --- TAB 1: DASHBOARD ---
with tab_dash:
    try:
        conn = get_connection()
        df_full = pd.read_sql_query("SELECT * FROM transacoes ORDER BY data DESC", conn)
        df_saldos = pd.read_sql_query("SELECT * FROM saldos_conta", conn)
        df_invest = pd.read_sql_query("SELECT * FROM investimentos", conn)
        conn.close()

        total_saldo_contas = df_saldos['saldo'].sum() if not df_saldos.empty else 0.00
        total_investido = df_invest['valor_investido'].sum() if not df_invest.empty else 0.00
        patrimonio_total = total_saldo_contas + total_investido

        # RESUMO PATRIMONIAL NO TOPO
        st.subheader("💡 Resumo Patrimonial Atual")
        p1, p2, p3 = st.columns(3)
        p1.metric("Saldo em Contas", f"R$ {total_saldo_contas:,.2f}")
        p2.metric("Total Investido", f"R$ {total_investido:,.2f}")
        p3.metric("Patrimônio Líquido Total", f"R$ {patrimonio_total:,.2f}")

        st.divider()

        # FLUXO DE CAIXA DO MÊS
        st.subheader(f"📊 Fluxo de Caixa ({mes_selecionado_nome}/{ano_selecionado})")

        if not df_full.empty:
            df_full['data'] = pd.to_datetime(df_full['data'])
            df_mes = df_full[(df_full['data'].dt.year == ano_selecionado) & (df_full['data'].dt.month == mes_selecionado)]

            mes_ant = 12 if mes_selecionado == 1 else mes_selecionado - 1
            ano_ant = ano_selecionado - 1 if mes_selecionado == 1 else ano_selecionado
            df_mes_ant = df_full[(df_full['data'].dt.year == ano_ant) & (df_full['data'].dt.month == mes_ant)]

            rec_atual = df_mes[df_mes['tipo'] == 'Receita']['valor'].sum() if not df_mes.empty else 0.0
            desp_atual = df_mes[df_mes['tipo'] == 'Despesa']['valor'].sum() if not df_mes.empty else 0.0
            saldo_mes = rec_atual - desp_atual

            rec_ant = df_mes_ant[df_mes_ant['tipo'] == 'Receita']['valor'].sum() if not df_mes_ant.empty else 0.0
            desp_ant = df_mes_ant[df_mes_ant['tipo'] == 'Despesa']['valor'].sum() if not df_mes_ant.empty else 0.0

            delta_rec = ((rec_atual - rec_ant) / rec_ant * 100) if rec_ant > 0 else 0
            delta_desp = ((desp_atual - desp_ant) / desp_ant * 100) if desp_ant > 0 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Receitas no Mês", f"R$ {rec_atual:,.2f}", f"{delta_rec:+.1f}% vs mês anterior")
            col2.metric("Despesas no Mês", f"R$ {desp_atual:,.2f}", f"{delta_desp:+.1f}% vs mês anterior", delta_color="inverse")
            col3.metric("Resultado do Mês", f"R$ {saldo_mes:,.2f}")

            st.divider()

            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.subheader("Despesas por Categoria")
                df_desp = df_mes[df_mes['tipo'] == 'Despesa'] if not df_mes.empty else pd.DataFrame()
                if not df_desp.empty:
                    fig_cat = px.pie(df_desp, names='categoria', values='valor', hole=0.4)
                    st.plotly_chart(fig_cat, use_container_width=True)
                else:
                    st.info("Nenhuma despesa no período selecionado.")

            with col_chart2:
                st.subheader("Investimentos por Tipo de Ativo")
                if not df_invest.empty:
                    fig_inv = px.pie(df_invest, names='tipo', values='valor_investido', title="Alocação da Carteira")
                    st.plotly_chart(fig_inv, use_container_width=True)
                else:
                    st.info("Nenhum investimento cadastrado.")

            st.divider()

            # EXTRATO COMPLETO DE TRANSAÇÕES DO MÊS SELECIONADO
            st.subheader(f"📄 Extrato de Transações — {mes_selecionado_nome}/{ano_selecionado}")
            if not df_mes.empty:
                df_mes_display = df_mes[['data', 'tipo', 'categoria', 'forma_pagamento', 'valor', 'descricao']].copy()
                df_mes_display['data'] = df_mes_display['data'].dt.strftime('%d/%m/%Y')
                st.dataframe(df_mes_display, use_container_width=True)
            else:
                st.info(f"Nenhuma transação cadastrada no mês de {mes_selecionado_nome} de {ano_selecionado}.")

        else:
            st.info("Nenhuma transação registrada no banco de dados.")
    except Exception as e:
        st.error(f"Erro ao carregar dashboard: {e}")

# --- TAB 2: SALDO E PATRIMÔNIO ---
with tab_patrimonio:
    st.subheader("🏦 Gerenciamento de Saldo e Investimentos")
    st.caption("Cadastre e atualize suas posições. Estes valores não afetam a soma de receitas e despesas do fluxo mensal.")

    col_saldo, col_invest = st.columns(2)

    with col_saldo:
        st.markdown("### Saldo em Contas")
        with st.form("form_saldo", clear_on_submit=True):
            instituicao = st.text_input("Instituição / Banco (ex: Nubank, Inter)")
            saldo_val = st.number_input("Saldo Atual (R$)", min_value=0.00, format="%.2f")
            btn_saldo = st.form_submit_button("Atualizar / Adicionar Saldo")

        if btn_saldo and instituicao.strip() != "":
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO saldos_conta (institicao, saldo) VALUES (%s, %s)",
                    (instituicao.strip(), saldo_val)
                )
                conn.commit()
                cur.close()
                conn.close()
                st.success("Saldo salvo com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar saldo: {e}")

        try:
            conn = get_connection()
            df_s = pd.read_sql_query("SELECT id, institicao, saldo FROM saldos_conta", conn)
            conn.close()
            if not df_s.empty:
                st.dataframe(df_s[['institicao', 'saldo']], use_container_width=True)
        except:
            pass

    with col_invest:
        st.markdown("### Investimentos por Categoria")
        tipos_investimento = ["Renda Fixa / CDB", "Tesouro Direto", "Ações", "Fundos Imobiliários (FIIs)", "Criptomoedas", "Previdência", "Outros"]
        
        with st.form("form_investimento", clear_on_submit=True):
            tipo_inv = st.selectbox("Tipo de Investimento", tipos_investimento)
            nome_ativo = st.text_input("Nome do Ativo / Produto (ex: CDB Liquidez, PETR4)")
            valor_inv = st.number_input("Valor Investido (R$)", min_value=0.01, format="%.2f")
            btn_invest = st.form_submit_button("Adicionar Investimento")

        if btn_invest and nome_ativo.strip() != "":
            try:
                conn = get_connection()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO investimentos (tipo, nome_ativo, valor_investido) VALUES (%s, %s, %s)",
                    (tipo_inv, nome_ativo.strip(), valor_inv)
                )
                conn.commit()
                cur.close()
                conn.close()
                st.success("Investimento salvo!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar investimento: {e}")

        try:
            conn = get_connection()
            df_i = pd.read_sql_query("SELECT id, tipo, nome_ativo, valor_investido FROM investimentos", conn)
            conn.close()
            if not df_i.empty:
                st.dataframe(df_i[['tipo', 'nome_ativo', 'valor_investido']], use_container_width=True)
        except:
            pass

# --- TAB 3: EDITAR TRANSAÇÕES ---
with tab_editar:
    st.subheader("Edição Direta de Registros")
    try:
        conn = get_connection()
        df_edit = pd.read_sql_query("SELECT id, data, tipo, categoria, forma_pagamento, valor, descricao FROM transacoes ORDER BY id DESC", conn)
        conn.close()

        if not df_edit.empty:
            edited_df = st.data_editor(
                df_edit,
                disabled=["id"],
                column_config={
                    "tipo": st.column_config.SelectboxColumn("Tipo", options=["Despesa", "Receita"], required=True),
                    "categoria": st.column_config.SelectboxColumn("Categoria", options=lista_categorias, required=True),
                    "forma_pagamento": st.column_config.SelectboxColumn("Forma de Pagamento", options=lista_formas_pagamento, required=True),
                    "valor": st.column_config.NumberColumn("Valor (R$)", min_value=0.01, format="R$ %.2f"),
                    "data": st.column_config.DateColumn("Data", format="YYYY-MM-DD")
                },
                num_rows="dynamic",
                use_container_width=True
            )

            if st.button("💾 Salvar Alterações no Banco"):
                conn = get_connection()
                cur = conn.cursor()
                for row in edited_df.itertuples():
                    cur.execute("""
                        UPDATE transacoes 
                        SET data = %s, tipo = %s, categoria = %s, forma_pagamento = %s, valor = %s, descricao = %s 
                        WHERE id = %s
                    """, (row.data, row.tipo, row.categoria, row.forma_pagamento, row.valor, row.descricao, row.id))
                conn.commit()
                cur.close()
                conn.close()
                st.success("Alterações salvas!")
                st.rerun()
    except Exception as e:
        st.error(f"Erro ao carregar dados para edição: {e}")

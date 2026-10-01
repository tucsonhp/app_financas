import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
import extra_streamlit_components as stx
import os
from datetime import datetime

st.set_page_config(page_title="Gestão Financeira", layout="wide")

# --- GERENCIADOR DE COOKIES (PERSISTÊNCIA DE SESSÃO) ---
# @st.cache_resource
# def get_cookie_manager():
#    return stx.CookieManager()

cookie_manager = get_cookie_manager()

def check_credentials(username, password):
    correct_user = os.getenv("APP_USER", "admin")
    correct_pass = os.getenv("APP_PASSWORD", "senha123")
    return username == correct_user and password == correct_pass

# Verifica se o cookie 'auth_financas' já existe no navegador
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

# --- BANCO DE DADOS ---
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

# --- BARRA LATERAL: CADASTRO E FILTROS ---
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

# Nova Categoria
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

# --- FILTRO MENSAL E ANUAL ---
st.sidebar.divider()
st.sidebar.header("📅 Período de Análise")
ano_atual = datetime.now().year
mes_atual = datetime.now().month

ano_selecionado = st.sidebar.selectbox("Ano", list(range(ano_atual - 2, ano_atual + 3)), index=2)
meses_nome = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
mes_selecionado_nome = st.sidebar.selectbox("Mês", meses_nome, index=mes_atual - 1)
mes_selecionado = meses_nome.index(mes_selecionado_nome) + 1

# --- ABAS DA APLICAÇÃO ---
tab_dash, tab_editar = st.tabs(["Dashboard", "✏️ Editar e Gerenciar Transações"])

with tab_dash:
    try:
        conn = get_connection()
        df_full = pd.read_sql_query("SELECT * FROM transacoes ORDER BY data DESC", conn)
        conn.close()

        if not df_full.empty:
            df_full['data'] = pd.to_datetime(df_full['data'])
            
            # Filtro do Mês Atual Selecionado
            df_mes = df_full[(df_full['data'].dt.year == ano_selecionado) & (df_full['data'].dt.month == mes_selecionado)]
            
            # Cálculo para o Comparativo do Mês Anterior
            mes_ant = 12 if mes_selecionado == 1 else mes_selecionado - 1
            ano_ant = ano_selecionado - 1 if mes_selecionado == 1 else ano_selecionado
            df_mes_ant = df_full[(df_full['data'].dt.year == ano_ant) & (df_full['data'].dt.month == mes_ant)]

            # Métricas Atuais
            rec_atual = df_mes[df_mes['tipo'] == 'Receita']['valor'].sum()
            desp_atual = df_mes[df_mes['tipo'] == 'Despesa']['valor'].sum()
            saldo_atual = rec_atual - desp_atual

            # Métricas Mês Anterior
            rec_ant = df_mes_ant[df_mes_ant['tipo'] == 'Receita']['valor'].sum()
            desp_ant = df_mes_ant[df_mes_ant['tipo'] == 'Despesa']['valor'].sum()

            # Deltas (Variação Percentual)
            delta_rec = ((rec_atual - rec_ant) / rec_ant * 100) if rec_ant > 0 else 0
            delta_desp = ((desp_atual - desp_ant) / desp_ant * 100) if desp_ant > 0 else 0

            col1, col2, col3 = st.columns(3)
            col1.metric("Receitas no Mês", f"R$ {rec_atual:,.2f}", f"{delta_rec:+.1f}% vs mês anterior")
            col2.metric("Despesas no Mês", f"R$ {desp_atual:,.2f}", f"{delta_desp:+.1f}% vs mês anterior", delta_color="inverse")
            col3.metric("Saldo do Mês", f"R$ {saldo_atual:,.2f}")

            st.divider()

            # GRÁFICOS INTERATIVOS COM PLOTLY
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.subheader("Despesas por Categoria")
                df_desp = df_mes[df_mes['tipo'] == 'Despesa']
                if not df_desp.empty:
                    fig_cat = px.pie(df_desp, names='categoria', values='valor', hole=0.4, title="Distribuição por Categoria")
                    st.plotly_chart(fig_cat, use_container_width=True)
                else:
                    st.info("Nenhuma despesa no período.")

            with col_chart2:
                st.subheader("Gastos por Forma de Pagamento")
                if not df_desp.empty:
                    fig_pag = px.bar(df_desp, x='forma_pagamento', y='valor', color='forma_pagamento', title="Despesas por Meio de Pagamento")
                    st.plotly_chart(fig_pag, use_container_width=True)
                else:
                    st.info("Nenhuma despesa no período.")

            st.subheader(f"Registros de {mes_selecionado_nome}/{ano_selecionado}")
            st.dataframe(df_mes[['data', 'tipo', 'categoria', 'forma_pagamento', 'valor', 'descricao']], use_container_width=True)

        else:
            st.info("Nenhuma transação registrada no banco de dados.")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")

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

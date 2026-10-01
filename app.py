import streamlit as st
import pandas as pd
import psycopg2
import os

st.set_page_config(page_title="Gestão Financeira", layout="wide")

# --- AUTENTICAÇÃO ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

def check_credentials(username, password):
    correct_user = os.getenv("APP_USER", "admin")
    correct_pass = os.getenv("APP_PASSWORD", "senha123")
    return username == correct_user and password == correct_pass

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
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    st.stop()

# --- CONEXÃO COM O BANCO DE DADOS ---
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "secret"),
        port=os.getenv("DB_PORT", "5432")
    )

# Função para buscar categorias dinâmicas do banco
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
    st.rerun()

st.title("📊 Gestão Financeira Pessoal")

# --- BARRA LATERAL: INSERIR TRANSAÇÃO ---
st.sidebar.header("Adicionar Transação")
lista_categorias = get_categorias()

with st.sidebar.form("form_transacao", clear_on_submit=True):
    data = st.date_input("Data")
    tipo = st.selectbox("Tipo", ["Despesa", "Receita"])
    categoria = st.selectbox("Categoria", lista_categorias)
    valor = st.number_input("Valor (R$)", min_value=0.01, format="%.2f")
    descricao = st.text_input("Descrição")
    btn_salvar = st.form_submit_button("Salvar Registro")

if btn_salvar:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO transacoes (data, tipo, categoria, valor, descricao) VALUES (%s, %s, %s, %s, %s)",
            (data, tipo, categoria, valor, descricao)
        )
        conn.commit()
        cur.close()
        conn.close()
        st.sidebar.success("Transação salva!")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"Erro ao salvar: {e}")

# --- BARRA LATERAL: GERENCIAR CATEGORIAS ---
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

# --- NAVEGAÇÃO PRINCIPAL (ABAS) ---
tab_dash, tab_editar = st.tabs(["Dashboard", "✏️ Editar e Gerenciar Transações"])

# --- ABA 1: DASHBOARD ---
with tab_dash:
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM transacoes ORDER BY data DESC", conn)
        conn.close()

        if not df.empty:
            receitas = df[df['tipo'] == 'Receita']['valor'].sum()
            despesas = df[df['tipo'] == 'Despesa']['valor'].sum()
            saldo = receitas - despesas

            col1, col2, col3 = st.columns(3)
            col1.metric("Receitas Totais", f"R$ {receitas:,.2f}")
            col2.metric("Despesas Totais", f"R$ {despesas:,.2f}")
            col3.metric("Saldo Atual", f"R$ {saldo:,.2f}")

            st.divider()

            st.subheader("Despesas por Categoria")
            df_despesas = df[df['tipo'] == 'Despesa']
            if not df_despesas.empty:
                cat_chart = df_despesas.groupby('categoria')['valor'].sum()
                st.bar_chart(cat_chart)

            st.subheader("Últimos Registros")
            st.dataframe(df[['data', 'tipo', 'categoria', 'valor', 'descricao']], use_container_width=True)
        else:
            st.info("Nenhuma transação registrada ainda.")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")

# --- ABA 2: EDITAR DADOS (DATA EDITOR) ---
with tab_editar:
    st.subheader("Edição Direta de Registros")
    st.caption("Altere os valores nas células abaixo e clique em 'Salvar Alterações no Banco'.")

    try:
        conn = get_connection()
        df_edit = pd.read_sql_query("SELECT id, data, tipo, categoria, valor, descricao FROM transacoes ORDER BY id DESC", conn)
        conn.close()

        if not df_edit.empty:
            # Editor interativo de tabela
            edited_df = st.data_editor(
                df_edit,
                disabled=["id"], # Impede a alteração do ID primário
                column_config={
                    "tipo": st.column_config.SelectboxColumn("Tipo", options=["Despesa", "Receita"], required=True),
                    "categoria": st.column_config.SelectboxColumn("Categoria", options=lista_categorias, required=True),
                    "valor": st.column_config.NumberColumn("Valor (R$)", min_value=0.01, format="R$ %.2f"),
                    "data": st.column_config.DateColumn("Data", format="YYYY-MM-DD")
                },
                num_rows="dynamic", # Permite também deletar linhas se desejar
                use_container_width=True,
                key="editor_transacoes"
            )

            if st.button("💾 Salvar Alterações no Banco"):
                conn = get_connection()
                cur = conn.cursor()
                
                # Atualiza cada registro modificado
                for row in edited_df.itertuples():
                    cur.execute("""
                        UPDATE transacoes 
                        SET data = %s, tipo = %s, categoria = %s, valor = %s, descricao = %s 
                        WHERE id = %s
                    """, (row.data, row.tipo, row.categoria, row.valor, row.descricao, row.id))
                
                conn.commit()
                cur.close()
                conn.close()
                st.success("Alterações salvas com sucesso no PostgreSQL!")
                st.rerun()
        else:
            st.info("Nenhum registro disponível para edição.")
    except Exception as e:
        st.error(f"Erro ao carregar dados para edição: {e}")

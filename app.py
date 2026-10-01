import streamlit as st
import pandas as pd
import psycopg2
import os

# Configuração da página
st.set_page_config(page_title="Gestão Financeira", layout="wide")

# --- GERENCIAMENTO DE SESSÃO / AUTENTICAÇÃO ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

def check_credentials(username, password):
    # Lê usuário e senha das variáveis de ambiente (com valores padrão caso não informados)
    correct_user = os.getenv("APP_USER", "admin")
    correct_pass = os.getenv("APP_PASSWORD", "senha123")
    return username == correct_user and password == correct_pass

def login_form():
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
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")

# Se não estiver logado, exibe apenas a tela de login e encerra a execução do script
if not st.session_state["logged_in"]:
    login_form()
    st.stop()

# --- APLICAÇÃO PRINCIPAL (EXIBIDA APENAS APÓS O LOGIN) ---

# Botão de Logout na Barra Lateral
if st.sidebar.button("Sair (Logout)"):
    st.session_state["logged_in"] = False
    st.rerun()

# Conexão com o PostgreSQL
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "secret"),
        port=os.getenv("DB_PORT", "5432")
    )

st.title("📊 Gestão Financeira Pessoal")

# --- BARRA LATERAL: FORMULÁRIO DE INSERÇÃO ---
st.sidebar.header("Adicionar Transação")
with st.sidebar.form("form_transacao", clear_on_submit=True):
    data = st.date_input("Data")
    tipo = st.selectbox("Tipo", ["Despesa", "Receita"])
    categoria = st.selectbox("Categoria", [
        "Moradia", "Alimentação", "Transporte", 
        "Lazer", "Saúde", "Investimentos", "Outros"
    ])
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
        st.sidebar.success("Transação salva com sucesso!")
    except Exception as e:
        st.sidebar.error(f"Erro ao salvar: {e}")

# --- CORPO PRINCIPAL: DASHBOARD ---
try:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM transacoes ORDER BY data DESC", conn)
    conn.close()

    if not df.empty:
        # Métricas
        receitas = df[df['tipo'] == 'Receita']['valor'].sum()
        despesas = df[df['tipo'] == 'Despesa']['valor'].sum()
        saldo = receitas - despesas

        col1, col2, col3 = st.columns(3)
        col1.metric("Receitas Totais", f"R$ {receitas:,.2f}")
        col2.metric("Despesas Totais", f"R$ {despesas:,.2f}")
        col3.metric("Saldo Atual", f"R$ {saldo:,.2f}")

        st.divider()

        # Gráfico por Categoria
        st.subheader("Despesas por Categoria")
        df_despesas = df[df['tipo'] == 'Despesa']
        if not df_despesas.empty:
            cat_chart = df_despesas.groupby('categoria')['valor'].sum()
            st.bar_chart(cat_chart)

        # Tabela
        st.subheader("Últimos Registros")
        st.dataframe(df[['data', 'tipo', 'categoria', 'valor', 'descricao']], use_container_width=True)
    else:
        st.info("Nenhuma transação registrada ainda.")
except Exception as e:
    st.error(f"Erro ao carregar dados do banco: {e}")

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Sistema de Orçamento", layout="wide")

# Inicializar a lista de itens se não existir
if 'itens' not in st.session_state:
    st.session_state.itens = []

st.title("📊 Orçamento Profissional com Markup")

# --- SIDEBAR: CONFIGURAÇÃO DO MARKUP ---
with st.sidebar:
    st.header("Configurações de Markup")
    st.info("Defina as porcentagens sobre o PREÇO FINAL")
    dv = st.number_input("Impostos + Comissões (%)", value=15.0)
    df = st.number_input("Custos Fixos / Operação (%)", value=10.0)
    lp = st.number_input("Margem de Lucro Desejada (%)", value=20.0)
    
    total_percentual = dv + df + lp
    markup_divisor = (100 - total_percentual) / 100

# --- ÁREA DE LANÇAMENTO ---
with st.expander("➕ Lançar Novo Produto", expanded=True):
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        nome = st.text_input("Nome do Produto/Serviço")
    with col2:
        custo = st.number_input("Custo Unitário (R$)", min_value=0.0, format="%.2f")
    with col3:
        qtd = st.number_input("Quantidade", min_value=1, value=1)

    if st.button("Adicionar ao Orçamento"):
        if nome and custo > 0:
            if markup_divisor > 0:
                # CÁLCULO DO MARKUP
                preco_venda = custo / markup_divisor
                total_item = preco_venda * qtd
                
                st.session_state.itens.append({
                    "Produto": nome,
                    "Custo": custo,
                    "Preço Un. (Venda)": round(preco_venda, 2),
                    "Qtd": qtd,
                    "Total": round(total_item, 2)
                })
                st.success("Item adicionado!")
            else:
                st.error("Erro: A soma das taxas deve ser menor que 100%")
        else:
            st.warning("Preencha o nome e o custo.")

# --- TABELA DE ORÇAMENTO ---
st.subheader("Itens do Orçamento")
if st.session_state.itens:
    df_itens = pd.DataFrame(st.session_state.itens)
    st.table(df_itens)
    
    total_geral = df_itens["Total"].sum()
    st.markdown(f"### **Total Geral: R$ {total_geral:,.2f}**")
    
    if st.button("Limpar Orçamento"):
        st.session_state.itens = []
        st.rerun()
else:
    st.write("Nenhum item lançado.")

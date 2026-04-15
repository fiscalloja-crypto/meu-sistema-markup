import streamlit as st
import pandas as pd
from fpdf import FPDF

st.set_page_config(page_title="Gerador de Orçamentos", layout="wide")

# Inicialização do estado
if 'itens' not in st.session_state:
    st.session_state.itens = []

# --- SIDEBAR: CONFIGURAÇÕES GERAIS ---
with st.sidebar:
    st.header("🏢 Dados da Empresa")
    cabecalho = st.text_input("Cabeçalho (Nome da Empresa)", "Minha Loja Ltda")
    contato_empresa = st.text_input("Contato/Fone", "(00) 00000-0000")
    vendedor = st.text_input("Vendedor", "João Silva")
    
    st.divider()
    st.header("💰 Configuração de Preço")
    markup_final = st.number_input("Markup Fator (Ex: 1.80)", value=1.80, step=0.05)
    forma_pagamento = st.selectbox("Forma de Pagamento", ["Pix (5% desc)", "Cartão à Vista", "Cartão Parcelado", "Boleto"])
    desconto_final = st.number_input("Desconto Final (R$)", value=0.0, step=1.0)

    st.divider()
    rodape = st.text_area("Rodapé (Termos/Garantia)", "Orçamento válido por 5 dias. Garantia de 90 dias.")

# --- ÁREA DE LANÇAMENTO ---
st.title("📄 Novo Orçamento")

with st.expander("➕ Adicionar Item", expanded=True):
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        nome = st.text_input("Descrição do Produto")
    with c2:
        unidade = st.selectbox("Unidade", ["UN", "KG", "MT", "PCT", "LITRO"])
    with c3:
        qtd = st.number_input("Qtd", min_value=1, value=1)
    with c4:
        custo_uni = st.number_input("Custo Unit. (R$)", min_value=0.0, format="%.2f")

    if st.button("Inserir no Orçamento"):
        if nome and custo_uni > 0:
            preco_venda = custo_uni * markup_final
            total_item = preco_venda * qtd
            st.session_state.itens.append({
                "Item": len(st.session_state.itens) + 1,
                "Descrição": nome,
                "Un": unidade,
                "Qtd": qtd,
                "Custo Unit": custo_uni,
                "Preço Venda": round(preco_venda, 2),
                "Total": round(total_item, 2)
            })
            st.rerun()

# --- EXIBIÇÃO DA TABELA ---
if st.session_state.itens:
    df = pd.DataFrame(st.session_state.itens)
    # Escondemos o custo unitário do cliente na visualização final se desejar
    st.table(df[["Item", "Descrição", "Un", "Qtd", "Preço Venda", "Total"]])
    
    subtotal = df["Total"].sum()
    total_com_desconto = subtotal - desconto_final
    
    col_t1, col_t2 = st.columns(2)
    with col_t2:
        st.write(f"**Subtotal:** R$ {subtotal:.2f}")
        st.write(f"**Desconto:** R$ {desconto_final:.2f}")
        st.subheader(f"Total Final: R$ {total_com_desconto:.2f}")

    # --- FUNÇÃO GERAR PDF ---
    def gerar_pdf():
        pdf = FPDF()
        pdf.add_page()
        
        # Cabeçalho
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, cabecalho, ln=True, align="C")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, f"Contato: {contato_empresa} | Vendedor: {vendedor}", ln=True, align="C")
        pdf.ln(10)
        
        # Tabela de Itens
        pdf.set_font("Arial", "B", 10)
        pdf.cell(10, 8, "Nº", 1)
        pdf.cell(80, 8, "Descrição", 1)
        pdf.cell(15, 8, "Un", 1)
        pdf.cell(15, 8, "Qtd", 1)
        pdf.cell(30, 8, "Unit. (R$)", 1)
        pdf.cell(30, 8, "Total (R$)", 1)
        pdf.ln()
        
        pdf.set_font("Arial", "", 10)
        for i, row in df.iterrows():
            pdf.cell(10, 8, str(row["Item"]), 1)
            pdf.cell(80, 8, row["Descrição"], 1)
            pdf.cell(15, 8, row["Un"], 1)
            pdf.cell(15, 8, str(row["Qtd"]), 1)
            pdf.cell(30, 8, f"{row['Preço Venda']:.2f}", 1)
            pdf.cell(30, 8, f"{row['Total']:.2f}", 1)
            pdf.ln()
            
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(0, 8, f"Forma de Pagamento: {forma_pagamento}", ln=True)
        pdf.cell(0, 8, f"TOTAL DO ORÇAMENTO: R$ {total_com_desconto:.2f}", ln=True)
        
        # Rodapé
        pdf.ln(10)
        pdf.set_font("Arial", "I", 9)
        pdf.multi_cell(0, 5, rodape)
        
        return bytes(pdf.output())

    pdf_bytes = gerar_pdf()
    st.download_button(
        label="📥 Baixar Orçamento em PDF",
        data=pdf_bytes,
        file_name="orcamento.pdf",
        mime="application/pdf"
    )

    if st.button("Limpar Tudo"):
        st.session_state.itens = []
        st.rerun()
else:
    st.info("Adicione itens para visualizar o orçamento.")

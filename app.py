import streamlit as st
import pandas as pd
from fpdf import FPDF

st.set_page_config(page_title="Sistema de Vendas Pro", layout="wide")

# Inicialização do estado
if 'itens' not in st.session_state:
    st.session_state.itens = []

# --- SIDEBAR: CONFIGURAÇÕES FIXAS (A SUA MARCA) ---
with st.sidebar:
    st.header("🖼️ Identificação Visual")
    # Link para sua logo (pode ser um link do Imgur ou do próprio GitHub)
    logo_url = st.text_input("URL da Logo (Opcional)", "")
    if logo_url:
        st.image(logo_url, width=150)
    
    st.header("🏢 Dados Fixos")
    nome_empresa = st.text_input("Nome da Empresa", "Minha Loja")
    contato_vendedor = st.text_input("Vendedor / Contato", "João - (11) 99999-9999")
    
    st.divider()
    st.header("⚙️ Markup Padrão")
    markup_padrao = st.number_input("Markup Geral", value=1.80, step=0.05)
    
    st.divider()
    st.header("📄 Rodapé do PDF")
    rodape_texto = st.text_area("Termos e Condições", "Validade: 3 dias. Garantia de fábrica.")

# --- ÁREA DE LANÇAMENTO ---
st.title("📄 Orçamento Detalhado")

with st.expander("➕ Lançar Item (Markup ou Desconto Personalizado)", expanded=True):
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        nome = st.text_input("Descrição do Produto/Serviço")
    with c2:
        unidade = st.selectbox("Un", ["UN", "KG", "MT", "CX", "PAR"])
    with c3:
        qtd = st.number_input("Quantidade", min_value=1, value=1)
    
    c4, c5, c6 = st.columns(3)
    with c4:
        custo = st.number_input("Custo Unit. (R$)", min_value=0.0, format="%.2f")
    with c5:
        # Permite mudar o markup só para esse item
        markup_item = st.number_input("Markup para este item", value=markup_padrao)
    with c6:
        # Permite aplicar um desconto específico no item
        desc_item = st.number_input("Desconto no Item (R$)", value=0.0)

    if st.button("Adicionar Item ao Orçamento"):
        if nome and custo > 0:
            preco_base = custo * markup_item
            preco_final_un = preco_base - desc_item
            total_item = preco_final_un * qtd
            
            st.session_state.itens.append({
                "Nº": len(st.session_state.itens) + 1,
                "Descrição": nome,
                "Un": unidade,
                "Qtd": qtd,
                "Custo": custo,
                "MKP": markup_item,
                "Preço Un.": round(preco_final_un, 2),
                "Total": round(total_item, 2)
            })
            st.rerun()

# --- EXIBIÇÃO E CÁLCULOS ---
if st.session_state.itens:
    df = pd.DataFrame(st.session_state.itens)
    st.table(df[["Nº", "Descrição", "Un", "Qtd", "MKP", "Preço Un.", "Total"]])
    
    subtotal = df["Total"].sum()
    
    st.divider()
    
    # --- COMPARATIVO DE PAGAMENTOS ---
    st.subheader("💳 Formas de Pagamento (Cálculo Automático)")
    
    # Defina aqui as suas regras de taxas/descontos
    pagamentos = {
        "Pix / Dinheiro (5% OFF)": subtotal * 0.95,
        "Cartão de Débito (Sem desc)": subtotal,
        "Cartão de Crédito 1x": subtotal * 1.03, # Exemplo: taxa de 3%
        "Crédito Parcelado (Até 3x)": subtotal * 1.05 # Exemplo: taxa de 5%
    }
    
    cols_pag = st.columns(len(pagamentos))
    for i, (nome_pag, valor_pag) in enumerate(pagamentos.items()):
        cols_pag[i].metric(nome_pag, f"R$ {valor_pag:.2f}")

    # Seleção para o PDF
    opcao_pdf = st.selectbox("Qual forma de pagamento sairá no PDF?", list(pagamentos.keys()))
    valor_pdf = pagamentos[opcao_pdf]

    # --- GERAR PDF ---
    def gerar_pdf(nome_emp, contato, itens_df, total_f, forma_p, rod):
        pdf = FPDF()
        pdf.add_page()
        
        # Cabeçalho Fixo
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, nome_emp.upper(), ln=True, align="L")
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, f"Contato: {contato}", ln=True, align="L")
        pdf.line(10, 30, 200, 30)
        pdf.ln(15)
        
        # Tabela
        pdf.set_font("Arial", "B", 10)
        pdf.cell(10, 8, "N", 1)
        pdf.cell(90, 8, "Descricao", 1)
        pdf.cell(15, 8, "Un", 1)
        pdf.cell(15, 8, "Qtd", 1)
        pdf.cell(30, 8, "Unit (R$)", 1)
        pdf.cell(30, 8, "Total (R$)", 1)
        pdf.ln()
        
        pdf.set_font("Arial", "", 10)
        for _, row in itens_df.iterrows():
            pdf.cell(10, 8, str(row["Nº"]), 1)
            pdf.cell(90, 8, str(row["Descrição"]), 1)
            pdf.cell(15, 8, str(row["Un"]), 1)
            pdf.cell(15, 8, str(row["Qtd"]), 1)
            pdf.cell(30, 8, f"{row['Preço Un.']:.2f}", 1)
            pdf.cell(30, 8, f"{row['Total']:.2f}", 1)
            pdf.ln()
        
        # Fechamento
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, f"FORMA DE PAGAMENTO: {forma_p}", ln=True)
        pdf.set_text_color(255, 0, 0)
        pdf.cell(0, 8, f"TOTAL FINAL: R$ {total_f:.2f}", ln=True)
        pdf.set_text_color(0, 0, 0)
        
        # Rodapé
        pdf.ln(10)
        pdf.set_font("Arial", "I", 8)
        pdf.multi_cell(0, 5, rod)
        
        return bytes(pdf.output())

    btn_pdf = gerar_pdf(nome_empresa, contato_vendedor, df, valor_pdf, opcao_pdf, rodape_texto)
    
    st.download_button(
        label="📥 Baixar Orçamento em PDF",
        data=btn_pdf,
        file_name=f"orcamento_{nome_empresa}.pdf",
        mime="application/pdf"
    )

    if st.button("🔴 Limpar Tudo"):
        st.session_state.itens = []
        st.rerun()

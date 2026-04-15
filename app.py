import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime

st.set_page_config(page_title="Sistema de Vendas Pro", layout="wide")

# --- INICIALIZAÇÃO DO ESTADO ---
if 'itens' not in st.session_state:
    st.session_state.itens = []
if 'id_orcamento' not in st.session_state:
    # Gera um ID baseado em AnoMesDiaHoraMinuto
    st.session_state.id_orcamento = datetime.now().strftime("%Y%m%d-%H%M")

# --- SIDEBAR: CONFIGURAÇÕES FIXAS ---
with st.sidebar:
    st.header("🖼️ Identificação Visual")
    logo_url = st.text_input("URL da Logo (Opcional)", "")
    if logo_url:
        st.image(logo_url, width=150)
    
    st.header("🏢 Dados Fixos")
    nome_empresa = st.text_input("Nome da Empresa", "Minha Loja")
    contato_vendedor = st.text_input("Vendedor / Contato", "João - (11) 99999-9999")
    
    st.divider()
    st.header("⚙️ Configuração Geral")
    markup_padrao = st.number_input("Markup Padrão", value=1.80, step=0.05)
    
    st.divider()
    st.header("📄 Rodapé do PDF")
    rodape_texto = st.text_area("Termos e Condições", "Validade: 3 dias. Garantia de fábrica.")

# --- ÁREA DE LANÇAMENTO ---
st.title(f"📄 Orçamento Nº: {st.session_state.id_orcamento}")

with st.expander("➕ Lançar Novo Item", expanded=True):
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
        markup_item = st.number_input("Markup do item", value=markup_padrao)
    with c6:
        desc_item = st.number_input("Desconto no Item (R$)", value=0.0)

    if st.button("Adicionar Item"):
        if nome and custo > 0:
            preco_final_un = (custo * markup_item) - desc_item
            st.session_state.itens.append({
                "Nº": len(st.session_state.itens) + 1,
                "Descrição": nome,
                "Un": unidade,
                "Qtd": qtd,
                "Preço Un.": round(preco_final_un, 2),
                "Total": round(preco_final_un * qtd, 2)
            })
            st.rerun()

# --- TABELA EDITÁVEL (PARA CORREÇÃO) ---
st.subheader("🛒 Itens do Orçamento (Clique para editar)")
if st.session_state.itens:
    df_original = pd.DataFrame(st.session_state.itens)
    
    # O data_editor permite que você mude qualquer valor direto na tabela
    df_editado = st.data_editor(
        df_original, 
        num_rows="dynamic", 
        use_container_width=True,
        key="editor_itens"
    )
    # Recalcula o total caso o usuário mude Qtd ou Preço Un. manualmente
    df_editado["Total"] = df_editado["Qtd"] * df_editado["Preço Un."]
    st.session_state.itens = df_editado.to_dict('records')
    
    subtotal = df_editado["Total"].sum()
    st.markdown(f"### Subtotal: **R$ {subtotal:.2f}**")

    st.divider()

    # --- GERENCIADOR DE PAGAMENTOS ---
    st.subheader("💳 Formas de Pagamento e Condições")
    
    # Criamos uma lista de opções para o usuário habilitar
    opcoes_pag = [
        {"nome": "Pix / Dinheiro", "ajuste_padrao": -5.0}, # -5% desconto
        {"nome": "Cartão de Débito", "ajuste_padrao": 0.0},
        {"nome": "Cartão de Crédito (1x)", "ajuste_padrao": 3.5}, # +3.5% taxa
        {"nome": "Crédito Parcelado", "ajuste_padrao": 7.0}
    ]

    escolhas_finais = []
    col_pag_1, col_pag_2 = st.columns(2)

    for i, op in enumerate(opcoes_pag):
        # Colocamos as opções em duas colunas para economizar espaço
        alvo = col_pag_1 if i % 2 == 0 else col_pag_2
        
        with alvo:
            habilitar = st.checkbox(f"Exibir {op['nome']}", value=True, key=f"chk_{i}")
            if habilitar:
                percentual = st.number_input(f"% Ajuste para {op['nome']} (- para desc, + para taxa)", value=op['ajuste_padrao'], key=f"perc_{i}")
                valor_final = subtotal * (1 + (percentual / 100))
                st.write(f"➡️ **Final: R$ {valor_final:.2f}**")
                escolhas_finais.append({"nome": op['nome'], "valor": valor_final, "ajuste": percentual})

    st.divider()

    # Seleção do que vai para o PDF
    opcao_selecionada_pdf = st.selectbox("Selecione a forma de pagamento que aparecerá no PDF:", [e['nome'] for e in escolhas_finais])
    dados_pag_pdf = next(item for item in escolhas_finais if item["nome"] == opcao_selecionada_pdf)

    # --- FUNÇÃO GERAR PDF ---
    def gerar_pdf(nome_emp, contato, id_orc, itens_df, dados_pag, rod):
        pdf = FPDF()
        pdf.add_page()
        
        # Cabeçalho
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, nome_emp.upper(), ln=True)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 5, f"Orçamento: {id_orc} | Contato: {contato}", ln=True)
        pdf.cell(0, 5, f"Data: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.line(10, 32, 200, 32)
        pdf.ln(10)
        
        # Tabela
        pdf.set_font("Arial", "B", 10)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(10, 8, "N", 1, 0, "C", True)
        pdf.cell(90, 8, "Descricao", 1, 0, "L", True)
        pdf.cell(15, 8, "Un", 1, 0, "C", True)
        pdf.cell(15, 8, "Qtd", 1, 0, "C", True)
        pdf.cell(30, 8, "Unit (R$)", 1, 0, "R", True)
        pdf.cell(30, 8, "Total (R$)", 1, 1, "R", True)
        
        pdf.set_font("Arial", "", 10)
        for _, row in itens_df.iterrows():
            pdf.cell(10, 8, str(row["Nº"]), 1, 0, "C")
            pdf.cell(90, 8, str(row["Descrição"]), 1)
            pdf.cell(15, 8, str(row["Un"]), 1, 0, "C")
            pdf.cell(15, 8, str(row["Qtd"]), 1, 0, "C")
            pdf.cell(30, 8, f"{row['Preço Un.']:.2f}", 1, 0, "R")
            pdf.cell(30, 8, f"{row['Total']:.2f}", 1, 1, "R")
        
        # Fechamento
        pdf.ln(5)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 8, f"FORMA DE PAGAMENTO: {dados_pag['nome']}", ln=True)
        pdf.set_text_color(200, 0, 0)
        pdf.cell(0, 8, f"TOTAL DO ORCAMENTO: R$ {dados_pag['valor']:.2f}", ln=True)
        pdf.set_text_color(0, 0, 0)
        
        # Rodapé
        pdf.ln(10)
        pdf.set_font("Arial", "I", 8)
        pdf.multi_cell(0, 5, rod)
        
        return bytes(pdf.output())

    btn_pdf = gerar_pdf(nome_empresa, contato_vendedor, st.session_state.id_orcamento, df_editado, dados_pag_pdf, rodape_texto)
    
    st.download_button(
        label="📥 Baixar Orçamento em PDF",
        data=btn_pdf,
        file_name=f"orcamento_{st.session_state.id_orcamento}.pdf",
        mime="application/pdf"
    )

    if st.button("🔴 Novo Orçamento (Limpar Tudo)"):
        st.session_state.itens = []
        # Gera novo ID
        st.session_state.id_orcamento = datetime.now().strftime("%Y%m%d-%H%M")
        st.rerun()
else:
    st.info("Adicione itens para começar.")

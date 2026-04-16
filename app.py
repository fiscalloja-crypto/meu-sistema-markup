import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import ast

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Vendas Pro", layout="wide")

# --- CORREÇÃO AUTOMÁTICA DA CHAVE PRIVADA ---
# Isso resolve o erro "InvalidPadding" ou "InvalidByte" 
# limpando a chave antes de passar para a conexão.
if "connections" in st.secrets and "gsheets" in st.secrets.connections:
    raw_key = st.secrets.connections.gsheets.private_key
    # Remove aspas extras acidentais e converte \n literal em quebra de linha real
    clean_key = raw_key.strip().replace("\\n", "\n")
    if clean_key.startswith('"') and clean_key.endswith('"'):
        clean_key = clean_key[1:-1]
    st.secrets.connections.gsheets.private_key = clean_key

# Conexão com Google Sheets
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Erro na conexão: {e}")

# --- INICIALIZAÇÃO DO ESTADO ---
if 'itens' not in st.session_state:
    st.session_state.itens = []
if 'id_orcamento' not in st.session_state:
    st.session_state.id_orcamento = datetime.now().strftime("%Y%m%d-%H%M")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🏢 Configurações")
    nome_empresa = st.text_input("Nome da Empresa", "Minha Loja")
    contato_vendedor = st.text_input("Vendedor / Contato", "João - (11) 99999-9999")
    markup_padrao = st.number_input("Markup Padrão", value=1.80, step=0.05)
    st.divider()
    if st.button("🔄 Forçar Sincronização"):
        st.cache_data.clear()
        st.rerun()

aba1, aba2 = st.tabs(["📝 Novo Orçamento", "📂 Histórico"])

with aba1:
    st.title(f"Orçamento: {st.session_state.id_orcamento}")
    
    with st.expander("➕ Adicionar Item", expanded=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1: nome = st.text_input("Descrição")
        with c2: unidade = st.selectbox("Un", ["UN", "KG", "MT", "CX"])
        with c3: qtd = st.number_input("Quantidade", min_value=1, value=1)
        
        c4, c5, c6 = st.columns(3)
        with c4: custo = st.number_input("Custo Unit. (R$)", min_value=0.0)
        with c5: mkp = st.number_input("Markup", value=markup_padrao)
        with c6: desc = st.number_input("Desconto (R$)", value=0.0)

        if st.button("Adicionar"):
            if nome and custo > 0:
                preco_un = (custo * mkp) - desc
                st.session_state.itens.append({
                    "Nº": len(st.session_state.itens) + 1, "Descrição": nome, "Un": unidade,
                    "Qtd": qtd, "Preço Un.": round(preco_un, 2), "Total": round(preco_un * qtd, 2)
                })
                st.rerun()

    if st.session_state.itens:
        df_itens = pd.DataFrame(st.session_state.itens)
        df_editado = st.data_editor(df_itens, num_rows="dynamic", use_container_width=True)
        df_editado["Total"] = df_editado["Qtd"] * df_editado["Preço Un."]
        st.session_state.itens = df_editado.to_dict('records')
        subtotal = df_editado["Total"].sum()
        
        st.subheader("💳 Condições de Pagamento")
        col_p1, col_p2 = st.columns(2)
        form_pag = ["Pix / Dinheiro", "Cartão", "Crédito 1x"]
        escolhas_pag = []
        for i, f in enumerate(form_pag):
            c_p = col_p1 if i % 2 == 0 else col_p2
            with c_p:
                if st.checkbox(f"Habilitar {f}", value=True, key=f"chk_{f}"):
                    taxa = st.number_input(f"% Ajuste {f}", value=-5.0 if "Pix" in f else 0.0, key=f"t_{f}")
                    valor_f = subtotal * (1 + (taxa/100))
                    escolhas_pag.append({"nome": f, "valor": valor_f})

        if escolhas_pag:
            selecionado = st.selectbox("Forma para o PDF", [e['nome'] for e in escolhas_pag])
            v_final = next(e['valor'] for e in escolhas_pag if e['nome'] == selecionado)

            c_b1, c_b2, c_b3 = st.columns(3)
            with c_b1:
                if st.button("💾 SALVAR NA PLANILHA"):
                    try:
                        existente = conn.read(ttl=0)
                        novo_reg = pd.DataFrame([{
                            "ID": st.session_state.id_orcamento,
                            "Data": datetime.now().strftime("%d/%m/%Y"),
                            "Total": v_final,
                            "Cliente": "Venda Direta",
                            "Itens": str(st.session_state.itens)
                        }])
                        atualizado = pd.concat([existente, novo_reg], ignore_index=True)
                        conn.update(data=atualizado)
                        st.success("Salvo com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

            with c_b2:
                # Função simples para gerar PDF
                def gerar_pdf():
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", "B", 16)
                    pdf.cell(0, 10, nome_empresa.upper(), ln=True)
                    pdf.set_font("Arial", "", 10)
                    pdf.cell(0, 5, f"Orçamento: {st.session_state.id_orcamento}", ln=True)
                    pdf.ln(10)
                    for r in st.session_state.itens:
                        pdf.cell(0, 8, f"{r['Qtd']}x {r['Descrição']} - R$ {r['Total']:.2f}", ln=True)
                    pdf.ln(5)
                    pdf.cell(0, 10, f"TOTAL: R$ {v_final:.2f}", ln=True)
                    return bytes(pdf.output())
                
                st.download_button("📥 Gerar PDF", data=gerar_pdf(), file_name=f"Orc_{st.session_state.id_orcamento}.pdf")

            with c_b3:
                if st.button("🔴 Novo / Limpar"):
                    st.session_state.itens = []
                    st.session_state.id_orcamento = datetime.now().strftime("%Y%m%d-%H%M")
                    st.rerun()

with aba2:
    st.title("📂 Histórico")
    try:
        dados = conn.read(ttl="1m")
        st.dataframe(dados, use_container_width=True)
    except:
        st.info("Nenhum dado encontrado ou planilha não configurada.")

import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import ast

st.set_page_config(page_title="Sistema de Vendas Pro", layout="wide")

# Conexão com Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

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
    if st.button("🔄 Sincronizar com Google Sheets"):
        st.cache_data.clear()
        st.rerun()

aba1, aba2 = st.tabs(["📝 Novo Orçamento / Edição", "📂 Histórico (Google Sheets)"])

with aba1:
    st.title(f"Orçamento: {st.session_state.id_orcamento}")
    
    # Lançamento de Itens
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
        
        # Pagamentos
        st.subheader("💳 Condições de Pagamento")
        col_p1, col_p2 = st.columns(2)
        form_pag = ["Pix / Dinheiro", "Cartão de Débito", "Crédito 1x", "Crédito Parcelado"]
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
                        # Busca dados atuais
                        existente = conn.read(ttl=0)
                        novo_reg = pd.DataFrame([{
                            "ID": st.session_state.id_orcamento,
                            "Data": datetime.now().strftime("%d/%m/%Y"),
                            "Total": v_final,
                            "Cliente": "Venda Direta",
                            "Itens": str(st.session_state.itens)
                        }])
                        # Junta e salva
                        atualizado = pd.concat([existente, novo_reg], ignore_index=True)
                        conn.update(data=atualizado)
                        st.success("Salvo no Google Sheets!")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

            def gerar_pdf():
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, nome_empresa.upper(), ln=True)
                pdf.set_font("Arial", "", 10)
                pdf.cell(0, 5, f"Orçamento: {st.session_state.id_orcamento}", ln=True)
                pdf.line(10, 28, 200, 28); pdf.ln(10)
                pdf.set_font("Arial", "B", 10)
                pdf.cell(10, 8, "N", 1); pdf.cell(90, 8, "Desc", 1); pdf.cell(15, 8, "Qtd", 1); pdf.cell(30, 8, "Total", 1); pdf.ln()
                pdf.set_font("Arial", "", 10)
                for i, r in df_editado.iterrows():
                    pdf.cell(10, 8, str(r["Nº"]), 1); pdf.cell(90, 8, str(r["Descrição"]), 1)
                    pdf.cell(15, 8, str(r["Qtd"]), 1); pdf.cell(30, 8, f"{r['Total']:.2f}", 1); pdf.ln()
                pdf.ln(5); pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, f"TOTAL: R$ {v_final:.2f} ({selecionado})", ln=True)
                return bytes(pdf.output())

            with c_b2:
                st.download_button("📥 Gerar PDF", data=gerar_pdf(), file_name=f"Orc_{st.session_state.id_orcamento}.pdf")
            with c_b3:
                if st.button("🔴 Novo / Limpar"):
                    st.session_state.itens = []; st.session_state.id_orcamento = datetime.now().strftime("%Y%m%d-%H%M")
                    st.rerun()

with aba2:
    st.title("📂 Histórico Profissional")
    try:
        dados_historico = conn.read(ttl="10m")
        if not dados_historico.empty:
            busca = st.text_input("Filtrar por ID ou Data")
            df_exibir = dados_historico
            if busca:
                df_exibir = dados_historico[dados_historico.astype(str).apply(lambda x: busca in x.values, axis=1)]
            
            st.dataframe(df_exibir[["ID", "Data", "Total", "Cliente"]], use_container_width=True)
            
            id_carregar = st.selectbox("Selecione para EDITAR:", dados_historico["ID"].unique())
            if st.button("⚡ Carregar Orçamento"):
                reg = dados_historico[dados_historico["ID"] == id_carregar].iloc[0]
                st.session_state.id_orcamento = reg["ID"]
                st.session_state.itens = ast.literal_eval(reg["Itens"])
                st.success("Carregado! Vá para a Aba 1.")
        else:
            st.info("Planilha vazia.")
    except:
        st.warning("Conecte a planilha nos Secrets para ver o histórico.")

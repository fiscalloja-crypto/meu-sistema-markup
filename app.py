import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime

st.set_page_config(page_title="Sistema de Vendas Pro", layout="wide")

# --- INICIALIZAÇÃO DO ESTADO ---
if 'itens' not in st.session_state:
    st.session_state.itens = []
if 'id_orcamento' not in st.session_state:
    st.session_state.id_orcamento = datetime.now().strftime("%Y%m%d-%H%M")
if 'historico' not in st.session_state:
    st.session_state.historico = pd.DataFrame()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🏢 Configurações da Empresa")
    nome_empresa = st.text_input("Nome da Empresa", "Minha Loja")
    contato_vendedor = st.text_input("Vendedor / Contato", "João - (11) 99999-9999")
    st.divider()
    markup_padrao = st.number_input("Markup Padrão", value=1.80, step=0.05)
    st.divider()
    # DICA: Para salvar de verdade, você precisará configurar o st.connection("gsheets")
    st.info("Para persistência total entre dias, conecte ao Google Sheets nas configurações de Secrets.")

# --- NAVEGAÇÃO POR ABAS ---
aba1, aba2 = st.tabs(["📝 Novo Orçamento / Edição", "📂 Histórico de Orçamentos"])

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
                    "Nº": len(st.session_state.itens) + 1,
                    "Descrição": nome,
                    "Un": unidade,
                    "Qtd": qtd,
                    "Preço Un.": round(preco_un, 2),
                    "Total": round(preco_un * qtd, 2)
                })
                st.rerun()

    # Tabela Editável
    if st.session_state.itens:
        df_itens = pd.DataFrame(st.session_state.itens)
        st.subheader("Itens Lançados (Edite se necessário)")
        df_editado = st.data_editor(df_itens, num_rows="dynamic", use_container_width=True)
        df_editado["Total"] = df_editado["Qtd"] * df_editado["Preço Un."]
        st.session_state.itens = df_editado.to_dict('records')
        
        subtotal = df_editado["Total"].sum()
        
        st.divider()
        
        # Pagamentos e Descontos
        st.subheader("💳 Condições de Pagamento")
        col_p1, col_p2 = st.columns(2)
        
        # Lógica de seleção e desconto dinâmico
        form_pag = ["Pix / Dinheiro", "Cartão de Débito", "Crédito 1x", "Crédito Parcelado"]
        escolhas_pag = []
        
        for i, f in enumerate(form_pag):
            c_p = col_p1 if i % 2 == 0 else col_p2
            with c_p:
                if st.checkbox(f"Habilitar {f}", value=True):
                    taxa = st.number_input(f"% Ajuste {f}", value=-5.0 if "Pix" in f else 0.0, key=f"t_{f}")
                    valor_f = subtotal * (1 + (taxa/100))
                    st.write(f"Valor: R$ {valor_f:.2f}")
                    escolhas_pag.append({"nome": f, "valor": valor_f})

        # Seleção Final para o PDF
        if escolhas_pag:
            selecionado = st.selectbox("Forma para o PDF", [e['nome'] for e in escolhas_pag])
            v_final = next(e['valor'] for e in escolhas_pag if e['nome'] == selecionado)

            # --- BOTÕES DE AÇÃO ---
            c_b1, c_b2, c_b3 = st.columns(3)
            
            with c_b1:
                if st.button("💾 Salvar no Banco de Dados"):
                    # Aqui simulamos o salvamento. Em um app real, enviamos para o Google Sheets.
                    novo_registro = {
                        "ID": st.session_state.id_orcamento,
                        "Data": datetime.now().strftime("%d/%m/%Y"),
                        "Total": v_final,
                        "Cliente": "Venda Direta",
                        "Itens": str(st.session_state.itens) # Salva os itens como texto para recuperar depois
                    }
                    # Adiciona ao histórico temporário
                    st.session_state.historico = pd.concat([st.session_state.historico, pd.DataFrame([novo_registro])])
                    st.success("Orçamento Salvo com Sucesso!")

            # Gerador de PDF (Mesma lógica anterior com melhorias visuais)
            def gerar_pdf():
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", "B", 16)
                pdf.cell(0, 10, nome_empresa.upper(), ln=True)
                pdf.set_font("Arial", "", 10)
                pdf.cell(0, 5, f"Orçamento: {st.session_state.id_orcamento} | Contato: {contato_vendedor}", ln=True)
                pdf.line(10, 28, 200, 28)
                pdf.ln(10)
                
                # Tabela no PDF
                pdf.set_font("Arial", "B", 10)
                pdf.cell(10, 8, "N", 1); pdf.cell(90, 8, "Descricao", 1); pdf.cell(15, 8, "Un", 1)
                pdf.cell(15, 8, "Qtd", 1); pdf.cell(30, 8, "Total (R$)", 1); pdf.ln()
                pdf.set_font("Arial", "", 10)
                for i, r in df_editado.iterrows():
                    pdf.cell(10, 8, str(r["Nº"]), 1)
                    pdf.cell(90, 8, str(r["Descrição"]), 1)
                    pdf.cell(15, 8, str(r["Un"]), 1)
                    pdf.cell(15, 8, str(r["Qtd"]), 1)
                    pdf.cell(30, 8, f"{r['Total']:.2f}", 1); pdf.ln()
                
                pdf.ln(5)
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, f"TOTAL: R$ {v_final:.2f} ({selecionado})", ln=True)
                return bytes(pdf.output())

            with c_b2:
                st.download_button("📥 Gerar PDF", data=gerar_pdf(), file_name=f"Orc_{st.session_state.id_orcamento}.pdf")

            with c_b3:
                if st.button("🔴 Novo / Limpar"):
                    st.session_state.itens = []
                    st.session_state.id_orcamento = datetime.now().strftime("%Y%m%d-%H%M")
                    st.rerun()

with aba2:
    st.title("📂 Consultar Histórico")
    if not st.session_state.historico.empty:
        # Filtro por data
        data_busca = st.text_input("Buscar por data (Ex: 16/04/2026)")
        
        df_hist = st.session_state.historico
        if data_busca:
            df_hist = df_hist[df_hist["Data"] == data_busca]
            
        st.dataframe(df_hist[["ID", "Data", "Total", "Cliente"]], use_container_width=True)
        
        st.divider()
        id_para_editar = st.selectbox("Selecione um ID para RE-EDITAR ou IMPRIMIR:", df_hist["ID"].unique())
        
        if st.button("⚡ Carregar este Orçamento"):
            # Lógica para puxar os dados de volta para a aba principal
            registro = df_hist[df_hist["ID"] == id_para_editar].iloc[0]
            st.session_state.id_orcamento = registro["ID"]
            # Converte a string de volta para lista
            import ast
            st.session_state.itens = ast.literal_eval(registro["Itens"])
            st.success("Orçamento carregado na Aba 1!")
            # st.rerun() não funciona bem entre abas, o usuário clica na aba 1 para ver.
    else:
        st.warning("Ainda não há orçamentos salvos nesta sessão.")

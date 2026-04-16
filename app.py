import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Sistema de Vendas Pro", layout="wide")

# --- CONEXÃO CORRIGIDA ---
# st-gsheets-connection lê AUTOMATICAMENTE do secrets.toml
# Basta chamar st.connection com o nome definido lá
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

try:
    conn = get_connection()
    url_planilha = st.secrets["connections"]["gsheets"]["spreadsheet"]
except Exception as e:
    st.error(f"Erro ao configurar conexão: {e}")
    st.info("Verifique se o arquivo .streamlit/secrets.toml está correto.")
    st.stop()

# --- INICIALIZAÇÃO DO ESTADO ---
if 'itens' not in st.session_state:
    st.session_state.itens = []
if 'id_orcamento' not in st.session_state:
    st.session_state.id_orcamento = datetime.now().strftime("%Y%m%d-%H%M")
if 'cliente' not in st.session_state:
    st.session_state.cliente = ""

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🏢 Configurações")
    nome_empresa = st.text_input("Nome da Empresa", "Minha Loja")
    contato_vendedor = st.text_input("Vendedor / Contato", "João - (11) 99999-9999")
    markup_padrao = st.number_input("Markup Padrão", value=1.80, step=0.05)
    st.divider()
    st.caption(f"Orçamento: {st.session_state.id_orcamento}")
    if st.button("🔄 Limpar Cache / Recarregar"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

aba1, aba2 = st.tabs(["📝 Novo Orçamento", "📂 Histórico"])

with aba1:
    st.title(f"Orçamento: {st.session_state.id_orcamento}")

    # Campo de cliente
    st.session_state.cliente = st.text_input(
        "👤 Nome do Cliente", 
        value=st.session_state.cliente,
        placeholder="Ex: João Silva / Empresa XYZ"
    )

    with st.expander("➕ Adicionar Item", expanded=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1: nome = st.text_input("Descrição")
        with c2: unidade = st.selectbox("Un", ["UN", "KG", "MT", "CX", "PC", "RL"])
        with c3: qtd = st.number_input("Quantidade", min_value=1, value=1)

        c4, c5, c6 = st.columns(3)
        with c4: custo = st.number_input("Custo Unit. (R$)", min_value=0.0, format="%.2f")
        with c5: mkp = st.number_input("Markup", value=markup_padrao, step=0.05)
        with c6: desc = st.number_input("Desconto (R$)", value=0.0, format="%.2f")

        if st.button("➕ Adicionar Item"):
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
            else:
                st.warning("Preencha a descrição e o custo do item.")

    if st.session_state.itens:
        df_itens = pd.DataFrame(st.session_state.itens)

        # CORREÇÃO: data_editor com chave estável para não perder edições
        df_editado = st.data_editor(
            df_itens,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_itens",
            column_config={
                "Nº": st.column_config.NumberColumn(disabled=True, width="small"),
                "Total": st.column_config.NumberColumn(disabled=True, format="R$ %.2f"),
                "Preço Un.": st.column_config.NumberColumn(format="R$ %.2f"),
                "Custo": st.column_config.NumberColumn(format="R$ %.2f"),
            }
        )

        # Recalcula Total após edição
        df_editado["Total"] = (df_editado["Qtd"] * df_editado["Preço Un."]).round(2)

        # Salva de volta no estado apenas se houve mudança real
        itens_atualizados = df_editado.to_dict('records')
        if itens_atualizados != st.session_state.itens:
            st.session_state.itens = itens_atualizados

        subtotal = df_editado["Total"].sum()
        st.metric("Subtotal", f"R$ {subtotal:,.2f}")

        st.divider()
        st.subheader("💳 Condições de Pagamento")
        col_p1, col_p2 = st.columns(2)

        formas_pag = [
            ("Pix / Dinheiro", -5.0),
            ("Cartão de Débito", -2.0),
            ("Cartão de Crédito 1x", 0.0),
            ("Cartão de Crédito 2x", 3.0),
        ]
        escolhas_pag = []

        for i, (forma, taxa_padrao) in enumerate(formas_pag):
            col = col_p1 if i % 2 == 0 else col_p2
            with col:
                if st.checkbox(f"{forma}", value=(i < 2), key=f"chk_{forma}"):
                    taxa = st.number_input(
                        f"% Ajuste ({forma})",
                        value=taxa_padrao,
                        step=0.5,
                        key=f"taxa_{forma}"
                    )
                    valor_f = subtotal * (1 + taxa / 100)
                    escolhas_pag.append({"nome": forma, "valor": valor_f, "taxa": taxa})
                    st.caption(f"→ R$ {valor_f:,.2f}")

        st.divider()

        if escolhas_pag:
            selecionado = st.selectbox(
                "📄 Forma de pagamento para o PDF",
                [e['nome'] for e in escolhas_pag]
            )
            v_final = next(e['valor'] for e in escolhas_pag if e['nome'] == selecionado)
            st.success(f"**Total Final: R$ {v_final:,.2f}** ({selecionado})")

            c_b1, c_b2, c_b3 = st.columns(3)

            # --- SALVAR NA PLANILHA ---
            with c_b1:
                if st.button("💾 Salvar na Planilha", use_container_width=True):
                    try:
                        existente = conn.read(spreadsheet=url_planilha, ttl=0)
                        # Garante que o df existente não seja None
                        if existente is None or existente.empty:
                            existente = pd.DataFrame(columns=["ID", "Data", "Cliente", "Total", "Pagamento", "Itens"])

                        novo_reg = pd.DataFrame([{
                            "ID": st.session_state.id_orcamento,
                            "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "Cliente": st.session_state.cliente or "Venda Direta",
                            "Total": round(v_final, 2),
                            "Pagamento": selecionado,
                            "Itens": "; ".join([
                                f"{r['Qtd']}x {r['Descrição']}" 
                                for r in st.session_state.itens
                            ])
                        }])

                        atualizado = pd.concat([existente, novo_reg], ignore_index=True)
                        conn.update(spreadsheet=url_planilha, data=atualizado)
                        st.success("✅ Salvo com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

            # --- GERAR PDF ---
            with c_b2:
                def gerar_pdf():
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_margins(15, 15, 15)

                    # Cabeçalho
                    pdf.set_font("Helvetica", "B", 18)
                    pdf.cell(0, 10, nome_empresa.upper(), ln=True, align='C')
                    pdf.set_font("Helvetica", "", 10)
                    pdf.cell(0, 6, contato_vendedor, ln=True, align='C')
                    pdf.ln(4)

                    # Linha separadora
                    pdf.set_draw_color(200, 200, 200)
                    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                    pdf.ln(4)

                    # Info do orçamento
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.cell(0, 7, f"Orcamento: {st.session_state.id_orcamento}", ln=True)
                    pdf.set_font("Helvetica", "", 10)
                    pdf.cell(0, 6, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
                    cliente_nome = st.session_state.cliente or "Venda Direta"
                    pdf.cell(0, 6, f"Cliente: {cliente_nome}", ln=True)
                    pdf.ln(4)

                    # Cabeçalho da tabela
                    pdf.set_fill_color(40, 40, 40)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.cell(8,  8, "N",       border=0, fill=True, align='C')
                    pdf.cell(85, 8, "Descricao", border=0, fill=True)
                    pdf.cell(15, 8, "Un",      border=0, fill=True, align='C')
                    pdf.cell(15, 8, "Qtd",     border=0, fill=True, align='C')
                    pdf.cell(28, 8, "Preco Un", border=0, fill=True, align='R')
                    pdf.cell(29, 8, "Total",   border=0, fill=True, align='R')
                    pdf.ln()

                    # Linhas da tabela
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("Helvetica", "", 9)
                    fill = False
                    for i, r in enumerate(st.session_state.itens):
                        pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
                        # Remove acentos para compatibilidade com Helvetica
                        desc_safe = (str(r['Descrição'])
                            .replace('ã','a').replace('ç','c').replace('é','e')
                            .replace('ê','e').replace('á','a').replace('ó','o')
                            .replace('ú','u').replace('â','a').replace('õ','o')
                            .replace('í','i').replace('Ã','A').replace('Ç','C')
                            .replace('É','E').replace('Á','A').replace('Ó','O'))
                        pdf.cell(8,  7, str(i+1),             fill=fill, align='C')
                        pdf.cell(85, 7, desc_safe[:45],        fill=fill)
                        pdf.cell(15, 7, str(r['Un']),          fill=fill, align='C')
                        pdf.cell(15, 7, str(r['Qtd']),         fill=fill, align='C')
                        pdf.cell(28, 7, f"R${r['Preco Un.']:.2f}", fill=fill, align='R')
                        pdf.cell(29, 7, f"R${r['Total']:.2f}", fill=fill, align='R')
                        pdf.ln()
                        fill = not fill

                    # Linha final separadora
                    pdf.ln(2)
                    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                    pdf.ln(4)

                    # Totais por forma de pagamento
                    pdf.set_font("Helvetica", "B", 10)
                    pdf.cell(0, 7, f"Subtotal: R$ {subtotal:.2f}", ln=True, align='R')
                    for e in escolhas_pag:
                        sinal = f"({e['taxa']:+.1f}%)" if e['taxa'] != 0 else "(sem ajuste)"
                        pdf.cell(0, 7, f"{e['nome']} {sinal}: R$ {e['valor']:.2f}", ln=True, align='R')

                    pdf.ln(3)
                    pdf.set_font("Helvetica", "B", 13)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.cell(0, 10, f"TOTAL ({selecionado}): R$ {v_final:.2f}", ln=True, align='R', fill=True)

                    # Rodapé
                    pdf.ln(8)
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(150, 150, 150)
                    pdf.cell(0, 5, "Orcamento gerado automaticamente - valido por 7 dias", ln=True, align='C')

                    return bytes(pdf.output())

                st.download_button(
                    "📥 Baixar PDF",
                    data=gerar_pdf(),
                    file_name=f"Orc_{st.session_state.id_orcamento}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            # --- NOVO ORÇAMENTO ---
            with c_b3:
                if st.button("🔴 Novo Orçamento", use_container_width=True):
                    st.session_state.itens = []
                    st.session_state.id_orcamento = datetime.now().strftime("%Y%m%d-%H%M")
                    st.session_state.cliente = ""
                    st.rerun()

    else:
        st.info("Nenhum item adicionado ainda. Use o formulário acima para começar.")

# --- ABA HISTÓRICO ---
with aba2:
    st.title("📂 Histórico de Orçamentos")
    col_h1, col_h2 = st.columns([4, 1])
    with col_h2:
        if st.button("🔄 Atualizar", use_container_width=True):
            st.cache_data.clear()

    try:
        dados = conn.read(spreadsheet=url_planilha, ttl="1m")
        if dados is not None and not dados.empty:
            # Métricas resumo
            m1, m2, m3 = st.columns(3)
            with m1: st.metric("Total de Orçamentos", len(dados))
            with m2:
                if "Total" in dados.columns:
                    total_geral = pd.to_numeric(dados["Total"], errors='coerce').sum()
                    st.metric("Valor Total", f"R$ {total_geral:,.2f}")
            with m3:
                if "Data" in dados.columns:
                    st.metric("Último Lançamento", dados["Data"].iloc[-1] if len(dados) > 0 else "-")

            st.divider()
            st.dataframe(dados, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum orçamento salvo ainda.")
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        st.info("Verifique a conexão com o Google Sheets.")

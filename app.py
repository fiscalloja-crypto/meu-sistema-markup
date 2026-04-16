import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime, date
from streamlit_gsheets import GSheetsConnection
import unicodedata

# ─────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────
def sem_acento(txt: str) -> str:
    """Remove acentos para compatibilidade com fontes PDF básicas."""
    return unicodedata.normalize('NFKD', str(txt)).encode('ascii', 'ignore').decode('ascii')

def nova_id():
    return datetime.now().strftime("%Y%m%d-%H%M")

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(page_title="Sistema de Vendas Pro", layout="wide", page_icon="🛒")

# ─────────────────────────────────────────────
# CONEXÃO GOOGLE SHEETS
# ─────────────────────────────────────────────
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

try:
    conn = get_connection()
    url_planilha = st.secrets["connections"]["gsheets"]["spreadsheet"]
except Exception as e:
    st.error(f"Erro ao configurar conexão: {e}")
    st.info("Verifique o arquivo .streamlit/secrets.toml")
    st.stop()

# ─────────────────────────────────────────────
# INICIALIZAÇÃO DO ESTADO DA SESSÃO
# ─────────────────────────────────────────────
defaults = {
    'itens': [],
    'id_orcamento': nova_id(),
    'cliente': "",
    'prazo_tipo': "Imediato",
    'prazo_data': date.today(),
    'editando_config': False,
    'orcamento_editando': None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Configurações persistentes da empresa
config_defaults = {
    'cfg_nome_empresa': "Minha Loja",
    'cfg_cnpj': "",
    'cfg_endereco': "",
    'cfg_contato_fixo': "",
    'cfg_vendedor': "",
    'cfg_markup': 1.80,
    'cfg_validade': 7,
}
for k, v in config_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# BARRA LATERAL — CONFIGURAÇÕES FIXAS
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("🏢 Empresa")

    if not st.session_state.editando_config:
        # MODO VISUALIZAÇÃO — só leitura, não muda por acidente
        st.markdown(f"### {st.session_state.cfg_nome_empresa}")
        if st.session_state.cfg_cnpj:
            st.caption(f"**CNPJ:** {st.session_state.cfg_cnpj}")
        if st.session_state.cfg_endereco:
            st.caption(f"📍 {st.session_state.cfg_endereco}")
        if st.session_state.cfg_contato_fixo:
            st.caption(f"📞 {st.session_state.cfg_contato_fixo}")
        if st.session_state.cfg_vendedor:
            st.caption(f"👤 Vendedor: {st.session_state.cfg_vendedor}")
        st.caption(f"Markup padrão: **{st.session_state.cfg_markup:.2f}x**")
        st.caption(f"Validade dos orçamentos: **{st.session_state.cfg_validade} dias**")
        st.write("")
        if st.button("✏️ Editar Configurações", use_container_width=True):
            st.session_state.editando_config = True
            st.rerun()
    else:
        # MODO EDIÇÃO
        st.session_state.cfg_nome_empresa = st.text_input("Nome da Empresa", st.session_state.cfg_nome_empresa)
        st.session_state.cfg_cnpj         = st.text_input("CNPJ", st.session_state.cfg_cnpj, placeholder="00.000.000/0000-00")
        st.session_state.cfg_endereco     = st.text_input("Endereço", st.session_state.cfg_endereco, placeholder="Rua, nº - Cidade/UF")
        st.session_state.cfg_contato_fixo = st.text_input("Contato (tel/email)", st.session_state.cfg_contato_fixo)
        st.session_state.cfg_vendedor     = st.text_input("Vendedor Responsável", st.session_state.cfg_vendedor)
        st.session_state.cfg_markup       = st.number_input("Markup Padrão", value=float(st.session_state.cfg_markup), step=0.05, min_value=1.0)
        st.session_state.cfg_validade     = st.number_input("Validade (dias)", value=int(st.session_state.cfg_validade), min_value=1, step=1)
        if st.button("✅ Salvar Configurações", use_container_width=True, type="primary"):
            st.session_state.editando_config = False
            st.rerun()

    st.divider()
    st.caption(f"Orç. atual: `{st.session_state.id_orcamento}`")
    if st.session_state.orcamento_editando:
        st.warning(f"✏️ Reeditando:\n{st.session_state.orcamento_editando}")
    if st.button("🔄 Limpar Cache", use_container_width=True):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# Atalhos para uso no restante do app
nome_empresa  = st.session_state.cfg_nome_empresa
cnpj          = st.session_state.cfg_cnpj
endereco      = st.session_state.cfg_endereco
contato_fixo  = st.session_state.cfg_contato_fixo
vendedor      = st.session_state.cfg_vendedor
markup_padrao = st.session_state.cfg_markup
validade_dias = st.session_state.cfg_validade

# ─────────────────────────────────────────────
# ABAS PRINCIPAIS
# ─────────────────────────────────────────────
aba1, aba2 = st.tabs(["📝 Orçamento", "📂 Histórico"])

# ═══════════════════════════════════════════════════════
# ABA 1 — ORÇAMENTO
# ═══════════════════════════════════════════════════════
with aba1:
    titulo_edit = " ✏️ (REEDITANDO)" if st.session_state.orcamento_editando else ""
    st.title(f"Orçamento: {st.session_state.id_orcamento}{titulo_edit}")

    # ── Dados do cliente e prazo ──────────────────────
    col_cli1, col_cli2, col_cli3 = st.columns([3, 1, 1])
    with col_cli1:
        st.session_state.cliente = st.text_input(
            "👤 Cliente",
            value=st.session_state.cliente,
            placeholder="Nome / Empresa do cliente"
        )
    with col_cli2:
        prazo_tipo = st.selectbox(
            "🚚 Prazo de Entrega",
            ["Imediato", "Data específica"],
            index=0 if st.session_state.prazo_tipo == "Imediato" else 1,
            key="sel_prazo"
        )
        st.session_state.prazo_tipo = prazo_tipo
    with col_cli3:
        if st.session_state.prazo_tipo == "Data específica":
            prazo_data = st.date_input(
                "📅 Data",
                value=st.session_state.prazo_data,
                min_value=date.today()
            )
            st.session_state.prazo_data = prazo_data
            prazo_str = prazo_data.strftime("%d/%m/%Y")
        else:
            st.write("")
            st.info("Entrega imediata")
            prazo_str = "Imediato"

    st.divider()

    # ── Formulário de adição de itens ─────────────────
    with st.expander("➕ Adicionar Item", expanded=True):
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1: nome_item = st.text_input("Descrição do Item")
        with c2: unidade   = st.selectbox("Un.", ["UN", "KG", "MT", "CX", "PC", "RL", "M²", "HR"])
        with c3: qtd       = st.number_input("Qtd", min_value=1, value=1)

        c4, c5, c6 = st.columns(3)
        with c4: custo = st.number_input("Custo Unit. (R$)", min_value=0.0, format="%.2f")
        with c5: mkp   = st.number_input("Markup", value=float(markup_padrao), step=0.05, min_value=1.0)
        with c6: desc  = st.number_input("Desconto Unit. (R$)", value=0.0, min_value=0.0, format="%.2f")

        if st.button("➕ Adicionar Item", use_container_width=False, type="primary"):
            if nome_item and custo > 0:
                preco_un = max(0.0, (custo * mkp) - desc)
                st.session_state.itens.append({
                    "Nº": len(st.session_state.itens) + 1,
                    "Descrição": nome_item,
                    "Un": unidade,
                    "Qtd": qtd,
                    "Preço Un.": round(preco_un, 2),
                    "Total": round(preco_un * qtd, 2)
                })
                st.rerun()
            else:
                st.warning("Preencha a descrição e o custo do item.")

    # ── Tabela de itens ───────────────────────────────
    if st.session_state.itens:
        df_itens = pd.DataFrame(st.session_state.itens)
        df_editado = st.data_editor(
            df_itens,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_itens",
            column_config={
                "Nº":        st.column_config.NumberColumn(disabled=True, width="small"),
                "Total":     st.column_config.NumberColumn(disabled=True, format="R$ %.2f"),
                "Preço Un.": st.column_config.NumberColumn(format="R$ %.2f"),
            }
        )
        df_editado["Total"] = (df_editado["Qtd"] * df_editado["Preço Un."]).round(2)
        itens_att = df_editado.to_dict('records')
        if itens_att != st.session_state.itens:
            st.session_state.itens = itens_att

        subtotal = df_editado["Total"].sum()
        st.metric("Subtotal", f"R$ {subtotal:,.2f}")

        st.divider()

        # ── Formas de pagamento ───────────────────────
        st.subheader("💳 Condições de Pagamento")
        formas_pag = [
            ("Pix / Dinheiro",    -5.0),
            ("Cartão de Débito",  -2.0),
            ("Crédito 1x",         0.0),
            ("Crédito 2x",         3.0),
            ("Crédito 3x",         4.5),
            ("Boleto 30 dias",     2.0),
        ]
        escolhas_pag = []
        col_p1, col_p2 = st.columns(2)
        for i, (forma, taxa_padrao) in enumerate(formas_pag):
            col = col_p1 if i % 2 == 0 else col_p2
            with col:
                if st.checkbox(forma, value=(i < 2), key=f"chk_{forma}"):
                    taxa = st.number_input(f"% Ajuste ({forma})", value=taxa_padrao, step=0.5, key=f"taxa_{forma}")
                    valor_f = subtotal * (1 + taxa / 100)
                    escolhas_pag.append({"nome": forma, "valor": valor_f, "taxa": taxa})
                    st.caption(f"→ **R$ {valor_f:,.2f}**")

        st.divider()

        if escolhas_pag:
            selecionado = st.selectbox(
                "📄 Forma principal (usada no PDF)",
                [e['nome'] for e in escolhas_pag]
            )
            v_final = next(e['valor'] for e in escolhas_pag if e['nome'] == selecionado)
            st.success(f"**Total Final: R$ {v_final:,.2f}** — {selecionado}")

            obs = st.text_area(
                "📝 Observações (aparecem no PDF)",
                placeholder="Ex: Produto sob encomenda. Prazo sujeito à confirmação do estoque.",
                height=80
            )

            c_b1, c_b2, c_b3 = st.columns(3)

            # ── SALVAR ────────────────────────────────
            with c_b1:
                label_btn = "💾 Atualizar Orçamento" if st.session_state.orcamento_editando else "💾 Salvar na Planilha"
                if st.button(label_btn, use_container_width=True, type="primary"):
                    try:
                        existente = conn.read(spreadsheet=url_planilha, ttl=0)
                        if existente is None or existente.empty:
                            existente = pd.DataFrame(columns=["ID","Data","Cliente","Prazo","Total","Pagamento","Validade","Itens","Obs"])

                        novo_reg = pd.DataFrame([{
                            "ID":        st.session_state.id_orcamento,
                            "Data":      datetime.now().strftime("%d/%m/%Y %H:%M"),
                            "Cliente":   st.session_state.cliente or "Venda Direta",
                            "Prazo":     prazo_str,
                            "Total":     round(v_final, 2),
                            "Pagamento": selecionado,
                            "Validade":  f"{validade_dias} dias",
                            "Itens":     "; ".join([f"{r['Qtd']}x {r['Descrição']}" for r in st.session_state.itens]),
                            "Obs":       obs,
                        }])

                        if st.session_state.orcamento_editando:
                            existente = existente[existente["ID"] != st.session_state.orcamento_editando]
                            st.session_state.orcamento_editando = None

                        atualizado = pd.concat([existente, novo_reg], ignore_index=True)
                        conn.update(spreadsheet=url_planilha, data=atualizado)
                        st.success("✅ Salvo com sucesso!")
                        st.balloons()
                    except Exception as e:
                        err_str = str(e)
                        st.error(f"Erro ao salvar: {err_str}")
                        if "404" in err_str:
                            st.warning("Planilha não encontrada. Verifique a URL no secrets.toml e a permissão de Editor da service account.")
                        elif "403" in err_str:
                            st.warning("Sem permissão. Compartilhe a planilha com a service account como Editor.")

            # ── GERAR PDF ─────────────────────────────
            with c_b2:
                def gerar_pdf():
                    pdf = FPDF()
                    pdf.set_auto_page_break(auto=True, margin=20)
                    pdf.add_page()
                    pdf.set_margins(15, 15, 15)

                    # Cabeçalho escuro com nome da empresa
                    pdf.set_fill_color(30, 30, 30)
                    pdf.rect(0, 0, 210, 30, 'F')
                    pdf.set_y(7)
                    pdf.set_font("Helvetica", "B", 17)
                    pdf.set_text_color(255, 255, 255)
                    pdf.cell(0, 9, sem_acento(nome_empresa).upper(), ln=True, align='C')
                    pdf.set_font("Helvetica", "", 8)
                    linha2 = []
                    if cnpj:         linha2.append(f"CNPJ: {cnpj}")
                    if endereco:     linha2.append(sem_acento(endereco))
                    if contato_fixo: linha2.append(sem_acento(contato_fixo))
                    if linha2:
                        pdf.cell(0, 5, "  |  ".join(linha2), ln=True, align='C')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(12)

                    # Informações do orçamento
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.cell(95, 7, f"Orcamento: {st.session_state.id_orcamento}", ln=False)
                    pdf.cell(95, 7, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='R')
                    pdf.set_font("Helvetica", "", 10)
                    pdf.cell(95, 6, f"Cliente: {sem_acento(st.session_state.cliente or 'Venda Direta')}", ln=False)
                    pdf.cell(95, 6, f"Prazo de Entrega: {sem_acento(prazo_str)}", ln=True, align='R')
                    if vendedor:
                        pdf.cell(95, 6, f"Vendedor: {sem_acento(vendedor)}", ln=False)
                    pdf.cell(95 if vendedor else 0, 6, f"Validade: {validade_dias} dias a partir da emissao", ln=True, align='R' if vendedor else 'L')
                    pdf.ln(5)

                    # Tabela — cabeçalho
                    pdf.set_fill_color(30, 30, 30)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.cell(8,  8, "N",          border=0, fill=True, align='C')
                    pdf.cell(83, 8, "Descricao",  border=0, fill=True)
                    pdf.cell(14, 8, "Un",         border=0, fill=True, align='C')
                    pdf.cell(15, 8, "Qtd",        border=0, fill=True, align='C')
                    pdf.cell(30, 8, "Preco Un.",  border=0, fill=True, align='R')
                    pdf.cell(30, 8, "Total",      border=0, fill=True, align='R')
                    pdf.ln()

                    # Tabela — linhas
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("Helvetica", "", 9)
                    alt = False
                    for i, r in enumerate(st.session_state.itens):
                        pdf.set_fill_color(245, 245, 245) if alt else pdf.set_fill_color(255, 255, 255)
                        desc_safe = sem_acento(r.get('Descrição', ''))[:52]
                        preco_val = float(r.get('Preço Un.', r.get('Preco Un.', 0)))
                        total_val = float(r.get('Total', 0))
                        pdf.cell(8,  7, str(i+1),                  fill=alt, align='C')
                        pdf.cell(83, 7, desc_safe,                  fill=alt)
                        pdf.cell(14, 7, str(r.get('Un', '')),       fill=alt, align='C')
                        pdf.cell(15, 7, str(r.get('Qtd', 0)),       fill=alt, align='C')
                        pdf.cell(30, 7, f"R$ {preco_val:,.2f}",     fill=alt, align='R')
                        pdf.cell(30, 7, f"R$ {total_val:,.2f}",     fill=alt, align='R')
                        pdf.ln()
                        alt = not alt

                    # Totais
                    pdf.ln(3)
                    pdf.set_draw_color(180, 180, 180)
                    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                    pdf.ln(4)
                    pdf.set_font("Helvetica", "", 9)
                    pdf.cell(0, 5, f"Subtotal: R$ {subtotal:,.2f}", ln=True, align='R')
                    for e in escolhas_pag:
                        sinal = f" ({e['taxa']:+.1f}%)" if e['taxa'] != 0 else ""
                        pdf.cell(0, 5, f"{sem_acento(e['nome'])}{sinal}: R$ {e['valor']:,.2f}", ln=True, align='R')
                    pdf.ln(2)
                    pdf.set_fill_color(30, 30, 30)
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("Helvetica", "B", 12)
                    pdf.cell(0, 11, f"  TOTAL ({sem_acento(selecionado)}): R$ {v_final:,.2f}  ", ln=True, align='R', fill=True)
                    pdf.set_text_color(0, 0, 0)

                    # Observações
                    if obs:
                        pdf.ln(5)
                        pdf.set_font("Helvetica", "B", 9)
                        pdf.cell(0, 6, "Observacoes:", ln=True)
                        pdf.set_font("Helvetica", "", 9)
                        pdf.multi_cell(0, 5, sem_acento(obs))

                    # Rodapé da empresa (fixo na parte inferior)
                    pdf.set_y(-28)
                    pdf.set_draw_color(180, 180, 180)
                    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                    pdf.ln(2)
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(110, 110, 110)
                    rodape = [sem_acento(nome_empresa)]
                    if cnpj:         rodape.append(f"CNPJ: {cnpj}")
                    if endereco:     rodape.append(sem_acento(endereco))
                    if contato_fixo: rodape.append(sem_acento(contato_fixo))
                    pdf.cell(0, 5, "  |  ".join(rodape), ln=True, align='C')
                    pdf.cell(0, 4, f"Valido por {validade_dias} dias. Gerado em {datetime.now().strftime('%d/%m/%Y')}.", ln=True, align='C')

                    return bytes(pdf.output())

                st.download_button(
                    "📥 Baixar PDF",
                    data=gerar_pdf(),
                    file_name=f"Orc_{st.session_state.id_orcamento}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

            # ── NOVO / LIMPAR ─────────────────────────
            with c_b3:
                if st.button("🔴 Novo Orçamento", use_container_width=True):
                    st.session_state.itens = []
                    st.session_state.id_orcamento = nova_id()
                    st.session_state.cliente = ""
                    st.session_state.prazo_tipo = "Imediato"
                    st.session_state.prazo_data = date.today()
                    st.session_state.orcamento_editando = None
                    st.rerun()

    else:
        st.info("Nenhum item adicionado. Use o formulário acima para começar.")
        if st.session_state.orcamento_editando:
            st.warning("Modo reedição ativo. Adicione os itens e salve para atualizar o orçamento.")
            if st.button("❌ Cancelar reedição"):
                st.session_state.orcamento_editando = None
                st.session_state.id_orcamento = nova_id()
                st.session_state.cliente = ""
                st.rerun()

# ═══════════════════════════════════════════════════════
# ABA 2 — HISTÓRICO
# ═══════════════════════════════════════════════════════
with aba2:
    st.title("📂 Histórico de Orçamentos")
    col_h1, col_h2 = st.columns([4, 1])
    with col_h2:
        if st.button("🔄 Atualizar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    try:
        dados = conn.read(spreadsheet=url_planilha, ttl="1m")

        if dados is not None and not dados.empty:

            # ── Métricas de resumo ────────────────────
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("Orçamentos", len(dados))
            with m2:
                if "Total" in dados.columns:
                    total_geral = pd.to_numeric(dados["Total"], errors='coerce').sum()
                    st.metric("Valor Total", f"R$ {total_geral:,.2f}")
            with m3:
                if "Data" in dados.columns and len(dados) > 0:
                    st.metric("Último em", dados["Data"].iloc[-1])
            with m4:
                if "Cliente" in dados.columns:
                    st.metric("Clientes Únicos", dados["Cliente"].nunique())

            st.divider()

            # ── Filtros ───────────────────────────────
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_cliente = st.text_input("🔍 Filtrar por Cliente", "")
            with col_f2:
                filtro_id = st.text_input("🔍 Filtrar por ID", "")

            df_filtrado = dados.copy()
            if filtro_cliente:
                df_filtrado = df_filtrado[df_filtrado["Cliente"].str.contains(filtro_cliente, case=False, na=False)]
            if filtro_id:
                df_filtrado = df_filtrado[df_filtrado["ID"].str.contains(filtro_id, case=False, na=False)]

            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

            st.divider()

            # ── Reeditar orçamento ────────────────────
            st.subheader("✏️ Reabrir Orçamento para Edição")
            ids_disponiveis = dados["ID"].dropna().tolist() if "ID" in dados.columns else []

            if ids_disponiveis:
                col_re1, col_re2 = st.columns([3, 1])
                with col_re1:
                    id_sel = st.selectbox(
                        "Selecione o orçamento:",
                        ids_disponiveis[::-1],   # mais recente primeiro
                        key="sel_reabrir"
                    )
                with col_re2:
                    st.write("")
                    st.write("")
                    if st.button("✏️ Reabrir", use_container_width=True, type="primary"):
                        linha = dados[dados["ID"] == id_sel].iloc[0]

                        # Restaura dados disponíveis
                        st.session_state.itens = []            # itens precisam ser reinseridos
                        st.session_state.id_orcamento = id_sel
                        st.session_state.cliente = str(linha.get("Cliente", ""))
                        st.session_state.orcamento_editando = id_sel

                        # Tenta restaurar prazo
                        prazo_salvo = str(linha.get("Prazo", "Imediato"))
                        if prazo_salvo == "Imediato":
                            st.session_state.prazo_tipo = "Imediato"
                        else:
                            try:
                                st.session_state.prazo_data = datetime.strptime(prazo_salvo, "%d/%m/%Y").date()
                                st.session_state.prazo_tipo = "Data específica"
                            except Exception:
                                st.session_state.prazo_tipo = "Imediato"

                        st.success(f"✅ Orçamento **{id_sel}** reaberto! Vá para a aba **Orçamento** para editar.")
                        st.info(
                            "ℹ️ **Cliente e prazo foram restaurados.** "
                            "Os itens precisam ser reinseridos — a planilha guarda apenas o resumo dos itens. "
                            "Após adicionar os itens, clique em **Atualizar Orçamento** para sobrescrever o registro anterior."
                        )

        else:
            st.info("Nenhum orçamento salvo ainda.")

    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        st.info("Verifique a conexão com o Google Sheets.")

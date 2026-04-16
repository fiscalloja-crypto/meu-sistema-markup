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
                    import base64, io, tempfile, os

                    # Logo embutida em base64 (400x343px, PNG da Matriz Solar)
                    LOGO_B64 = (
                        "iVBORw0KGgoAAAANSUhEUgAAAZAAAAFXCAIAAAADMI+XAAABCGlDQ1BJQ0MgUHJvZmlsZQAAeJxj"
                        "YGA8wQAELAYMDLl5JUVB7k4KEZFRCuwPGBiBEAwSk4sLGHADoKpv1yBqL+viUYcLcKakFicD6Q9A"
                        "rFIEtBxopAiQLZIOYWuA2EkQtg2IXV5SUAJkB4DYRSFBzkB2CpCtkY7ETkJiJxcUgdT3ANk2uTml"
                        "yQh3M/Ck5oUGA2kOIJZhKGYIYnBncAL5H6IkfxEDg8VXBgbmCQixpJkMDNtbGRgkbiHEVBYwMPC3"
                        "MDBsO48QQ4RJQWJRIliIBYiZ0tIYGD4tZ2DgjWRgEL7AwMAVDQsIHG5TALvNnSEfCNMZchhSgSKe"
                        "DHkMyQx6QJYRgwGDIYMZAKbWPz9HbOBQAAEAAElEQVR4nLz9d7QuSXYXiP52ZH7mnOtv3bq3vOuq"
                        "Upmu7qpq32p1q1sgBzwhCZmRmBEgAYOQMG9g1hseCDRrBjOsxcAAD3gsjBAMCGEkQAaE1OpuSe29"
                        "qaruLtNVt/z195zzmcyM/f6IiB07TH7n3BLrRde6/Z3MyB1779jmFyYjaTL7HoJhJgBExMxMFsxg"
                        "uCsAmNn90KW8klVjZqJAiAkgZiYCiB0BMPmKYE3MsZG14q64P3UFgAALcKhGGW/M7BljI9cCD3lN"
                        "MIga9r+sVgIAtpRzFZomIjDg/gWRYWaAiYiYLchyICUqFUHkX61DhtOKJwRi30gQnK0nBbKoFWmi"
                        "7Cm5m19h45gxTVGHiVkEZ4AYTl2aOPvLzESN15Xhojkj3QXy1FJjkFYyFk0gZeGbNYaMtwFibSSl"
                        "gHLdKVlbUWG6IBjRChGYmLxtGcAABLLMFjWbLB0BudHWCzMRokkAAIGICcQgWMC7T2xIayaTNCcO"
                        "GzuPnIXBELGT0VsaAENkQU4L5HSB1JyYqeycaqP6weSKcb0G4ihOqaKoSbLMPJlM2rw9YT9tXp7U"
                        "PrZJO74+O5FBAMOQYbg+hjDmqu0rdmkBWsIioromRwjWW8iLoRAkokTpw6ERY3zED53rKhvmvLcy"
                        "X6pmgsAjMVB0n6qQPljG6LJOVlmTC1cQ9Ami3CQVNW8qFa5D3BH68oxqjslf9vG9RgFkKg96KyeS"
                        "7pXm4COd9iXPhjFGSIkZV7intHP9NdeWJTIEthBrq/cNEelcxYWaxpXv1ZJEKxBYsqtnTMX0gsJI"
                        "jwMSgkHKLJnJo4mYgyWgUQjINo3vLoAetJRhKNddKJlfVMUxof98PQaD6tGBQymbiSgmC6hEPiiH"
                        "TKrCiPN+FxTyNFWFb/p62usGMODG5RlvtanKnIV5/tNQm4WByFz4/xTNKZaSnibAuAtwgSZ9Kg18"
                        "NQBYyssY6dm6TrKLmWeWgEsLXmY2ux8cqGI39kBE0nWMnuop4ctXDkrz0DsQKVES+Ualm1QHRbTB"
                        "BCYXMkoNADAmd28FvhCwMXyfum71bmFUz8UHIx0Eq2ZShhbGLkoV1QSTF3YpRKjVHbBaatVcv4Cj"
                        "hinIqPGHi8lGVciyrOd/LPTrri+FdX8XglZ4JiIOKUdKyxbSWTG4pIqWHxuyU8EAC8hxqSM6toRy"
                        "4xAuc7CDLOoBbuADGAYbl1sy1bg8liQdN/zE4BIU+zhJLOOIwoKjphzTAm58iDUu1bjBFxGxZRAZ"
                        "4zuPwyDFBWb2uNLDrcwrtPbKNEIUIAaPKtmnWHYYxIo9lVm3TOPVmrFOiDMKS1LBiRvp1wvBeMVR"
                        "ANd1flxQcGEAIZM7/cSuh8/kYo42B2Q+2hPDAm7Q6ski2HMIZ6x+C2NWdOOaC2FU25lj1bBYEjHz"
                        "gJQLkd/ZD8HnfoxlFLg5Ch+jM9SvvCAZMUX04zsiPBaDdemkzjIdXGIiMCw57AYKo1qL0OMEw564"
                        "ECWFldmpQLfFzETGZSkVTJzhMIjCYBSADSqOsgpeEpYTuRzzQW+tEoyIyDqTCIALBy6ZQXjxAq5i"
                        "AJaDpImGSeRTRXlXclmeywFXyHwSbYkiAA7NVZAFUntyEzDuGQ6qIDYcJqp8ivNyiUuzwxYRKke3"
                        "9wpxKNKyl7fUnvojsloWiYOZCILUNFbVATHtoARtWWuVlSewK/ekKNxoUdAZEtO1Fzn0BHIQlQCQ"
                        "ce6UiEkhagb/1sFdm0eUxhsSWZUgk0CZ5YYIjACfY+CxTFCdmlIkbx5OS6SAfKLY8HgIVsFmtP14"
                        "s1DMVMyyqtxYPcVouaRZ8XjEISliE3KO73FSLbr53nTaJ+OgzPQhtiYtyvylQqP15Lpfic7eJpc5"
                        "n/zWWiihdSJHMukoYcllJxJ9heaTuCWGu5FhuDlh3fcp51keK+YFg9GCrBiYBFYx6cD2JgGlUYYh"
                        "H1/ymW/tWi40sMvsG3FQoIzMIpNH2GV5mMjvmHllZNMon4LZNKaE1jmnoJlS0dBVDTJTTMKqponB"
                        "2Pl80emlsVVYgp+OYQYg094BBbDOTQllnVBDtOIAiiSbWnigDMCPPkAhzah4rvnJ9J/liYyNcDG6"
                        "Rr2fD4YWHIwtVcR+xpzJQGxP4JyMDFwe1WMO6cHMv5B2ir4efuaoQyCby16SDsvIpRWim4tshJZb"
                        "PUkq8ovGGAx7reFQ2HUWadgKiow5ijyD+aghKs7ZFEWbkmUg/6u2FgNxGosgjo1RyCMdYa8BwNal"
                        "Y44Izq25cMChxgaBNC7Uagy9kRpxJhEHrUqvMDPYhKCpQ56vSyYGr2gQ5K7ETK3F1wp00GkMYpQl"
                        "Q17Bl8JYyAPLIDwDTE5i8sugMZd4mEXk1MsqSWUztp49EozjDVQiPrOhdB05LFAmvhqSesyHpTip"
                        "eklVVI7kkisx3KjN2PjseBCpBiZ1y82dM/kY6TpPplxtGD/6oO/5Izh3AcRjnJCsjDH3/IDtbKBA"
                        "WrgoPrss67iSHkhWG6vipNclc+TVJJJIXvJ6VSk2hgGfckLyECVQSPChCROQhkw6hD/HeRVYi6Kf"
                        "1BXpYAJc+EivOHshN5iuqyPgMghLGS+aE2k6om6GtRws0BuuwheRi/Aj8hYE9/4u2Vh5EVTSysXX"
                        "aEWoESJqch0mq1e6CJ/s5y9yBBQssvJUxkmZr0pWq7d0iwDczoGQ6kK0VUhnI7aLcSGIABFKOitG"
                        "q1A93HIG7wzaD7j8PbWpIgzAAA3EdLZIbSP8zmsCYQo0LqAY0fVGiJEXDiVWcwhbKSRoiI3xAUX/"
                        "i/CbdN4Isx4UJ/IjJ9KVkYJ0gaOhZ4+chYffYTI+z3+sSqpMIZ4px3sHGSKT6EwCk7oajZwiL1SZ"
                        "+ACQDAlDbAjAhpmAWncQVaRKeQo2EfTksaG7aSLZLPOXf8p2mHDdJ1UdF5TRSy71lRM1slel+8NH"
                        "BK6EyzBDHwCzGrezFz9LoY5gCmIjdqC8b+ODHFhKnVbma1Qm1Zovdc5cAcLVi+WzUlNiYtEKCaIJ"
                        "a6PwycT1sbTCgaY4BkkrmaHnzKp/KYJdG3soBiCbBCO5RZRO0qf6EaMVdWmMlimExMPZMEM3keWh"
                        "Eb0matRzauEuCkfNTVGWjLSMAGBINkCIweeGF0RwgwpIvJNlKPLYjdmALRkZxNT9WvSm2mWB/2NK"
                        "AMDWQ0TFniabX3GXxVdC0vKlTbEAxXATBNpg9KnTVqpRORiJ5CuD5NrjVrQDwNpo9xvZYB/gAzJy"
                        "QQBgGU/7BwnM1g1dhaNy74yvzNn60Qa2fSRys01WbK6iGSZDqoMQRnzuZo0NgIhsWPTJXPcgRSs/"
                        "d4bUG2O3RrW5p3wcD1E1YS8pUTQJQuQji9cmhYiNRAtllPfjIyjwoCfFWcZcIlqZ21KDrxkP63lG"
                        "Blm/H09lx9Tatdorsc/VcFMTKQbg8inReRqIEeA2gUGsZ4XcYy6spwNXnyrCOJSzHO5U7+KXmJA2"
                        "u7Bsle5MTrGFWKBPX2oSLNQhIA2CzAy3ShZ8wqf1wAWFAb7PhUxgCwbB6El3CnHaul5zSwluAS6L"
                        "LzRm1hWRVP8ESxhDCmUJ2FDbQb0hY+LeHwKRMURuPwTBzVJjIOcHHEOYZzukMeWfFK/Ghk24xrq5"
                        "GtthkoIHqAgoEEzM0cL6eKVGNyrK561EU/ZQOHOe/UvJtiAry37Co3Rs6FAWopW/znGYkRIPcMkT"
                        "jFgzjUWC1pC0mCw6M8RnfRZwjzNFR+SAEDLPhJZogzYUYIlXKZG18rjaYZt7ShLuA2Yj1W4lo+sw"
                        "J1yQLLQx+7ke1tDG80DiYzGvMof5wYx1P4yyhDCJxcTs/MiqUYEvYvApexzzUJy+GLXHzPY4gEBm"
                        "L4PGXqJS188uS6VOHqBBaJN1F9ZZqJmCht/6WQpsXAsWMOB6dNOKyzteDMPbt9J+JavlNFP4zqIH"
                        "9oE/rHuqYZSWXehXQ7zOz8xMIU+AiS3JAAShO6q41XUeX4smOWUvo6zVk1HMc6PaUujFTxkMOkyM"
                        "O8gba1XpV6/7HO6HHxrjRlksWxnLlKqWbsp+67a0rWq2tcZyVeQl9xTdy4RKc7pmGbkUXWfQpNvX"
                        "FfRkHIWdGboJt10p0UC4z8E9VHqooo3oBZnxh7Y4phZYRliqSsXULhPhNAGyw8mGdJ4/zczcxiDi"
                        "nNvETWIjw8vYts4SmcZ1N3vWSMKwsKqdx+idAcEnhQEJtNHTxjo4qG0ISiFy/7ihPxGsdY2TR5t5"
                        "rgscOiAuQ9lE8ETvFAY1snEU4rQxdo6EnkKxQeYC5pDEE6II2KVm1Qc4DHOMi4CUJ8HEgeOGlJzJ"
                        "8C/CSyei7EpQJgoTq/kujqAj19exNQaYXA4Pq0qyky7UbEQ5cWQKv2QW2M81UP5ZhqSq0qp3s2qh"
                        "QugRQMeszE6ENXkDUSs2DxBMUVUUmlPzasWzHJumOtvujgASvxROAQF6E4K2Ak67L8XFknfZZ9xA"
                        "ywvoam6MIR4Se1sJlTQa9K+IxQnRNkymxj2qIgBAgNs9yahYciyZt1SMmPXqj4zl08mCwKAOECHW"
                        "Og7yyf4EqsTOoxgdGAxLaJynsXV7bimM7EzogAgslCwSa3J4PJYDIa/ThBoc5SRd2XWqjOEVG/GH"
                        "GFCmoojhiGQYu9nH9LrToGhob2FOtomNENyUyTRqIzYqEfottcWquXAeGAwvXriQFzK2AAfPNbMN"
                        "2w6gI7xSC+f81OKC7JjVIkRRIyd1uBHokxi2Bj6prZJ6uzhP9mVzHsMyWLaAqSKDUGttdaFZE4x/"
                        "ggDjXgtBeHHJSif57SkcdEKI+37FiSX4WhXXtN0imHx8YIy9Cp9hDTMuEbrcQTYYrwmT7iFOAnDg"
                        "WsmZPF4qIgdTngmEuOsAiA2RJEYfoGHrpjYkWpsw+k6c0K1NsXvvjPwBCS6ZyHye6nhIxoAyI414"
                        "laIpJKhRbZbWn9prUpgdNCisPImD7ACSd3wfmERkDgz7J7XaQ5ANaaaGKYQ9Hcv8dBfYjm8Wi8+q"
                        "XZ2SSIOZhKQGVmk29oDnIRl7ewSaINgYbf2uN2YIbnSSlV4N7y0BRssoidm9uEPwu8/GMmh2pdqJ"
                        "mX50tSzEEJG1CGuiUeG1POoZzYhnDHi5oXI3oipceKoGvqy5xH1c6+QiiBr0STcmsmoKqjcY7v0k"
                        "TZP9ng8CtJs0uhWtuuiNIewIw2Uf6d6StNS6PuYAJsQYA07xIrEawWbySUnVR3EykqHenWGXNtzL"
                        "XxTez/ABTkJaLUxEvBKaQ4iMPjh6RBuhiJ8pjHOW2bgVQUYSXBQqCIoILaocrmSOCg2WitCFupJX"
                        "jKpgQx1KOytMaQkPfhSnsFZELkI8s9pk3CHG55o2aajVJuWhDDOxCZgmxp0Q90CqaXnQ03fRKQAf"
                        "paOgQdVWTMVJtUy/Op0EuxctJNWM76JgGILtanmegg8XN5QL1RJSYfZBH1xEOmGVyCDsPNAaYM8h"
                        "6RTlw58youjwNQYyztUPSuCPjyCxwr7vtyupqwqEN5g4JmAFjSGWGXVS6bvq78x95Kgf24ZXEny+"
                        "9hUE2YQkRqnuIrEiOYc2KA95EJ9wGdcbIkX+XBhnk6xQSMNJoFSWEQYaYVee4BLdzSC/pSuN6Bw0"
                        "7pXpRSAbWkHMB4ElIviBpe8slxQ1z5bZiNIoEUd6Rl5PDDuStYVaF7TcDDP7W36wLkdB6XSVLQJY"
                        "ibzMIgNQ5JvEE1xQZDKgwStWwivUvATXcAmFvy2z3+qpzaYsSsPZdZ35nIwxuIc6FDhnFtRgw8xh"
                        "HHETEbEFKB/6hSmOPA1TCY2DeAJb9CjM4RQd1kWfkaCMGphD0nIqJeNXZsm/zg5DIGvZvY0sAcoY"
                        "is2NIKlMQMuWYPQ8Pcs/ovy0L8aKrFtI6wCImjTfsAuApNBGxhWznHKgVlYBiRLhKcpvxKzObaLc"
                        "XHiqUkmFqYgakEvW936cIf0H5P+vsrr0K6dNq6lHhhwholJ9Jmnkk3JSAZCpnIOAUFJZoHKIn3NR"
                        "ed5xWZ1vigoUxXrTD3lCYTqKLKmGc9UWaw6o9ELcbSsRBzFMQwTJHnRxy3OjHnQs6R6pYRaPBx2a"
                        "0HxRiuk0/4WRVK6EVXx4qBL2/oSO0Nx7RlzcZpneGgmcFU0ia5pDd1TYG/PzBMCGobSkZopaZRbW"
                        "WP0vDIF0Q6UCNQ9Zd4SckQOcDADqBzUCKAkCsDZbE1Pzj7Gjk0fKrnRqCOz5cWW+nyENRNp9EM9+"
                        "FGGKLgiQD+pfSjNJvBIeEQX5H8yq07096agAGTGFXWPuT8AfV4KAYvyujVAnH/2GzOFxqf9TAEYd"
                        "HmaxNdmyIqxqnpPAFPtec8EQCJmHzjEXCj3hjYDyvs67JusFqRa2nsEAZSuxGoWS3xMEB6/qqEmg"
                        "IBvNQ6qV71WQKvrKhtwebsV+EXAcdMsqeSQQTGur2kK5N9gHhRC0pRfCMWexTvYDyjbGwodHN+Si"
                        "L4mVZkpyZ+cm+KwWOyriRG7jg/GNV4WjM2MuOMkjuKJf+TPljap2G2+7bKdDgadG4ISTCBKQ/2qd"
                        "BqFso/KqSsUgdKOkr4Q45eaPMkps2crxaZ6yjBZl7oaNx8h+ko9D6iF5sUC1WPY6AQR/Xon0ClLo"
                        "nrKVLvqwPicmnUYNHBYqilpmgMNxtgZwmzG1c0YumK172ypFbQGFUQxrkurD6E32BbsFjQR2Mfzx"
                        "ySl2q8xCUuocnCECv4AgG05CSgu4NLz7GrWqgGd2JcEL1V4YuUvSkLpilWjiIUEWvwcgT/uUDCDi"
                        "9LNo2y3s+OASlUxgyMJAxMi1VReiBMdLff+XH7Ua+HgnvRb8iwaAiAwPJCuQqYkTUGov8Amw7A3i"
                        "fPWwCC5hmcszp0y4AJ5BSwASmEZqIVv10XhHc2jbHzkQ2OZ0jAo3jRpFkL5r5ULNUCqGJd1cMqSS"
                        "D4VTg0tUIDCy3k4pJMVpdImmesVNP0iZw2SQWNFMgqZAbi5m67RdpvW1QsIrJs70DCG+bkIhAOWa"
                        "RDIerIpeSWXMCWPZ3bJIPiutsNZeos9IVr3Nx3qENhL7EglTgmXcrIqQ4RdNP4xV462CgUzfvnK5"
                        "eggBViRdxgCH3YhC36G52hgnaSEwnE4FOIZD+JRz1jQp/zCIAMODHzcSJfuJAqly6sZBYE/fmHCq"
                        "XfoqoraWLHkI5bIjhD1m65e2i6GlaEbQm2Yvsw13K1vuBPywIzIJqjXESQyr9ETJ+8YNWZ5fIrVH"
                        "AyqOBPlDVBHPzzNVhR8NYv3TB2FYcZ7QyRiWOmyTvqyTQkByI77KjDhqTf7VDWdQsWihpmmiuN9A"
                        "1QyWUsQylUU4k0gLXi3FtIW/UtVMCaAq6GMke28uI5XJvbek7Eeyjk+JRYjJYiJRGKq6C1Kr7NNI"
                        "QqZB9LkLIeC4W6mq9apZQjJXBVHYL+oUlTQuxq+JVzVjA/occxD1eBQqM4bCVHIi1QQD5J0rPVLl"
                        "JG0xZFcRUgV0qdmqBzKDHmsDSCYEdTEq0FoiAIKzgo4At3gBkFVTHWIi0eBcaouKiO+sgJkMsbXa"
                        "BFntMQnakI1oBPVVDeZknk9ng2z+T+CAVi4HMJ+owI0EicEG1hDBnfcgYYX8K2AhBJAVUYLdc2bE"
                        "1sY3FiV/AhJSHRDIs1DVPjIY73sCJiDmPDBlGoA3jxqd8fhVVi7NdzORKksAwiuW0bFDT4XeCWsg"
                        "vmnZtgMHsuD2EoePHsXRethRUHAVABSh0TAc3lThn+LRiCzhVQCdki5cIctgcp+tcteBEAERt90G"
                        "kZ34Vr+b7PajFNEww+OqR0SODLJpSOuW1/eD58VFBd/y1tWuAfhJ7fBM3IarM0d4vNV0Sw7Gecpz"
                        "tWZIIKGMR+SW80pXV1aHUwaI/duDSZ5JHABMtWNhEgko/r/PN0kkgk5cin6sk7lWNQpozikMK5j9"
                        "3rI44eZRQDYsYg/ClBzat8tGSbVLtWU+zUxmgsKzuhhMNlhm1qIxxtpktiiTXeeYsfxchifCSDJM"
                        "Sw23+ghe7lBXPNQHp0JCe7sctFK07ToRovKYcdOdBGV6OEjkzTQWHdsksTLvxFpwCXE5V0WVq6yP"
                        "OMxRilNrzKVrZpxnfap9v1SCJlXJPSJxyrGXTi4H/vPPmRUUx1Bl8kNkUKhIwk1GkJTp5zplZvf6"
                        "OAohq1ZVXiGKXuGbGLfe5NEURsWLxXukmuHKlQglK8qTVkjN+JZESoiOaKCpsSJhWx7cbEPCnwSj"
                        "sudd/M0ol0rIWilrVgTcOA4dC3zulhuTVjnRko6Iz+Gog/BIAnMinZAuRZy8FWdm6WvY+2R94Upb"
                        "WuY4Y8+Wko6sjImk9Vv70CRDaUGQdAORqnccpMWSg4PUKr5LmNJwb5xuIO5+BO1bMW/EtRtIhAq4"
                        "xioyJLBczvxWPSchlfWDgVV2GwKDHbgG/D4dnxbYcLpcwn48mBeVnwF3qhncD9Z7UDW0ISJO3MdF"
                        "oOiPGmeEw0/8bGOhz0hZXYGK7A4IKfjAJuzXiJAqQzpjxUkaFOXGMiKg5EwX+Ky6vj8Mz0FBbE5X"
                        "EliZx6ZqjC4jdUlfMeYNKeTOdDkvvtzL8LPsskvDpup1iychjkTyYr1svEaCEXrAkox9SnEy6OQN"
                        "DC4zGlJqVwbguPbjWf8NXWa/s5dpSJsoDKmiW6hupTi24DDgJWAI3i0aGVLA4YuDvWXfldAsfJpY"
                        "+Yw8VDMt47fRcjioidqsxgEt3vGgcbL+f21hUJpyAUuT9xteCLKc7p4Iolm1IUAHAo/n48iG0x9F"
                        "94SmJW7WA3oK1JNwjFoyISI3ftVBMAs9jjEXGtxiDoF9JMwkYk7/1FK4tuW0BSBEWKRMjpXSqgRe"
                        "iXIELysNVOBSivKqaw6VEYEYB5Lw4RWlt49n2suUUzZRshSa4jD/kjhtjLzpIEuPFpVo0TBrKEYn"
                        "MxLQWkYrbRVF8HWNk/sYZMKAyybMfkqUnc+45Mwk79RxyVhsN8uyWXYMT1iBHRpZC+chSiVoq9qc"
                        "Ft89mw3hN9hqFjpEOXIlRx9jhHSt/RpFCq+S3hW2Ss7AJVEqm4lxME69SLUySMW/UlK5MWkrSaBK"
                        "TcyEeRJyGlLWuickltGpk1C/NHcvQlpNx8/Sw6s95MNein7LOu5fa4fiZl6t2vRYCf1Em1d4q0Qo"
                        "FH1ljHNJb0UIzpMo0n4szXKzT5T6L/ncwG2RAiXghh5UUsjeEh8Ww6Z4kbGaWavdRDKYENskF9/Z"
                        "GHIHzGdSBB1V1lIy6SSCb0hpGZNjpaiQIqwRP9HPW+9xLtA77jkZqTEz/CgP8np3+PBkwnkI83Bf"
                        "lCQi6yGuDBJd4JCUmNkB+cl3l2pk6iFs1AysDoivl5LsUtlXakksWeWkjhuoRlAd0ktYRtR4DWDC"
                        "AHIrDw3l/UEIm9SIQFQfjCueB3+2crii53ck6nEK94gI/uCX/Lz88JsysCPMa7VgY2yqGijFlxA9"
                        "MhAiWlcbyJaBWGSs1WHmuLCT9bL/mGgIB0TwJ4VYAtgYALn2MqEUsIq5Te8eSv0Z4YwURjxvIyAd"
                        "OaKeBtkCmlJgBPN3XeGaco2CWSIdYpdFPKVYDutgFL4gy4BfTHesIJvX1oITNRL9xCsz8KHVokGW"
                        "p8BeMJgkK/s66VtQiCnafYqViTiZw8picM10fHQPAZpgBS+Ix1IqpudQ7APKKFUTSmb43vAqVLXE"
                        "JyN7oQNHCgF6FBXdI+OhmisOUBJ/K226TC+URogxPQsSDiGb4MbzMOSGl2H0oQdWWVrTQoVWdHPV"
                        "/k1CRlgyj+rS1llyXsqrHDiH92O5ekP+OEiUHHs8uyBxIdvLoqqQHysQyfzpQYjL19VSXUnWzC0w"
                        "VkuM0CLpx+DQzD5iUTwFiEfiqW7LnXoUAqCcBBdEDeiN08/6KRtmNT+zSQNjkKpa9gVZrparaa1t"
                        "kYpaep0iHRsIgSUhB5DshQXgTwvzMidRJk0Fyo5JUUTsPtVElDNQC0HbzadaXQFQq0JEcUpis+mL"
                        "Kpjj/H32r6qWx98xP1SSoewpjtOfldseoBEBxrpD7ih7PPAQgovk2LSCt+1sHFHGiyxRb9aVVhoU"
                        "3Mso10Jk5H9zKzp1ZxZbpYYAcste0JbmLrtn3I/wMka0Z2dHqsUR9jgxgExwDpvBattxpDlAdUGq"
                        "GW3J4akQZTKaGXgpnM6vegSjYlGCNrrMmNW1XAOjSi7iSbRGhDZZXR9JHAgTZ0TUgsJXNQKzVlFL"
                        "2PTFaCoAwzSJv8hT7hAWr3EXyPwF16FhRU8NWNxZKNTADyHr9l3YaOhL1Xj5mlsY4cW0Jj0ShjwR"
                        "m8izgvncIc4+7FqCW/hj9ZGMuDUsNuFbkc80hKVIzoOF7isblrFiFGPVJ157bLzR+u+8E8JZVf5/"
                        "7p7HCG6rbTRNrchsxaD8nYUwCb4hWFM0Bs+2f7UEsm4iA5jUqpSFVFJINYrpK75zPMoOqSM0Zm1u"
                        "KoIyMVLIL77JG3ZWuZizMVKHYYSlE09PXCP/DDhAxA1CNKwi30BcsRFC3wir+Ruv1ToKH6XsePV7"
                        "AOnfakVy5EgaeR2RsLLsb8XcoMQRA5ZkKQqRg70ThyWXaOVKEdKFn1YOe6H0/saUqrCVX61Xqo/H"
                        "v+QYQasiEIkaifV9V42ykAIcYmaHY3UUKK2fkk6KCZ+Towj8oxVuGVAIiBxCd0vSilOGhebBAxky"
                        "3nutfJdRQ86QhyTLSQ9FeYnciNjI9dDRoWnLbHQWJ/bzsuyjR0QBjqQpdBVDUpaWJVFrjSpDzHrH"
                        "pTGtFo6koskFn48Pxp7KknO9BCPiMJepfAvKkKOAIfhTEFa+leDd2q3Uqdwjr4W6kyaTnZbw4ZHT"
                        "nJfgbqWZQIjzf5MorN7b144Y+gVa0BJEZ/BKmg4wTQNPf9MyuzVKrSvdHYp4wky4Uu56yWTPaWYi"
                        "B0lHE4mUtsSfyimhh9zSjOotCRGJy8Lnba1IcchKLxa9W87kQXquGo/SAA8Z8uiL2siQ6y4hVlyR"
                        "NBIxMXtLTk4Thjdfd5IZhcwW74Z3PiuwP2UgeetISeltTuLpGA6X336FIQS+gGgS4cpm9O9yeCKa"
                        "VOkBIQqH1gtqyqz8Un3JeZWH8rqMQYRUBkV8PM5ebEJUmsOkgvEoaQIcviYVdkUxGT9kVF6dhIli"
                        "TMRZX5QdpBkrMaa2YRW+SWbcmOMOwbFSBk2tSeWWeejU/4bWPT9lWFQ24D0lrNtQ1mLtin+K0+qp"
                        "ouKNNt5gBgbA7SHk0CUVdQSL9K4QDlNIWvMi+eb8JLFkN1cp/PCHjGe6DV2Yp9lqVgfYvxnnE2Ct"
                        "iuK/lv1Yd2HIYz4iSWaTx8m/pkoFJT+gCKTcsNfvbdHnqSNNYtbGjCdpPJM9hAJhDoB3PheLiqCM"
                        "EKsAhvGHzUOjemYXZtwXess5r5zPqt5CmmWvAVDmmVo9jhk1c5LeL/QTWSL/uJsN8mepBokj2iRZ"
                        "bxIRTDAwVrCX2U9e6/NAouJiNTA57KrXuypYXufCxPlVKq1AVy1juBJdT5mBBYihR6nSsI0TWQH6"
                        "w3exFVHCU1bgqMImYsyyiBmTjhhSHldU58Afes6S8t1XkEOKdxqTmc0AVCn0bFqCSQW+yTAsk9rW"
                        "wADYghpRew48NNQMUwYRi4SDMIiCpCEJcQjhouIs28hoQ+VP3WyyCY0VX6EvvRYZkJ3uUqGGDfNE"
                        "rRQvdoOAdHwxxm+b8OZIFMY1FSgkPzy3YRFXIo5oPk3+lUBbhi1FnENfa2OidA7FhQ8b0JlWgIxk"
                        "vLiVl36FSrrgIH+W9WsdlEautIM3iJlf8SdRc23m2lfQcyOUKNQRyz5iDNEJI/hHyQNDuBMlFLlE"
                        "vJR1YMvqFEAsGRwoE43TLBKt3JbOhEk/QwCHXUg6lJiHoD0KFZL0RUH8JDhSgKshfcYMpDSWFBXC"
                        "yu1NCYQsFeJvKbRSzXPBoAluH5bAaQcbQsdonpK2RQZPNswC6Ga8roMOKMqWcK96iFWK1tWS7UUc"
                        "t2VF1fiQB4DB6csySZCt6C63q/LPmD0Z4ZtLqX8iZmwNoYNQYVYTIIK1rPPtWC9m2buajVkEtKUT"
                        "Ru25nwHSO1CYRxnBanESdGTzUWEDestCHI8DidWKRAL8NQ+ViDZWglLJJMSV7PmRPVVICLhT0gmy"
                        "UQY+CoqWXBhny/o5iSAjMctVY315DJwqE/UWVYgjRgIVeF0blnxnyWmo/uNtrJY4dHcEXO5UbXxY"
                        "ZQLYZ+IgIKLVAWFUFNSSyCGKkjCHWhFfGDG//IiVMSKufus2uMI5HmTIINm4wkdk3f9ZDxBezSGH"
                        "O96cmWQIqsCZmu/SNAUKcdACwsk2FZnVmL8EWbL1QXeVuFZcSPbFhgFE9MOcZ2ZGXDkMscV/GYXU"
                        "erINsFB/G3GfUjd6HVZ9keXXeEklBiaYZAzkoSLrXthsOiqLJN2nz9hwjl0yzMxjO5+qhVMjpJCv"
                        "5HQ75jiNGGJ5dJKUBwmOob4xzGD3YiAovNwaKBBkLzLSrS1Qjq2TUOoLYn7MRT5jJgkWyuqC0HE4"
                        "Ik2Rd1Miggk25qrrpRj3mHsgMuPJekOTrCcp37ivEErfsZuLT7tCj/hSzx0HUMyBDmlfO0jR7bun"
                        "2nSJS4+n8jyc/Rkjitoam6MYb0pxrBy6J6tP2gIKnJJwzKzVqsdBFKBE1vFWjiEvkpi74DrGhNwo"
                        "QdDplyi+70rM3oT1MJQKUxYo7TqV/dFfJNJHBIpwvcaZFlxfZwbiYVjVKFOdpwMZH7bc7mrppkzt"
                        "GxKm7qPwb0RzZIxVNpDhrEhETRptGCyIVPJOnTxf8pXoQdXK6GeznEwy4SU2mqwYaHGl4Qw3KYdU"
                        "DMUqFIByxok4fGQ+KD/FR/5H6KDKaf1J1IheprCPe/cQRLKtyOF96TsbjkJVYNw3HeNd/JfUD/dU"
                        "nvDcd16VNyE0BOU4Vmsb+5U2tT9kistqb7BjdxuZa1H8HWXmuHUJiCMsooSBhE741xgTpmM4BCnh"
                        "1vOsBlAOfJDEiEyEgHVjKwhBUNAlUXI3ZEKSHJgphBnuhSTX6ym69lUAMMtrNbS/qsOgUyvEPerQ"
                        "SsFDDmAEObpQYa3N3grOWqz2clZBPxjmlXQUVtnL6S1JjZ5BPuD2Bb+xzDuhJqX9QXV9jBYFIEqw"
                        "TJk8FYZTThuBZDYAJ2WeyXVNmDkeBZG9dBXSZHxK/5tWi9edaeX5KXhcpgHNF1s5VQJqKBf7jUXN"
                        "lU4hrTBNnzkKonNecAHSzyZuPtL3ZXB3F9PTGrRF1bDIGHGhCje/G53QnfThIZY4UtBIVAHFV7rr"
                        "GhEu5E03ibTBG7WQpFcoQn0b+iYCNK0LSQIpzkLGkryKpGFC6DWLEAgAFaP9q45+dUaYDDKxttoo"
                        "dciLHI4fCS2HqAF53aP0Ox2zImBU7SaiFqFKazJ6eOH8/iMaYOXlYUEiwJIoWQxxcG5zgFClivGH"
                        "tyjTdxx6DdSDrNKJsiXyDMj18IUInxpEUy5wqddPY0wMDgl9RWlP4ybjN3gp0ASwWhr2LqCZDObK"
                        "IHdg7lgYCpwmydX9EadQk7o+h4eZdQbJ24VKqEKNic8GWQQJZhbs+lu6mJWLadKaq3iR5Pm0eitR"
                        "MP9un3BFfg3c1G2LFfdhOoaVDwjMCoiEQ++G/jMq0nudSWfrHqIwe0K+6PzAQeYQl6LRCOOi2Swm"
                        "uvrWx6BoZJ5pJmtU7CMiDrP85A+3ErdH6P7YP3Eg5uNONuWUpUrFFtxnd8jxEJ4NMVqQJmkGJG5k"
                        "YpIc0evem9VxJ+9RdlMV7q4RP5EukIp6jttfl/Gy+KG/q/8vjRQjQ0JpNMqQIk0gfNDBS1unI60I"
                        "FiBCGL8QIXwhlsOR04orP73LCakaDqX0T7hZcMCE05yhM02Ab1ZRqiwgwr9JEeYTwsb9Gn4k+Hp+"
                        "B5+fLmaQSXJ5oGAN+f2u7kJknhsicfrSSGTLju8SAutv8Yl+XGomP69ivdw5G4mJxnGtVPMywIaQ"
                        "0sZnOO0a8i2ytZp6PbTXSpaNFZcJqSrZ0KMJANbiye/wuIfDKp94G5Ln0gFr0lpEH1yxe1kqSFvU"
                        "iUi9mxZ6jjl+LIwDEpKd5wo8l4EgeSSOWr0OIa0nNaMOsx4hQINzL2DRXNILJSAXplXTYV9FAtN0"
                        "/siNskq/DNa6c1k/pdCxZixTSFm4UKD84HCIlVOKVlRokTw69nRYhM3MOLX2YFHVQWcqeyaFllfT"
                        "D42WzwKwbmrKZkZeDFk8/XAuArs4F4/JHO2LlG19V2J61Iy/pSY3D0B2pCYS11Xz5algMjOyAbSr"
                        "voFuTJSrJKzncx2ShT14MBacPdTZwAmk1yPOHzXf8sGi0dG6DqqkD7rREGXqFoDme8JX0JJuakup"
                        "xKqRJ3gjnyNakqWoWE3Xr2UCLWnuNilxDtXds1a9f/daS6SWDRTGUk7dr9JHOeyIdi24zC/thVaR"
                        "9SPpfiTiTF3jNrmP7+g7WfZV/0pDEZqVPhS7AESpCHq8CZmGY0RrlCsA2DDrUScKs4FEpcCJ9x2q"
                        "nMUS06dgFMXMPkWCT8iCXtJW0m8M8/CjLHmyCm3kz0hR8HnKkHhR1arS0MapuYurbIB47rFsFJ1Y"
                        "gDwlYoqjxmglnyvm5Ckiw7DhpM8YmnWoZWZiA3UunVcaMYMJxp88FdUjemAtWr2Q2ywpfShOlr/d"
                        "XaMjbwu6SV9GuVdDfSSuwKJUAooKfdE8AeHENJKPio+JVbVaSpzPVcu9dr9S8EkAgdYgBjcAEQ0M"
                        "orj93bOTBQ7hUcEEApJMzH7U7H+PGGfV7Os+rAw1CsyWAEvGKDgriEyDfXKQfYQBE+ZkOPQZGTeK"
                        "YiurCkoP0vWyKOlqOEENsxuy2qpzB97yqFctupeF5yAqADJs3ReJ2xIHEed+PjZSyC5uxmKSN7Tp"
                        "Z5RlQ7aEURc0rDqjp8RuCYYvKFeby2TJDTwdwBM1IbKE1EfxbqDg1+ACcQlFHiwUITsyXMIcoQk9"
                        "KZAOHPbDFFqrcavK5oc8ZTHPWDt/MJNIwqnOz0g7S+ebUVNhwIS9KvtB+5EYGjiGHBVlDTFjul4t"
                        "mwkZMowB3PrYnJLKvEtrgMKyr07w+sFqat8IsojCm1/OTvTggAWcuCs+uEoFpfxo/HKaU9Z0DLje"
                        "xTkdUBFZtm5Xk+Zfp3mERKbCUEQJFetVvClOkricPSFpT5+eQAE+OblMjPShpzS6KLWccBZMcd8I"
                        "qvneZGTKOVX9eFcESMXOY26ml0wQ3YqDssG7EuERoTUh3/lCAYtE5jKsQ6oh3a6iTFlDqoJrNXk8"
                        "1Vu9d4pqeVzb7D8Zn0rVo13snC0Ea+nlSiuZNkbZGLtRSeAbDImZLMDMDTWT1XrA+tk3v35vPl1Y"
                        "y/CL4wdVDhEZeQMmSQOl4VWo6W5VhkcAh3OGWIu9Mal46Fdc8UWfFqt5CXSTABdF8gdRgEbM1T2R"
                        "OpeL3tUXe19bORCAbgnGfbfGxTHygxvSnan27LlhhdvA68Nh+nXBBDSNRag8F1EAmsUxBulpKo64"
                        "X3FwehT4EFF0eA1Yty6GkiYlaYmdKFneCTXkEcHoEPOLoJcAhctkFkYSo4ZXxQnIpK5Yn7jUEVJO"
                        "iIjL8ilHpPQlZCQQKSihHPvUS4Ab4iQ5sKWA9QzLBGKTtnvNJX58Vl9R0WW/qMfS52gt2Wa9ePX2"
                        "Mxf/6p+54ZZbb/rmH/oq6DDIst2Hw5jD/DmUmWGwymEl3ItKy4aJifm5uW8id0QR++/sGr+PT43L"
                        "QAOhCdT9OiDHVVoGJ+dSkN8q6FjKcZPWlLvkhpHWbXNI34RLtSEpJ/pgWi3HmOGK0XT2KQqg6JGE"
                        "2/NhtMWSX+nkwqCzRBQ9vbQe5khBk9KCZdkpYSCvn+KWMOlYwg05uQUpNnFZIgPPgRqBDdhP62Tc"
                        "QpnXqGP7e46nhIgGX2XT2YUaonZPGnJToWqunbky9VotGWTjtFTkUJYapNDiVyAD9o8g11bGVC2N"
                        "8rjtSV0GGtN2C+bu6T/83Vd/7Z+d+f7vuLi49OR6LW/D5MG3aMv52CBHFWfeW2W7hiK9tuWTtLEC"
                        "G6LGnXntl48hapffYmHiO4HJZCY+3xyrInxFn1nc5LBHmlSFlFRCk9WsUWY2Gf2qQ6HWd1F1lFzM"
                        "KuSf+fKVXI+GjXQeQIieGcngdfP29xH0vu9TI6VqNKx8x++0hH+/IZWriHQBdzgcpWNl0sSYCP4u"
                        "5HUH8gcKgOTleaLK4wG4UZ2gG6gi0bg3rvAUpVMVYiIlrizLhvFLJrIayLhgkddP6/z/qVTbYvIb"
                        "3YxBb4fV6sVH7rn6F3/sht/znpaXTw1XsbN3m+XBhMXGalwMlL2rkz8jRfYZxYpARPdVOmUQ1Fec"
                        "Mjm8DBneViTBv6qyC7Kl7GJ+cBu01ZCNMwOuFbVTUm0NDPYTOWX/RmR4LIK4TZmj6uBZABrFAeOl"
                        "le9n+FN8PcqC+C/5a9KG9cJCwGHy8ciMaQD7seW2YYajHUbE0xddJGKw251MIOYGAMgC1m2QBDHc"
                        "llQrKjbB4b2dDTwQYGAkCPuNKWkGrpUwPgryybwNwR+ADBA4nCpAluA2j0ocScatRATYuF2R9bvc"
                        "ABpw2CsPkUUws+eHeVD+5jgzztY3BDLOXlUpnErCur612Vg3B6/NuWpfO86M3tMECGtjWhCtl1cP"
                        "z1748R8+8qd/6JbrD7/cXd0bwPPt6aWFZbBBM3DPekNPbE76XbQq+Sw7GRyI70iXAx+jTShLLXJF"
                        "Qy2HXyBYXc4jcV8yZgAc3gMFW5ALYay50iolIhnGWnanU3BhdeIP3Lg90AhShLhJlC7fSThjv3tL"
                        "Q7lK0bJvsJ/E6mp0OGzGaEtamUIdHkU80aEaTQGwigiZeKPLvfsOKwISiUymHhWwkI+wBBjAgK3M"
                        "hajoAGVb0oAI5TbE54aVyZKyTfKKCbPMYcWxN6lQPqa6VFL/Q2bl5LrEDhFBCRK5rSk8/tRy2fxQ"
                        "muTBzfEo04NubgPo023p3qwmuZJajQMgLFoRQM1s6DF0z3/jm3f/tz9509c/sjfsPNPtomnJDgPQ"
                        "Xr4MoM0OvWK1ShuMze/mDS/K6GQqyWzTnEZVjbrLSncr6aRZJNqOx2XxIO68aSEYzFLjp6RBPWTj"
                        "cAJHtsdF9FNyWP2diayul9oCEgPw1TM/8Qkj6LMyJCxpcYjfwThkw1HphAfCePsOHzQertyFvCKl"
                        "bcBp1gRQKMFCYLagJ9+P/iWVIKD0XTXGZo6k7/ra7H+z/5Q4Ba4qwmWmFm7E7+iNZK1IraxQjQLV"
                        "bJGhKp0G8+RfK3k+K7kcsXJdQUhtaGhzYVhCAwzExI1ZL3ZuOPbKn/2j23/0e289ZJ5fXbra0DY1"
                        "a4YlMKi96AJWXEOIIpciIqqF9EUo7bnnlPbiB77ENTI7qUmdh3goBdZQibzuk0felHJ4lpN3DDVv"
                        "489GJstUlMZcJhrtzdQ2MvepxLiDlDay4sObPK6H7nGnmRvwILyN5cZlQUTPgB9aRYQssEv6o7r4"
                        "CnfGCyKoTnwjwFh2EYZBsLIhX77wGioEAKyTW0gsJuidOcypynFp5OPg6CBc2Uqln9jBeD9IdNmQ"
                        "AIM4NwEknWT9Z7tAsgaiE7UiPhZH5JN5kUnFTgpJE/MyB7AVsUjSVq5jXKaf/QjuU7JIOsIT3CEl"
                        "DfqmodXKojv73e8zP/njtz5478X+8lc6S5OmAS8BEDcDr8Hm0k5CY4x+fCUWbmOED0Yq0nmFiKd4"
                        "iiEpkt85yAFuu3U9+Vx7XF2VNoWZMXQm+2SYWT5LrLTkTUvepKU44WiQL9JwwCyMCB653FEcH9gv"
                        "fSrt5d3n2NPG77nKsAijbD5+SDUgkhxhKfQkZpp+QSSbzAvBWrTMzIYs/BotqW5IsgX2N27Kqqnh"
                        "oWwcRyCe9HcWv1XDITgLLcCd2iNcheimaqdTD1BpswQy+pRhZ7JsWWINs37EX9s8LM5wtY44ittR"
                        "SJVVUNqItfTwMPMT3WtZws/+3NB6RaoDl1rw8hC4JQL61fLy3Tef/0t//Lrv//ZZY7/SX+xNY2Cs"
                        "vFbHbveANZevDECjiNRnQpySrY0HwiDphRz4qNCQQA/X10G3OVAaSxUbEY2MD1jbuELHEm1HjcTl"
                        "QceRNqeQMvfBOwVo2gCpKqPUzVIfBGqNDglJvbUg14RLZpYDH0URCkDFg8ZFFms32C5nyqp6QsqG"
                        "INsERZePp4krBntXkcKms/GGqjwkpY5vCX56KyQ4iRTZI4rJSkNp0OQxHjbzlkUrp4qqeVWJHKRU"
                        "Addvs5ReB4cjCIZMt95p6cUf+a72L/6RG2+58VJ/9dkBU9MQ2BIswkmLYCZicHtlZ3BSkzoyJKXs"
                        "Xbdqh7H1DK6wzFIP2VNO4WVfV3W1wdulSkYcaf+KLO7UmrIhsUABUyqKJZyM8Zypolp5o/NWygGi"
                        "VeCPWYb0ZRXv3kRgkA0Hzvn1KVA4QINkx6Pa59gWrBhKTkHRDaF4WWlT3HF/odbxosGQguqDC4pL"
                        "MEbgvOghPKgry+pbbChzzAzF+Pre/itfTEixsYeumttUOlbai22KVSM1qZKTTFeBW1chHiCTaTuE"
                        "eK8Hxbyk9Iodl3TkuaBkTTZvugAvuX06JNF1lx668/L/9qev/3+8p8PymfUVbhtD6F34YKdVvwJu"
                        "CDRY3lkYoCFySomjFWV1YoRyQom/E3bqJXxKFlHmwfIZFK38VEDdUL1E4iQcBKN1UIrh335Nx3HS"
                        "s+HD9Kw2o5NK8zqHQalCmmbdR+HxsKMgmS8W3JD4WmaEmYOU8lb1IAskBHIfT8wRlvIZWSyIyghT"
                        "XCKdIl02lsQIKuTXjY6mtbLoasWLCDFU6bauFTsEh9TEY6AMf+a9IlWVJ1PWbBmLg2ZyhWaJSwNY"
                        "IRYIMIeNCyph5m7v1CWYQv1rXcrZT+3QDJQqVYfh/jcsFYJE6Lv1w3fv/Ye/d+bWM6+uLr3aYNK0"
                        "DDaMUktwQLfvze7COmdjdh+hAAA5qglhrJdpXtJb2ZUluMgbTvEREaVrs5X6aYzTgSCNfTHicZlv"
                        "oPpLOZejkLhMlok1qxxfq5aIEwXXLOl0WEKEzSrCZsNT4cY1NDokVLqDZbg5Y8pUpmKZl2okvW9u"
                        "ImU6oVsTKQaIFEEkxMs4ElQPMZp9VSkdUKTWBJCXoTaGDHL+UtVDvOCqa21EIwgATV/MiI0hEc2z"
                        "vqUDVkAQOWbcXKpJcoMDj+WMA0TJnCQRWbt45AG+9dSre+cvz6YTAFT/9KwnQ4a6rlku1oBPulwj"
                        "HfiPFqgyc4W4PG6tfJIvClWknBg1AsGoMZ1otc9zoiUqbrE77n5M82lHRwo10JBzWxitnziTQIZx"
                        "+89+j5ni/kgiZZSZ2zF0Gmgxu89rgsh//TbUtAbEgFWwLWli33CguI8Ch6cEZzqtse4qyRIuqxOh"
                        "/CaaVncW9XUfhGSS5wcA/rOyxAHhiwPVdVU1vqiX/BENgigMK9J+JZK1RVLqEqfSRkbkPvdSzxBa"
                        "D4WJMLMlP6tjqo+geEDfTXgYmf4ImZLEE8Ys1R9aRWzdl195ILd4YQeLlsgtqdpbTlluhmbCjJ7Q"
                        "YNPkhmmMWXRmd0k+/tdCg6sbiOhFmIohZSVYjrZ86VDtX+53+LygCzax93OaRMT+IGBCqrcQOeDt"
                        "M50kSVlNQqTqjiRFqcQvi+mJdcHH3NBL8eOjpR5yNxzT1T7RShXhOdm/K40Fw+LQhW7ztq3ZBAGV"
                        "F1YPUsgXkD8vgVWLkKYzz0QI/1rFCEeIBZq+V6Sg7sa5ihVrYLIMSyQzbrGJUpvV36WwUof9Apxz"
                        "iahY4TaugWqeIh0OB4dlFoM86tVYdUSMMUItbSpWropT2HE9l1bVUDKT9hMDYDCYDDXWdJhM1qu+"
                        "W+4YatTR6svbb2wIvWEmbvwjKYeKE4LBqqPlCqgMiLweXC8ElhD+zYNvSjm7ZbIBVyJ12OXgLzj3"
                        "M2aMWniSnJ3W7vo3YaFCaiG7MBBtT64GMWMvhzVNbWlZnTq+KTkXCqUVicntZy2RU6nsZnytQyhi"
                        "fwFbCYsMssx27DSJ9C08RmHr431MOlaW3qHpUCxwti2pWx4scmb8LU4hXs3pYQ/qWS82Ys8knVdV"
                        "ggQUrQQaAcxQ5uLsKTisxqvCUoy5EmGNi/W5uiosjTEAJB5ISlyKQ+wNbpBfT3rcO1slmusUkvdX"
                        "HDf1DQ2Gtvu9Cw+97uUf+p6TA3VuM7C1IOpuvtHCdjBN9Sj3YMLGv7zSmG7drLvwXabCi1RfIDX+"
                        "XPBaDtCNsrLS0tuDpIW5qqb9n5TC9pEkYdx/mdWJVSNxhLL7IsPawKrCiikiIIZEopqkIkhNb9eG"
                        "sKQJ4yJ49sHCwLcRCC34AmAFtSKyKvWb9dzGaOqzEyV4NdMdYqJwWccEbEYIyS3pNnnUwW8tuep9"
                        "198G8p8olA2RUTvrHJL023PUyqa0JhfDf0RsiGSCV6k3FT7+TnvbUxHRwysZrssMw7DSsCJAIQhG"
                        "7QVAnQcXIk+fDUm/CdoVwhLuy87T8scrbouxE8BIZwW44P+LzKtEYglozHS1XE36r/2R71781395"
                        "5/vestsvrzamATBYPryFm84YDL1HIOyVk2ERBz4YAJnlmldr42c1guDuX2sdjhbICRE/E5c5on5n"
                        "CQAT2dr5MxSs2iUWUjnPtWtillLqiJ2SqrTUcOpf8l/s8fDDKoYzcSqdqJWjS3YlsF31a9LcVR+v"
                        "jlTGSwwLrfgiKuZIROFgE39wMhgWIR+T7A8YYauUuRazoRWd9ZB6MGzmDJvuY2r1O/RcTS9e1jIU"
                        "sAo01ZicQthwwQ6Ai7xMBIpb+RNk6mxOthe6ABGzGUMdiYVoHbUUrcF2fo8Ce6ysVr+ZKF8JUdoz"
                        "GUZAyIpcTK5baz3XyU5nVv9Weicr5fUysLHaPYsAP4vHuCFi8Gp57v67zv/1/+n63/Vuwuz84090"
                        "wBxkiYxlvv4ETp9s0Vu4LTUcvoRTbtZ23WzanQUv1zAmzqgH/fhDbmX0UHYHJzMSEfbqRqAWjjOF"
                        "hFzLYeNKkJuFiAlv8A2lMjn5tF2GClVWVvNuqQIonERqWJ1qL3aB9O9U5MqyaajJ4v76urWsDnqK"
                        "2+5TCmwtZ02XrVRL/GpObbwgGuCigvy2SF98r9jufsCv6sMSekKYq5ANKt/cgj/KWndVKSuc2csf"
                        "CY4lZWdxVlJ1GJEfQ8nf0ePl/LkasNKxtcxX4fwGhnyyuVCCn34H/BEjoigiEVn7Um5/MSeFd7nD"
                        "I+Fuurxd40LzM7pcRYlK48goAmrATMxqcWWrffGP//7J/+sP33Tm5CuLK5dnx+58+jkLTImZyHC/"
                        "vuE6On6Yh36AmSp1cxRVN2x5YNrZM30HmhKKmKbrKnXpf5EOnaKZZARiFknCFuuOYDnu2CdAX70W"
                        "L7yitPKToUMcDCJMiSYdx8xEhqgJbLMODXosIjhBiSAcVl0vPq5BhnCdhU6xYyV1GQRHi2Cd+mkN"
                        "ZdUymgaRDorrSniVuQ0ET0RPi7g9InnfMIeTjV1lGfNHBCHmFTpvEMUGOBVDHiDkIkoSZh1Gg89I"
                        "EuK1KuQL7Ukm8UeKhZFbBBfF7KzYUFQUGXfCf3hzMkinzqcgrVjvijYAQGkOknK0cnTjPlwi88mk"
                        "5gaTyoYwrgcdGX+sJuREjbR/vXpBDa27DutX3/H6nZ/8kyd+51thV0+vrph5a/aW/ORzA9AwQIYA"
                        "3HTGzOd9f8U6xKR7yaUHa2DYgpueQTQ0x05eWUx6XrXUgIf0EE5hhpQgkrNK11AvonqRE22PKAcS"
                        "s5QaKdyPW9hKCCxESuSlYqgERJPCiyiaPCXPBsphliEhpZmvCzZ+S/zLV3PVU+h60LihpADch1Sl"
                        "eUQ5c85Uw1n2SOZNtQwbRM2u6y4Usq6iVis8oPAnQLoUHe7bsA8sW9mNQilfZUTLYM0R+etiSS4I"
                        "Wj/mC9Eq9LfSg1vfZIHuAKlsJcyrk5IEdadG7HMR+VTchKetdy2JWb42gSRYR0il1Fhm0bL4aOW+"
                        "gpKqcdQqdBGTEM2ESB00HNRN8O/FMDNgBuphmGjaLc7fcPSlP/0Htn70B248PD3XXblCTdMQkWnO"
                        "nceLr3TUGMvUEAHDLTcQmp4B2Ygp+MC3zWYYiKibHT5ydefkz/7M+v/4x5eayfXg3p+3EnwpRbgx"
                        "w0lHlLoK404OkShGeSq2ROl8rxO8gjnIQkzMzemGmyzKKPuM0TPkHmLug4lWs7iILPJ6KG3Vd0g3"
                        "QxnNW34nJnXH89hhBwcpWjq0HEKuelmhwlmJhrI/pY78mYlRlVzHPlGQzsBFtYhs5VYGcVMN6ugQ"
                        "82eG9XxNf2iNG/MTUYXnEkbJQFKsyNNkhpWDeSKzoYqkAaTxCyAGW+uxXuWI9CT6pIaogbCYss5J"
                        "qitrMMr6s/0LqfOBXpq0kosyhExI6IgsA0/qQcau12Sf/c732f/1x258/b1Xeecr/d7EtMYvsk/a"
                        "sy/yuStt0xpj3XTi8vYbp8CS2ICH+G4+nATG9pbabnLk0N7ihn/zy/g7//zyb31+zub0dNKGgxMS"
                        "zuDMX2FnKHPVSqv5cPydGYxUDlCoyShDWX5GzV1XsSPSlMDkUmkmSEpHQmrIx5TabfBXa31vuh9l"
                        "rsoQtNZMzUc4AGqpYzNTqTySwp2syOMtkJ1otqn2b7OOrly1eBQaQdrxKJwngJQIwWpDszgM0d4b"
                        "Tmgjr+IYEJO+d6vpCtX7i+xHWKE99wXCUpkslOMlzZoWltz+T0ryYrC2vHJRsu0dUS3pRe8DQsSo"
                        "/Cv0S786WMl8TwueTKwSEZOB7e694fn/5UeP/cC3TyfDc+uLq6aZmMZJz+ABNPvqM8tl10y3wANj"
                        "AGBvv7lBvwZaYFCeaIbBMvfT7fmiu+k//Kr9Wz994YOfngA3TrYOm8Faf9hxaQZ182Dt64kOswFg"
                        "AmFCHcm+/spI2siL1rzGUxqdqbjmiGeaR9B8XmqhNs6pSZwKY+Eqg7o3Kyy5OwDYz4gmsW+D1NXr"
                        "JfNt/C7nf6OSBctisFNhUR4pb8mfKhfloEWSpAof1TiYk1UNkTqXAwLRA1QWMJKgOSIC2WBMPtFz"
                        "AgBJ8LZYRmhCNr4VrLqaMq+koJRWTC0dUXo9wvJU6nw5KXwVibiAY/tmvIKZuCIhGgt+22Tgjrnd"
                        "olf+4V+55RveeX798rM9zKQxNhyGSzDgAWi/erZ3M+5MFhaHZt2tN0wwDH7ND4bAgx1gaXJo1vHR"
                        "//xh/I2ffvW/fHQK3DCZnSBYHjo7MrYN0BtiADZddZVHMvQkmD1AM91ZVlQhlNIW62SrulUai69V"
                        "p9dzAoGyyoIjLyeoRoU9IJ3nUacP6YnaDGrZLDRT8hrQgcJLhmqVOCQnYdTfJSyQ6oGKjiwHJFK9"
                        "Kyh6vHL8qaptaorVfITgbXUrd36xqmr0TGm6jnJXIOM++KUA/5y7mJ2xw+z2+2QNGd1fY1LVopKO"
                        "6Y5/q6JtroeEWvinTO8bitTJnLlejZnVO9KGaL3ub7udH7h70Z0777Z8y7YEd+ohUwdun3nOejDF"
                        "GOz6zInF9cem6CyDCZOBOmIzOXwEdPiDH6e//VM7P/ch9Hz7bLo9GBq4b9mqb2TVi5hc6CY5ODSR"
                        "QltgdjeLCKpf6s2VuiKK22J01g9ADxKtiscJ8SvWEZTBxywZqid9NIYktDbkliTvQg8VudyBu97w"
                        "2AW5ap4YNbCCfuyaFh7+qR1EB94Tsbm9cnBXY2VfXqsTB3qgsY/wqppmiQKSrwNgzXDA/9U5SJLq"
                        "/uscSWaQE0QTmuKZ41y703igUncys5AykF9Xg0ctLwIWyEtV59VaeliKRPOcdUqsQ97RYNjQZL3c"
                        "JaJ2MmUCbPfA65Ynj86Hq8agYTCHU3QABnpjsLvXPnV2AUxdW9YOp0/gxOGh7wcwrOXp4a2hOf1b"
                        "n8bf+RdXf+79ZrE+NZ0enRHzAMMDiJgncLtYy11aUWNxsklnstRu99d8lXZVLSNs1K+rQR/puBaQ"
                        "jjPmxAD0I1BRJgN3m8dohSN7oxJ3EDpIVmko5M4o0Yb4uF9JjNZ/sBsEVsm/jFmb28jikR40HQT9"
                        "bkbFGawNTdhs33YyUqszGQd9obLluHIXBc8e5LjptAjEfpOXt48wpysM+1ppmnI/4mdvgDg+zfKz"
                        "eK/i0IQ1AWE1fuaksMsMjW9yLa26KrxN5E5vhk1AZSHiAWBjZqthQPf0e9+yfaU78qnPraftYWDv"
                        "oXu2abJgWPZngojsxIxmYl45R8+9wtROwMY0FjzceF0zn/X9rp0f2sL8zKe+OPs/f+riz/8KrvbX"
                        "NZMT8+l64MFy2LjGzDRQ29AA8d5M0uzA1Q2jXQBqv7ih9CBvDp8gUaQqZ42hMDPpfQfAS8cJvxlo"
                        "4MeGif7l33RWK8+7yTO11UwURa5rrkTMcGSE31Iilh+eTdjYbGDjJQrDRg0Jx0DQvuFQR7dM7A2h"
                        "KqNQEtzIVZnucoZHUkRSrbSJKp/B81kGTSKs3JfuFLCmSI2G4xJ7j0ikEVb0Oi2IJr45AYzV3GxD"
                        "RAlS0Ha84SmAiYwlWi2vnjx07k//KP7oD9z+3T/6VbbXgbkxVx6+7wj6qyAAQ/pmJLFtqDVnX8G5"
                        "i9O2aZmZqQF2bzi1ns5nbE588svH/+G/vvovf+nKleWZWXtqst3Zfm+wjZvqYTBT0zY09H23t0vt"
                        "1DRzw2v4WUXRbe5FB+yUMaNy/x/I2LA4U8ncGYIjVTI0lP2pWy4ikc/EWYulpJm1Z5LqppVt55Lq"
                        "LiuVdhA1HqAEwyNUDvB7jSRTRLYB5hyElP6zGlA4rshWwtnB/XBMjyM+n8xHCFn3CYkx85Wh3VjZ"
                        "FxhuiAuZ2vWP7FbZRJG9MVZzc3oIFfI/3cHobTNZrNc0vPRd713/+R89+cjrF0989ckvP7Fqm6bv"
                        "lycO4Z7bB6x2YJpisofBjHb+3IuTRT+dtcby0FrTof+6+2792suTv/wPdv71L164tHuibU9P54Pl"
                        "K9wTsbEGBmgMyDRdN6xWF47OL3zL+05/4kvrp5+nZmIO4jsHt97S83W40YhjROHZBp3kStkKkcn2"
                        "SWU1y2yd3S1tIHMi+czX/oLDYTmftkuCB6EzVirSMdh95msMDZaZYYx0+TvDL9da0l6vhP8M25fp"
                        "q3wqS1OA229AbJkK3J6CrzgayoCbTzP5QEN1m4pzG9ygDNNFGPKHgmb4rlRyVe37BsQxZiSlc7KR"
                        "bVPHMti972yb6WLvlbtuvPqXfvz67/82nnRfG3bxladOntvl2bTZWy9vPjOcub63nfvMkh/gKy4t"
                        "zPyrz3XAFghMNFiaTOf/6de7v/dPn3zqleOmvWk+t4Pt2BKjcUMUQ0zGrNaM4fzpYzvf+63zP/Sd"
                        "173unhPv+/3PP22PpELl2a4KedJgFOPqRvC1z+GrIZ1wwK2RnzGvIfLjweqsEJB7SjWXSyntIZM9"
                        "IzKW1dzni+LHbQo31IlzDKxVi6rj/MuCGTb9LqF8FlSzVSVUTSmlSKVl6ORQhqSS+AZ1b662mfOo"
                        "Vvd5H7UBj7L9WQSoZaMC8VEgGxlLwSBvkDqTKGN1TN7yTyhzLy9qhseaQNE7xa2KVgs7dlpoQFh3"
                        "K7N++g/8rulf+BO33nXTc93lqwvLW8dPfOqLduAtalpwf98d9tjWYBcDTPHRJxgYtv3Wk89aYOoI"
                        "DzywmX7gY2tD9062GgzDMPjvpxkADREm/dIOeOXOm3Z/4Pds/8DvOf7A7VcwnHvp3HLnygzUIGwc"
                        "HXNF6TgUBswRTWwq+5qlMqR8zrHap3BDiuoWP6mj3gKtV9gP7EhkEYvNPaWI5gEP5sak94WMNboh"
                        "g24uLQCEtxWIaYPY1di5bwNjfphRK39npYyGKAJcNStmj2i3hLLaMZ4zAsnjyWzCqHIyrHSt/VSN"
                        "vLq/y+CS/a6i1LJUCabE9+9uZjaNWS9fef2d5/7ij57+7m8yNDy2d3mYmdmEV2xnn3tiARxn6oHV"
                        "m18/b9plZ8kkb3YTgQdrLFbGbj1zdheYhTtsbGtmE6bBDtZ/K5dt07RAv1pZ4pcevnv3B7/z6H/3"
                        "rdffdNOKl2dXl1ftFH13aLHqgJ7QJAcWIO/QqkLKuxxmFcscNuarcldNIFBGMOsCFTsgy7AhUgSy"
                        "DqFR3O9fzTpViFTKqz2oarfavI1x2CeGORRlzFBfU7QiAK3fhe2Ocqx+4CUVbyxpyI/Nabz6oFTO"
                        "+j7nN+0JZg6fPiwz4SgDufo4vxseZ8guKrJhqEcZgArDPoZ/xawOgqps6AC6QVFKKAZo36h3ENPc"
                        "XB9AeXZStcQedG8h2qZpeN3tfuf77N//ybtOH3m+271C3M5MCx7aSXPu8uxLz+ySmfUWE7N66N4t"
                        "2EtEICZmAzJsejtMeOiaQzQ7fMeHPjJ97Ondpp0wD+Q304ItG2oI1qJrjBkGXi0vGJx/50P4ke89"
                        "8R3fdOjkiT3svdhfWhFx28waM+yth72VJdMyLJhKq9sQd+Ri+OnXZLWuxpJHsCKxHgDudLZgUQGT"
                        "hjqJ2olcRPA3/YvkonL1C4bInSpdYdhXRuFi+pa2w4O4cDjxhkrUmQGx6uPXXlygb9psTvjgbVRT"
                        "0wEhUtVJqnTKSKSqufzjoJIfvslNDW4TofXDtYipI1GgWZ+ulgvyKpYeGGaNysUsHY0ZFiqF9jWF"
                        "LKFt6A4dMUvRrsXM2D/A7lDpSTPs/Pe/e376xNPLc4vpdDZwB9swczNvn37avPDKpG1nQ9efPrK+"
                        "/aYt7lYgZmMZhtjazk7nA7av++JXj/3jf73z0//x4qXd000TNlj7gQ8DxGbKw2rVXZy157716/m/"
                        "/56T3/629vChy8PiUnfemGZqiIDB8oDGLFZmvXLnKB5IsM15dDyWkQClfTuC4ylXzhiqbh9TlLaZ"
                        "MrjoF4FDc9LiPgC/5FYYHku6me+M1cnM9bcXvzzzbXkY9kEJbPLh+vVM9Qdpq+pXaRO+oarnY8Rc"
                        "qhfDRFVCk2urNmUrjmqIodXwmseskqWxVqBUN2Z2JbzdQEpb/2stYSxCjWXqu65pCMRdP5w+ur7v"
                        "jm3eHcg0dugD5xaT+WNfWV9ZzLa2zN7a3nXr5JbTGNaWqGULa5ftZD49eubzT83/yc8t/9XPXXjx"
                        "8glqr2ubPh6gSCCQMZN1Z3n98vHtF3/375j/wd933bvfiLa50C/2uitT0zSmIaI1wP6sFcLe0vSD"
                        "MU3kfr8kVI79R/Of7uG0692VhDYHK0Gc69GtZDxU9L6543Q6FzZDZyV1dDSpRh/9W4ewMTpjvFV9"
                        "87VFLmZuw3klsez7LvQG5sbKvnFn7JEyeCsKHmmH+zK2d91js8BRgrWyRf3/4WgXZrZGTRykccG9"
                        "owtQA//uWP56bVbGmi5zWlZfjRpIiV8Vod7QuJXYcF8qjHbTQDAwhq01Q2O2V4urh+aXb7rlurMv"
                        "9hMyfW9fd3t3+81ra3vTGAYZtkw9g4H55x9fMq5ryQDdffeYw0f69aUJsG7aZnrk+ifPHvkHP7v4"
                        "6Z9/5aWLN5rpsdmWYbsCGjcKY2YQDz1161duPrn3fd82/8HvuP3RexcYznfLZcdkWqZmRX5sbhhw"
                        "JxHBTK7umdVgTNMyOvj9mWPy5bqqhiokqMFtlUhQkgYUCU4BCAb+tc04dZ09DvhXssPdCmNp9nJ4"
                        "TDMpL+tkH1KtuJLOgmMeV41oVYuq0tk3oW6863rAAlaOSH6N5YDB8lqjFWqKy5KbbFAmgjFxuSA7"
                        "alDj55LtMrhk6vZoK9yqYUbjDxVHBsUr1PYV9mAq8uyURA4CvDeYxUFGTAYGZKkxGJrV3osP33P+"
                        "r/65h//tLy/+4c+sZoe2sbr06P1m+9BqdRFNYwJNMg2tVvSZxy2wPcAC3UP3bg10CRNMj1z/8qtH"
                        "fupndv7uz1x69sVTbXP7dBvcWx4sJwdJkB2G2254+Q/+Xvzg7zrxujt3sPe1bmcFao2BO7aQ/IHS"
                        "ClAwo5lc3eEBTWuMtW6QlXua1puosQq7pD6iVQfF5K+LVfVH+v98o0UM4vjecr1bc6DtLC8Yc+B/"
                        "AxsV2auo8yDIXVys1M9mlJC54cbiK7QJTLnGsqEZ7YEbjGOMiNZghs7cRfU6BattL0zuADo3ri9A"
                        "daZ6DWo28KO/aVwEPpl6hDOSffumKmxJWW5pmiEgsgb5WUDfEK1GwqIPsqnBVR53FQw6Y7aWe+eP"
                        "zZ//sR85/qf/4J2Hjq7/3F9+BnSLHRpg522vn2HYAcjtt2a3f2pizr7UfPEZa1rb97NZc+Xh+443"
                        "h6+7cOnUz/7Lvb/7zy5+6dlDMLfN5hO2Pbq8O4iY0bb88t/9iVPf/k1XcfFr3fkdoi0yDcGSf1uF"
                        "FPPkHgYAai5ftcBED41KMwga9v8vSa7acTWj1SmZVB/ljsBh23M4zapO3FWvxk0UWwd012tISJQM"
                        "BkUB2pWU7BVUsS+GqpLSBDeUKhbRPMigR261ZIN5XvukRrWZLCgQURjF+CnJg6CtEqOmoxWrWg5x"
                        "DS6/Mrn533AmfxaINqSpauQiorGPmwEAbDgty6F3Cs6PzFA2xJHNgCjc5SBL/q3TgxAZoSwcUnGl"
                        "rO0iEHig9eqZ9715+ZN/6vZ3vXEX9qnf+MztTz27PZlO+m44dXj58H2HsNp13/oLD7OZTB/7qn31"
                        "wqSdm/Wqu/OG2fHrb/5HP/21v//Tr37iy8cIt2/NZj0PvbXEMMZa0wz90Lo3McgCjbV06hgeuOny"
                        "cPEFu4Jp5uHzdMafFA2jV9nc+23MA8BXdsmdQgOSM911rnLVLSj8RkyTmzNrodLYWeGKH89mzskM"
                        "vxkYemlenNwZuXMZiTtWWgh+RBKdC4iUg/3wVORB8qA0hASg5bPmQidDEs5HlH6MEvOgeL9qzOpx"
                        "B2BNC/x2MFZexuIx73M4QYXRg1xXhTn0W60m76s4eaTahO7CrC8lZ2tK2dNCoUp2AzMFzToKew3R"
                        "6poKEVniwfDQr6/bOvunfujIn/z912/Pnt67eHXr2I0f/sTqymp7fmi2t7p6/x3tHbeth74nmvqg"
                        "AIK1aM3nvrruMZ2CjVnurq/7wT/x9BefAujeyXZLQ9/bnkGNWRtqlmsGP3f40HzVH2U7c99Js0N/"
                        "/Mhw9OisYeJGUKGaSHcuqnYpUbDyK1c93smUKoDIxTEVSvLMryH/QSJX4KcSqlS7BqA0k2rgXO0I"
                        "yaORqypoqj4+wjkzQx0NwIqIFzZ8Yj0P4mmyj4OeUoGvrZSPt+Ni5I8dHOBBiSoq1lkrq1zF57pk"
                        "FSgeQiJ3iUi+/gIHu4wxYc+6f86YTWv5in4doMpvGS9oBgA4+vvKWN4tS6pzrcmct9eErah0p/HK"
                        "7rAbO/T2tpMv/8zfvOltr7/QX3qhW09mtN130w99etfiBkMWWL/lofnhQ93ycjNtEI7bJWYMw+xT"
                        "jxOwRRYtzV650r18/sRka0a2Q79igJqJYVqt9oArt91w6X/8/jPzwzf/mb/ylWZyA3hChtmuz1zH"
                        "Rw6th866OeuUTRetrPYWf53N5R0/jlBxa5+tKhJF5FbmxpudgkZe4lEdGnECM4fPEyRDEzHs0DqH"
                        "aSlihoxXNDOUbCvNraVgOJ/h0sJqNrRVZ0RUlE9+1+pUjO1arfdAh8Nn7JZ3N16k8F9loAu4l1xz"
                        "2Tb8SUShGyigdyPpyeFlJJOIxOwhno5WY0Jl48SSB+E/7UhnTwM8wpcPu4ZX5EKMkx+bE0DKnpei"
                        "tL/N6kJqgoGmHrBkj4ePztLgvoNuWuJmslwuYch262/7+snbHt5bnn/JmknTwEz4xVfxmcf7tqEB"
                        "fUN7b37EAFcN4L7ROwzcW8yPH37l0ulPPwEyc0uGiVtqtiYTGlYDmJsZtZP1slutnn/wrnN/7X+i"
                        "X/up0//Ln6J2/bQdTMMTgvtyYn/jDTSZrf0p7sSKW78bM+hKiwTAXNlZA2D/uq58SjLzz8SWUMO/"
                        "ZbYbUbtfqRSaEncAOGtkTg0sCTRJx2XCBPsnxScQZww4fOG1XgpwJC5ps/hFVDEVbcbFRbHSuqIO"
                        "Eps2hxqMnTh6TWUDH+HWOKMuGIevM5W8Vi0G3pg0ZXY33Wn3EhiJiu+q7DdmLiXSYwEH3LL8U4jt"
                        "v6FcpZZlqmqdnF6xqWIMGY35kmIYG6zZpRUCEbeDsU0zWS2G7faF97zr2Me+YPu9xbvfepT7c6bd"
                        "MkR2sO3W/PNPtC++2rfTyXo1nD62+/B9R7BaNZh2loB2dtQs16f+3fvbv/1PX/jai6fayZyZrekB"
                        "02HdmgmDu8XC4OI7Hln+yHcd+s73Hjlx/Nxw6exw8fhXv9YAR4gbEAgN0N16gwGtnYtxAUnGVIfB"
                        "XNm18JPc9bkJgTMcvwmQaDUbHGx2KgBh9U8DAulokiVFDdaAStM1ykGulH1E6wVz/I3UFDVORPjI"
                        "phuyhIELBSKsea5qQDMfYj3r81rHrPRagZWYfX5aw2ugpfl4LVcAIB3j1YlL9XKlVjuwDMWtCjQV"
                        "VnXniYqzKJZFt7R7Knk4GAGyOrqI6vWVjaLnsF//PgiFtE+ZaMQxvPsTYGGIh8lq+fyDty/+j794"
                        "19XFoff/+NlbTu695fUGq10DA/cN8Hb+wU/3PR+atnbYXdz/OnvXTUO/gjV2tr21stv/4QOTv/fP"
                        "L/2XjxmLW6aTbWsHAhMb00yt7ZbLc/N275veQX/oe7a+7V3HDx/e4Z2X15d7Ntzw4a+9sALmFgOD"
                        "DQNY3HETgTswgQcUbyAEGfQsBAy13Dc7uwPQIJvgLpSTeUGWWqq/y2wUHFX3lEuiovl86KfIkooR"
                        "cS6l7NCCeW0SiRmnKDImSJ0pWZ0le5BGx8TXF8uIVubmsgf3zdzpaQ3pKH0zQNA+XA1zRfZINOUv"
                        "+nSZTEhk1MIjnKULdbeUkws7iJTTJOOpwBBzbswZ1SxMZDR109og5MWdKh0ipKZTgUjZxSywHqRw"
                        "3I9TBQdOcrdIZkHtarF3ZH7xx394+mM/dPrGW/h/+NGvDHb70fvpjhtXdtnDTAnUmsl6deQTn98F"
                        "TlnqgN1HHtyaTHYNHe4mp//rx4a//VPnf+E3abBn5vNjBO55MLCWYYZ+1Z0/unXlO9/b/oHvOvm+"
                        "t/FsstPvXOov9MZMmrYhmlzemTz7fAdMmTpmY2Fb6m67cYKhc56le1CjiUQqAlmsO97Zs6iBMW0k"
                        "2e+qz4+pvVqhyG0OvCTzTcit3dNRuxY4YzxrQv1J6ZWcpRHI48NrMFoNyiLlVM9RUZnxbwaeJPB+"
                        "3HrHhghS2rBhJemkfRFv2Z1VYTYzxGF2zq2CZoAzizhEMunoWmE9PaQY8wN4FcV8HWcEGQOxlfBP"
                        "SMG8cTdDZZggnLuvusJvEPMTKyNdS26LBnN1S2osG/aCHaQIOJNEmt7mMBgEU9N1L7/7jXv/+//z"
                        "1LseXXH37ItP3/KJxyzQv/ttk3a+2y0GIsvctjM8/dL0ia/smaaxwwRYvfstc7N9/P2/vv7b//zq"
                        "L/+GXQxnJrPjLTBY981tQ0zg1bFDL33nt5gf+r3XvePBgfCy3dvpFlvGtNSC0DPDNLNzV+nl8zBt"
                        "62bXu8EeO2RvOWPQD2QAMhvcWAoTjKH1gJ2F3u1dR/3VbF3WLBva11lCi34SY6w+pQN/sZZwfKjU"
                        "4fJtCreyoSlUW8jE15lecZUgNVHFvmhIVxiN7HlkvubSgj3M0eij1GkJK+oMFV5XhWn5U/BDvhL7"
                        "CLzKaLvqBSphebqKg8b55/CmO4WblZnLMbDpfoSjGqNMQCVIpU2zBoBZQ7ovmHn8KI1RMRW1Wi+E"
                        "lpnZEAENcdetd7/5rbv/6m/dfLx9dnF+d37y6KcfoyfPzo5v773z0UNYdmi2CMMwdJge+dQXzEtX"
                        "D023Jt26O3Vq+/zixh/4Y0/+/K9hz143mZ2YTToaejYNQNaiAaPBsDz3V/7fJ374+1bD1ee7HcBY"
                        "Mg1RR8zsXqUZgEn7/KvzC1eHdtKCAeqHoTt1zJ4+6b7cPBAmlYUa+eSM243l/jRYLGl30cC0sEO2"
                        "yrQhAFW9QJrL+nRDZaT9PmKE9aezhsKf1UlM8SGEiONxTOYdEoNSG4tIPwS+zHRHVaR9sAJHUnEi"
                        "rxg7yCovGc2WQ9RNfONaYN5YdNtAJAvGYyE8PMgJQCVWfe93fxS5RaKA/FuRQsNpZfICWut4cywE"
                        "B5Qae1fpIWlUU8hWizZEt/SLMvUMUHDFxQ/1twHYEGzTNKtVT/bSocNHVqsr/903Hz6+9dze1d1J"
                        "MyFz6AMfu7oett50d3/fXcOw7KkB2QYYQIc/8um9AVsTO23Aq8WhH/2Js8vl0cn0+Jy4pxVAQ9t2"
                        "izXA7bRla601x7aXb3poZq++OKxMMyEHk4l7N8njO3Rinnm+W9p23jRDbw0Z2P7MKXPs8DB0lpr4"
                        "doEWXV0JP5jRmMWK9hYgcjCSOdXe5tRbZMR6qVbIhlElAKmGg8yhgvHEgZ5gn7HWVUPSXEJch7BQ"
                        "rWwRzu+sZcEBOjIExIfStEoR4m8XEA8crVCo0cBt/aV4T6tAjxOrpQqeiSgcnVFHJUK2HFUVxcKP"
                        "zhyX8SOgzJBRW0BhpKpR9pWtUSUShT0IbhzHRHYM31aFdaGzZF1rr9RkUF18dtQx3BQbhe+S1Ppk"
                        "JG04ZGqz8MfMxGR4INMTmdXi3B3XP/sTf+L0fH7l2KHlWx+Z8rqb0LyZDDs72x/6JAH26x/eOnas"
                        "6zEwMGAAVoud5uNfWBEdYbsig9V6MtiT0/lRg7Ulbsisll23eOndb7n8ljdaO3RoaRj4ltN886kG"
                        "oKYhsAUPBPdBG3K6Z7Yw7ZPPLoPs1pgWbG88025N3O5191K6kU8W5dqCCWiLQFh11HVEgKXGaQ/K"
                        "4MUOq7Fpg83oiLbBRzSQKSmPDp1iT4kxuxVMz/pmx3SWxX7F0++xYM68VZKfdXFMaBrj/JeZbdjc"
                        "IGRLb+XwX3K9rhn3UkK+idJT3pAYhI7Rf1TVuiF7UChZZc3r5uwkj2QNZU8pLcj/5Y1m1NwFRW20"
                        "g5WqPJYuM5gTsxpb3dNOVvU+NqkoyZmtbM4BmWNkrDqp7LhS01bq1kNEIB6atuttvzr7fd+884Gf"
                        "ve3Bu5bnzp17x0OTu27thnVHQ2+mk89/Zf35J5upwfveOiW7BzJDb4nt9PpbPv7lw59/kibtlGEt"
                        "hXV8yxZ2vbzcL55+71te+Jm/vvVL//SeO87s2cG2NOFh597bJ6eO9dwN5I+5yIyVDBG6+dNfs8Dc"
                        "WrevzYD59hvnNLNcnCzIeQEzERnAWACt2duzixVRE88YJkqOGxZDHevf7Ed5cYNhZCGvwFaxjv6t"
                        "oBBDaalkOPOUfd1N/6X4AQBrrbWaE2FbjFw7u/tPWEoYy1osvVunCuznEbr4I5L3FVinlGoXSrUN"
                        "RDRnB/ReVyX46eggmf12EiAJ3kRxOdkhW5kFsAF8eXFkE3yV/kFYDVvm5FmS4eHYc1WtVkl7s5Fm"
                        "kEh67YWZiIfu3hvO/vkfP/E93zyZN+f+7H9cAPNvesdsNruyXoLYojn0wd9c7ywnD9y+fvj1R7vd"
                        "btK05siR516Y/7N/ufrHP/vsXneDaVaWW2AwTTNY9KvLM3r5297V/5HvOfUtX99sHbn86oVnHn+s"
                        "IzppAGB1/90zahfWkj6dSvQBwBisFnjm+R6YxiPYYW85MwFdDYCU04FUQgEAs/GfLSCzsxhWvUFr"
                        "YIcNatvcEZm76keyK0JHP1jWl+upDSRPUdhRlXm1GlhgrK1EKZvmbWKdQiLmZCKfC91x6IvK3PdY"
                        "lNgcUsdKiN1o/f7fkVke/cBYMCpBb3alyiJVxuoV+E3UBEp+XEMwQc0+J4eXYD36cjajWrZIzALM"
                        "NkQ3aYvlhWrNrDzFBcgq9APVnd6pQn9zRkprtfxRQUOhCQKIRGpkdDIiHLYylEZMxBZ0fPLyP/lr"
                        "d77zTS+sL5599tIdH//cMJ+273lLi9UOmYYML1ezX/3UHnD0zV9nb7yuB5148cKRf/kzy//vz5x7"
                        "4vktmFumzWxgImMHTLrF+WOz89/+rbM/9D3Hv+ERmjWXVztXBzM7e/a6F87vTqfzgToievDrZhj2"
                        "mAjEhhp9YgERDRaThs5d5Odf6agx/mtGzAbrm0+36HpC49/CNpVvHQU6hpgs0TAMxvZX99ANjJYB"
                        "CxLvqth7UFrS0ToAlW5ZPi7ruVVqWa/tlwKT7gsTSVZsO3hHEvtKmqWjBfQdBwTuhzGm9MIUVZVO"
                        "mgOlquNn2tgAeoDEa8I1twhm29CkOPMG9VXyg75eAukN0XRzoC3cO1ZnsHyk2slvLeRDytZGEbRC"
                        "N5dUhHy1tLSGMpGGx5EmpU15O4tl+yLNEFiRPbUBCUpeyq6TMcNy9egb8eiDO4tzL20dve4jH26f"
                        "eXX6roea++/kYU0AtVN87qnpJ77UA8M3/Y7rrtrtf/TTwz/82Utf+tq2MffPt8hatkyAJXTHZk9/"
                        "5++e/I/fe+bRBxdNd6Ff7HUMw9RMth5/0l5eTKdzu+7a49vr++48ir7TZxgo2wWY0TYvnjPnLqFp"
                        "DDOIeGCeTZZnrt/C0BGB0fvKecghgAhkh8ECTdPMtyc4dfPuamvgqxPqJKsx+0lfrfOyf6ujFW0q"
                        "++ae7EfWR9KKcuZoQqITNSIz4YreJFV0btjBU61QBOLIv9it0y1RLmM1Pogg8kHDarQqtVdVZvls"
                        "5kFtQrFiBK+lHBD16XQkcGCcAmciOQfOehdBrVl/SFF2mTRShozNWVFVpjAUJcVnxMkoOm/MGaoN"
                        "pVfGZNmk8yKoMdCAd37nO7fmk71dnrI59usfBcO8953t4cPr1WXD6Nt2+yOfGS7umCPbhz/8+ZN/"
                        "4x99+bNPTBpzy9Z8buzQDQvGlNgaA7t+8W/8+WN/4HsnWLywvnJlsC2bxhjYwYLMZ754uecjU1r3"
                        "Pd9yK99+I/G6G5HbfTy1ee6lYXc1mcz9XF0/2GPb9vRJxtAF/t0+LBa1syVrLaObNm2zNW+mR5e7"
                        "hz77eP/hn7H/9y9ebdqTsGC3YuMRqoJY6htZY1l5cymVX81nZSn6To+/PJs6MwVnURoreNAmkWGI"
                        "NHBUMCOzVe+KCBDj7KlS5AxhZJlgsxI2F4o9RQgBi+FmQP0ZQggTohrNHtwfKvGyDLFSjdktzMll"
                        "VyE/RUiIyZ8BDMMvjYcdW0FCmbrKoV+JvKo4Jct+mglVDCDCugpwq3JE5N6uyiiL2W0uYxnS/X+W"
                        "qUrOwy1hm51fWrINoev52Pbee995HXcvzibm8uVDH/7UpdZMvvEdU/TnwYPhgSZH3v/RBXCq5+2/"
                        "/9MvADdszQ4Bg6Vh3fds5hOzJqLVYG8+Mbz7zRgufrXvJ20zR+N3UxnTrxbNp5/ogYlhA969947J"
                        "8cPDsNMTNS5ba0UQMcOimT9zdsWYEMGCDTAM61MnmuuOw/YDYJisAYMNuLFgy2sDNG3TbG+h2b5w"
                        "efvTn7K//tH1+z986fNftldWh4Fjk6mBn2IEM4f8QiFB5za5QbcH7az9Mr9ECmdj4YoJ8xKVSDSG"
                        "xEucWLYWoWWs6QKfW4JkpwwiN+R0F5ssepaNVtF9afBjSsjCHJTppk/JANa0pcCCmKnYfpnxMe7G"
                        "Ca8jSpSIkFzL5ElJyX9GXYyDuABouVRx1QLK0WKmuBBPc0MJgdKhpJjxwjhFUtNBM/a+vlEN+vuq"
                        "N6fs0rVhu957yyP2wdfxerEz2zr62Oeax58yb7inecPdk24xzA4fGejEv/2VyQc+2Zn2RD8M89kJ"
                        "YrZYrboB9vKdNw+XFyeuXpm2Tc/96sG7+abr13YlCxdEBGOpnZhnzk++/NTQNHMGgMX9d7OZ7PTg"
                        "VoK7ZhggDLBbTz63Ag4RLBgwBNufuW44emjgpSUyzDTAWB4MhnbWNrMT6LbPnscnvkT/9TdXv/Gp"
                        "i0882S7tEeD4ZDadb8FyZ4fiS1zkMzRG8EgN3u4DwBM6wSyy3skQjUZPGerPuBJThDLOaqiqGQNV"
                        "aabYKrfwsv5m8eX6QfLxZiJlBWGgjTfIY2OKtfdvb0OG35etTN3Vgbeq4A0gjl8rrTPSCOIeHafm"
                        "6HjgDQX6wu98UKlw8qgs5VMZtxnbVU8o6xwkU23gyhVjjSHb8ZVveed8e35hsbCYHP2vH1ksh+Eb"
                        "3zS77qbJ8vKtv/6p6d//v8//p18fLG5omhWTsdSsVyvg4gO37vzI9594x9vu//4fe+zScMN00gKL"
                        "R18/nU+WqwWZVjYqYAC3s+kTz7YvXpi0U2ttQ1g8cA9h2C3PCPH8M4hg+8nXXlgCM4YNr+CsT5/k"
                        "ttlbD5aob9vWzGeYHluv5o8/i9/69PK/fHj1kc+un31pwtgGzkymWzPj6PWDdRYt40dZ2XLJDbor"
                        "NaYei18lBMvyB9K+1uaU/YvUIWtJsTQz6IhWDaPVp1C4M4VzxrOJkcBzxRfD3FalxbHoqcmWAXGs"
                        "bLjb+hEgVT+duYnoxuASAzOlX36vVkOhaOZB/UlEUK8QswQmxYYc1OcuIkxjSXDxEjKz+maEC1UI"
                        "cZAUEd1puWr0sSFFWqP0GMxRJC+3su6sZjNxpFKBmlRxNwebTLbrhmNbq29++wlen29pul5svf8j"
                        "O8a03/I7XvexT577a3//xV/8AC37k9P2KFEPavvVDnD+Da9b/cj3nPiebz55w13NL/zCk8++1M0m"
                        "poed0PptDx0CX3RfFgoMGUaPdvvzj3VrO52bZt33R+bDvbfM0XdkDFOi0sA5G2MWS37pPAEtAaAe"
                        "hoD+plMDTdezw3O01+/sbn3pcXzgI+tf/fDO5x6zL11pGafQbE2nE1APZoYNG+LI7aqm8JJAfJUh"
                        "fdG99KgSg+i+SNmuFH2rGuyqd6GspYAqEnNZL1lsQIXqwVglFcSTzUiJXwRmmkDflhJnIbjKg34T"
                        "VlcrAdQGC3el1fd4w35EXe3A+xXKKJv9CGhlDMrmZKp2oPkp8TPSHEJELpRRuskF6pCZjD5qitMt"
                        "ZlwpgMZQb95X8+GIyJVb1cpV2asEHT+G0A2rR+4d7rmLV3v9dDr50rOrzz5Gh4+c/ps/9eqHP3r2"
                        "0vKG6fzEVrPu7BpE/eq5N9519Y9+/7Hv/pYjp49dXe+eH3ZOf/hTW4xjpu27Nd9wfHjoXsPd2qgo"
                        "7rZ38nD080+sgW0whn595qb1zWe2ubOE8lxQAMTMzaS5eGHy8nmGmbAlsCFuAXvb7TdcvIoPfeTy"
                        "b3zCfuhTO4891V3eOwmcaNrZdNYCPaO33Pm1P1jIl9v97GgRJkaUmxnVhvgyhrM2lMwdMmPTma+s"
                        "yRxfVlWhJDfCLLGFpOU0kO8VyIYCwWvgPlxmLZPKK85Vx4YOZVhHYZPVWD/mWaUS3I82uURlz15D"
                        "qQbXfbEfpQcbVbs/A9hjiaUWa7RjOChF4Wc+DMz4J7/ALGANiIZFYboqsbBqsN4ARcd0kl0ZS9Fj"
                        "CWOMLgCDBli8562TWXOh6wZz/HW/+K/6C4vpFs9/6QN7bXvn/FDDa9tZa9qZXZ/9cz9s/8wP33xi"
                        "9kq/fml9hQmTbm/7I59ZEo4C0364+sA9uPXM0K+7hhvCwH5pnJvG7Oy2jz/VgbZBgF3fdevkuuMr"
                        "3mP/vcfAr3gUsxkafvHV/vzl1rSGmQAaLLezw//s55d/719c+OpzjcUx4MS0nc7nhnnBbC0v3FcI"
                        "2cmefttKgVOfq/x1f4Z7ADI1rdVMIre6g8QpqS9mdk2pSwhYC/f16rKyzrWprVZmJ9Jmy7yYtBCU"
                        "mW/CqEpX/XMs9NeF3A8wthVn8EiRKT2lSprHRm/MojjSjt8QZRlsvGrcv047DLjthdGuNuNP4Zby"
                        "ySxB2qQkygE5YubJgykzaQcTuvvacankMQxclg3xLtyS4XBZ02VFYrbuwPs1D/Pm3O9810lztHnm"
                        "hTv/7v/n8j//eZ62t9uhn28fGgYsdy/P2qunThx99fLsxmOrP/K915+YfqXbmWAyR9NPTPPU893j"
                        "X7U0mVgMjOWbH2on8/V6ackYDqsQlmnamq+cHZ55cdk0LRGA/v47ppO269yiMIclOiIGrO3ZtsYM"
                        "zdHjr16e7nXrydyEJRYmmn/6MQPc1k7biQFsx+gHP83QGDSW1ewnwdHUKrJw36Ng9VUgZ8aJhmXu"
                        "Qp7d0E0H7LgsgWUGnNVn5jD0U2g1hGKo8KHoA+GkEAmFzOzOONKGqTkPGmLk4zUJ7glXpBL8mCrK"
                        "qFQVVhM5eC53NgwMySvKPhiBD/4y9cEzTJUJzbExJtgwEcld+S8+Jc+GWUMfQ3229L3ofTXlFkJN"
                        "eXgpAqfUYgUbRs2ajQx/SSLKBDyIEgJjibCowf7NZMtWAJAxw7p76xuP33Tr7T/5N+23/vD5v/0v"
                        "ppcXNxkipma5d6Hpv/Kd737p3/2Dux5+AEO38/CD5sypxXppTWuICXbAnD79RPPK5a3WEDO3tPvW"
                        "h+fgnfwzotZi0jz+FF+8MmlbWAvC8Pp7G9AeAGMNQJZNb83A3DSYHDo0PXH9Rb7113/j5D/5t3tN"
                        "e5xsE+kxT2fT6YzA/TAMAxuGCS49cLFdW5cEeVVuJolEFFuiFekFbRj6YqXpmv1AmWu1/oZJAhnf"
                        "qkdsEDFSRlRF3lCQqy4UKjkeRGSMGTPmDJeUF4umE3UdPHpIxbhKmDUSQnr8czOOrfaKdH8VQ4Zq"
                        "BNk85VpBfIrIgE2RZFR4Hel++Gn1GD5UeIquEACdJzu2Uqlk55CF8sy5oSeqabbUhtJYBaNlgqv4"
                        "VfKbM+9tndG0fG5x/e/9w1/73JMwuHM2txiw7C5ttRd+33snf+QHjv/Od02fP3/xiS9dALa/8dHZ"
                        "fLq32p2iGUDEGCyO/NqHhw5HtzEsO3PD8e7B1x3m5dK93B+VyhZm63OPDx1vz8kOdjg8Xd5/z2F0"
                        "HTFsPzANk+kc24cstp9/9fAnvrD+tQ8vPvCpq196irruVDM9zNwjcQYbkg3cxu9gDBkCEtTMRDDU"
                        "MCi8QR0dVXAKhcUcsaJqhig7Qiro+lmFsnPHOrSoaZWZxfNIat7Hfn11ZClA5e8YnbV0OsWyn+tI"
                        "xz0jlIsHE8fUP0q7LbVRluxZ8Y8W8JthRDWEEGZT1je3lAGNTGVl5ZQ5gVE2jMV0BUtEjHCSctHH"
                        "MoDPglepoIIZucXGeAtAOLNB7eKL/2pqaTh22uMMD0J1fCl4WaTaBrsvf4QW9bmaMToTEbsX8sCN"
                        "2frSYx1wfLY9H9Y9D8byhe/4xp3/+Yevf9sjfTO8zN381z609dy5rSPz5dsfbbG+6L7xBXSTxrxy"
                        "cfZbn1sQHWMiO+zcd6e9+fpuWPegSWjaMhki5m7+xa8ugDkz+m44fZpvvQF2vdfOtrB1dOi3n3p5"
                        "8tFf51/5zb3f/GT/ledbxmHgyHQ2mcwGa3s/VkyVzeJ5DjB5Zfu5CwY5mG5AQ2+6YQ+2B9p2Phtc"
                        "34FMDi6cOVXQl7b5Mj+NdWU1xlUpo7Al9uM4347UCgMCSQlipeLMHN46Msw2zHNlHLrEbAPxiomS"
                        "n3/MC6cfXsn0sEFeoiShHjBUlU3A4zIAaJ2kLkp7uq6pkRW3fUupiyr61T+I/D4o0bKqAJAs+cDI"
                        "O9CKuLaAEJgrzGhg4q4b4zwZIUoiALEYtsZEKxRCwcOoTFMHiVOb8XZ5S6thM3H9HJi3prMBq9Xe"
                        "C/NZu7ZHbz76yt/7i6+78fTZ7uKys3Z2YvvDH1v32L7ntr0H75nzekXUEsgOE7Nlv/Jlfvp5nrQO"
                        "mK/f9OBsPt9ZL4xJd1Y1jbm8O/nK164A2y3ZlTX33dHeeuuhxc7tjz83/fCndj/0W/0HP7184fw2"
                        "cD3R1nRuXMZkO4AGj+0L8UN/MWBcHQKDJjAT0MCWh9Uw8Aq4ODWL20/xg/fh2PXH/v0v7a6664xx"
                        "Fq5pMrN7XSds+g5vw+2vx5FdmmO4eDPNtKM1cIv5r1CGHh66r57HyaaR5jzaEvoaIVor9p8+E0Ye"
                        "JasF0i+RgcSQisiZzW8OMuLULZOn5yPGSKrZUEqgmCFDLZIOVQKqyZ8iWsZsh20c5mMqbqXK0jkH"
                        "WvyQmBOeBQOnfZwNHPYJN2nUGI04ryHrVocAJcFqN3OxXB14owFYr185vPXiH/vBGw6dPPWX/86z"
                        "3/DokTMnLizPX5q2h9qWzl2cffRzA0BveZCPH+tWF9H43hwwOfrJzw176/ls1oJhsHjLGwj9HpP7"
                        "zrtvgpnQNs8+x8++2FAz44GNWfD2ib/xT+kXfmX52S8vz1+ZA0dasz2fTdlY2IGtlZcCyy4IwIoN"
                        "TMgrlgxZpmGgYTkAl4HdY1vDHa/rXn/v9M0PTl5/39E7bhruvs187EtbP/fzLxs6RdwD5L4O70wd"
                        "ABHiUHNcq+UoqRx2VUcYOqiVkatqHrV2xZt8hWziguFOdAeRYR5CYMq9EnGsUAUQJnjY6AjugPas"
                        "tFePVqWk5Z+1+iBQS8mnFuJT1Vh7ELrlI+4nciW6f5kobKcIfuWij4oyLFMVgVcS5fr6JF/ClRbk"
                        "wBm32KdZcnqUuxQkrtsTxi24JrKwHctBRgrlI5uv1AiKIKyGD+7/GGS42zs0efE7vqP9Y993/Tse"
                        "PfnDf/Y58JX3vuO0aXYNHbYD2i364hfw5bONMVfe85YZcJVgwIbdoZR266OfWwLHDaNne/3R7oG7"
                        "51h3ZMDEZE0Py9w3QHPi5FO/yZf35s0M/WCn7davfHDxi7+2AG4yk2Y2mzg1WdsDAyMgZ89wCHzw"
                        "58cQLIgJjTEMbjq7tuslsACWp44Od3+decPXNY8+MH34/vm9d/CJoz1oD93a7i15hZdfONYPjZm4"
                        "7jYc8xxF/Uhg2A/SbkABm4eKGZ3szyygqCFCgvfhP2tSWJcfMCJsjU7ynwqvklPzaJtFbC1LCaAy"
                        "2FGVMb3AgSUKcz4H+n5zQYRBVk5riNH3WoeaOh5XIXH4HW9SPEPDxlflCfE7Amp46i6oSVPRe9Qh"
                        "WxNqy8p07rQZ19JkaI5Cv9SDS5Z5qjLCB+IDKXBM1QdMDNqY5Jomowk2Bt3QP3Lfq3/nL9zw6H07"
                        "U/vyV768/sUPdofnW299A/FqQQ2GoWubY7/x8dXO6vCtZ3bf+vA2L68aGLdTvJmY81e2PvPEHswW"
                        "E7qu/7q7+I4bh6FbMx8Cr5t2mG9PQacu78w+8bHpP/n3C2qPGjCMsWzJzGfzw+618MF2jn03kCGA"
                        "bdjwJiK4LzmzAcEaGtYG9ipwFVhef6S/94HJWx6av+2B5g33bd1+0+TQoQWwg27B66675Bb4jWUz"
                        "bSarrhmYWyJmAyrWwBScq0KJrFPk7lhiG7tbrS+zcmE7BdIPr5at+wfl/HElRGVoVoMwm7dQkbbe"
                        "NNgl9l8dBhZtscRf5VavIcDEwm6VcAzNHsRnqr/d48YY+bJWUIQX1VpWh/u4xz3kyfpmlPW441Rk"
                        "8eimmCCUQSITubF6jIMoAlCZSDdG4deq+306u3KxHHqMo7aMYVgzsatXf/i7jrz94Us7zz/Vnjj+"
                        "/s/SS5e79z06v+cWHhYrNDMYXiwP/fondgntI/f0t57put2OaAYM1g7tbP7Fx9qnX5y37RwE8O4j"
                        "DzZbs3U/8OzoBPbIK5cOf+YL9lc/uvv+j1597Il20Z8ws8NsewflwYblzTU/JclQJ/CA2S8Ri7k7"
                        "F6a17c7femrv/jvp4fu33vT6Yw99Hd9+Pbbna9AS3flh1XUXDdGEqUEzQ2ONW2UbBpj53oItJi48"
                        "il6qA7rNfbE5S1WfylL4WFzTXg3skxRLW9UVMtNVlUnFasrMQ2kguTUycqwU3WjgpBIQHLCtarqM"
                        "NkU934VtWGAhBKTD+VbyXMINjenfMlEHZ43+DBkvjIO9eppJ6VRv6lFZt5wkCv/4QZBHbgxkI0QK"
                        "w8AKkQ3i+Idro7MsamT5p6S5udENrV8rBQCZAgmm64dTR66++42nhisvTyczxpFf+1AHzN739unW"
                        "1u7qKoG5bdovPcuf/0rD6N/+hmY6XXR7IOoZrR2AyaGPfX6x6qdbc2LQhFa/813XmSOr514+9KmP"
                        "0K/+1u6HP3nh8We31vYkcHg6QzMD2zi+EyvyBk0WZIgHAoGa1sGonsBrDwRgDVomY/ji3/qJI7/n"
                        "PdvXH1pPJwvgKrpVv8bqam8AahoyU0NEZNmdRhOXzADDO7vs3fVa1Jdl4gNiXq/uNIhkdNIxYDZH"
                        "nth8LSZWrm9AGMogXQX/fUM10NGkZERSJzImr0dl8SthTlelWoBidbKUQtXngn8Go0UYxyej2EBH"
                        "/Rh1JO2oDlVlTMQKhsJXuQzDIp9dckQc8rKCKoWMViURMVsy2piIACb2+zN8IIYSLoFaY0UPtTLj"
                        "2IBxMkS22bglH1Zj3DW5x4ZGHDEAZAwvl4++ubn3rt7urSfz2bMvzz78ib1pS+95S4NhAZrxsGy2"
                        "j378C/zqlcl0tve2R7cwXAHNiFowG/S2m3/sMz1wamDDtt86Mv3EE0f/zS8/+2sf3nvulTnjMHC8"
                        "nbVz0zAPzC5agcj4DQhs4XOi9bNTjQWbYeBhtQCvgd3tOZvm6HI9J2qIQLCD5euPdN/+DfbmY8+t"
                        "d7r1koiIDJmGjGnDrlHXCIEJNASpXcDClR2vU0LY3J1tAC9iUwkNsn7JOr3qzNXYUdT3yMCt0CEx"
                        "pwop5wtjWwUFZJToLEidtJCpQsJowBP5/qkaP5z+WxlsBjoVnexbFAMIbzVSGztAxd3y2TGiZVRC"
                        "oqNUYNlIFUJ5snISpjDS2bRKkgkNUlCTb4WZQeleNTBYgmISiTBiapnKymrV/LbhyhjZTHXye994"
                        "d42FiRpg+c1vn03my91dmsymv/V5Onth65G7u4fuNsOSiSaAHfjwf/3YinH43ptXr7+H7HJgM+mH"
                        "jng9PbZ9bnH8M4+/TM1s4L5hu1yf+kt/8xywBdzQzhvjExAPwwBvqZKBXHezy1NE6PqBuw7dElhu"
                        "T5evex0/+uCRd7zBvOlNt/7E//nSL32QZ7NDw2C44WHoTx8fDk+XdmGNmZLpBM66LOSyGxC+wKNG"
                        "A0QMnlzZJWCi72i1V3u2hEVlnervaoeWNXUEYa+ZpBr5fXMWhW1UaepIWs2gUHZVHRCU7KXDo3rk"
                        "KouulkEfNZaq5OOsCQm+iqbvv/Yaxxr7l5HwLwKYNHtApq7C5+JkwstTC8IIStIdjHCaO+BTqMyJ"
                        "uIflOjACmzlYjQTCzaJt1ljS/ZoSJz6zmchozKKwGo8Q1/cpREDf2+Pbl9/z1m1eXebWsjn5gY8P"
                        "FuYb39oeO7ZaXx6M6cykef4V+7HPDIB9+L7hxOFhvbOaHoJpj63XNz3+0ta/+c+r517ZbluCtQDx"
                        "MExn1xExc48BGMhPUKi+C9KiNbQemmG9BlbA5e3Z6t47hzfeT296/fzRB07cfztOnlijucLDq5cv"
                        "7YBPuc9QOr+58bQ5ug276N3ZrhTeTCAiddAVh5MzEy0CjRsSOpC3j9pTrpUG999FNdZf++KUEJsk"
                        "yybfiFUJW/AyOaPWqVxClZ6ML0PAiDgS45KJ/A1JtISoY0F8LCptuCJPpbcifFMnjm4aiZRIZ59W"
                        "kevIpugmiUpub03gjOKeezfQU8oR7oMODfmRIwNkSAaBYE9T9rw5a0gyTEw7QFhBD8vIRSehsLmq"
                        "7Em0SmJzFACK/lgCr8RW328MgBKbTttNHmEi068XjzxkH7gb3WJnq51cuHjoNz910aD9xnfNQC8R"
                        "DFsy8+nHv0TPvjwFlr/jHScmJ7Ba3/HYU9MPfWrxK7959aOfvXLhylGanmI7NCB2Z6PzwAzA+E/R"
                        "SO8QA0xsiAhEvV2t1xePHFrcdcfwhvsmX/9w86bXH7/rVpw81IEW6F7sl+v1xaFpJi/uHXvxVQsz"
                        "dd1p0ALLm25o2im6BRqEb93KnkkyYP8hHBBknirOCNnmyu7SIXl1bnui6qhA1T2UqlSbboZQxjRf"
                        "6YuifjiJ2G1WgLYOINqnBGXJqSFvhX0fKX2hUAqbXWFwXKBiZbkF+DoA5CcgD2RV7FbFjFVwmjHg"
                        "fuRnP45En30yzAYKqQcCYT9uhhirgTkVuPwhIsHFHB9ywFr7qnIMIJoyp23oM8oOYotjPertK6NQ"
                        "0MvS7wbL0DbLYJMOAUYecS9qXPodX2+25zvLBaaH5p/93PqJZ5o7buofeWBql8ZS0w+7k+n1v/bx"
                        "vhtmJ4+ZYXrLX/m/nvnPv3Hl84+1F3Zb4LRp5828Haw1pmM7UXvcEMI7jGHAdL2xtmubFgSCGYb1"
                        "686c/5N/8PBbH9q695bu2JEVeIn1Xr9eri8NAGCIaApDzQznztLFy2iahmCJiNAA3S03GrQ90KjO"
                        "iZ6r0LMuBnAvFDWXduE2i+5faorP8kcZrTYpv5jo1KTK66Q2lCO6t2qOQ+ytxUoX2gL8TPLr2EjQ"
                        "DdaJYC3YsnunZwPnGTU1eHS5KRqk/C4D0L560+JrUu7PVgkA5IuRXO/G11gECnkkXPzgojI0A6Gn"
                        "KAz+SQU+QjhIdCwlCF7T8hP5TUCUSJvj8H1lqwKigybfAxevFJJX6fapzoyht8e3+m9521FevmCp"
                        "RTt//yf2Ojt7yxvM9SfW3e7u7PDx2fTGl8+f+Y2PnyU6sezpx/7S2cWCgRvb9tB81jCstUy2b2GY"
                        "J2z8OUCGmMhYmMF2w2oNLIC9Y9v2+InDL50/wnZmjFl1y3e/lf74H+r43PPDgPUl6z6mR2SatmVi"
                        "C5CFZUY7eeHVfmdvYqaNx0MEwN5ypgXvypoQeYxJqnekSE85cGuGnnZ2+CDbFCPQ3q8aDgQ3sggV"
                        "M+VY8EIRTcrK0Ue8CYjNxslpaRFhy07iWSphK3QmO+AqQ8iS7ZLnPIvExnL+UfOUg5SIsJL4nTOX"
                        "UD5gSzXoKyMtJrLMxAywAdkgViIbs0va2s5kFKknrWJ/+ITBfiKA2eqPRKYQSoNPy8xk3HhCOl3v"
                        "HfPMZIorh3L1QbFMNYx8zuM1BDQZ+oxxoomTsd1qff/9dP/ddr1eNDTfvXrogx9dAPy733tkep25"
                        "vKSPfb75L7+x/IVff/Gx5060k+l6zcCp2RzWWmbuBz/mIg9dCQxjYC1W6wZ8BdjZ3lq+7nXm0fvN"
                        "Wx+efuPbbvjI5+hH/sLzs+ltRAz0t57h4crlbtVPmmnjzj1GOLkY1CCMc83smRe6nqczch/3wsB9"
                        "Q+sbTs3QD8E+GiJLBAozVswsq39qRZgZbnYfu3vew8WHE2U6mIGEQNSeghLZFAH2GYy7p1yjRiKh"
                        "jIkKZJRzhWh4rJnMuGXIZ5m0t7nHbTZGc4ZD+k8LgnHWJPNf9bnT2pgJUYEx3gV+osOOkdoQ/bMB"
                        "BxHFSXd1g2FlixSnrOfBEoXes8ZqEloHceDfX5WZiOKjERSDfaCTd7BIkkkI31WjrGYgn/w6cfLB"
                        "XkXZ+WpF0kzAajQPAB3OSfeHRNdSBOSPVSAw0AKX3vsmms+vLs9128enjz05+czji0OHt/aGM//r"
                        "X//aL/7a6rNfni5XR4GtyWwK/1VhaweZGXLHZDD7Q37YGLNeXppNdu+9a/3mB6Zvf2T25ge27r15"
                        "OHZsD3wF26t/84tgOzVmNfDEYH3PHdSYvqPGgG0ASEiNHtYCs6efG4Ap+XfdmZi25+vT1x/CIAf8"
                        "E2BCQgsXKsUCZIi7HnvLxh8ASX6eNLPPDWl488iogqmVr4anZDSQjMvGumzMirLxUdGir+iuIRpk"
                        "fDwkZ43CRrHehpKFbBmslNRKmlkOOGArSIxFn4fFaQBOSuLkG1ra3Mfhuk/WLlfLFenaMCeVmFSt"
                        "b1CNpOERRzCk3dFAnjDs/lHW7O7sA6Y2wBzPrMeXtZv/jTcxZMTR0JX3vGXLzHbmx8+cX5/+J//p"
                        "6pXVbKs58mM/8ULXN8Ct7dTMpoYxWDuEM0wsERM1ZNhadP0wMQ2xy/Ww3bk//P39H/quU3ffuDh1"
                        "YgXsYn21Wy1Xl421POEbHn+qA6Zs2TIfnq/vvmOKbkHG+DU+rxElPsgQ256efcECM7eex7D90F93"
                        "xF53nNH3IYOPKSqYQTQQSwbrNRYrBoxEK9S6b1PQH8/KZbSSm9osxzxC/FbcuGqhQTo/rkwTM1KT"
                        "It2OhLhAiADQxqVSEaoMNCKgjkTZNxCy4vK+cC4UJMzt4zUpKakY92GN5Jw0E46Ip+tUmQioWG3J"
                        "CfwDDAqjMD/dwBJx3Kxs2opbIuT4uJuzSKupoVy8i9xu3IS9SevXwermnLxP0LHFl8UP+GDa3Obo"
                        "lrFNhK6zD9x97Ja7b/tPv/rUL/z63gc+dvbLZw+1k1PdCmSOzreILTPbwWNSQ4YJrWW77lcYlsAV"
                        "wvLUidnV5XVDPyNY5mY+vfyjv+/Uww89O1zcW12yDDLUGJqbBhPT7e7Ov/q1FTBhi77rr7/R3nz9"
                        "FF1vMK0mRPJ9zKvOvPhqDzQMv8OlH9Ynj9LJw53t1qAW7n3S7AsAIObK12qdNN1qslxbsZFsoFFV"
                        "XTWslKW0/CKUlKOElLsU0cOPIo32x5jd03MUpDm/yy3OQHE4/A+yx8TrCW6Horti07WlXKgCH9Rr"
                        "7oddkGGO7HEl4wGnBRngdB+WGwZsRMi1sV7yO+tL0Tszh9UlUVwGXioi6YGxohzv63yS8jBixwlX"
                        "ySyGBtKUTOdH4iofjqpYt1taNlT/7Quvsgw2pvzyLgAGTNNc2Tn2fT/69Bee3AOfAh2azFoeWtDA"
                        "6IfBeD3ZAdyAsF6ugQsGyxtOLu67y77lgek3fv3p3cWx/+F//hrTjUTcr9f33kQ3ndjrzl8iPmqa"
                        "Dn5+iMEwbfPCS/Tci03bHAIZ5tXrbrGnjg3DiqgB2FQVwsymaa7sNS9fYFBYtiaAuzPXDUe2B94D"
                        "NX7mC+EbxZKNJHsHmq6bDKjZWdnFsgGRLFFUk67u0JHElvTa5pI5/BhZGUypvmOuOVTUh/6TEvGD"
                        "4Bq5JNMgDmL6lw5Sxtiv2lf28WRypU1HKfZVy5jLHBBhBQoEZx8C0pDmwH1ZqYKs6u/M+UPGU9Nk"
                        "Kedl01nMCjz7Q92ydp14SSgez5zpg/Fn4EmyXAxwm/spk/qAhp5RKF0LG92pRgSN4bOvmrMvnprO"
                        "bjbcAis7GFDPxIYmzKbvBmuXTTMzTcN84a1vuPKNb9l6+xu2Hrp7+6brh+3mCo5e/jv/eGe1nsxm"
                        "GKhlvvSG+9pTJ4Z+r6Wm193GzJjNn3wW5y9vm6mBIaC7+1aaTfdWu9SQBczYkM60zYVL9txFQ22D"
                        "sE8C6M9ch3ay7FiAt9tGjwILp+TcrLxp9lZYdRMypnJKQ6HbgzvPhiKklInmoTCymbgx63GAJqno"
                        "1BtMrSW2NTby0w8HshQCffx3o9EyJzsKUu8ONTbDNM/ugVwjOpSadE+9qxoySobkVi3hW7WiTOE/"
                        "izCgdvnS0cqm3sO3G2OMCFtUrFzUwmTncoihUNw2oWG/zQNkrTgeys4rE1H1z82Wmv0Yq7AhzmYl"
                        "7S95YbNp255attwxDbBuqpL79RrYBfbOHO/vvfe6rzzFr1yc3HPLzs/93dtvPPUi1hd5tdeth0U3"
                        "TPmW3/y0ZRwHGuIBWL79DTPT7DAbRue2OLFftusxnT/xNHUwEyKwAVb33jkFlqCwHUGBINmbzhZo"
                        "pi++Slf3DE3agS3BGrJAf9PpBjQwLHhQuFrmDRByiVdb+O2tcWdvWHVMhjD+2u1mDE5kgaaYLUrq"
                        "VEltGDSVADz8LCfUHdX85UFVTeK1XKEQOKy2+ZB3GWAy3u8Ei41zlY3a/DE4IcxxiKdJFsk0UA1/"
                        "15gefLwgovQjFBLtr2VrXNX9KJ75qRWR/Fl2ktTRjAbop+vo5QlPUykuA3Q2yKfBUS6ChorMnEVA"
                        "eeO0qpYDJpOsRSg9jyFKpJZUJZVxpbVN6IkbJmMHsrxoWrJ2b4uee+heftsbp1//6PY7Hj7K85u+"
                        "9Qe/aocT73jjcOPxlxevniUzaUFkJpP59NLu1hefuApqmXtmOtTuvvH+k+h3iUg+VupMlwHwkcef"
                        "HIAtQ2QtJubKPXceQ79DpuIAcgFs0UzOvozOTif+NWbnUetbbmiBPddv4UUc1+Nygr68kSPQgLxn"
                        "NubqLvoBTYPwbB3jZCpVluDwS9L1WucaShORnLAsVpS9K1PaSWYMtc7Ng2DWemFIuRmkcvlhtVAo"
                        "aW7GJZn2wg+UI7PSwvWDVZFL6bLLKHe6Vzk7SCnk9CmiGJftO30jaC+htqFkuFrnH5UbnQ2J5dXt"
                        "QK5ktjiWLqqdMUZ2Q9mcistWqtpLEy8TTdb9gOEKcPX6Q+vtY4eeffnwLded/ad/9fSbHlgf216j"
                        "v4jJlX/9S7vPvQhg551vnLBZoJkbM9BgB4vpfOsrX8UzL1jTToCh75d33dTfcxsPK4bDLcIpYJpm"
                        "uZw+/sxVwvUADQOfPGZvv9mgW+noX+tKRtM+9xID24Z5IMAbQH/T9VMM6xAXJW9R/B0AgkgdcZah"
                        "q7tsQY2vdNAEnF07SD9mPSWeXxIs0nOS41G8ahOm2/2zYzQ1CBir6XzB+JfSoV2A1RJkNYhINJTl"
                        "+5R+jFwjETPJFgfEQ9XSunfAMhfFNfrbSBG4lgVpAT5QWnMqlruSBKzAToBc9AjjZ+laDi4qMRG1"
                        "/c0MDMLG+FjPbNDDQSLLPkpR8HBDybqjJIJoRpy3zgaGebhw++mr73q0eecj7Xvfdeu/+UX+if/r"
                        "mbe/oX3f2xfrC8+vLk+s5fnxkx/65N6aj193ePfNr5/T8nILJouhMdQzzWaf+2p/dbU1nbXEYF4+"
                        "+LrZmRN9t2eNaZj8NCGBBrKTSfP8OTx11pqGmsGshtUtp2c3n2qGYU3uvIR0ThBgH3moB0+fe8EC"
                        "M4CYYdhYdLOmP3Nyil7268lnUJltQwDIxs2esqoM0a25ekXG/vIuUW4VG1M9Ae4tv7jSMtbFOquN"
                        "nQCjW5SO0zRrD8rIwO01KUckDIJ/lwlIHSFr1ONT1nPHI4xhxJhFG4AMWikox2k+V1EY0PiVaIz7"
                        "i1yvdgezZdjwao7d5B7Fk3VUnGmfOZc8xVZ6lx1Vm+ViMIgiRQetWclOtU5NjLKEKkHjycUxwTfH"
                        "rINkjxHE+xpL0Rw3DZbr1fd96+7f/HM3nD561ZgrMK9+7GOXAfOuN29zd9ny1JhZ2ywuXpp8+FMr"
                        "APfetnf3rYeG5ZIwgZtApKXF9sc/B+CwgYVpgNWjD7XNZLWy7D56GzhgtgNNJ489NbxyoW2n7l5/"
                        "722To0e6YafuHgD8pJYxQz959vkFMLEgggXsMNhjWzhzXQPuXEYHN+4RAO4789V9g5Et0+zsAZga"
                        "cufGA+kIJUU3Y8tY8cHyqbGyIahpIlmAQPoR5sxKAwM2Mx72/4yan4Z7ZUQInMSGqkE5kHWhUPMW"
                        "PYv9amNsNBWcNM66VjzkXS8bEnIIIQWjlZKNkqqPZB5e1BQ8FaN+JmeQH9Ymdi/xUf46SBTQdql/"
                        "uxc4hXa4EsXEuK1r0Upr2KCBksgBA1kWl0s6A9qJvfj7f/fshlNPLl65Ot2ef/nssU9+fuvY9vCe"
                        "N01p3RFNYId2q338S+bxrxlg/cgD7ZHtxeqKNQ0TG2JujLlwafvjn92FmbsJ8wnxGx+cYLhsTINs"
                        "o4Bt0E6/8JVhzdMtM1ieAIv775yaZtlZ04SZ0lIUgKhpryzoxVcaNFMLwB0h0POJ43TdcWBwC/EG"
                        "kI8KSoZzm529KWfGBdDlnR44AuWQWe7UKk0tan+PcsrfEGJKaxlDzWXoLJtTEIk1cYTRXC1GRFMp"
                        "QUMqSxKzxoWO656BoEAND9909FT0fWVtA6VnbRBfimGC+y90vI+4m9FE2Vh2sRCMw/7pjGYcEmo/"
                        "Vw8aIuM2B2byVDMkURNO7aiUMrmFx40xDeIKC8pqB0+trKZgs3xFqlTZ27cJTbOg45Xc991dNw+P"
                        "3NcOFxeEWTM//KGPdS/u2jff337dHdyvB2PA6Giy9eHPdrvrSYPFu940B18kMu64Mgab2eyps8PT"
                        "L9hp2wLoenvDCfvA7RNedY3TMhH54S0BHbrpF57YASbMDZMx1N971xS2N+yG+nFlNvYgE2NoTXP+"
                        "Mr96mUzTGPavl2IYrjvOh7YsD31DBtyAid37JaqPDPx/SFTh/MNcvsqAYZCPd+lgv4waI1qtDxTK"
                        "Lhvr1oxIWeR6LZ9xWBkvMx8Z0xIacFPlPIuVOlwW1bQe3E43HjPUlKYNHCJouDrodvxzJrUmKL6z"
                        "QYEMqPwAsajKzqaq2Bms2OzSgSENQFSTtXgXauZ94Cu7Ey2Sx6WJOgNjphYqVM4wG8ufVencj4N/"
                        "j/Pg1Q5WGGAyhvudd71letPpzg6WzLBebf/Sh9ZA++630nx7bxgYYEPcr4/8xmdWwNEzx7tHHgCv"
                        "12HV2FpmzNtPf4mvLKfGgA3Zobv3Trr5eh76ruhoblra2Z0+8dQS1DJgbX9o0t19Wwu7osZD5wq7"
                        "bgTRNi+/OrmyS62RORED2BtOmVk7DIMFCOFthLwHq8ojZrbg5sqOy8G1pkdQTCaauyIdqsNKGWL0"
                        "U8bEFFt6qdh26TIjBEf5TAdoFSLVBJ9RS6s45FjRg+5E1UTW+mgQ2Bwf9i2+L+KFkLo0CKpiVx2q"
                        "9vW3UIeYjdvMmT5VBxoFpCxa8eE9YOIQwsd40PwXdlbJt1J0JMrsIIvdB+yPTLrfTi8Wkd1dbRra"
                        "+5Z3ToivdphNZvTlr9Fvfm6YN+tveFOLbk2mAXM7mTx/fvKZJwDgvtfZO06j80fdgTEAA9sjH//s"
                        "GpgDDDLA8o0PNrPt1ZC+CuPsuG3bF161Tz/fUNMw932/PH1yfcuZFdYduaSoGFQiM9igoafPYmc1"
                        "CW5ogAawN59pTDswGobVqhYaRKRPPtNGRQQezNVdG74RXUlUpZGXdiKhQX5klasApLTeMoK4B636"
                        "XbV55mjVaVvaaKXFhIJgfP1IoauyTQpoZj8fVCXNI7Fk6Klirir0b2iCQi8a/QwA9+W4zWgia2kk"
                        "CkQ3DiHc9c0+yDkTL2MjmgtAIGJ4m2X33dooTjhhJu9sSnbMixLi3SwZZozpnnhtseY1P7hfYYIx"
                        "xF3X3XHD+u0Ps93bMWzM/OhvfBLnLrf33Na84W7Y5RXQ1FpLs9kXvzx58dxRwL79ka35fDG47wAC"
                        "DNMYc+ni5FOP7cFMrdsuiL1H75uBlwYmic6MwQKNeer57vwON4aAAcPqtpv45LGu790p+9DDbV0s"
                        "M4ieOrvLIDLWEjUYGAawt984gemYmJgMBvj9UA6uGeZwiBAxyH2znkHMZGENA2xx+apFMZ+iXSjr"
                        "kWqezu3fe86moZ82trKC+CeQLDZV0RaR2KfcJUCvp7vi0IDJSKU0TXiKEI/89SvviC6G4E0yvwGi"
                        "PG4qUpGfqlaxX5IuHaoMXn7Mlw44N/VBHi/SwSDKfs2TUpIBWL24UJVBR41SVM7gTKChqrmhOEKU"
                        "3KA4CrMxus8qSUBzVRKsJsn/VqVqykAe+yxZblo77L7rzXTLzRg6GILlox/8xJJp8ugbuutO7g2d"
                        "W362mBz/rc/urOyh7enwDW/ehl0ZM/Uo1VI7bb96Fk8+a9t2CtDQd8cPL15/7wzrZfmtT4ZFO33i"
                        "KQy2NcYlw72778BsurB2vfELW8xYYaBnzu4Cjf8EDpgZhO62GyewnYdw/ijkkMlpAPfA4FyPLdzu"
                        "F/cfA01DXU9XdwG0FnJmVl2fY39WezMMMq+to8sI4n+MzxCF3xIOFA8+0SZPVRNhzYy9BuVHwBNi"
                        "5MlxA179OeByrZkQcim0lpvlmIOXRfvRhqRudLzfTLfefzUgl/WKaj6KkZ1NkeU0HXG9bowZ6xXh"
                        "n5nDm+hWz2SNANGKCFSf+KxIt1nwajl4OKO0lJQzs46GyGxw8Vu+viF73rKZbOG5lycf/TyD7Xvf"
                        "PAMtBmrB66bBcnn4I59m4NC9t/Rvuh92NTTUkBkAgEGzQ59+wl5ZTZvGGNv0/fLWm/j2m/aG9cLl"
                        "4ygLgdgCW1/6KgGHmAbAALtfd1cLe5XsZoUQ0Pfr5msv9MCcLBuQtQYDtifDLTe0sB3CCXNu8RbE"
                        "MCCyZBgw8LPpBLiVI3fu+0Bku3W7szCENjw7quoxlWrNZ/rPjEScaEPaLk13X8qhGjJzK3nOkATC"
                        "SrdKqMnE7pg5VbWRFQXEmJmpFjrHnt1MGQGLVH3chU4j0WEsaYx1Q7jqQi/rY/MK9VWYLqwhNxfd"
                        "rlO9prkBAekraRNxQk2Dao2qMrJVQTYEbs2bpqazR8l2VSeaQsZY0ZbXf8vou9XN13Vf/8jWsLfL"
                        "DJpvfeRzwzMvTM6cGt7xcIPlEg1Zi3ZmvvTk+gtPABjeeD+uP8n9wGALZ+HowFuf/MIOMCN3HDKv"
                        "Xn/X5Nih3aFnCss9ruGBYYiWy/njT/fABENjMbTG3nNbi2HFFJah4yQjO4jgEvOkmVzaaV56iWFo"
                        "gLUYQOiZjx4azlwPHgZyiBBWchEGthaWDXPDTJZhGW5wCCZyYYva3Z52lg2I0hPoK12WWVQtt6lu"
                        "AsD7uGXW9aXxbMhDJdms511fu+U5Kcr+3WK3kUCaEQkjURkJRjpaCansMibVcdwteoHJf3bERYDM"
                        "aDdosqo3GlnHCPGR9EJvHU1syAxBAvjTRAO32j/HulaiUmhdjxnznDPGQ0YtGwDqH0XIiCFysxIz"
                        "TjKyNfOK1qNfJRsrY63vG/TVLac9S4Ztv/e2h+nmG7q+Y6ADZh/8yMJi65H7mjtv4WE5NNwAPc22"
                        "P/jxvVd2twhX3/ZwC9plBsEQiEDGYHdv9vkvNcBha9dMAFYP3weivWzR2sWedmJevdw89yKDtsBm"
                        "6Ifjh+1dtwJ9R8YbOkgZvYdGTJabdn723PTF863xU/MWxHZYHz/KJ45a21ti9JYGRsfDYNlaa7m3"
                        "PDB3FkvLA9gSeqCH6dCsTdMbw6Zpe8vdqoN7C7Gm46z7KC2jPVXAnGvqzaxC6dJjJU3wHnbVeCa9"
                        "rafmOBoSxlpj7Qb2DMHIoC8KQnBvtgcjTBgu4/JYWBxptNCBHD/kg61ykszbdZOF9iXYxYfGmNOq"
                        "qZHahEHKeKHphD6wxjjNbtAOQcVBXUGEPaAZoWajG67Q+Oi7jFCb2UjvMkADLHD+296z1dDlwc5M"
                        "07366tZvfnIJ2G96m5lM91ZMjTt1oTvy/o8sGMdOHHr1ra8/gvXCEFkMRLBMk9n2V1+kJ58naqfM"
                        "tscwb3be+OAM/ZqMO5IUzB5oMVuabj191rx8Yda0UxDbHrfd0Nx0Ct2aLTH38Bs8HSZjyGjc2oG2"
                        "6YVzuLRom+mULBNZEGCXp07ixImmGbaBKdCBWncmlouocAM9GFi3odRY5mHglW3sQF1PjW2/du7o"
                        "1eXKGAaaMZ0fTLf16yNAoLLRfKyVkkJpivs9UbkhDI4l05LJKnUiQ3E/ZoZACXDfiGSWtwv98mJF"
                        "5IPrv/Q+5aeA3umuh4Q6FlwTACl76yCer/zZqTsGpjJ0bnhc6rha5I9ILgOB74PQkL+s0axuPT3f"
                        "o4Lkx/SwOdxsoPAaChG6fjh1dHjnG7d4eQFkJvPZJz/dPfbs8tBW/w2PHuPVBdsQmKatefYlfPax"
                        "HrC33zS87pZ2WLiDYgZmwxaYtl/6Sn/u6lY7ncMO/bC86UR/z62H+kVvLcA2HKxOBFg7sDn0xFf6"
                        "RT+dTJkawnp46J7DJ6+f4vIc7cSHGGpg3GDNBIzV2AHm2OGzrwzsXqYerHGbVGjY2jry+adO71yx"
                        "fdfuLbvdPd5dYG/Ji6Vdrni5xmLB6+Wwt+z31lgtseyGxcp2a7NcYdXD9nR5b+/q+joyFpawz4lY"
                        "eTlgMPrtl4OFMw4p1uGK+AZMmIfJ8667KPaejhkjffFyKOfyX7ElAgbfyX43ErL8zg68+i9lEmNw"
                        "W7jCZikWhHEtuh+DOH4woV7NUec9a3/Lot3GZsrAsSmHoOiwEGhGYUgZxTRluUYUPvnM+bOBhyyK"
                        "xZ7Mwp+rFS7sP8RLyVbAcJkMxgLxmLYLVpkZxhjuV+94ZHLXzcNqwdb2k+boBz6xt+4nb7hz+Lrb"
                        "1uu9BYH6ft1uzz/xOJ29sAUMD99vjh6+vL68Ns2sIYBgaU2z6z/3RG95a2IswNzxGx7cuvPOGRZb"
                        "rZnDEAiwDdiAYNcNza7//FPnGIcAw5aI+iMnj3/xyUMXz9nV2u6tmr093lvYnRXtruzeXrdc0nLF"
                        "u8t+sTJDd/ULT1EzPQE7gBhsrLVmMv+tz1x97/c+2Q2d7dvBms5NtqvJFI+w4NBWE/rIvQUJcAui"
                        "1lm3vL3xWkuGqrJslHXTuHFWZio2PKKuy/DF/bZuwYrdPADcplYEmsjiVHBM8iP4ZEgrUwoxDbuA"
                        "5a6Tn3x0613ex4lCDGKAQTAgch8YCQs/ohDZVnIgxxnHNwzXjcTtBnCYogyuqlUrSD9YfWG9GhCz"
                        "CtkP4UelhnycGEJ4fIHZZ/84Vq2UUjtj6W7s+r6mqf8MJ/zmsUxloQOloWooJwJRA1z5tvduTw/1"
                        "fUetwbo/9MFPXgSm735Hc/xmgyvbmGxh6HHdLR/55KXBHm9o9b5332WO7tDSDGjWTH1Hi475pTO/"
                        "9dlXCVveWg2ZrZv/3X/pX3312HJl9xa0uzB7S7u7wN5yWCyG5eKVTz0xm7THBhrIop0c/+l/e/mn"
                        "/vUrvaU1Y+idA7TBbWbhx9Tx3tC0mblD8sgBLaBddNdZHDNk0DSmtRMCCAYGcLuu3CEKAxn/hgbL"
                        "SNVpyV20rG0gA84H0XbWU6yOuBojJXlaphcwbkLSodovUHcNb9U+/nAIxD4px62FwR3qaEOPFYhA"
                        "BJtqSQARUQNFJ40GCEwA4WsvzE3qvpztxsj0qZrbNMqO/AMAWnBseox6Gb8CBQ2FIj7Kmt8wpq3y"
                        "XRZ5xdTryz2SMJN/2iuwTOG3llrzEOKJfjaPc9ds3IGOFW6dkn/7Y4roPJEtAjAM9uihyV133PPc"
                        "iy9cuDyBtZ97cvvzX1kbmu31Wz/z75YXLm31vVmtp1fWu//u/aB22xD99L/f+Y+/fOHi1dVyzas1"
                        "LxZYrWd73TPnLh9rJrNhGJho0k7+068uf/6Xd4BZUCAFXONCT4N2OmnWbCcEMPqr3RHgsIGhBhPj"
                        "j+Qzbi3JfznMCA4Gu8lTApgxAGgYoLUhw5ZBHbN1uxcH0wHEloDeDR3DyXxMwTcYLpzJu+t5bs8B"
                        "kSg20XLdI6o5eKyDqneFBwEB+vXpDcTDGNBrLMQsClNHmXwOCskLthpAyZbRGFqRuJIQKjfQJ76f"
                        "spr8FueqypWpoiq4up50Bk2m358FuSr0yCoAXFstNgHaJOlFk9XXNyCsTSVYKcF9OApulbegWX6E"
                        "gjMzVOxFy5asIJsNyysi1EbOmclDetHE2MeFDwivkkdSrhiYTNanj12y3d6qw9Atd1ZbvTnV8JS7"
                        "Kx0W4ZUXAoxpjlAzBZuhWwDrEHcAWGBG1DST1u3JDFnBGBMG2MnciuPAbYfwCR/OZJU+nAsFVXA4"
                        "2j04VZi+zbSRzQwwu9dssqkHT0maPrg+vcEknuY/8R6RvnpTL+NqLA2nGSvhMDPIDfa/cYDiwoxe"
                        "MiIiiXqSuU3mdIq+OIJ+UIpV9uDc2RFh5bkQsKJoyoOEQthMwM1QtxiHMQBreT5v8oA1pspCcUmM"
                        "CD+SWD7GxMGNaeRe/N5TMHQuzwk6SMBS4oDIxMG+u75fwNKiVcw32WAdTm7gPMy9hlA1xhWz7XuA"
                        "GjR9ww2BYZi48TM/TCA3n9pi6JktCNQY9yTgXmbqiVuQs3qShaZgNAEHxaYpVPT4MVNamZykjvai"
                        "qm1Ucv6GdMZhjUqVauodU6OuELmtdc4YKKjcpYg9/lvkKgq9IMp0FADI69kcaBqqBQXyb63JyM6k"
                        "KJOZh+p5J7LzkgjWJgQDTfkmVvLyv0Z5KcF8RT6OHsLQW0M8ZszmTasetgIOD6K74OelnVQGg+Uw"
                        "tUxHG3JX3nY83jvqOgySNjOvm0MAz5Kzcxw7lgFyorU6RKSWKEWzlLZxbVso0pJhZmKYdmINLNiw"
                        "GQDDbBhD/Hipi+oOUjloM7jxmg+khIZFhylTgo9AhsIgJGZ4oLDwXDMUkLkrOYgotqMfCG4n2kja"
                        "kh/7qDcMCsZQf1k2jxJihdEYJS1XAMjmaIj8/CmSLIIYG/U8VNIWVRZLWUZwhfdFlW6eiAvD1XqF"
                        "YqRZn0ncjLkAN5Ay+ruEooJ6oXzhzwTKJhsAVhlFahPVypttVIkEqAnHQG/fQ12o+NOGHxy+MhLm"
                        "xpXIxKrn0yi8wcJYKDPihhb36giIwrbgcpKlyrgKzAith2mauKZDYLLezkywTXJCkSjQcmQeAIPj"
                        "awseiYXWkkweZWck0SFWrOlBzSY6NmTt1i2gy3iJOaHLtR1DdTDL8eTz0u7r9VUIkIu6PvOm9wU3"
                        "EK9bsk6LG0sZBzPnkgFBqOauZ3O4DLAb7gWAI5UzMBt6PtQMOEvSCSmDD39HtCWZnjIYRUTMQ2i3"
                        "iWaQTMwlKs7wteLTELEzF5OS2JQSxuBP2UMkMoWiW6n2aBoK81K1OelFjSQzmUusl4mjGQ7Vikg6"
                        "zmrZDclv/7i/AXJ77BJtl0JnnRoq1kp6GqJfNXJDM+SCaM4lMmilBYvb36sy1dVZC5QolFqF0ba4"
                        "IO5+yzlTGa2SPfk3+1E8WzS90RT3LaUd+lYqXGurqxik+FF5t9ouAGYZ6JUzQbpavpata4rD6iuo"
                        "2flGrrSl2fDfJsWO2ZJjwTWpvxsoQ6R9yjjdfe5qyfdtJSOoNZVp/+C8ZTXLnLDv4wdsmhVSle0M"
                        "cGiHvf4FduzfaL1TKsGFKu8DsfpXqvnZKe0Ywu4mTg7cfaxei2VmgXWVWDBucWUGHtf/NVuUlyXo"
                        "f99IfcAopv38mlja8CJXGTs0VxzcWYYazvqqDIRq18aetJX21gEpOBDtpkP2UfIG0yIiuA+pBtb1"
                        "9JsIxrFJxTeNTw1Ur4/pbuwWVGB6rZpNAlBJRE1gQfrY3dnAT5lYUBunUJjFiHV8X3m4hQKTZ/kt"
                        "oZZO8ERPA6X2W04K6GhVypVG2LqtxI+dFMVpT5aGXSJ1cxkcQmLSsnvfXM5W8iMLcu9TsyFKP9ed"
                        "jIb0j7w3HRmlHKjfJYpJUmBIIftGLJ0ysyaQKjDywLx5L0v18bF2q0+FCjI08+O+jJnwp1s6RMiZ"
                        "HrJQ+O4U3GSCV7IlcgeUC4T109xEcvIgiWmXYYHjV/WazXrQ3I7gBu89ZuQ2tBhUzB6W32hA2qNZ"
                        "KesIf9XrJZ2xymMAvowg2f0QqnIrLHnOWN0QkTNJM8Bc+lJGYXMTcktzmLE99pQuYyJDDcQUKVL/"
                        "ZmqkANM8a+GiKXmJ0aAEWFrq4m41TJTCbhA964Wq+HJ4UdnWWE9lhleylxnSBgvft8WScvVx5Sas"
                        "k32oXzcYCvGO2f3nHsmE1by5MByZyjjXfipNbLZPaWOzHkiGhCOkfMBywXispYzi5o4Ziy8lnbGL"
                        "KEywrLOv6+r7WeXXAOiyx7U16x8Z8QM3VHGY3yaHVbJ6Skk1kZhvQcmDJWWjgrZSPkngLBJrz5tT"
                        "T9Ti8r7l4DW5mMfRIE7+PQjB0gjHOD9I3+3bYgnHhFUdm5D7v7tezcSSbJBRCAkSWYI/4HCwNPuy"
                        "wmadpKEDLfNA8YWjmMAddCQ1csmojDGHkchSfVZYGQtzY7fGiihoo6Gw7Ntied0Bub2WglANNPmn"
                        "CDbs5YsjoCKw6u45gFxiSQiTFPkIYnNnO1sca0ieje+msd6J4VphuJk3BtT3RINC3JmTHM46psAq"
                        "dJKTp0g6KAgVhhVyTS2DprMQmnO/UUM0qVpJa8oqcH3HzOYskoWzzQBh7E/dZSUDY9T27bLSILU1"
                        "1ii47QuDWzrMEnbo39jLCJ2rkLfyLPbnbbmRFpFORwiPJMP7sRxQSsrp4JrC3JS7mCOsNMPsg07H"
                        "tPmaC6el2soGfqTygZ3Z/Yh/bm66tGaKc6WxYw/I5LWUfdLUayoVozHhhOPYsD/Sc8yNJT9TtoBT"
                        "AVklBxGGJNd1L+wjw4EgGHPq59UaG1oZgwnXknuugewBxgejFZQ2SP0LqDdtEYFwZKNKbCQQs4YF"
                        "oQuSbLEZ0BxEuiLmev6N+juhK3/qpzbE/s1YaYzviFBGamoVbNbCa+j4DW1Vr+9bn5QVlp2tu3mz"
                        "UCXz2SMK49BmIteqhPRxAE14pywJ6Cn2pPCfz95latXwp4xH1nJWP9uxcRDOxzNcjGjXGlkysjrE"
                        "ZL3524lZObsjXX8QUkqxxOmHIcofG/7UHaT7S/9AmnIyY6PxHhxz1bGIFslwOA/LmV0ImW4cYQKW"
                        "djXdi3Fk/eGiNuz9tzJa0a1mqM8POpLxpu5m8XzmuOSUa3Pf3h0ROL4HWypKNVThXAu1uSHy7Nfa"
                        "L6JqFrIpiO1PFoqrgskreWmMiD82pooooDRYAYJ27JUuuJ4nEMjKOg/zhgAh2wWBOA9S0YmT2hgK"
                        "iV8PKMBqnkuv38afaZIvdaLO7HY13QpmXO7MTFQHVn23VG8m8pibbcjEVTr7EhT2Sl/jYiQY/KjE"
                        "BG6lr6mYQdGWUqwzJHHbjH+rExX5EaLmx1sdUbNZ5DIBhFvuKySc7Q7XFlbJGwLCSA9SSMYFFQ6q"
                        "TGTcqv+ilksi+pnSejZ0swi1wYBKMCJGEGPKSEPeezn9//2GIdJu0E+wwkyTqpXy2Q2U9ytRw2M7"
                        "gHwcSZrRIT7RWBDZOZJG6JrJBC+P4cIiyMYbzG6qLQfpuWz5ax8FqfGgk0GMzOGzzi15KH/v+6du"
                        "azORsQo1WeRuhl+EWuI4IxkrQfGZrxXM6wfBzGqXr8sr+7zUUdLPuLKsD/DzQgpbaRey2C+yV1W0"
                        "STtGKYxppfkSnqRazt48iGatH0kYHccsmfwS9Vkt2Up1l4j2zXUbWtlQeHRTSYVP+R3b4tx3q6Y5"
                        "pueDsFfQ5KTB/x95/x1uSVHtAcO/VdW9w8mTI8MQBQQRQREUUC9KliCKKCCI4RoRURQxIIh6MSfM"
                        "AQMYwAgoKqJiACVJECTDMEyeOXPS3ru7q9b3R4WuDvsM977f8z7f83ztcejdXV21atWKVatWkY2Q"
                        "Mj9smhjkDBwOVtghV1UJ5oLZX/wwt92C3/WD/r86Yqui2LZhj5dkU6hoS+Vn4fBq4dmr8s/7GXEU"
                        "ONRVnIdvSw9rqY/cNDb3Nxur/Dg7umbX6OHRn/2uKrNTvls5J4wo+AAuQBbO3rEfMDPcmXGGWoJd"
                        "l9Y0YGaHAttu2C/TgrtnB4o3XKvI8iZbvQ2ZV12nGwEAOohbM28LJb3w8p9s04CvGwkdth+C9FRk"
                        "B7PdRmcHxMSaescn355NVITZPc/btSjrI7Oc1A4HIv84ANimww/QIgBoMx3AnoZqfBNnJArWAqR8"
                        "3WFnjfh2aPQf5lLRVOKQ4fpSxrB9DUd17sNQ0Jhns6n02gEtKQ9f4Sz1oEBj9fLIX/agcgpGOXzr"
                        "HlXnFkp2X9iFfpK0IoP86hCVfLrS0JRuqoKy0k3hBAUQkFNFaud2zuwtusJhBKgAaxRyuufVVdV4"
                        "zidFLHO4CSCUVqEVU6w2l9ZuqrXGvii23k9YbPMq1F+VIx7F27z6ARB0fJtbr/vWbTnf4FY4amNy"
                        "jyjgUEfrNlekSQNj7V/P62zFUGgHBzZymYoK1keJ+C0oNh66IBDrJCNZMUE60ExcKh+krKtFF5WU"
                        "vzXhA/iJXHqtwrhY3UlERVFZcxXV+Lbl0VMf2VmEoOXzHNj+ldj35VP/aqut+5wdCgplZjHBt9lB"
                        "r59CPgrVlfeuauVgqKVmB97ZhtXnABAVm/TaNb+ZpQ8VczFHUKn7NmjeCIiC2Z93LERNqT/9sFn7"
                        "3Blo9ZHlRSO2DEmlnm0A4JnEf1ISi9u0tlwK/9xMD5rLidrtHCJymerZiBqzMGLHiwCbJYh91bYi"
                        "ySDWOt/W73M253Dk1gq7BA8MDQJYAjY1DjPKgQ6OuRh2S72nhEBbBk3lY0EUxl0BWhtVVzYZXGf9"
                        "Txg8WAFufyLoed/TvUo1I+eQypBZnBQGkUMJv63LWYjF/j+VD+2/ZS4o2rM52xZMntwr8sTppTO4"
                        "mOO0jxYv49+TZ9hQFQt9rPsaNnxq/gcCMjMAUL6X0CyjBEt5vp9e4FFITNUmXWxg/iAo6baMgZ0t"
                        "gKq4De1b9zDEXQ2CCugAGxOFSIMoCNoo2NiKUrAkRiVpakEjFVV3TXOAqUEyayG1yedJNg+S+8TP"
                        "FDMIKvBSvSUFT1mh9nUgEAASLLQwm91dDgS/esdgQS5Y1Zv6gTBjc1oBDJm6ANE8bsD6eAZF5phl"
                        "d/gpYIMHbSWhCMjXhFwv2FmH2hOMkRxuFTQP/mEDQDDy3oo3DGLrMeBBCGGI0G6iJhBZW5SZWRi8"
                        "WKza9KNm9ZG1yfdYsKeqnE9EJu0OkaQgH0Q+Xeus1uBdgApnEJmfAn48wHkBYtYIDBDrsPhdkIAn"
                        "AbJV+jqZjaVLxGaQ3FoymwOHLFEIsGYIspvndEm1+PNDHRHWXIHt4oWaJhIIMmdVzYtt2hz9WvE/"
                        "w5tA8fuVfUMhHAXNay4iyyt+b0C4L6uXoUZygjC3o3J3w+WI88KKUONGhSalQ5b55qkIZQJpDVI9"
                        "AEkJRfBT2LIhI+3N5tCvrjWXCrRZwDKIJJARRUmioXt9UERCxDLiYhh5kd7hyd4hzxJvSiSzLgOJ"
                        "y87hP+TiTUmyhw8p+JACIq5WhWIT4U3tuJe6U20uBJIqLVbVW/jEZyPxU7bhkypU4bcCECRkFBNJ"
                        "1lkt8MWekMiUhiofFvuUr34oCmHjIpDVb6uY18GHvhIuflVqRQOaRFNKCWijvLTWIftUhUWtuRQU"
                        "YyNkhCC4rcS1dlmdUq+32nzrxYaqmLGtW5ewX7WhLrKWprPQSn0rwY3cPSnPEdqmQwYNTdlKbaWf"
                        "tcZdoYBV870ddxkaHhzTNryIc0HMEIIeX7VlYmtCsq1ZUY6U8hU25z01b5U4xcdCyDTrLF40sGjh"
                        "qPNoLFyWyohXr94yvpWYBPUPrSBPFEF3CE1W0yt3GJozZ45WWvic0OalK0j5kSqcf2x8cDi7w6h3"
                        "EOnClC7l9g8Atm6QEGBoZmExmNsZYDB0cAiQ6SO5BnN8WiAFW1jZGho+x4TwqXjdE//O0akhU+F+"
                        "OHuFidknys5FvcE4M7KUZ6Z74xPT41tnABJyJIpIaxszGOqkcLyHBtWOKxfDOL/OxS7JYu8ZGVQQ"
                        "wVgfFh63+OCsZosxZwHZquy3HlEWO8TW3HZanVzP7XCbcuzi9XK/QdujzAQYmeoNtIcfW7V508YO"
                        "kTSEW/EcyxwUcmJohALObM/hraCu8sQ3V2XwEhdv0xDzhc2Md0Fg+YZKbXi4uXAMvZeRHj6fxYGd"
                        "dCvMn5GZSibvKRRmZI3B7CDJYUYFxWF/iIrJV0iqXu+bX3vfC16wT5YpKWUAMJRSUSR//4dbjjjs"
                        "A6C2dXH7zk/l7XhZYP916/tEWmVy/lx1/fUX777bCl2JwFRKxXF0yqkf+cH3/9FsDSudAeS845pL"
                        "kDB75gFAaE57y5ZGf/7zJ7ZbvkArJpFX7hmmDjOBCIIXXm5epqzr8glHr5xKVVcsfC6q94JW8FZp"
                        "waiwxalYgxcK/v+FXrjOBO0UQciPJPJiGWBmpbgzM7N588S99z3+q1/deMXlN23dirjZ1irz+fWL"
                        "SKA0SZ625/yb/vkFQWFwKWrQy36BMoDLH8DlbKGQZgtSNRfoQYWhimP7v4JJmjfAhVoKKKEsSxuN"
                        "5t//9u8TTvwgUeEAoSLuTH7deqMhKJaDyQEVEMGdOViQTaGRVTKaqj9LN2GZCsy5FAkj3fMTGfu5"
                        "oEZOObLO9Y+TcY74CpP8gVHiDiWyWYJDEcDsvi30pBivvE2RTIBiGE+tlDIEAKJIaM2Hvug5b3/H"
                        "sZ/+5C9a7XlZlvWvreAsW5Fq+usIU4pmL3nyogvfusfuO2SZiqIQnwBICABCAkAKK7ItoLUXG5/U"
                        "2BXU7GWr3v72N223fHGWKRlFIUsL6l+L04oeKyHZl/DHDB83Gt73ra0WbPdhqQZm63/Wy1UPU10B"
                        "T955haEnJNy/xZpMPVKgMToyOjqyww7LjzziwP9+w4NnvO4jt9+6IY7HNKd9wh00gyWBhAymQfrB"
                        "Wyhg4BLeLDRPAs/bzbcVPizJotwGKE+2u9JVyRncEUEr1Wg077zzkRNf8YG1a7qN5ohSOhAlocum"
                        "/TJOXkfZgykIrKJcMyYYh7tHvDvlS1bMurKcqnUeTU3lrhppHaSXKUyz1TliHpr8SQl1bhoLga1H"
                        "par8olgdoLl8CTtWuipfVW6YlVIAtNbMrLX9Yxd+rZS66MOvffZ+K7udLVLKWep33afwBu4/Usa9"
                        "7sajjtr7DW88Pk1TIci3ZRCco9TKc20nvEsEyTWusxAi6U7vued2b3j9S5XSQhDrvsYgc+Gv9mG/"
                        "v7DkU/+qXyU1sDlg+oJqPJ66Ost9DHiInTHlsRf82UsplWVpmnb3fubO1179qac/fUmWdUxYv6GN"
                        "Ej61exrAyf267P+0ZtbsuSEUIv4mbMeDp9lTpulKoU6tGebG48l/6OnZNs0AJ0kqpbzrrkeOOubc"
                        "J1erRmtYKzOBVZAj7mfOMR6wWRjBowKBAeX9p5L08LWVZFbYSkl+IRdhCJ8HddonBevXfBLCGfzB"
                        "wOcGusa6KzwPJvVQvPoZh76sAaMCTAmeGuYgb8cVEFH4E4IAGhhoff3r54yORFqzXXSpu/oJCAAk"
                        "WKXJ/HnxZz7zTgKEy1rn0OhvAuFtfdf+utvNaxiGhJ686MLXDY+0zcpDqSMFYOpelR7+v/bXD7C+"
                        "oJK1+2avsIpbwyqevyoPIYSQMo7iVi9NFi+e98UvvSWKesyROeC2CKcxgbT5GoWq/ncdn+VtGeby"
                        "k/InbG5Co6y+JCmlG434vvsef+mx5z7xeKfZaulMITity/WXgqV8Y6nWxJF4/yCw60rCSIRvQxkU"
                        "fA6q8w23dYUSKpSb1h0Oj1E00OeywJmR2hkXHEhh+MTyVQnKjGB1wwo4j2qnwaoyK8QOM6viWSC6"
                        "IrDYdymv35BBRSaEj4QQaZrs/cxdL7749DTZACF10FAfI8vfwxzBRmiobP3FH3n9Lrtsp5QSsuxl"
                        "WCGVG4zEmhwF1lRO3pDTmoRIOuPHHL3vcccfrLJMShHW+f8/V43l+b+4HMEBjSjOMvWCQ/Y5+ODd"
                        "s3S6Zu8kM0zEmf35v2/m/wpf/bdEIOKAEz3XhLaJ+VypLIrkA/evPurodz/6SKc1MKwUQBHZ8Jrc"
                        "P2CrL8MWdcBoZanEXBBJlM9iUyhQ+plLs3e8KgcCQSn80rDHEBmBVSxaa9WX5FxNgZLF678LC1n4"
                        "wFyUxP2JsoBZh6kSZMaStrKcXaNVbBXlI6IoyrL0zW854aXHPiud2RQH4mZ2DrG4E1Ha3XT00c86"
                        "8/VHZ1mXZM3ed6dbyt+WEO0pL/gKnKUjI7j4Y280aKCaDv3/1vV/lyqzXv9nWVCtx/Dki160JzAt"
                        "RFQipwr1/z8RlP9PL++GAmUmql5KaSmjxx7bcOxx5z380HSrPUdlpcXxGqfPeJb+cXgTlik4uDl7"
                        "heIiR1St/PUSLVTMYZ0069x8qR74SHf7ff4NvA0GgEubPBB+QSgsq5ufRBBOEnvgADdbDeQrPE/R"
                        "YqwlXD+tEcyGMKrCo6Y2YSJKvvD5d916y1vWrk1k3GDNPry19mJrhAqVZQsWRZ/73DlSklJRgIpq"
                        "Q3DwUPhbuwMZAC4JdiGiXmfzm9953J577pBlSkrBfSqvB7Lq93vwi6BVXwW7GBHq5z7tFOqsEGTR"
                        "ywheuWjKsrFZApZrBsI3mcMZXrNKNwKww8olyEMFi+9QUil94LILLz4XUA2EtUgL41AqZTgA4X8h"
                        "oLMsjaJ49ZObjz3+3ffeu77dHstUAlAlIrrQELudZI53PPNQ6JEFkiifpgw8hrp+1DZZUNpmeQC1"
                        "c9mhYeRuKRSUCDKOkjvMJI/8JAKzKMavGztQOCfWfK6dE+frLTIY2Zm5EKwSOW7T+KfiZfsCzZRH"
                        "LvnJzSodV+lACEpVtmLFoi994SytJ8ANl++M/LRCAUJXvxBSZxs+dvEbd9xxWZpqISQBTMKEh6MI"
                        "pAVIwJm4QpjVIyIQaWIz9wooE8MshEizdPvt577zna/QmoVdC8ztr1lQ5Dsr3F/xEsW/mlfhu/47"
                        "7M3Q6bo6Rb/mRKFyQSQIzOXjP4MmqDzivs5iVYVLqQxQfdAiAAwPD3qmKXJdIGerPFmsx6CnFoA+"
                        "cJkXs+PfXjBU4o7FqqVkU0wpFUVi46bJE04471+3r2kPjqVKezLz8JfmfGDn7yjgX/9WmykJP4dj"
                        "FtrZkrUsVmj9NBRdBH9ftbzITeHaKIFAIJQcIMMUheAG10gYh5XrANckeeEa9r8okgt9CG1F01WL"
                        "nCCsh2ya8Kp/V1gE7Ucx9m1BEbJBS0XrB+XramtEUZalxx5/0NvfesznvvDrxuB8zhJm4c3GAngA"
                        "s4hl1O1ueOlxz33tmUepLJUycm/76HzXtQBWH/FohZljHjOakU7Xv+vdb1qwYE6aqigSJczMevH0"
                        "zMzkdK8RxWDNDGlDDdjSf24FERPys6P92BhfhEiDhoba7aasii2GJgilMDk5pXRpBjNP5+EtVeG3"
                        "njiNaDY1tpuNgYEmF1NowMKrOp2k0+3atOLsSdNEKpED1Cp/BrPWw0MDrVabWQN9qajVaqJe7j8l"
                        "BzDLsq2TU2BBpKDdnvOc8RwWc31sPTsKllN8OXLYZiGYmQRNT3bnzR9qN1vstmD1U1FKaSnl5i3T"
                        "xx//vn/c/ER7YFGWJk996oCcz2hgqUwo+1hxawdV5ZHrih2/6jFaIdG6h4ZFnbybdSN9PoLGGXOU"
                        "G+WmIIe7cPzUWqmu0AUgRxlVgzYXsVzUEt7Sp9yBg//EY4YqfqJ3d32JstPhZhQLtW7DxiYpIqWy"
                        "iz/6hj//7V+337ax2RrSKgtm93L5C0BQlGXdZcsGv/TFc8BMkM5vmqWF/HME2Q440AY+q4+QKumN"
                        "77vfyjPPPEYrJWVNzc7sKl9mxmFqsnPYS96wYQNE1GJAUkROx2itLXtAm1QQ2iw+gtwB4GAmZhZC"
                        "qnTrT392wQHPfaZWLEpgsATpiYmJww5992OrpxpxFM6eejowh8fnnOHRQYhko9PZ9Pa3H/n+8//b"
                        "+Lxh9VmWRVF81ZW/PeddXx0YGNU2FIQL7r8QhhGkPY1dgzAwoM9/36mnnXaEUkrKalYiBuCel6WA"
                        "V8HuRRnDBu2rV2/4r0PfPjMdR5Gw2xrBgqTTyXYHpZuF4pD62SZocg2QAKSpQQqSUTQ+vuHYo57x"
                        "pa98QLMqWhLlS2ktpdiyZeqEY9/9lxsfbQ0tyJJeaDGF1k2Jjzz9+Gmfkkh0g1ngGw5CQ8lMCBK5"
                        "4Huz9ZzqXPgCJC5FVeG4EyqXR8U/M7+t6A+WeI0myPlIlKA2ugtOrVG+aGpP1zB5kIsA2AK53vM7"
                        "DNwNnLkeQAyimtk4/y9K7FHqdS7PaVZpBQAkCIoGh9pf/+q5hxz8rkQxkWBkgAggtGsoQoheMvmJ"
                        "S969fNn8LMtCrujXjOmBAExEq9uP6vbHskm0oM2sgmYCuhdf9IZ2q6lUIqjhWNTPL7AQQmtFQqC4"
                        "y4eIMqUXLZp/0itfev77vk7RSlZpMOejHTsyQo0BBgm35RmAAGki5mw6SxRQS4UMkGbxxJqZ9esS"
                        "Esw63OTozOkANDiry/yWEas0mZxIK7hir8M6KW3Y0BMy1To439yjgXwcgQCYWAspVDZ+/vu/ctxx"
                        "B42MDHkGC4caXtBZ+yaIaTSGhheIgYwtsgCefKLb6SLoLArb/TxWnVkZ/Fu8XP4SgEXU0Mmm5xyw"
                        "4hOfOq/VajKrWZSg0loKbNkyffzL3vunGx9sDS5O064I0sb1811g53MQGCKBS2QimhkuFpTrjHp2"
                        "O+hhXVYmb/v2s+/ILHgaLLE0GtI7lKV5dyJCPv3Nbi0tF/zBpDuxECjIAYRDlc8xOZlS6InTpoXV"
                        "hDrjy+O0Xpqwi5L35qi/7+8WFUXyU5npCS4pZZol++672/s/8PLzzrus2VqqFRc22AEEElHc62w4"
                        "+eQDT37Vi7PAGSx1rXR5g7FkrOUfuiVOKUSvO3nM0fscdvj+SqVCxKU+MqPXy+6//4FnPGMP1uXd"
                        "IQCMLDvr7Sf96Ic33PPvKdlqsfIYC1QCWNjtbwCYhIA/+okJECCRcmwCNcJVXQR2PoHiWBKJOCZm"
                        "6UYzt6S8heq1octhwELKbiatjVTSNe6JFIIIjYbQ2jQaliQuGLbWLSEa685Mbx2fMgKrBHN+b8GB"
                        "NxmCxsHFVG6li4iazaiXRpEkGGzZdRoOZEFYobMKHSqYHW878zqOGzNTW5+5z6Jf/eIj8+YPK6WF"
                        "kFXjw9SutZZEk5O9l7/yvX+64YHW4GKVKtFnt3ZZuztWCn+GZR1StRDGW80/D7x1928xO6a/uOjo"
                        "UR5TSgAJkQPTb/6nSNXk/zESr2hDkht8216gyXKDhexWeHfV4apA5YVVgm2aPESoE9VVRMxW1f9O"
                        "ZCGScZZl7zzn5IMP2a3XXRfF0kWru9EVyNLukqUDn7jkTcyqXy79/uBsw3MkYqWzdjv70AWvBeA2"
                        "tPj5Y9ZaEdE//nHf8Secs3bdeFVaASBAax4cbJ/33lNUtlVrMCvjDBbC/bUJpDb/klKsldZaK6W1"
                        "tuHXzlqoB9b8o7X2k6NsL7i/8DF8Qe1jyb1D1XegfB32E1sJI4fS3DBrpTUrZiaSBcumWqmVIFXT"
                        "AUBhaaj/RQYG7fvrNlFonaM6RIiD3D03/yptLOWZqfGn7Tb8859dtHDB3CxLhahf6zDdJEKnm73q"
                        "VR+4/rf3tgYXpFkCAnE+RxCK5n48UvO8aHwE/9ryKMgRdtPwVXcyt05DbnUSo7CPB0VPM6+67C95"
                        "cJjDQ0Sc6aXdqp8mt4aV2xl29aFcaVgJM7u4L7+GqPIGC/ZX9cqDUYsV1t4jbIi5sH2giOJtXEQk"
                        "SDTixqWXnjM2J0pVjwS5mDqloUkIlW361P+8ZdnyRUorH3m4Ta+Ty2wpQMJLexirl1hGIks2nX76"
                        "4fvuu0eWKSnCRVgAIJDW+pJLfvDwQxOf+vQPyJ1hWbqklEqpl738RQc+f/esN1mFM1BrFkAws9bW"
                        "wPf5W2x8bC2yABBYEQRImm2bNUjQ7P9s5U5qW9XN9XaBASCSURTFURTJOJKxlLEU5i8SIpZCRiIy"
                        "RaSMhGjEURSTzJSGNF0uE703FuBYsUAh3oLoA5U1lKzjCJDJQWU2pkAQRClogfM4L3J/eUPMYLCU"
                        "jaQztfPOA7/6xf9sv/3iLEuljEPwihVqErrbVa86+fyrr7651V6SZalg8ntzKv1lx01hLzx3FzHD"
                        "xiTOwzVRYB/tFspMR/xyoZ8jqrEkvEgygqVkxJQusht1lQtEZ3OTS313FYbHtpHPbubGG5DXEpqa"
                        "IRAlE9ThqOwKuY8Kz90APyUR4z8pPy9jod/nNQ9JUJZlT99jp4997L9Vb1yKmEBCSCJEMu51Np38"
                        "yoNOPuXQLOtJEVXhnF04WgKqL6IJMkvU/Pmj73nPScxplfmVYiHlNdf87dpr7mi2dv3ql3995533"
                        "R1FUK7OYEUfy/Pe9SogOOHLHW3nODEGuoTbMbqL4V9b98b2r6XKVcJ110a/mXJx1Op0sWz0ztaE3"
                        "vbk7vak7vbE3vbE7vak7vak3vbk3s6k3vak7vbEztbE7tak3vbkzvSXrPb7vftstWDCX+04dlNaU"
                        "SqD6CLz+fafABGAyPOwZqoYgKwxif7IWMkqSyaWL6Rc/++guuy5N014grcqYNF9lSrzmNRf8/Be3"
                        "tNvLsywzq2T5MlalXYNw712W+Ktk41S/DQnDSQDyQilsLqTDWswHYqvmVeXD3Kyp1hZx1YFkIirM"
                        "tlK+Bt/P1czRGiZgdW/Km7bhdF1Qs33YT8qUQN+G6T6r3COC1rq6P0PKKMuy/37jsX/8w+0/+vHf"
                        "W+2FSmUkGlnS2X7l6Cc/9TZmRRTXab9tcEiuwO2/hcJCyCRZf9773rD99kuyNJVRuSoS1On2PnLh"
                        "90HDIlKTk+rDF37nyp98pLZFKYXK1BGHP/fww/e+9tr7mq1RrZWzO4N5IKLSv+7GuIP1HbKE5ydn"
                        "/DpRn6vaInI5hwAn7gGRlJKhn7XfDu8974w4Gsq0Is2erzwVGUcQgACRIAaWLBo7+eSXxHGkWZdI"
                        "2vWrAJiX1zkHurlgrjgmri74mswhCeHuGRJulqquIQQSTUiZJN2x0d5VV31yjz13SNMkihr9EGiA"
                        "UUq89vSLfvKTv7cGl2ZZSkKARc1hFQGsXhTAesHsB6E44vlNUb2Fkq4sAcKelqjIP/SrcLUFioAW"
                        "/LaSN4BA2+cpksksEcJudyP3QQCur9T0PJ//CkVS2GRwoq/jWLOyABKCGcpliCt3IHhIDmsFbMxu"
                        "0FTNWl9hkiTdTndkdIi1Ds0EU1yQYOZPf/btN/3jP6tWTUaNFhBrXvO5z16wdOnCotHuGmAmoTds"
                        "mJg/f8TMbXGJJS30ZgsRB5oczCwl0mRmn2fu9JY3H6+1FrK0nk1aKRnJ7377N/+45b5ma3mSpHFz"
                        "zs9//vfrrvvH4Yc/txoWYNFM9P73v+YP15+t9CiIqY//VbZ2NFuvp0/qBSKifBqIPcNURXZoUBfp"
                        "j13i4apqBZzCe86+ez5n3z1rYZ798s1ReZqPALis9myMAn9wniPvCP167urwOzRAyvXQJdhiDv1C"
                        "trPsRaeMWcg41d2Roc5VP/7Icw98eppmUdQIfZHw0lqDNSN67esu+v4Prm+2VyRpMstEXdCd6v7T"
                        "6v4z36hx99hNs+S1BRxkUUt2RyFq/TMiggA0quY/W1/PAhNaML7O0EsLWjd0o5ldiK2FjnyHSx0L"
                        "MQIHNHuLt1rMWZU2qDesM6/Y6ueykVmk4FktqVmvOsJjAl3woS+tXz8OQtWjIiGU0kuXzP3yl98h"
                        "MBmJVtJZd+aZhx177MFZlklZcAaJoLQiIa6+5q9f+9qPiCKVVQYp722VhcwryXr6/PNf2WzGJmFp"
                        "8a0igS1bJi/5xBUkFjASE6ms1eCHP/z9JM1E3ZKWlFJl2QEH7HX88QelyUYSkmEy7RRyqhSMiwBc"
                        "1vkCeP+LXHn2tFXygKpXqPz6echwiMqyLMtU+Je6vyzLsixL08JflmW1PnJ4dbtJyS0qeCvWh9pG"
                        "AGYRYYGgmc3WdIWlUDprya2X/+CDLzp03zRNZN1GVA8eoEhG//2mT3zvsj8MtJcrlYlgcnN2bNfV"
                        "Vv+VwUCdd+YfCE8p2xhi46TVtW4wzbPownJGz1I5FuGkrPmvF3j+Ycmcc+56X+lefCKIpJurC2a2"
                        "7K3wNmdthTklbevikiteBMQ/16zjRvyXv/znne/4LJGoo28tpUzT7hGH73/W246fmX50110Xfvyj"
                        "b9RKmTxyVDSbiGh8fPotb/l0pysBMGu21omFvEL5he5IKdPe+Iv+a7fjjj9IVWwlImidCSG/8uUr"
                        "H37kybgVa02A1Fo1WyM33XTv5T/4jZBSVVUZKTOU573v1JFRobMMbkDD2ZZQYBU1WxWFBbgMbFUk"
                        "e5qr03Mh/ZDHZD/iJ6IoiqJI9vmLqm9NarMcCTVeJK9fv8nQfUlSW7TAwlWwusPehBNGvnQlDMhp"
                        "62D+DqyJzao+6Q2XXfbeo45+bpqmURT3n2llZhYifstbP/2Nr/+mPbAsVRmBBUToOs2O7RI2+r1F"
                        "2e8rwMAMZnI7QFAtVqrWbbnNMR+W4jwSM4e8VlZW5SZzwVMwEJNzqUpeng+kNKCXDc6idAQRE2kQ"
                        "I889ZL1Jhxo4lVRoBYECKev//ldx5MoynHM2JQBz5iz8wRXXfOfbV8dxpFRqs3MHxaVsaq0/fNGZ"
                        "++y16KIPnzpv/pjWLFycDuxqC7RSQsh3vfsLjz/2+ODQMAAiYXyGfCtGYYaOzck6AIGJoZXmuJle"
                        "fNGZUkZc1uykWQkRPfH4+s9+/qdCjrFKiYWpmZmFGP7Yx364dXxaiupuXhJSKqX22mvH01/zkiwd"
                        "lzIigEiT0KXCNcS3DR3BoS1RUowhzZT6XhzNfsp8tqs0O9Dv2xrLETB0eMft9wOSKqxLRDCJr4P0"
                        "SkFtAQSOuGpatw6hCY+wN76kOThbpRu/+bV3v/wV/5Wmic9PW3MxMysp5TvP+cKXv/SrVmtxmiWG"
                        "sWr7W1tF8PdU8VwqZlyuKoEQhTjmwsojQ3AOZ6gR88q5BpiShe6dklKxflMbhVqcUvWyrPaTgDo9"
                        "aWllwoCcd0rFvpYxEQahBHLtf3v1Mend9EOS9YhGzzrrs7fd+p8oipRWwRSPMx9Ag0ONa6/7wvEn"
                        "HKy1lpEMRT8glUplFH3nsl998xu/J5rfS6ZnAahiKjJDSxFlyYaTX3Xwcw/YS6nqVBRrDSHkJz71"
                        "vfXrOnE8wFqwTSBJWusoHrz//o2f//yPhRBK98pdBQshmfU573z14kVDWZqQCFHDbOOzdABhgL26"
                        "ZD5FFJFwnn5uRxS1dInayhX+3339//WlFQuBrVunrr76dhKjWmcVifYUDXmg6BI+lYsAEiRkM+2t"
                        "/9xn//u01x6eplkUxbN8orSSMj7v/K9+5tNXDQwsy7Ry2T1mc6XL7Vq5WWNtIRAQhb0ErkBgW/lp"
                        "65yGOSwRxB+Y+hAEMVRNNtRAVL7qaY+AUj6sgsyZ9fuqLVd4q5mZUDTE2ORVmN3Jd7WiQO6z9S/E"
                        "S+AR1g+Su1fMrYmpwTPOuHjLlg4JoSsxR0KQ1rR4ycK40aiKea1VFDXuuPOhd7zjK83WImYN7eyp"
                        "MmaMkmUEksI81iqZv6BxwQfO1KztIkeAHa21FNFddz34zW9dH8XzlGIT+2MYjUCalYzmfv4Lv3j0"
                        "4TWRbOi62cZM6RXbLzzrrJeqbJyEOWzQRph7DVYZQSduKjikAvnndkbJjC/ZLyUF6xdtxP+W70MQ"
                        "i9rY1x96f4YVldJpmoKUEPGHP/ztBx7a0IhbSlczOjjrv9LfcsuuTL4+GERDVGSy7a2kOO0++fGP"
                        "ve5tbz8xTRMpRT1PAsxQKoui+IMXfO3jH72i1V6eZhkDKGYzLwGZOzEF28fDVW3FE2RxSi4k2rwJ"
                        "zvfW1Fwl18+7TbVeHgtRtmFLfeljW9kOhp6dLAIaGlM+m1cIRG5zutTRfk6X2YYh+/6wdzmdM1jw"
                        "JYs2V40fGw5CP5XeT+DmT03UnxCAbg0M33nX2rPf8VkhhMkB7zWDUxRQytogvi0Pw/RU93Wv/djW"
                        "8UhGEvbEKhhfL4TQQsIGvdDaoEZJSWm68W1vPXGHHZZqpSiMb3ZkToSPXHzZ9BSZpUOT6dQCA2JG"
                        "FPHGjTMXXXSZmY+r9lkKobV+85tf/rRdFqVJBxJcR0YhVlE5WbJSoFRB7nQUuKQoUCpjpJx7V2pF"
                        "OxejpLdtOH5/2OD3q/pLCCGliOM4U/z+D37ls5+9utmax6wElbdA+5EKHfmAzFyfjVNWkkqGn4nJ"
                        "pmfJhSlDa2IRiV539fvOf+V73vuqLEmkjInqwybISasLL/zmRR++rD24LFMpI/dTQ5oPb5xdk+89"
                        "KPJymXkdrxk2dLRnKiTk8cNQyHm2xF8MMEiTYAQzVqV+UXk1JszRXK7NI7rylVf5LEpk4Qcy+BhO"
                        "i1ZVcdhSQayaeyJyWxkLvaiI8OrohbKpajuEWqXyzewxD4AZIaXSZnvBZd+9/ktf/FHciLPMsJAP"
                        "szAUX+OBa62llO8779Jbb32w1R7OlAKiPFVLXUeEkCHkQlDam9lp50VvfevLtVaiGIlKIKW1jOSN"
                        "N/7rZz+9KW6OaaVs6mpv1UCTPUNs7uVXXP/Xv9waR7FWZR1IRErrkdHB9573Cq0mQQ0jKUqiv/gJ"
                        "iOpEQvHyAjzghLK9ExYO6zdf9ZkJInPmYNFYICISUgghtE48VsPmTDta682bt3RmulNTM5s3b1m1"
                        "at1tt/77y5de9fznv/3ii34RNecbsR4wT9jL0h6AWbtfaN3NbAZiyIGkpWwmnbVvfcsxF3/kdWmW"
                        "iqhhSKDWb8h0EsfxhRd+90Mf+kartSzNFLM9ZyncM5eDkTsWjhMLmcQ9sFw31BZSz4/Be9cRnxGo"
                        "9E0gDcxgcR6U4EGqHaMy71egremgBwpgFzhKgN2CU9r2zY4oUUn3VduAx4JVAFWXoUi+Bc4JSnLp"
                        "k1p8l1U6Zp9ocwINESAJQqlMNha/+9zv7L33bs8/aO80SyMRoy6+lp0NmGUqiuTPf/rHL3zxp43m"
                        "yixLRRQVrOVtzM0xEZOQWm/54PvfOHfuUJqmJulV0JYx7tSFH/pumrbjlnbAWzveSQoNEEnZ7Tbf"
                        "d/43fve7vX06Gs6T8GgppNbpya86/NIvX/3PW9Y0GkMcYLWKI85TLRTelnDiBFJIzeR/hRUHutcf"
                        "PhpYMUW9CpDWSkh5za/+/MlPX95ujWgNkoDGnLmNj330rduvXJymvVKYpemv1kwkrr36hve//5ut"
                        "5uJO0pnp9KYne51uDxhstBYo7lIwB1IiS9gzXGvThIRGVhkzzvqwy4IhucZxo9t54tRTX/jZz52t"
                        "VCJtnvX6SykVRc1PfOKKD33o643mCsXkEijURJYFOCTXIQ6f14kMAH3lllMgYGZBpWCZ3HZxLbLd"
                        "xhxEJpnGmSk4Q6ykq/pH5BZ6VH7oyYyIopzwDLzQgGCXktFhgRl2mxX76fNCvexAJNexGrgo8P6Y"
                        "c6kfPMnLehzN0p8qUqxfUC9PS3TGrFlE6HQHXv+6j//lL1+dM2+A3Rm6Vcjh8hA9+tiat77tE0LO"
                        "Yeh8EjtvoiR5888FoKBJyKS75fkH7XnyyYdppcKlIttKpmQUXXnlDdffcGeztThTCdlwWwLsPn+Q"
                        "BjNYsMqarbE///nBH//od6ecekSWGY/Dd5KIoBQ1m/F5573qxJd9GBgJThXJ2y3i0Licec/qTGB/"
                        "CXMqpyUSV5bdSdRONPgm2IpasnI3bJcImrWAXLNm4o9/vAeY55xECUzdeccjv7zmkzvusCRLMxnJ"
                        "sA/MDAit+ZTTTli7bvrd514KsYwoFiJutOZCK616giKf49R3OYCK4GR1SP8F0Wb/K8J8xxxMaASI"
                        "ymQUdTtrTzj+ed/85vlEGTgmm6OhzrbKsjiOv/jFH5177pcbze3yhHXk4eE8fZMTLgBgdpHnFhJ7"
                        "8dE/UbLvb/ERs9/iwC7zTV0xTfnSoZXmhgCsRRbEHniWD+QpeeHuOxiYZn2sE4Y5HtRtGzaVOwee"
                        "7Oyub8CpQg5HMU/2yhY1uVgNWcJ/4i8TwTirDreSm4Plqn7KodgtRt3uKvfS2B2WUhnEmWo22/fd"
                        "v/Hd535WiMhNZtV9zay1YtZvfeunVj+ZxvEoa8V2Uoi12iZsmqAN28ZxduFFb4gbsrZDJESnk3z0"
                        "o98HDQNKQLjukABppZXiLKNMk2JWTKlWoJELL/r++JaOlFFV7psd0S996cEHHbRX0ht3wXc5ViuI"
                        "ZbDgsIpahOQ1OCKjgj/iCMk3YiwY69f2xxcBiBqxlMOt9mDcHGw0hxvNgfbA0nvunTz2pe9+YtX6"
                        "KI6y1DgEhV1sQgilsne9+9SvfO09xOslsSRo1dOszIHypS4HpAWY+UenQft2uh4lXPgPIYraSXfd"
                        "i1+y53e/+4Eoshl9uF5aEZjjOP7Wt689++yvtQZWQjZISCEiIc2flFEkpI03E1EkoogiabZ/yziW"
                        "USyiSMSxiCKSkqQUMpIiAmTV23J8XXhiZIrwZ+Gyx4lwn5StUc/vgWkSJqR0FmvRJHRI4mK1dl7b"
                        "qwd/5TUbejPba6yQC9aFOBdPMMPqYq9q/J2qHAlBKZX0oAh/Ti76iiQvg4sSunwVm+trC/j9Jrl5"
                        "TwCRUlmztfjb3/njN791dRzHfWQWKaXjKP70Z350zdV3tNpLMq1Z+nQ8dqsHux4FoHplSDCn9SSb"
                        "Tjrp4Bce8sxUpSRFiE9mVkoJIb79nWtvv/2xRmNQKW1sK2YBsNJpLDut5lQr7rTi6WY83YxmWvHU"
                        "0DA9+MBjn//sN4lqjyYHM0sp3v/+U6Koy6wpP5W4xjd0mqoek+wqZM2eRGGpBEX0lmuggkdU75Ca"
                        "77Vms+KhlY3RT5JuozXn7rsnX/rS96xatSFuyCzNqnE5RDJNO298/XFf/eo5Sq8yaXngSLoEWJGL"
                        "tjFt5yCspVULN4M1WMZRr7vxkIOe/qMfXTw4JFkxyZzRSgjRWmnWn//cD8587QVZ1u7ObE1m1iWd"
                        "9b3Oul5nba+z1t2s63U2dGfW92bW9zobks6G3syGXmdDr7O+19mQzKxPZjYknQ1JZ33S2dDrrO92"
                        "N6Hk2PXpjjchKU/iXthN5d5agMn6yLmfSNaXZxcbkPcurITIGH2agkMe3HMKQSrVYCsBgCATqzfd"
                        "PWTuYyMvyNFltdcGSm+Loup8CUFWvxa864JRVh3OcB/1rF5J6epninkezG0tIrMokkbx4ne982v7"
                        "7bvb3nvvrDJNUoR+pVZZHEc33Xz3hz70vbi5SOmem252+2XzpKm5eM0btgJLKJXNmdP64IfOYGaQ"
                        "KLquzAwhxMaNWy+55AohRkGZq4qEIJX2dt9t7Ic/Or/RlO4UaCKQ3evLiCIbGV/tuZRCqfTQFz/n"
                        "hOMP/PFP/tloz2WFwKAOdwIbTNWsOTok+m4itKe8zvDmvf8iZABXw7ZXRsJmDDfprNNqjd5+x8Yj"
                        "jnjvr3/90e22W5SlWkbCwWD5SkatNEle//pjW+3GmWd+UuuFUkiNzE8J1dYPcD6TUUNrzmPw5Osy"
                        "NzghbDP/xY1Gb3rL8563009/9j9zxgZVxlLKfsFTzCylXLt2w5OrV5/33lMhG2AQhNKZUopdrkSy"
                        "GfXYDLRJCW2e2ydmU5fz1BrN+OFHNvzwipukHHCOYYkl3VDVydAKjHaSx7v5xVFmX79nfy+DPO87"
                        "s4PCOn0l3kMsNVwEhshnHA1OV6dw9orZ5ZTNpUylN6DKvspwpsA81LBcbUmcmcz5C6HKCkWyq6rg"
                        "61YLF3Dt7JnZhRuBAU0g7a0DDSlofKs4/fQLbrjhyyPDLTdVBxCxVkQY3zrzhtd/bGa60WiDlR0Q"
                        "F5WTLxEywFrnCAxwIqJG1tn41nNfvsvO22VZFssopGMGsVYiir7wxR8/9uiGZnOpVj5VLpOItd74"
                        "rnefseeeO87StdpEH8xsZpoAPv/811xz7S3dTADa2Zul2HQiIoayGfZQ9B9CLBKDC/mV/K4LgMzE"
                        "FrPztoJ5UwYHZ1NsWw/lpEwizXrN1ug992w8+sjzr772Y9ttt8CFjAc+CxDFcZpmp55yxOBg+5RX"
                        "XZKkIxQLrTJCvQpkMKBM1i4PU0B4gcdnpxI5oNK8lihq9abH99tvxU+v+ujceYNZpoU5pS2wOqsA"
                        "LFq04OOXnLtNPPyvrr//9Z4rvn8jRXYrDAc9cEhyULtu1hja7hNTxB8mEExg5dUYweSML59gPf8Z"
                        "UFqgvchDVV7uCCsHgTWBtUmVWw5mDe29wneBUxoUqz7xP/2tSTnoYx3MGJanEoqY6nv11QyGX4j7"
                        "dDu88mU7AALEnLXao3fcsfqssz8jZKwDx5C1FjJ61zlfuOuudY32mPcZ2UnrAhgOfgpkvNYM6F53"
                        "ascdF77j7FdonQlRDllmhpDi4Uee/NIXfymjhZpTjx8hKOlMP/vZO5x88kuyTLlLu3/tXymnfokx"
                        "hJCZSp+x986vec0LVW8ijpqhVgwtf7KJSALI+g5B2ETVcaCg8uLkQ5Ef6q4av8DcK5W1WkN33r3l"
                        "6KPf+9ij6+K4kWVpVfBFUZSmnROOf8GPfnh+o7FFZ1pSAy5AyUDoOVCQCC3BsN0CybNXCaEct2wW"
                        "RXHSndjz6XN//ouLFy4ayTIlKueIhLMcQUOslHJ7uvMrzdJsW39m63fwJOv1kixTU9PTZpZ6Fl4o"
                        "sXPlIvfH2yqcJwVDYKY8lctXS0VXtChnHMbMadQEcgGFNYIAFfz2c9OCZsIv6mEXRU+4WlsJgG0W"
                        "szxjvb3ZRR4ZggvW4QlApnqN1tLvfuf6r37153EcJ0mqlEp6iYziK6747Te/+etmc4nSXQqDGCxn"
                        "y74jaQ1YDXCWbvngB149d+6Y1jXmIeuMSHz6U5dv2tSRcew6wmaRWIiJD3/4jGazAXN4oRBCkPvX"
                        "ndU3GwJNdREzv+e9py1cFKdpt5oRzNcQTGiWZTL3n+4JtaVnFU+BpWKzABv8WzdHTZSptDnQuvPO"
                        "jccc+e4HH1wdx01VI7NYRu0kSY459nlXXfWBwdZmnXWFjJyLZHis6HFQGSG1fWQfIGpcHmJBJGXU"
                        "S2Z22XX4Z7+4eNnSOSpTs6RhqNYqpfR7uqW7iaM4qvuTNh1rHEVxHMVxFEsZuT8hJUWRJGKGzRXc"
                        "N3ls0HPU2wHOyva/8zFFYHwhGDUqPdmm/dEPnsJPS3QkTGpUtpt1eXahG9oOQI1lFJh85s9nW9bO"
                        "tgqXk8v76WdpNBTD3rysfk550/2v3C50i1gmcoTBWkXx4ve856t33vVgs9mIoqjZbDzy6Jqzzv5S"
                        "FC1gKNLFaUU7XtKfhRX2Ied/IqKthxyy56tedZhSqRRRCUITjHrvPY9c9p1fR/F8zlIGMWkAUkZp"
                        "Mnn4YXsfccRzsyyVfaZvqwNRLEPGpM+UWrHd4je+4QiVjgvRgJUdVPOJDTsQ9bh0KY/NVTBCEKbV"
                        "hpNNPprMiAkTIV1Xb3jvtlAUSjADQqWq1R65694tx7z0XY8+uiaK4yxLSgKCwHEcp2l2xBHPv/LK"
                        "C5vtiSztSUkslHYilXNFWx/M6a1FDz3grSwQkQYLGSXJ9JJF4qdXXrjzTkuNbYVidfVIrru2yeCz"
                        "1kA2YzjcP8WcyCVgqrUFrwqeU60scwNt3f8AvFDGVXRzRW54jvYNObqCExpuMpdzb7zq34RWccGq"
                        "6ieSK0PiC+dk7b0GB/w2RKQvUAKj6k6yrXabLiGHhYuoBIl469b4jNM/8f0fXPedy679wQ9+98Y3"
                        "fnLDOhZRS+vAGfRNGDwWj6UooYW1Zk4+fOHpcUMCBZIMhJq4+KOXTU3DZG4AwMQg0krHcfcDH3ot"
                        "wCievkt9rn6YhD1ZR7/1LSes2G5umkwLEi50pDgQRZqrQ6Cdt0VxCEIAQvrLa3UfPRXjw38ZNJET"
                        "nlJpc2DOfffOHH3UOQ8/9GQcN5TKqt2PoihNkpcc9twf//iigfZklmaCWuSBCcBgzn/WMrMLyQAR"
                        "CU+ZQibpxJyxzlVXXbjnXiuztFc6FfGpCKnStS1nrXxVCYCInJFM1TLhh/3aqi3swSs+KfuA1Oc4"
                        "D0+3YSMhkYRNMOeTVB6SmpyBsyNllpJl4VUHNzObg5vcTxTnQep7ODtUOfpc+TDoseYTN9HEXMM2"
                        "Smdxa/j229efesqnzjj9s6ec8onf/fYB2RrKdNaHhwnIc28Gkxu5Ibd508ajX/qCQw5+lsqUEHFp"
                        "H6k5+PNvf73zxz/5S9xYpLQ/sE8IKdJ0/WmnHfrc/ffI0kxIIM9eMsvFwR+CGwhiVnrhornnvucE"
                        "pTYKSRQcgOQ8CIMZXamKQ5QKB4f5suLdMzu/L9Qp3m2sTAPXDJbXU8WuAXYkSKWdVmvknn9PHnXU"
                        "OY88vCaKGlnmh8lDq2UjSpPkyCP3/8UvPzI6Mq2SaWlWPIq6s7K/N8ReQKXuBD+YYyKz7shgcuWP"
                        "P3rAAXukaU/Ggqk2MqY6KNt8VUU7V6Cq4o0BRFIiWLmug8e9cwM/e0pF1DHjUxes/bSpM6wKFXJh"
                        "IagAQ57JzCfo6qcNZpHEpcbMgFIxGth9S0TGCSVmE3damGkrtZL3s09vfWE24sfuDFBKlXfPstZa"
                        "aWU33LkkGJXuCICVihvtZmuh+Ws0h0hpWZT0ttF8Gc/slGZWrBWrTKlMK6VYQym9ZMnoBR94o4FJ"
                        "K6WV2yeexxnxhRdelqYDJKycByBBWdobGmq899xXKaU0Q2daKdbKnnHl5t0Ll1ZaKzbFlGKllLI3"
                        "mjUbZyZNs9Nfc9Qee6zodqakEAGfWh4gCK2gbFVmUt+2qN19eMhKkaD9v9r42mzj+Nie2mLcFXso"
                        "lh93MLNmKK3cRm6jgHRgknO+L9qQB2SmkmZr9L7/TB99zHtWrVofRVGWZVrb7ttztzIWUvZ6vRe9"
                        "6Dk/+/n/jIx0k+5MJFvwR5cTAEkUM7M97kz7vrsTxezxZ5LtnC+TEGk6E4vp7333ghcdum+32yMR"
                        "qcyiztNdiEA3KNoNjfIDpHU+Xo5gORhKv9ISjqn/JF+BMRfbxRMBEngKE0nm4K66/Snly+un0FwK"
                        "lCgFCiOov056UB6QkPuDBSMx0CVGrAQ53euEaCgOUJRltSXNPK4Hze6IzKMwdOBEMIrhIVzjJwfG"
                        "Zz4NbK0jmA0rDmxXgAAeGGxKKarJzk2IkozIn4BEvsJii/YMvByzdlT8T/fWzmY0GnFti2Zr5oUf"
                        "fvuCxfMA1JygDggpfvrzP1332zsajaVK9Qg2bIcE6WTre9932s67bof8mPX/x5eEBOI4+tjH3/iy"
                        "Ey7WECSUmyzwZk/aHmzV9wgAMDzSlpFz9Ys+oPmvmxOFVUjWmiWAzdx2FEVCiEajchRIswmgPdg0"
                        "gJjChq7Iji/gjC8iIgil0kZ77N//njj2peddfc3/LF06v77fUgI45JC9/3jD5172sg88/kRHiIi1"
                        "MoG5AMtIRHGz9luzPjE42HJnRxu6VnPH1He/+5Gjjn4OgFar/tv/ly8zZAPtFph8st9+ha2BU3xo"
                        "aD1nvaJkqIqCwrd9QxP6Fct3X4amD5XnE+xUT+SsdCIya759ZezsIBZ65RnblXCvQsq2t0a1hitW"
                        "ZdcytFeti5HnA0QovDWTEEI077jtkVjKpJcJSczMGsaQV0rHcbR1vAvETufby23Wq8FArSR1T4x+"
                        "jh9+cN0t/7y711UkhNbWeoANTgFJuuc/jwlB1jIRghhSEAlhTju94ILvkRiFUELbGF0ipKmaM2fu"
                        "Xnvu9Jcb7+glypzLbVKmEBFDWVMlOF3Zz4TDoQjmv2RnyZ3XTMw8f97I7ntsd/ddGxutFnxMGgCw"
                        "kO1bb30oy3Sn0xMg4Vu1EQ88M52mPSNMuIwiYgeScw3h9YkzwamxevXkLbf8e3qqG0kppV3mBKCU"
                        "arXi++97gkgSCaKCm+YJ3c/yEjEgOes1B0Zuv2P90Ue995JL/ntgsJUkKSs2HrpwKSggBWueMzp4"
                        "7ntedc653+p1IMjtfCKa6WZ/v+kunbELGzQIJyEEGFEs163dorS1qgVEpqdPPe3IpcvG/vzH26I4"
                        "VjozaBRCCEkAOaplJ2mJc+uwQGDs7Gp2VE3uN+cUTmRNIRh1HeI1wDja7fj22x8ESSAFM/XJ0+nL"
                        "hyKton7+j1fh84rM5KIn6B9WYStX22i93JUG8mRVNbWX4AjFofmpXcCks0fYHTUgmGukpqGGknCt"
                        "wur4zv3jXxVnoDwYREpzwrrHxogk5cQogwU4EnKAOYKJvrGs7vjc/CIBmwSIvCav4iRAjmDugFPA"
                        "WJFam7NjLXETWEEIO9dvudjGJICglBRiQMgYrBz+bVEpSWWTWiVuRonyjbbs/FGLGpfgw/WCyEar"
                        "mOlhdxaOtgkJwCDZbo5lWb767rMDCBIq28rczdNRUmTPE2EwtKA4ioZyjzhXVNoNmRWLJlrYmMBu"
                        "wCJAEHW07rLx0N1GNrIzBmAWjHaFMAphsX7E7RwEayGipDcD9GTEWpvYVwZMoDgIxCQESa1Ve6ip"
                        "VZylEZEP7JRESqtp5tRauDYLgBDCCgUiAWpoLQHJECTSZiObmZomkiAGZ16Ikjnzy9n+nJ/sHgQs"
                        "OV5zzTkxRA4TXhswGGTPAyeykRnGMHRCzRQ2KbQFCSZJ1GYthPA+WuHyzGhdikqRkt31fxBe7Kaw"
                        "/bfhknPFhrKSuc6NYwZYc6sd5QILIHOIeen8rvDL3P8KHAFfrBi4aPYKaGYyA1/AhTUCtXMVaxzS"
                        "sowga6Z6+UVcTmjk3EwCyAaWMYez4MZtBSsw+/k7tj60xyWT2aiqC6517ZDkMJMACa/44GSAQ1Nh"
                        "e4TXCkQE7YQAK/cq6DJYIoIJzDcqOpBnZfwEj2w6aNZ2JtHABjtBZS/Lz74XBOEGFwBDgCAKoDsG"
                        "UUQCLAjB7LIV77oWVzn9MDMRsyRNEHbq2nfAA2liTFDUi0LkxFYceR+/zkJEDMlmL4Kv1hODj0xg"
                        "5QbXQUhsrDFYiglIx8+YgYkVa2I22AGzJhE5KK0jrHPpTM63coe7m2IWXFHFlHervTRhL8mCRmz9"
                        "QttBYR/KYAI2rGhgNgNUk961xNrszl+yHiJzP4EV6IlynG04KMx2B2Wh0aDOsLwTzjUy0WCPQax1"
                        "eyCKii+IKiIphK9aXakPRWw4I9aq2ZI88p9yXZK/YkVFd9p8h0AouAJu6w9pG95pvStLN2RnguF1"
                        "jjOsQjYgq9GsONtG0J0FzEwG21hPtnTvJ9oCTzk3kwlgUmaOjwvpLjxeCWCYc+S1+8bNjLKv0Fuf"
                        "AblYtNjcI8Sava/hbEci7T2lHCV22BUgjddJVkoy22wGkhg+96nT9OUJiNpxdF3QnqGEsw/ICRUQ"
                        "uywshfxrgcdTqDAkHLv3mzRg5je8lAwR42mPciTaIWRi7a2Aov0iAtHKgDZH4AgiQDmPzAaVWlHr"
                        "xstJYkMIJjGp7X3QvAPFiiJDfM4mNmNntxIaI81KJ1eVApEwse22HgbLUt3hFXgknlcLeKkWLmG+"
                        "NOJPxaHj0DAoSpWAx81PIPdsjDwjgKIgDNKNRqVhZmZWdUcz9rmImdifuFl+mc/+lDKFhT1xMFUF"
                        "GQPFWDSrIjgInvZM6Gtm+J4asuCC9+ukVT7LEwBR7V9ROZSnIJw0dT/8caM2J6UNFjdK1paqm2Vg"
                        "M3dtrEXB7ILMrfSz7VbR5IQviKSf/bD8w86AMI06eBzVarJsblZjpEltCjBDFOjYyUfTaxPPV2zd"
                        "UZvZy+YolZkBc6KHhsW3M7zyWnPbh8hY7s6TrkxHBMqZrCXL9vAi67E6E9FJRlPEVCBgBRNB5/zq"
                        "ccvK2puEkKMYIDLHN1qBTnAxEr5aZhZ+eJncHGJ4/KxDT4BU8hzNdj3VTEBaTWJaKuo2K+K4KJst"
                        "oqzDO7sWYTcwZiRcXwolZ7FX+gkEymGx26bhyLfOGAoFpkNG0VxgM5XjscX5dooCBNYZ6QtwoUZj"
                        "UlpYyemePt0OzI3yqkRN9w1s7KBF2SL1MDiYET5xEsquLZZsN9c2wDl31179Bt733SaE8VUWhHIN"
                        "Fh16C0rMyF+28qbmcvVzFSaPTOsDO+PEa8LAntdcIP2g+px6A5uQ4cKa2ZGUY6lKKK8z/bwgKqqm"
                        "MhpdToBc2hpN6VVu7exG+ZWfXrAvXIKDvGwAArM7bJ49MslBV4i6rmqEguFkW7SDZZUCORoI8Geb"
                        "dqxbpSXOzwYP2d1KTA+JFd9eWlVw4gczLFBuKyR+0x3t8h8EqrCKhNnlV9BAbhnUEX7ZfwplT9hT"
                        "R4NOkYbfOH1VgDVAWh/AwoD6AgbLBXxbVOEi30UT/VCyPHMrAbknUgtMH2xaNV7/mTc6OOc9j+cS"
                        "VdWax2HT4ebe0pBU8VZbj4XJDJbts/0iHwUnsj1vhwZQP7u9BFj/MS1oAmZm1mbWL+w9MxNp462U"
                        "aiqJ0H5IqCpIV6wGsbPc98GwlX0hSNZQdVzhm6nS1LYqN2Xg6MTbenYr9VPpckkKF+0OK+PtDyK3"
                        "IGihtdRRxBOKsonziKLC8wIOHXMV2CowMvp1oVpVuZiddq/3Fqsqx5talcq91UNRXavldUCAyI1B"
                        "P/vC7PmwUNrUgFa3+hEtwVFHEF67Vvpm3fegaK6By/CG6pFtCCsBTBR528+pKDCgoQnMLIlDVJZ5"
                        "qbbjvm0nrUoi0SRZyj3B0viV5TIzsRFCJsaEQGYwBUEQtBFTbG1o+LwxTpiXq3UXU36gQN8eOc80"
                        "HxQnoUJOcE/I+M8SMJg0Do+VaOzS+Ydk5Vy/mlWdkhone65U6BtSqVhR8iK0BeGozuRjCPmlYIuZ"
                        "1QxmAmlimXe0xuAt/QynJSpmSEjVBGtxFwAoiq2C/CI7VEqQABNIs9YkyB4c7Qwfs6/OuZCG3cqS"
                        "o6q3wHYawqfctj3R2wganVVqFwRQrYIPcVgS0wjYxw2AldIujszYnAJhAr/afgat9nWRAmjK1lk4"
                        "ZiHQtZ2vFdUFPcC1lbMj6PouEIhEDCKVsUozQAOZq1JCkIwQCdLamMG66r+HwIcGS0l9lYFnBzS7"
                        "gIOCn9hn8ZGgSROkoIgEpxnrxLBu19UoQJGMm0JmrBW0opq1phxFVePFZiVzkr6Wf5yk4BItFKQY"
                        "a0CmLMGpIACZ1M1gq60xltmnJYU1lAPk1F2BHqoa4OVidZ8XqLFkRwQ/XaiaFqBEI2ZqKOoIBiFm"
                        "lKdOwnb7tV6kTy7IHwZRYWXJ1kIoHc9mv2GltUiMYNESDG3ULjPYBK+DNYOUIEhIIq1ZK9KyLgt7"
                        "CDnbiTI7sTWLjR+S0CzSypesRdfsD6sQehQWe8GOxSouYa0NWQK9v0AtPAkKhFMSef39+vBUrNDi"
                        "fYksw6oYIko6GTDdbvaWb6+XL1CjQ0IIkaY8MZk8sU49tlb2OBZiXiuOFaeVRcEcMyWEzA5wP4bU"
                        "QXq/sHvOKYWQUqso6XWBqZEhtf0OeslcGhokIbO0iy0TvSc2ilVrmmkSAUNxq0k6086k7QOSl7ne"
                        "pszjDP2IIBj9sJKC+epVEEGzhJie25gWSkymrVQPgpT1XAzqnSUGYzLmMNjn/aS2e8JV2zyEqo/U"
                        "gLdxwg7ad0ENpqOMVKMpdZcwARoECaZUcIRCd8P6q0Rby5+h3URAYQaanDPHbjE6VMBEpECDzfWt"
                        "aJptooKIEMHnFHNTOlrzTMLdNAZakRyVsQKrKhdUIPe2BZXJuzgYIY/349ZZTJBZrpKBHEgG22Cl"
                        "XWOoIgokETnPIv/ef+Zbqn3Yp1ceHQywSQJVksTkF0y4IMvDm35dDW7g/jWhOmBosBACSZZBbX7O"
                        "3tnxL2w+b5945x3E/FEVRwwSSLOZHtZsbNz1gPjDzfrq6598ZN1A1JgnoMDExfTFJTOqCl6tiK/A"
                        "6bHqx8C7M2DmCFIDSWdqYLBzxPOzF+8fPWev1o7bZWMjFMcElipLOx25fpO471H+y20z1/1p620P"
                        "toD5zWZTcUIQbjHbGhNucD3zePyHAwo/TETk00WVRhY5UTIzCwGVqN1WTn/n43MiTs780JY77m9E"
                        "ceSjuFwbXlUaQPJJiuo4lu4BSTYkSHsMz0IYIc8jlIyBzBIiDwm0/qmIOMmetuPmi87Z/awP3fPE"
                        "piWyIY2BNQu7EpUXsKrF/ECTjRZVPr6lwt4cQEVCyLS7+f1njRz/gmhqskMCgqFJSbNxwublIc1a"
                        "KRqfbN77UHbjP6eu+9vGLTNjjeYotNY29KVm6dnJbuO+V/oYeFIlmv//7hWOOCpj5ygk/GnnB6IS"
                        "iquD5MV/Sdz0g6POdDKitICCAD77FpWUjyiSdfVh8WLHaUxaUCSS7vjyhRvf/+Z5r3hRa87CDiI1"
                        "tYUfWY3pKaGyNI6ygUEsnsvHvXDmuIPEW18x8Jnv6W9c9WQaL5PEQusgSqLeKajte+m+Sujmw7x6"
                        "a/boSES9tCvpiZOObL/5pHkH7plEIz1wZ3oCq9Zh6ySyhEjw2BAtncc7rsiOfL5+26vbV9/Y+tL3"
                        "1/zrgYG4scDMcBFlzIJzq6oe2grq8ht7SkUfWQxjt4KY00hO7rac21F3sNWDO/3JkoqLnCwOHELl"
                        "Wbpx96E7UG8IVPVEnU61TpnrVCjs4D8iItYTJx/VPu7ozb+7oXnpj6ebGMmgwolIHxFdpMbCWDOb"
                        "EJSaYqFiDaOyq0NA5BaGOdlhgd55yfreqNDt4UgrokhKa6qxMBmHhdBMjd4LD+I3niBvu2veJ7+/"
                        "9cd/mJaNBUQAN4Ga/CK+3X4i0/PmNpm9dJXov66PfS/PLIEgK8DoBX39HFZtdaUaZy/pOlAWNEBp"
                        "UEPK27YziBpiDYkbWmsCRCR73c3Pf+bWSy+Yv9eKLWkS/e7PzV/+Kbn9Tv3Yk2Kqx1ojEnqwrXbe"
                        "ng/ZLzrhJdGe28987n3xs58xcvbFq6d4O0G61rB+KvK0H6KCJ3b+FAAYzCqKRK+7fuflW//n3YuO"
                        "eG7abq3fPDl0w1/iG26evuNuPP6kmuoQKxJCDw3xLtvzQfs1jzxk6Jk769efMHH8IXM+8c3kk99/"
                        "DNHyyM6XuLDtCtqrHYKRUGWX0HMYnFy1T4JOSNay1+OIM8EKgIY2U08ISLAWbyWcFNGVb8HzyszL"
                        "wapd5uVFIJrJtx+KP2Z28a4w5wYRIU2weO7kiS8c661/8NXHLPve1Vs62aCZFSQ705VPYoQ3fsBz"
                        "3eOaqpXFzrzNgWcuL5UY6gUzIJMs01F8zV/lJZdNtBuDgpQQICIpBXOqWRNISlq2ON13r+gl+7ee"
                        "vc/6y54+uP/lOO8L65VcRpS5TVEotviUxFBYMqTwqvYKP6m9rzJILQwV+xTFcQRAIIrgphL6KbF+"
                        "vFc1eWphIne4CALaCkpaFRoiodZUQYU0fePhjWDiCL2k+4xdJ77/sSUr5j766OrRj3w9ueLX0zPp"
                        "XGCEhCSZERMzb5lWqzZ0b7hl5utXJhe8afSUozuvPTbN0sG3XrxeN5YIpOgf5k5u72S/tyiya8jA"
                        "ZL0zwzlKyKjXXXfQvjOXfnDhnsue6HSGLv9943NXTNx2dyvDGNCGEC77uNq8kR9f37v+n50vfLd7"
                        "wkv47NeM7r795ovPbuy64+A7Pn7/jN45EhFYMYHgIhutv1/GsHO4aok43BKYE44TCs4iBkgKISNB"
                        "ChDhWlhdc55Xw1XCqnbVEAY0KmYuNeLSrmMGMHNIbszayxaumYEWzkEDWJDQWm1+9VHtnbefmNg8"
                        "uf/uE8cc0Lz8+plmu6W1W4NzoAYwl5Dp/b58nZLgTh0OzUpn7gUV5tPMtlrXETCJOFozTjf/uw0s"
                        "AXouFppcVh8FJID6xs+ndlm6+d2vGzztsPSdpzWm09aHLt0gmwsYGTgyZwPPTqilDiJPj1HmuKKh"
                        "2ld41Vq+1Z9VZJZqzinQKS3h4hXIUaH13RD4L9XLnYRabin8GbBrbRljf8ENwDauEJI+aCJAg0gr"
                        "GhCbP/bOOdsvfPKB9QtOff+Wb/6ymYhdWu2xZgtxnEliIZQQOo5EMx5oNRc9uWn5my6a+fJVzazb"
                        "ec1x0XEvSLLeZG3Alu/XNs3dWoVTRCkBmqVMelsOP3DL5Z+cu+eiNQ+tnn/mx2ZOOX/8H3cvQXN5"
                        "qzXYaCKOlKRMUCaII6EbzVazOW9Lb+HXf9Y+8g0bvnvtWJb2zjhm8qsfGmvywxrBsYOs3faUEvAe"
                        "Lu09phBU99Pl8DPx9oSi0Wkrddnk7e6G3P+ZTbuSkykVL8C0Yra/FEfAHEHgyMZ3x4hT0wQTAaSd"
                        "JVVj6TCIIBjMlKSJmDuQvvLoOO1tVZjDauupx6MZTWRZRAxRN3VNVBl6Mjs1GcGfJ//cAatUxi5U"
                        "OwCevE3LFIHRbEZCNJutZtxoxnEzjptxoxk34rgRxY1GIx5sNIYbjaUPPLn0DRemn7ii1dP8jlPi"
                        "Iw7Mkl6HELEbdzwF98iXqUqxoPvejO3r+oS8b+69uKjYK+WmtwFbIClyIiv5cWEtJUBnaT4omYvC"
                        "EAsGLV5jI2DmWkQEX/XDJgOCpVTpzOHPF/+1TzbdG/rQl6b+8q8FrcGlxNMqy0ySK2aje4UGKaJM"
                        "q6ghuLX8fZ/s/fGOoUZj/DXHN1qyoypOYT911O9y0JJzBwJIAYCFkFl3cp+nbfraBcsXN5/812Nj"
                        "J71r/RXXzo2bT2+2JHE3U8qMtdnCYnCgtVYqk5Q22qOPb9zutedv/sR3RntZ6+RDex95+2DWe5KF"
                        "cEFX5MVuEVQOACSP1fDGFKj8W+y+++2dnWBxzQrKsP4icqrNlXReeT6FnamOCn1XAS4VznvHRrZo"
                        "CKHV5FGH6Gc+bXrdpuFPfScZnxk+6Jmd5+/TUekkhDnnqQx2YKt6W6hGhPkOOtioJO5rcRLUwywA"
                        "SYDUOmItWZO2aR+9pCMNoTQpza1GM25sd+GXpn77z3nDQ1NvP3WoHY0rFozM7oue1byooLFeVPlR"
                        "CLXaLJ+gztQqsXMJqhJJBIwGWA530t3UVtuNatWzPK88sQ6/706J2hFwVMkSmb3RmgJk/t87ZP+h"
                        "5nD6t7vw099ljebCNE0UxzDzOwEjuR1YAppj0l294EuXb6XG8LP3mbdsqciyDC5YxUNY6NhTM7VM"
                        "DGSB8cxmNFJaZXOH13/u/cuXjT320Po5p71v/NYHtmu1l7BOlc2pl3vTyGU/gYQmyrJeFMWiteMH"
                        "v9z5wo9lwumbXqZOeEGSdKchzXiLEMgQvR7hpn/UJy9lnfJgKzrZ+Tw2U0A+sH5qRmv0QY9xBv1h"
                        "Di7K1CybsLG/PEh2E6YJbgoRgqLkco/8fwqGjelqnkchi9rNiVNe1o5k9ve7Bz7z/c5f72wODtFr"
                        "XjYYic2sta5bBXJ2H3uB62W/6RYg4Gei4Jdo4WMgHTBWTwsRplJgn6aCmSAEiQiQxZBQdhUYRUYs"
                        "kGpI4pSXXPr9DTMz7efs2dlvT62SXuROk7OgFomhOrj97A9UKKHfZYRzqdoSq87C2pXmyqZpeABq"
                        "LgWo0iQCEgmfl2wxKk/WwEmrPGBiW6CG4JYdq9JzL5IdXQMaktT2ixUiuv1enagxEhSY95STFuvc"
                        "FWFOlRbUvv3fw5/5zthbL1izYXMjisg4HNtEbu0VCAUPuz3R3vg7LOMs2/TaV4wesNuGTdPzzvpY"
                        "786HlrTbw1mWMBiQ5GYrQjw7C5GhCVoqrQlp1Fp+wedm/nDz0nZz6gNvHlw8d12aaSYvQ3LuqmLV"
                        "AGuGq8SfVXYNwCCY8xwDUzrY/0vO6SsnNnHGF/uwgNzGBtnYbjaGoZFZwqaq81mt2W9mrCI9lwtl"
                        "IebLExhaEGVp97DnyUP2wsSW+Ks/nO7y8iuu7SU9Pny/ZJ+nqSzpCCTl2m21lotcnWRhNrpEe8el"
                        "bIvYWgpeBQC2p7aRmV/TVtwzAEEQgLRxo74H5N4RBEGyJEKmtZTNW+5SD67CnDnZnrvFQCJYgArZ"
                        "MatKdxYhFZZBkQERUHhYWAeR11WGrYVhVngstXgez81FU6xOpdQ3HHJRyAzhje+SfyhMssyK4KxK"
                        "ydmFfUkymp4RCKwlVLOhwTpLyOQbqa5beVKzpqZJLhRla7aOvPPjW35y/YLpXttkQSlOV9cwc604"
                        "q7PFgu4wiCjr6R2Wdl9/fEMI9a1fxdfd3IoH5maZMrgQgmqxioICYwZYSUFph5d84AvrV2+Z94wd"
                        "J153PDhdDyIXVOWKFmHsh9va56XLynzk0zB5rUU7rvxhlboMJOFOb2egVeEpod2ZnGH9thUj2T2w"
                        "Xq8xMwFKNwgTpx4pmwMTv78t/sudUdxYdO2N2e0PRAvmdU96SZOxlRAX3b2yrnW1CSJpU184K4q2"
                        "MRHcj2YI4cKFE45kNW3Ysn1mqN62IjAxE28YJ0g11NZAajND9B+Rfsq4n6Iq/eynNsL+bbPRaiWu"
                        "QE3lYWLivETVwqq1uWaHKWS2oq4p24fbFPBhnSHJlgAjZklIONo8IcF6+XJi7hIkk+Zgn2gR3czs"
                        "dkRTokk2m6OtZoOEyXxWksg6/LAfwCFUwgqewOEyU9giZjV50mEjuyxPH1gz7ytXjAsxj1QKkj7D"
                        "iEGaZ4Iio/rKAWhkaLQatz4weOV1TCJ7+aHxotFeloZdMEYWAgYPl4ZrFE/d0HhPx5r+dkxtlS45"
                        "Uz46QB1twGHBMaSbZy9QeQ6Dfhmy4QAAlI9JREFUS35n8n9WBr2I+UIbzMX31hEjkiqbfs7Tpw/e"
                        "L5ueiS/7WSdVgy1BkzMDP7yGMo6OeUG0cuFUkmXOaqySaMlcqmoFbyGG3fGroh7hhZ4SBSi2xJnX"
                        "hsoAFboOAnMMLZGAkWUMCA4XJisoKov+/vWHD0uGQk1Jn6TW1RbezF55/w7aq5wjjer8WA6u8Ilv"
                        "g3MUF77yNwEcXjOUd8BuU7dv23YFtGCg8bfburqr/mu/6Fm7dnvdTZGMpSIXZo1ABDi+YqPHJEEr"
                        "rTOdUk6R5RbcfVn8BVRbtX7JjoWwqVhSpYYGpo9+YZsa+oa/ZY+uGZJxw2wrcy5Q2FNvGKPk35lI"
                        "AiaC0kSjP7xmZsuW4d1W9g5+tmQ1Jcgmpwbgd/kFJqnvhc5Po+mL4XDU2KOGIGD9PkMDnlpMu7rG"
                        "ZidtnWIoEJPQgN8RXVXdDOtzCU8ns5jeCDRZSVEzM2DyZUvwplOOGZw/p3vzHbj+Jshobk9PCzH2"
                        "099PP/7EwM4rOse8oMl6M9lMrez4Am6pKqyZTV7sELGlGSuPfxN1Adh/vasRMBg7imTA7IHP91FZ"
                        "/BWdGCKAFIuENc+d21u+kLNe/OQ6DUjtziiqxVuJo2tR6pvzhUPc1tI8XLFQaGyTu6uf1IBBEL7E"
                        "LFKjKvNCQchFDiiVr+Nep0yCGmYBNCwDw6J15YnInLonouGfXp/c88jw0tG1n3rP8MqFa7udjVoQ"
                        "kSKbzRKWDYqiE1YDh4qx3PGA//N23ZP6LrhhBmDSLkMQ6ZR2WymftiLNkuj6mzNgmEzeYTvc5RUu"
                        "1BFcCKTWGnH8rwfkvx6KGgPdg/YWQMqIiEJ5ket2DmYVOVgSQTAcAQYKusdCxXDHtVXlQgh4lagc"
                        "vxn7KZScNVcIfPhfY+LlGAixgdx4ybnF9yhNejttlxz1/CxN+HvXpNO9USmVYh3Fjcc3DP/sD1JE"
                        "Mye+OB5pd9NMOalR78j4f8POOvXdVxwUub3ACwCZ08RckjFjIflD58vVMpi1gBaQba03H3ZQc/ul"
                        "2aNr5D/uBGRM2mzkLH5SmkspvyrbsCHMRRYuGzdekpRaqbJq7ZAFZWqowdRR2DELFOpFHceGRcNu"
                        "cN3kV0nXlSRUtc7abpQ6GTp35fIM0hxFtGbznPd9ZnpTsvCgp6/95efnvOxF4xE/miRb00RlOgI1"
                        "BLUiEUkzmGSz8TJskuxq5bMAHIwcyB2mUNspzz9CCPDMnjs3546q9Rviux9IgUGf9tCNcdlEd94l"
                        "he3mEAKxkJ1s4O/3ZEC81y7UjFNVOPyVnNrPjT44xnaweTsu73ixsLNSfav5TW60Bp9XcWaq895P"
                        "LneCugpgGIPY006edR06lEruoR8pCh0uJ0ViUMw8/upjGjssS+94YPTnNygRDUEl4CazAo1955fj"
                        "a9aP7f/07qEHxjqbFjJCsM220AkEw+Gfenj6xMRUrxKWyEZKaLDWWsEcaAKASAiWVtnbmAsCC6GE"
                        "FOn09K7bbX37aa2Y0l/+UT6ythU1ZHXqosqM4Y1nsqp8CTnd47NquISVh2/L5NrfozT8FJb0KhAm"
                        "pzYRB4uzZTVCxYmMqoitysuici53JkRTVZbXidvi5Uz0UkkjeZgEa91oDlz9Z/nfH5x8bMv8vXbZ"
                        "+N0Pt3956dC7z+we9Kx1S+esEfrJJNnQ7XV6qUqzJlEkKRaA0Cy0LI9wAcg8KVhJQW0bbKMejXMD"
                        "AWQ7rIhEK3t8bbp2g5BRfiKEqSmQg313cYYwmAUHILr/4YQzuXgxzRuB0uQyoxvu8m6X9sdnMQBi"
                        "66bZP58qPByyCoUQacD5OAEgBdT1Sf1sQuHYrAkK+EkiQg6GTSHv/UdtgLTOFGkSAGm2r5iCE2k4"
                        "P//JA0xEgOilWbZiQedVL4k0+Me/7o1PDklBGrGx9aI4uvvhxnU3NZpD6jXHDjTjTqZtbmjj9wV0"
                        "KwqRjFRsKHD3UKT2gELyk2itvjfrUTaXnOs1MoYiDWbJsknUEGgSmkCkIVIter1er7tmr13WfP2i"
                        "eXss2/zvVXO/9L1pkm1SLgq3ouFqOdr9VMUxDUeTwnpKooCK2rokuYpN9JUG5j3s3EsIublnk7rb"
                        "MwmIbB4+j8SQbXylVbb0I8F13mW/r/o96Ve+WqxQxmNAc6O54Kobttzz4KazTx87/iD14gOTFz8/"
                        "7kw0ntggH12Nh1el9z3c+89jyQOPNx9di17WABpxq0kqrCWH3LdVFd8e1GAAiKjUfTMnYUx98yqb"
                        "NxZDYtNm0ekK4Q60DUgqXOCrabGku7SN0miNjwuleaCtB1pmaEXosXhp6Kt0qQ3NDj4zgqZYSUR6"
                        "YNwvtjahcWFqzSkuRrGEw+qdQdOWs4AKi+JE5KybgobIcR4aeZqcnV3iQA6+iznbetJhcteV4v5V"
                        "Yz/6zTiJJSaZKphAiqCBhd//1eaXv3jOfz07feF+yW/+PhM3W+xO2XEY6OtSVPi/upWnpN3hamb/"
                        "jTWE2SbmIlYswdk6lQoFCSizx0iIZLDV2WlHnPji9slHDey0cMtj6xb+94fXPbxmcaPZYub8WJYi"
                        "MKHorOPW8mB5aL00CPtVy4yhOPNvhag5bqb6VUVcWrJgkw+L8u1+fa1WT8Jez3r6KRSi0kc1K4Al"
                        "CVj7Ze0we3kxy4e2ctJKU9ycd9+qgTdetPHLu2bHvHD0oH3l7juqHVboXXbTEBqpzKbbT2xU9zyE"
                        "m2/rXvPHLbc92ICc14xbrMCkw/GoVRHhWy+hyEukAHNso2j8EQIEoCFTgDo9ViyE3UHju0BevVRx"
                        "UuUT2xAIiDIWCqIh0JA24zPbvKV131iZY783PEKldel8HMk5a7mnZf8lzkmkBtocISV6CJnCc683"
                        "Y12BEgx5kTwtuk1Q4euEn0gKOBMqo5GBiRNfElOkfn5DtGrDYNyKoHtMfj+TiOL4xtvxxzubRx00"
                        "c/KxA7/9+5SGOdLZbsCs4N+KVKPpA0Hs8zV6pkGR/QEXWeoADzcm5PEeBJCa+ODbFzx754lOMh1F"
                        "MSgFsmYUzRsZ2Gl7jI11s5669uax8z657s6HFzRagyaVKgLdE0qQwM+qjkh/IeAKmF20VUauU971"
                        "NYdSrCT4qi5OSI1hehnKFR2A4Nx5Q6jmYDR31KxTy4E1Ecq0kmES+jWehkJiqgr7UGxXbUh/lV65"
                        "/kvBzIrjRot5uzvuT+64v9uOeiuW9PbYSey2U7zjClq5nLZfjOWLspXL+agDem95Zesnv48++rUn"
                        "1mxe2my1tdbBeUIey8b6qE+VZyANketfuaySBK1ImK29nDEBmZAEewyn52xP2eXaqsI6kATEQgEc"
                        "RxCSM+38QRfIF0iQwJd0DZh22WeTLmLYfeup3KaaJ9a54+YRVCRZb7+jyBu2Qe8Gs7AB6By5ngX8"
                        "b3YlaILNacXOlTXHXwtrZTpPMBRzANx595QmW488JN5nd2zZhCt/MwFaDs7M/kMTrAtASJl05vzw"
                        "l1uPeDa95MDms/aYvvU+HcehhvZ8JQIl7mkVLrzR6BAfzV8yQVkjSKlhke44DZqtz84MTYJSzX/6"
                        "+8PvPGnRYGMzVAtNwuAAskTP0NpN+MttrR/9Zuqq323spEsbrbZW7Cy2GkIt3YejDMDsfinZX6XL"
                        "87L/1juDXCGAUiulm7orXMZxxbQAFEwCP1+FF8b5DSwjAmwiccmi1X8S2uqhVdIH0jq4aw2xsJg/"
                        "PRihgLSvahjY9sWKkCxuRiTGUh3954nkP6t6+GMPSJpSLZyXPG1HPmhfPuoFzWcu7731xKkD9l34"
                        "xg+svvW+hY3WCCuNGotmNv3TZ5C8rLGcY/4Zn4qge2NDqiFVj0H5AU81gts/1FpX5vUNz2tGBGSL"
                        "5olY6Mlee7Kb+cX3kgQJADb/txxIhaN5Z3fPrQYjgASZNM1kzhANNJMblFps5UNvPg6ssGK8K3mx"
                        "ZjHgrComQaxBxNqOlc6FhUOaoV6AlZJNOXXqMSJuJjf8qX3XfTJqkLLJYRwwYK20jFq//dP4PQ81"
                        "99qjd/LR0S3/niCa4w4lLfYh909LzbndSyTM8eal8gESKGQouPT8WntblrSmqDF2/c3ZGedv+MbF"
                        "8+J03X/un/Pp76zrqHmbptXqdfKRJ5JUjcWNOc1mpFTm83B4JNSCXTWO3FfbMLKCkmU8FHmwdm9T"
                        "3twsVl6Z3hyRimKrlRtfAdncQOHjEvz+jysBfiZwuwRuCGuthekKAz4230JCtVhA3dgIFqw4Uynp"
                        "XiPmZitutkaazaUslj65Ycnvb5r/oS8NHH5mevaXBlaNz3vWDhu+d8n83bbbmqUZSVGZDbF9Dy3q"
                        "0k+qwGbgFYLMUe+WudF47IkuJ7x4gRoZSlRmUsrnk4a+5hLefP3Bvw7zBCBZsbQBIddvoC0TQkpZ"
                        "BbWMMof+KgI9ts2v+krIzHVz+XkObblBAKWHXHQHSvRqmNaVDCbFyFdVeOSZIey7ECJLZw58VnrQ"
                        "03vTE/TtX/R6ejRiSUjNZ5bMAKIsbjTWTw7++LcKSE94QbTDkpk01dYZpLIjAhsZU4gjgxt3u7uo"
                        "bl27hEwrKTzraZjTRgAQpNK63Vj6kz+0L/mObM5ZtnJFFLfGrryBbvjHTvc/sZSiHZoDcyCU5iww"
                        "O3IZVMJGiYQKrOpuqc/4hWM9q6FUbqj6s4SBbV0EnyWaSlRQrMgetoecWFyiIrYbyNkIKWlGLqiN"
                        "/dbfEFkl9q52PijPZnXGk4I9m6eOCf1Xno2JwCRAQrBgaM1KKa2UUrqrkckYjWaz0Zy/aXrFF74v"
                        "Xv2e6Uc3zd19+6kL3jqXeJNCgwU77etbISdW4MP/yEYGUBFyBF1QzJpZszmTmjXQuPehbHICy+dj"
                        "1+2ZeIrA2hYrK0Y/QCZu0f7rLxJMApCsKY67z9xVQqgHHtGdBBHZwC+AQBqkPPX6+pnZLtWZTcz2"
                        "6CMw223+5o+IHOMJG07Jnqhzmqra0bXk6BBDrum8FrcYF4yvJoDAwi4REkDa/rEfEY/qQu8A2MOY"
                        "IYg2vea41vDw9K0PNP/wz6TRGEyZSTSIBCgSFEsRS4qJ2pqFjOb+6Nf6iSejlcumXnaY1GpcEAUr"
                        "V8Jv88z7bSWFeaJdpCh7PJhbF7nmtqjZO21/u+wyVgwSAZJJgKGYm62lH/96etkv47ExfOr8Bccd"
                        "HAPTzWbMnKiMWAsOWqySkLcJCvgpyrI+NFy6CjqsRATVb0uVVFvscxGRJJLBJEzlBHmnrmElewB9"
                        "SU5zH2OvCKKvOTejtgWlrdkV9n0u9LxfPeGQWOoJDlhymtBqPM3QmrVWUnJrYOmNt7Y+8S2Vanno"
                        "85JnP51Ub4pqBsyjIv9ZMjnDbhqJYrbmGOkOhtaK4sZd/+H7H2+MDE+85ICI0WGhC7ZCgA34UWAP"
                        "gXvuignBWZrtvSPtu3s3ncEfb1XAIJPKEcUIDdUqjdpWct0UkCDgZBahrNKM3ZGj2L9yAtHTErn7"
                        "sHcFAOCMrxLaKZ/UKDiqIe4NeDWEwSBCksw8e4/siAOymW7jW1eun+nOJMlala7KemvMX9Jd1+ts"
                        "6HU3pd31SXc1eOsDq8Z//tsu0D35cD1vZEOSps7iLiDBE6oz0xC+CnvnDFYKbcZyZ3Ornhx+hMk5"
                        "ppGyVpDL3v3xiT/9a2ysveWT7xnZfYfVvU4XpMCZC4quQWAVqlohxUHuqmqZIsC5dQYUqPQpiIVt"
                        "X0HNHnuAmcOissdY0x5XliRLMpVqzPjch/IjxBW3ufZbDhzgENyw0dp7O1MrJDMxK9T0KxeC+Yck"
                        "WHVFtPyXNzx29ulDuyyf2G+vgZvu6hAPszMvK5agp928CwGXcnEgyXYL9lzBhhRbpuJr/6Kf9bTo"
                        "qBeKz/9w68apMWEOxwsnxYu6gYOH5NvVzGApJeuNJxyORXP5nocHf//PjpQDpPP+ExHDLy3r0iiU"
                        "0Rggid30jB+aIlH6sSNQMQ1KwaY2X9iFNl+gSkWoI2suDFnuWXCB7e2nxUoYIBYx6fVnHtecPzi+"
                        "cXPvZS9svfh5A1J0BEmQzWfgEMzEBAFGqrKxlQvHp9ZP7rGSX3qQ+PY1W6N4HmtQMfC9JEADis0x"
                        "FqKr0LEixsz7nOBJSBEBQpDUEABr1g0Rb5ra7k0feOQXly7YZcmmL54374SzH5rs7RCJ3MislSNm"
                        "6jPk4n7cVGXJ0hV0ikq6rYqB2m9RGf3wCiEkm4HDxlpFzvfOH7lvPE3bSksZgauip0/XKKDpQkkz"
                        "f+zHtQSo+9c6I7kyr3Se3MSt8RYyAndngI6MBkgMgFMDb2mWoVAVCyUUS9482Vi7Ebtsr+aPGeuf"
                        "fKxgtWvuj4lEkFMYpRt2pg1gDzwBC+Yu0ehPrl39mmMGnr7D1jNPHPzYN7ZE7TmcpFo0Cif2ALBH"
                        "0ln7yg45O47lTAhKur3dd5g68bBBpfhnf+is29hutqXO0kDpm1AjZvhN0fWJXh3whuh83s0QCWWE"
                        "OBMrDy2AcBTijmLx6przs2/zAWCDZ2upFEeHCMwCYNj9z7kPEMgxgABJhTVrACQF95Jkl+26Lz2o"
                        "nXQn5s2dc8yLBUQCIpACMYSEVO4o0gzGTuEuWKMbpzMDpLeeduz2l/9uQqk5DpYCo3rbU2vtHUO2"
                        "y6MuXUyIWHtGFErSyqlPMoIFZOJ+IyZ7FjozMt1rtqN7H1389gvXfv9TIy/YZ+P/vHPhmy56khsr"
                        "wSlDBqxENltJkSxLpkAJgFCabNNMK43UNgVCWOcshlilWriFGRvW4LtRFhkcrEnPXnu/HnqyKgm4"
                        "qnwNzYpQfVU7VtVgznLRjLiBiZNPmD7u0JEvfnvy+ltl3IhYo7DEQ7lL5ZhEAZKUjKWKoMDoJRkQ"
                        "g8AaXBSUYS8c0gwY+VEOKI5NicMN9mVT3P1o4/LfqPNeLd7ycnn93zb9498jzbbUCqXIAgYXxsWI"
                        "cCu2WIA1SNLq8/97eJe5G+9bs/RbP91M8TJCwsVDVr1gdcxZJqAc4EAaVJWEcwOJyKfYNp3MT4pl"
                        "bY0EAihfJssNUDeSHPTJWr/VESdriVCtw+hUS+mVF7uC1daTjmwuXrj1sTWLPvOldN0EJAmzxYvA"
                        "wp5MqmzjRsSCQGknxcrFA+eeEj97z8kX7x9ffeN0oznYh4s9TVqL1Ckq+9Z3SmsdpAmjQMLaqIhc"
                        "XZFdoWHWbONNGIiUSpvtgd/c1PrgF6Y+dVbjNUePP/ho65PfW9NoLRYKsHvXtHdDUWSuCqLgn3h2"
                        "C//td/V7WfUz+rVYrK0GzioAYVhDjX1a/TL8WStiZgfIl2fm6ra7Pl/R7FgmItZmYRIaHMneWWcs"
                        "euYz1q95Er//51ZJyzL0QBE4MIIogJmJmQVLrXuLF3ZXLGbda6xaQ0CEIJdWbQdDeEpS2LskzAWi"
                        "MXFsxII1i3j+5y577ND9l+y386rPnzv/+LMfWrNlt3Y71jrj0N5EYDAEOtBRd5T1Hj3vTHns82a6"
                        "NPdT35t8ZO38ZltAsz8i3et2Wwnn0xAe/DoSCZUZBzopF5smx6axf9kJbwupXbHwOdiFq9Ijze1f"
                        "sZZ/PUXn4k1r6yS4F76t0nA4IImANOXF88dPPmIQsnH1Xxuf+3EGLAlknLkRQT3kJKeJrnjioP3G"
                        "jjxwy+kvbV/7ly3MIwYHfiCCmxxRBeAD7jWGlfNbPW2zs8T9OLPWjNDd9v4dNLFUeiZuLbj0h49v"
                        "v7z9rlf0PnAmPfBo5xc3jrdb8zKtzHiSxfC2RQ8qlOyf1CuPHG+z1VbhhforpK7wSfChI3hnMbJ1"
                        "fNycbAnQcAyosmPIf1L6WbX9PPzFboeQ+ctEobCjHsMhJpQJXiH7vpF9Lxoynp5p/uKajdmm5KhD"
                        "xPP2mOp0xoUE6czOOtspZQaxBhNrQEFAxtB640lHjiyZm63eEN98Zw80YIjGI6HWznL9MuaGzM0N"
                        "Ir/GEfTOoFobOKSgdeMLzv7kmnWTS5+96/i3/mfZ8oWrOp1pIZtCGPNEE2m3DkbEJNhswAORkoIy"
                        "qDR59K2nNt59WtxqqO/+BpddlTaaA6yUhgiW2hyHkAWCcmccICZyy/b2MksTkpkB7dcu2UaT+cOy"
                        "XFFjHrntx0TGbGEXXEbwDcMuQRIz+UPBNLNbLiyRFhzDFWEmuJ9VrjA3GgrMEKTV1Akvbu+yfWf9"
                        "5sHvXtWTcod2u9VsDjabg63WULM13GwPt9uD7fZQuz3Ybg+2B9qtdrPVbjXbA+2htqAFV1zdSZPo"
                        "hc/KDnymStMZQZSHvBaIwcBmoCrwQhFOEZQPYba8ABKAsJmIyKHCqS2bjUc3WZNsLv3w56eu+fvY"
                        "0OCmT71n/j67THW6U5CRoRZn5eU4CQ2oflcV/yFi/RXQMwMF5jUfCmF3BZVQMftVarH81mx+zn/2"
                        "KV1qrKRAfE+CXuWdKb7yij2XVv17wS6CIWzIJhUy1WqttdZGr2tmzUKrhKLBr1/Zuf+J+duNbP7C"
                        "hxbsvfOqXmeDgJCSGaRIGS1lTokmIhIxC3Smtrz4wK1vO04JpD/7g3hgVavRbJSDvisCuozP8hww"
                        "PAfmusIGxIOIdYa4OfDX2+ae9fHJcVp4+D7TP/vCkkP22dKZWd3tQYgGyyY4JiYm1mANViRAsSSh"
                        "mHq9yWH56MfPGr74tWq4MfWbm0ffc8mklkvJRknn3O/ITLOGiWBg7R86+c1kVoiKNOkp0j/MlZ61"
                        "KQgsjPSIQJKE4FxI5fKKpIt7IZAwebAsLrgAbAFmf68BN9wOjjLz2JLk/UbmVImB9vjLj6Qo1tf8"
                        "Lfrnf1oijjIFraG0zpRSSqtMpZlKsyzNslRlWWZiXzRnKktSEoPX3jhzxyMjc+dOveaYJvG0IkEs"
                        "EWR6qcITEG2hF0VQy4fIcYEZhTcn7WZwU62J5icGs0Q0ky1/60fG/71q+U5L1n754gVL523K0gSS"
                        "gXgWSVRh2H4QMvf1LRycuZ1YlQw168J1VfUtUQVeUO7IcKW9mu+32Z5roB9XWwPYs3doigZlwuZK"
                        "RFmDU/NeQ7PmOI5Xb5x3zsc3b0x23GuHR6/89NxXHTaT8YO93maVZioTrA2DQinRSzjpbhGdx197"
                        "9NavfWhw/sjGv/57/se+vjGK50HbcyCegnLwgj7c2GLgqnJUfsOAzmTcmvvj38Wv/0B37czYfnts"
                        "+MnnW584m3ZZ9nivuzrtTCVJlmlN2p5vlSWUdJNud3Osn3zpwVt+denwWSdtHWiLn/xlzunve3Ki"
                        "u5gEabfLp9YAsYFUeQJFAMJbN45GPZ79Qz8gxbk5AmsxPa217ibdbtrrJd1O2uulvcT9ZeYv6dqb"
                        "rKfSnkqTlKE4nzYt01uZriqq3j53+PbK2cLKgkRDJ+NHHaj336M3vqX5jR+nTAtMPnRQnq6nwNWB"
                        "3GQCWMax3Dw9etkvO6yaRz6v8YydOlkvMxFtFaoIBahHeygganiqzGg+MT4LY4vDWko2egsQRrsw"
                        "Itai0Wg8vmHR2y7evG56xf67bvzyB+cOiSdZE4QKeTBETgmNJUsqFL794Axqg5sGoPA5cprJyz+V"
                        "q1Zihi1XD1ItL8r6L8m62fa5I+v6VgNb3gnb3AymwLAiP3HmAunIraGYkn7iiRx4BRQ4HIEIgjWR"
                        "IJ21WkO/+dvMGy988ovnbrfTorVff7941dEDP//DzD/+NfnkRkx3Ig0ZCwwOyO2Xp/vvKY44aPCQ"
                        "vTqt1vRNDy14/fvXrt28pNmAZhTnrBEYF4XZt4JMsDuNTUntcIVieefGEgikM7RaS376+4nV6yY+"
                        "9d75z3tG912v777yiPav/6Z/+/e1d94vNmxEt6sBEcc0Oi9auQT77RkddfDI8/acbjWmx6dHvnhl"
                        "cvGXN/X0zg3RVCqDUAZCv0nVj6CzlarAA0Ru+6R1v7ySRMFB0E4hAWBkIhHp7tunSbq22RDMDCKT"
                        "6RSAED7js/DS20Cydbpx/+pBpkGq4DlQooXLL8kHr4gDG7bYMWal4mjLace12q3kt3+Jbrk7i+MI"
                        "ZiHPzkOZD/PxDdtks8NTa5ILrv79qne+eniH5dOvPnroX5+bAg3bs3cc0RoA/bqFnSl1XMBuC6rn"
                        "bc8+lE9seUS7Y4jAmRYAgxSYTLI2ZntYBUgTAIVWe/iPtybnfmriyx8YO/r5E+9/a+M9n17XaC8C"
                        "K4aECdRwflkg6MtIDsVN6epvBBWkc/UrQyqz2FC+8v5CjQJkIgocmdz/8kU5SBsQNu+EKKHi03kN"
                        "44sJEjXWby6SADtd5Qce5ELwQ/HkhGYNKfuxN6vJWqtoYPFPf7fxkYc3vP8tc17ynM5RB80cdWC0"
                        "bmtr/WbeNCFTJZuxnD8nWrYIo4M9iKmtE/EPrxv50GfGn9i0rNlqc8ZMbu0xl91mriUfoJACHE58"
                        "DwPDK3eBCygyEoTAmdLN9sjNd0dHv27DG1458NqXjz5tRff1r+y97li5ZhOt3aAmpiUgWi25YF5z"
                        "yXwxMDwNVjMTA9fePHrJt9b+6ZamiHeOJBRnMEFPxZEMgEQYRO5eaZ8nwA9KEMVStdHMooVgUpHs"
                        "tHnjF8+fpwURUlBEJAjCzWRY2WZdSdbMOs3UcCv+w22No97UTTHs2DMf2Vnou0IAuSFjLrc1miFF"
                        "2ktffABevF+KDv3oujRRI60YmWK4eHK2Kd7twHlzw5oeICLSEI0oemxD+xd/kWefFp10FH3lJxMP"
                        "rx1rNjS0O5fMweYMQY9tcpN65H+GrXj2Ce0yY0mJWJFII0RWhYvUJh4wbjjYZcfWKkOjOf+7v1i9"
                        "2w7q3DPk2a/ixx5Xl1453mzN1ZyKAMKSSVWiXv8zlCD+vjQowVt2mMzx4O7Z1VwjlcIW+z1BYA2Y"
                        "/7g8TO6Dohnp4fASKv8yrKVklHlR5bRwvW1JeVwjOXotAKBtwGUJwpor6Kcj6KzXbM65/aHo5ees"
                        "O/QAOvHQ0f2fgRVLpp++M0SDQA2whO5OTsX/fji6+V+jV1zd/f0/OiyXN1uxUiCKgLRWODJAgTTq"
                        "y2N50h4viL1890o1GL8sa7TaU9mKS769+QfXbD3mhY0XHzj4jB3TxXMnl+yqSSoIATSV5omp5v2r"
                        "hv52p/7Fdd0/3jyT6OWtJlhpzTGEXRM3mBXBFk7fjxLpEIGhYRPEFPbco0LTdtSgNUtClmW0anxs"
                        "IEo1lGAmNAENEgISInL0YJNEsgZzBnCSYapJmyZdcFEg/XMEB9RSGoLiL1+YCyWJBAg0fvghy6bR"
                        "ufGf/LsbJ0Q0pFVqMkkVP69VJ3AZzECsSCz83pWrDn3OorGFjRcc2H74yilgxBo+AaileyfCaoYg"
                        "4Gq4xSXnG7Mm4unuaG9mZDqJgC2GZKhOcziZkEbNFRdf+sB2Sxa8aL/kja9ZeMv9k/+8ezKOW9DC"
                        "+ANV8DwkoZxCwMKhUVYVJe4hAJTGyMtixwJ9sVQ1+kpNBDKRmZmi+CQv7JFLSgrGcjZzrvTWw10S"
                        "YVq7hOVOfJFNNm2/C21L51iZp76mgoDYxkWkoQQDFJHWSToDTC2c29txebrdQjlnjNrNVpqJzZvV"
                        "E2vx4JNq7aYmMBI1G8LmCRBMim3GlLBpD00pIIOC3Y5hR7z+9EniPV+5nnp0ETE0gYSktEesp4Dx"
                        "5YuyHZfwskXxyDALSd2u3DIhVq/DI6tp49YGMBI3JFHGCiA2QYNmKHOslW1+S5wFXQftmMEbtmUd"
                        "E5C1WVYWzFqKmfnDm0AKJMCCSRNDUGQPzTP2uGVUZlYMDVaamRAlaXPLzAjQ9CZGyaBzTYcmYZV/"
                        "CraDMa/sSGnBIls6txNHUxNTzS2TcyAl6ZRBouyBwjkEuXrO8cMAseZY8sycoYm4KXppa8vUoEmB"
                        "BZR5FQFPCiG8ZCixRojnUgQfQIBaPG9i7lBn0+TA2k0topYTaeW1f8u5LEkAWjflprmjKpKqk87b"
                        "uLUBUiZ0KZRQBkuhnCop3ZIdVILWjhAVeLZEKgEdYhaB9ZR42XxEYM3NprACy2ANloVCE3cbV2js"
                        "VY3G/BU0QRBIs8r7WyMKzSQIQCaHrknCCzIHFtU4hlwr4F0v2dQoJDGQJMzcA1KAAWmSHwGREO04"
                        "JkaiFcPSMofxotXKw665tmxkPNkjb3ymJOMLm7acBmUm8k9qFRdAxFpkaQr0kMemm+baQrSimM0Z"
                        "MJYyALLixspBrkS6eSYvWVuOqgpd8wUqytMX1kor1ka5RD6jKkGYA6YAsFmAtHVqDlAkIIUE8vTc"
                        "/hIlkPyBNGT9SytcQrlca3ozkVIMJiGkFMpnrQllB9kNRcTB7FJImaYdIhBJpSVrBnEkedY48Nmu"
                        "2V0tW4Ypy8wsqo4iqyP7NsfWF4EQrE2XGULFUa6EqgB4DBRqqkiTfuYPOYFVjNopVOXsr9k8/dmF"
                        "jG9UA2DdbFIeOBpOe1TUcl9fjINFkNJIFBoGESSM6cOMCpAlnWbPUyu2WgfDNoQqM2sSmhngKNYQ"
                        "LcaQZE3QbBLAg4zON4zsGCWM2S5rHicjSmIrp3iTeJLtCqP0GttxnTDh8dXEniFWWWsiFTcAagMs"
                        "jRSHZkhmzZxoDRdlrmErClUOVVHjOsLMnp44eJXbLyU5FWh+eLnJIBJSCkHMkD67sktG7pNY2cKc"
                        "j669tHYHjwW4hZ9X8E17acWusMdnLbGFPW5Ewp7pgJJI8vcuUSiZFfPQ8AdZkrD8GQlFUjJrzYor"
                        "cRgISML/DOygcoEq1+RwQ4sYEhIsmTWROS2tmqoADsVWz5LQseEziFLZOt2T4yFcn/Gv+hpiTH7O"
                        "qp9kcMoeoQFUhWGWy5sLToUwQFGxBAJf5qnWG3JvYcom4FK4bLZko6xL9n/R0DXkTTbGE+Ug4Er5"
                        "2TWd7TUxBDSDU+VjiBg+FNxUGyLLj1OIvio/+46Y4Q5o3fy5+Ym8cgZIMEgIjTCZDBxDEsxUFwmz"
                        "SgWCgrCTZ6xNJBNbFRf2nUo3/cYxJESyRjIV33pQvRELWC0SoBUAWBsD2n9t/qt9xXYPjLO5LM6N"
                        "H4bi2Dn6KRjORZQWxmX2zRJkZs4spCast2A8uo6wY1UujqAJEzOqRRopzJzlr1zUSxXVRWYrWwAh"
                        "y1RMdQ8Vcb69V4bDSHb2s+xzACA2fVScayzuRw/97kP4Z0Ev+s4XueGtmQDNJfg2JUyxjNXBucAK"
                        "hUtY1Sz2XvAhB2TETln5h3BwFo4ScVXBiWp4DAu3dAS7GpLX4+2IfhIk7BHysbKLYAj4PFQ/IaVy"
                        "cSWlVGf4NkRRgEDbkSIe/RMCmCJhD02wp8KYthigfEU1F2Bm0zSbQF8OACuqaK8DyvaRJ5QQqkIN"
                        "ZZMqMDTITORrlyPchT7YySw7evmHYAYDwfRNiMDwSRAZE3BdrswCgA3xFNAe8kPtvcmT73i7Zp3a"
                        "zDGFwoKKBWDEK4MQbHpw/SgJkVLlBdsqgDvk4ZJ5Fd4Ia+mX3uQNFVU1O+1ocoQJi91gwaoiEwuV"
                        "zKLbKvdGXfa1anPMVSyAKjAlDFQeMufbUwF20QPmtZvGCoivTgoU+8aBQoazMthtW/fNa5/ELiQ7"
                        "05TrSVnbFEWSLc8+R1m//heAqUUrmf0kYetFlJH/nNxWJEF+X4g7ES7ogru8rEHuzPj0A0Q2XEyp"
                        "XqfLWgi7A6msRkLIDbu6Zgpzt/lIOa/Km3UeoNCOMDe+vz7zkf+3qAZdH93QWOS7Y6Kd7Vi+nJQL"
                        "4XSQBCrBPQ1wZ30zEVgH9g2RPa6MnShlNrvtSqycIy3gZ0c/RboKJHgAbRF4X7FmE2Sv3UYlhWJJ"
                        "dmG3buyKfBha60ULDvDGdXngSmwMZ+Fy8InHqU2G5bjDkk1QWwGeIs5RHq/6wkXCzC2PIgcR28z6"
                        "hapCWVy6r/Y0QIsRDHYRjn14IeouZ58XcZYbQg5RAdMaXPn+U16P72QIsWWwkFEraPJE5jFWOE8U"
                        "VfLiCCAmrcyyFDSjPOFgFvLdQSnwasGcLEvCJiy2f6yJSJO2UhWZk7yGyjTDzIoBkJq1i/41PVUg"
                        "DXv2FDNRkvTmjG4+/eVDI60newlIRCZc00xEMGVF/INZQXvHx1ChduPHYEEsTHyOBguOQXnOQoaZ"
                        "1GZAgwXIbdqhPJLQIdP0BQxttyr6TTUkYNWA285ssn267sOEJlrwck2W/0sZs2bARutDgTQTiCSE"
                        "SZfqqAEEFsKUC+Q0oIi1lcbsT4tXZkM77BMWpAVseFKBXU1lWhmdaOY0XZskWFLFtCIn/+xmdfJy"
                        "EgFpw3iMTJpImWStmr1cY2uZgmHPc9bMzOYsRSeiHPiKWXn2rlO0zCwUGKSCdIY+Jy4zKW2P5DCR"
                        "y2XvL+CsguETPMzVVfhJH2uIA2Oq4OshtwwLToAvFmpo/3kAnqnKGEx2O4JpkQgUN17pyplNeVTp"
                        "Q33bfsAChy4Q9raUdmDlC8AOC/kRkq7+bbu1vgauuDlsfCKhmAWZ0BNNBGJBxNDaCCmLTRIyVBEA"
                        "gTXr1Cx4kdkoBmEVGRNYMKeatICUkJq0lXVExMSpZlIQAAlhZ8HNAhhYaYaGYGfWYcn8rR99964j"
                        "o5PrNw988GOrNk8NKe6ApSQmkirjfOcYiFmbfHtmnZFAxIoEEzXMxnVmpSgDC9YC0DJicKS1XQ5j"
                        "sOCMWSCKBBSUZghtVrVhRVaoTqWwmGFIu1MHmjmFVmBBUhEJrcglMiW4LGQkwFqDZWm8mM0uQ2FA"
                        "ZwMThFmmJpZapkDOgwxiCAGthdsPyToSmhAxTIpko1ik5gQsAE3SiHu4aWZizjRTfqCGwagAyEz8"
                        "ESs2kQRs8i5Hxi83K8MwgApKhYg1K621oAaz0lqREbLFS0AQMchIemGlbD79pVgI0iQIjAgMkGLN"
                        "gAAp2Ak9DUh2uak9nbsbey+E0FpDSwgVMKYiaoAVKIMZCS2ZFagkBVDkFFu5+xnyggg/CS2vkggL"
                        "6ymVrxMUhX4B1lUyAslJOqpIAN8ElFLNlswFlrFyre8MQYQgPL0sR6rNA7BEUHiVxy75ywsXv+pB"
                        "rlC1k0UZty1xBtIiBRpZtwt03aA2gAw02GgKE6+kwDrpAlkgkRUQy3hYSCjFOp1xz00BBTSiZpu0"
                        "SlMfZKAB5bYKtOK4zUJlvR6QAJk7viUCWlFTMBOhAegsGd91V8wb0X+/5YFDD9jjsbXZA4/ouDnC"
                        "DK2lzqaieIQpIacnhdZJpkQUSyHZNCpF1gP0VjcusYhGpCTmDijKEgVOG4220eHEgkkLQUmvBwjZ"
                        "aJBiYycZ+4UCB5+I0iQBUtdxj+1G3IgZWZZoQDSaUFoLkwmCIwHBSqdqRkYDEIrYfujHVEPptAdw"
                        "wAkKaMaNYZYq6wrwZNxqu2l7rQk6E6xmojiCliQMzsnlq7JGMclhKSNGqpKOw3YGCKBJohlHio1F"
                        "qTURa5Yqm3IFNDAUN5pap8YXTFMFUBwLR6ZCU0poqWQrEMlmUxhVbo6FILsI590aEpT2AEw6Y6pF"
                        "si2EJpd1R5JIUg3MuAINEY2KKIMyIR2UJhmgZKMJzkwED9ziO9kjiVhBqGSCaFjEmqwVw0xCM3Ta"
                        "AXqudwQ0KBqJpbaWYuC4BWDnzOj4yx9HViNxQjrx/Fhk56C6IsOWCoete7MDTn4VC4SwkmbVbBLF"
                        "jZMcadqMX57gnOitERPeyXSdDDESGpblAyOCmnNAc5ekrq1S//teRATWJJFNv+jZvefsPUgCsWQF"
                        "tWFLdN0Nmx9a3W405yvVaTcnTnhxe+kiAc0EBaDZEI+ubf3wmok0m7dobNMrjmwNDQoyxplWjWbz"
                        "pjvpuj93lE73f0bnRc8Z06xJMqDAkNHwz37bueehJlHnsOdmz94zzjRpTgFMTsfX/XHzg2vacXO+"
                        "ViqOJ04+emD5AnSTbHBwaGpiYnAoXr0h/sEvJrrJ4NK5U4cc2P75NZsTudDaAJADsnvoIfGfbupt"
                        "nRqSgiFk2ptcsWDLMUcuXrk0Io2HV2U/vXbT2vGRuDmgsuSQfWgmyf55TxxFUmsGKUKsko0vPzx6"
                        "co268a7BRtRkbQSWVUfeA1Aq2XvX7PDnRwKaiYQAgwfazd/+BTfemgH6gP1mmgJ/uIni1jArZlKC"
                        "Wqz0/OEtL3nh2C+vm5zsDkMoFw5GRJxlPDrYOfGw5tw5BJ1KwQRqDzTue7j1k19PJdzec+dk7z34"
                        "Bz+dipoLiDNAqixbvmh63z0Hrv7jFDCk1Phhz2/stXssNZMgKUlKdHX7+1dtfXL93FZj4thDxS47"
                        "SK0jZiUh1m5KfvWHDWs2LpSNFmkFQWmPW/HqEw4fedaeQ8y8bqP6/Z/G73hAx835zJHOekcfgsee"
                        "1Hc+0Iois+ohlWBKt556orzz353b/z0io4iCKTZLh6wZIIrSZHqHxVtPOHLRgrGsk+j7Hkx//ce1"
                        "E+liKQbBTCSydOuKBd2XHrFgl5UC1Lzn3omrfrVxU2dZsxkBWZr1dtmhu3zRwJ9uTiAGoPP1DmNe"
                        "EWnNUVOMn3LiyB//MvHQ6pHIzH1Cax0NNLYe92JePj+GYGJKgcdWpdf9aXIqXRLF0nq/hdDFsqll"
                        "uC/0yCqsWvhZNa9qBVbRmKrlXw+G7WnJZHPyx15a62ZL2G0TbgKVQunDXBI1efOBiClKDJCfYwp8"
                        "3YLvGgg7Y5mzOQe8VKF3VUIx7CusA8uaDFm29YxXzN9vDzXTmdAZpZr22T3+ydeeceTBWZpOMYv5"
                        "Q1vPfcOiFm3odWd6SdJLkl6310umSDdUli5f1H3jyYuQblKZytIky3SSJplWIGg9dcJhYy/cF1sm"
                        "x3udpNPhmRk93clSrQVBq+nTj5/77D1Fmqg4aoDiXXYQP/7Ws457AWXJlAAG4+mzzpgzZ2RCgNNk"
                        "YmAoJsGRYImIVW90YN03Pzr/PW9uZr31QjSJoHXciKbPee2yuaNdViAp0t7Go18wc8VXnrn9svTO"
                        "+zbc99CmZ+8X//qHz3revj2dZVp1Tjxm7steMkerrhkBQULpZMWi6QvfufzcN8xtyY2awcSabNwI"
                        "WX+EhCCtZg57QeP4F7e3TG/K0l631+11e71eplizlFpPH/HcxpVfXLHj4s1ZmgjJxA0SnGWbP3DW"
                        "yOcvXDww0NFaC2IITcLMc7HWeuG8qbefOR/p+jTppGmaZWmWJqmeZpKcpbusmPzeJ1e+4YQs7W0R"
                        "gghKabX94t7Zr50juceiqXTvda+cv8vymfGprb0k7fayXqI4ZcGkIaSYOuf1i5fPn0q6kwKaKDt4"
                        "/7Gff/sZz95tSmVdKRppluy8fNUvvvW0o/5r9P5Httx6z9amTC792G7vedNCnU5GgrSeOeOVi/ff"
                        "J2admiNuWWqdpnvvOvPJ9+589mtGpV4jchHsdmsYf1gKpTrP2mPqi5fsNjoy8a/7x59cP/3SFw9f"
                        "8bXnbL+QWaEhZJZuPfFIXPG1vVZuJ++6Z/q+B7YcfODYLy7fb9/d1/aSGRGRVt1n7ZGeceKcLJsQ"
                        "BbY1UoQjEirtHbRf9tnzFr/hJKGzrUQRA0RSsxod7L7z9EVD8WSnmyaZSnRy3GFjV355p+3mr02z"
                        "LJAQhbA7J3rsNI6ZA/ScW7KtqiyJivSxX1WcxCpHhx/VWVWex61AYDcXaCZVoipARf85n6WqeKe5"
                        "dAtxwW6zlhNq1jkoSesi4goNBf0J49bKBl1NJ9lYTKrby666buOVN0jAJHTfePJL1p39ul3/dPN/"
                        "ZtLFTPz4+qlLvrFpJhsAEoAACSRxawxQWuHuh6Y/8o0pYK5L2JgCutUaSdPJJFU//cP0V37Ugdk3"
                        "BwCTQKvZjJVKpqY7P/zl+M/+DGAEALDplMOn3vbfO/32pvu66SCQrXsyu+TLW9ZuNagzniNajSGg"
                        "12gO3HD9w8/ee85rjp247BerB9rbs85AmJyaMdvB0rSz186TH37Pc9953p/+dMcgMALwN6589KTD"
                        "lRYDZogmp2aSrnYnj0khIt178i2nbffVb9+9dPmcE140evl1U41mm1kUBsT5cbrb+/2NnUsvT4Em"
                        "kAIC6IFkszXUS9X0ZPLof1Z/4OyVb37f6gzLo1h3Z2Zednh73z3F7f98rBUPsA1hDQeIoPjRVdOf"
                        "+vbWDGOABiIgBpJ2qwkkRPTH3z5w2glLHlu75jd/iwcGGkhUlnUnJzc5JapnJrPLrpq+8Y4Y6LnP"
                        "p0VjWERKZ7Ruc+dzl43f/fBCQAEKuP8Db5h/7puWnHTWGqVH57Q3feOTu1/76ycuuWwdsABoAhM/"
                        "uvrWlSsXQ0TmQO6prZ3OdA+IDZMQNaE3v+nUFR/+6M3Pes6iA/dt/vnWbtxs+NVeZgaRhiSQVlve"
                        "dNoOv/zpnV/9uQYWAOrrP77/4P2WzXQJkntp94D90ve8Ya/Xvfe2f93XBMaA3pcvf+hNr5r3+Y8+"
                        "89gzbtkysxxAd6a7deu4mQ10/OIRqDM13I4eOf0Ve5z5pt+98tXP3WunVXc+0pMNKTSDFbRas3bq"
                        "s5et2djZDsgACTz4xfcte9sZy9/18Y1oLmROYaoOxI3jd6CcvCDnca6UDx/2cxhrBVAt7yMw7oKp"
                        "8MKkm5eDfjE0D2vw4BarM+sjVeMIZNLjcv7cV+Hy6yGUaGH9zoorQZ8D6n8GuMsNrmrP4fmEJRBJ"
                        "YGx4pBEvGhieNzw0T8qdrv97l3Q2OBCzzqBJsmw0h4EG0AJaQBQ1RiQ0IISQrQiSRkCDREOgFmS7"
                        "2WoTaaAZURZFETAEtIAmEIOacSMGJwAyzhpDrTieOzgyZ3hwLIpX/OGfm0hiZDDSSjK01lrGACJ3"
                        "/EcjjgezWAONOG5umB4964O3vO31uz//mdlMZ1wISTZ3VUoiYrX5Tacu+fkv7/zTHcODQyuarYFG"
                        "e6jVXvGj30z9/Z+QzRagBZmoLjNRRWmqVizK9tlr+Fu/TH75h85xRy1oyi2azRpIHrjgBkpobeb7"
                        "26CG7aBoN1rSzI+MzBn+2lXrJsfV2W9YmHY3saLF8ybffMZ2F3z0zsneXCFSM+lengFgIakZx8PA"
                        "MDAENAAxEI8RMaCGotbtj/C7Lr7jwnP32GHZ451eF9CChOCGW3mIAIobBLRBA0ALiGU8GAsClCaO"
                        "SM+fOy+ORwdHxkZH5gHb/+Fv69sjjYaM03Tr6cfP27y5d8llG5qtp7fi+TJqSTn/wdVLf/9XATFo"
                        "1kPdDnE7ZZT1es98WrLzDkNf/dn0b/+cnvqKJcBGu55AgF0aYk3WLWhE8YKFQ27ypCnjXf98i9w4"
                        "1RKiAZ5462k7Xfq9+/5132h7aHljoDnQGm4N7PLlyzfe+5/1pxw7TyVbgEhCCo4A6eMrPMcJitJs"
                        "6yH7N5pNdcWNdNudyWknzoHeQsJwMYN1JBpz582Pm3MGBhcMDS8Dlv/5lnXz5sWAZsrIR8UGV+j9"
                        "eJ5iF5/kJ3b6Tj959i7GYAZOHPurllu58j5wKwstsp0/stBGQY0m7tvMKTKb4x45XLHiQtU2ByIA"
                        "YbYOmBlRE7vmpr5yK8whQpN7axKSBxuJGfCRQfncikONDS9gu/iSr4UbNHHeHIPF1PTmJN2UpPOA"
                        "LMLkO16/42Nrs03jmqRQGgON7LADeOPUlDTrVzK+/d/J5ok2IUuYBxrYd7cOoklCCugsaz+wCl0d"
                        "AalWzWfsxC98drfdgFYcx/LxTe277+/KqA2AOZ6ZXp+mE2k2BZaxmDrrdU+7/4Huhi1aNph1TFId"
                        "vJ9YvaHTiAmatWjc/WC6aWIAIK3V6Gj7gdWt8z96+ycv3P8Vr7/pifWjNMACRBCsuRknO64Y+vFV"
                        "64RYkKYJQ0MjA7Xaw1oTQQEErZVmszOZqKmyjaeftPiOuzaNz4zccnc2ENOLnjvw678mrUYzY3IH"
                        "kQJkgjK4m+qdt2scst/E8GBXK5aS1o/TLfdmUjbMcDWHFl3wxf/86vtH3HDzHX+/7cmPXfj0X137"
                        "6J9ui89pNVJt1rxKFhYUeGxYHf5cmky6IAarhJt339ed7ElAJVk2d2z07/fiO5c//MWPPOMVb7xz"
                        "Rq+IpYgkg6QgCTSYxP7PEGk6OdiMM80ibj6+pvfwKgka0kh0JqYn16ZpN00jQI4NTp71xl1uvm2y"
                        "m8VAb7+95/z5bxuIFoJVht68oemm7CpQJ82mOvOJmgBb1JnjbUiw3vz6k5f9/s9PprzstzdOv/bl"
                        "S/fbnW69byaOGhlrYXiEiEDQSsq5l3zlP//zvh2/vnL05n9t+s/90R33rp9MRyM5mqU0b1QsHBV/"
                        "/UdXRAtUkjCQsRbUJTH/hhvWHPz8JcY8B/mR8LtBnW8FEtj0yuNWXnnNKil3uuKXq775iaevXLrm"
                        "8XVKRgJgFoJJTU5sSHsy7TUBsXTe5KtP3Ptnv3kC1NQAERPC895Ce4eCM0ot35lZGjepVJYz5KZ4"
                        "UBJhhZ+2+sBMmW3HhW/dyyi49etA5lgnMfKfMYf5K+AjrikwHUsd4OICn8/EANgdWFX4PDjO/uLQ"
                        "/vTqxU9dBT0Ptpmx2bCWz5QZk9JIQ0CkveTMVy175nOjOY2xVnvr0MD88enogk88hGghtNKaWjEd"
                        "9JyFkz0ZCSEEkRx8ePXGdVuNfu0sXqjf9pqlSgwTEAm1eWr4oi+v721RAPUyvcv27Rc+Lx5sNFij"
                        "PdC6+W6+575xRgQ0KZt606uXHbh/PNBqjg52IzmycUZ+6FOPClrCSAAaamUvOHDx5s0yakASNQZG"
                        "1l+xbtNmZTSH0qrVWHjd3xq7/+zhSz++z8vOvD3TwyAGS9a60eC4QZ2EWceCoexIa6U5P7eZDWUq"
                        "gkwyvWBe9/l7Dp/x3sfAC2d605//9n0vO3a73/59jaIV4NTMvgNgFwKapmrHlYMvOYSGB1pKc7Mp"
                        "732I/3X3Zi0ISFln7WZr8+Tiz1z6n3ecsXzfnR8YGtFf+u7EnNF5Ks0QLEgRSGvr4GjNI0PyiEOX"
                        "dZNIkBIyS3n00Sc3bVkvAVbQrKUQyy79cbbLiq0fP3fnt33kEUELI5dRgUBSpAc+e97gEDcjMHhw"
                        "cODXf+488EhPNFgzQ828/fSVa7YMDg3IVmtmbGjhA6vxma9tbDe2m0mejAYw3WEgAgni9M2nr9xx"
                        "+0T3ZoYHGmd9eNXqrU0gVSpjaKABoZKe3H1ltv2K9nkf/TfrlZu2jn/7J/951Uvn3XLvZiWWikxA"
                        "ZAy2uSg0Ihnf8+DQSW+697hD5+/zzNEjDx4cnTP8vZ89cvlPp5jHWm0wsumuZhJEGTM0E3QG7s30"
                        "NEkAKZDCRktE5lgjcikuhKA0SfffjVh1L//VY8B29z8xee0f7j/xyNFPfmOTjBeAoBQPDyaXnLf7"
                        "ps7AQEMONjojc5b8+Z+bLv/FhGguBStioUsZ0Cos6R9zvpLoTI5iSQrlSmUp0HmzgRvnLKOq3GC7"
                        "Od/PT4W+WsGCc4YLyGzNCexAt/hshUJ+kZW+XDmIkdyklRdGls5KB6/65h1YuQHFbDf1hYYo5QK4"
                        "IM58u0AooY0ss2ZXFNNt/9r6yz9zROOHHdw+5Hmjr3jF3xHtFUn0UhVH2LCVzrvkP5PZcljtujGO"
                        "RhtNTmYaA7F89BE+8733JLRMWjREojkWxRESNdRqXvnrqS9cuREYdbhuNxpjzArQJKObbln/m5sE"
                        "IX7F4e19nzHnlFNuk9E+Mu7qTMYxtkw2z//EvzdOznNBFVtkPCwbkepmgoWQyJgH2tt99tsP7bz9"
                        "6MXv3em8j/5T6R3AGQma7sWdFCu2i26+r4toCCoBQYgoS6EVSwkAQoCEAECSdGfTKw5rLFlKRx7c"
                        "aDQoSccENr3gWUPP2UPcdE8viiNmBTtwRrioVrtx3Z+3nP+FJ4ClPq1FIx5hKKAthEgzTTRy5XXT"
                        "z9x1+h1v2+8lr7gpw3LWa5yu8yMEf0BVI46e3IxzPvLvyXSxiQghbG7E8+JIJYgjkQqRaN1ttrc/"
                        "95MPXv75XV97/Mjtt60WcqGDTEMMfulbj/3mZulm1sYlhmU8mnESs+hx/Ke/P3H3YyOC8Y4zF27e"
                        "uOE9H1vbaj1diBRobNqcbbe8wdwRYi4w9JmvPsKUDERbLr1wl2abeVwBWqlMKwVkkgZZbXjVsSPz"
                        "h6aOO2x4oN3rdYdHBicPe8Ho0y5fc/9qFUnokORIa9ZE7Z5e+YNrxn9wTSoxecDeqz79kX3Gt/zn"
                        "57/Ptk4LJRrz58ZPbkooApSCMDln1Mplzc2bzJQcBJldWjY2kImFZfyYeeNpJ4yMNcdPOmxkdCib"
                        "SQbnNTovfOHSr1+xfiqZByIpGplq/PZPTz6xRZGe+OA5O9/+jyc+8bWJ5sD2UBocMSkvMZyDUpYg"
                        "PlzB8VFguARsG/Jv9UkgvMzXwpoxdmbNcr0vVrW5vLTKQ59zMFylZM4fgN8xY8NHwYLhUhcYUWbS"
                        "vFSsLLJd9XHQ1gMvlmTYLR25EchQLomwOSSPTa7xMNsUs++Gj3D2B+Gx3/HjXVwLMA3cfq/62x3R"
                        "n28fOf9z62+5s/ehdz5TZWuZBEhoikAUDS5FtFw2txPN5dRcnmEUSpp+aMnUmB/Hi6J4QRQvjBpz"
                        "BBvgJZEQrSawJGosJLlExNuRnJ+piEUEaKLh2++P/nHnwM13zT3nko0PrYkuPmcPla1mihgUscg4"
                        "i1rzgPmisUjGy0S8SHNLm31CUUQikiyU7jVai8+98N4ddxw993WLJ7ZsllFMEprb192w7nWv3gVY"
                        "2+1kmjWUSDrTQ42NK5en9sAOsNYKECqjdrNz7IuWXfunibH5ywdHBkbnj8WDi/7yzw1nnrwD8wRB"
                        "+LURG/YFoRExDQBL4+ZCES0UcjGi+SkLSQ1AK4qZiLkbt+Z97nuTL3vDvx/bMF/KGBxpmwXQOYWW"
                        "D8yoSQ0SzQUQy6N4uYyXc7SspyKwAkAkyUSYIVHxgrMuuPuUE5524uGDW6emI2FSNpPiBPE8YIls"
                        "Lad4O4qXq2gopYwRRYhIRDfd1bzpX4N/u3P4zPc8stOuK085Zlm3u0FLgFo/vXr9EYeumD+8vjMz"
                        "mUFMJPMnZrZfOxElSggrFZARZYqBLE1nli/ovPCA0auv3zp/4YKhodbYgpFpPXT7vevPePki1muZ"
                        "tI1HZRbaZMtJd1o2naVrgOGotYAHVv7lX41rfvXQAfstAKYnJ+Obbpk4+407sn6k22HoSEN3OxNz"
                        "R9a99IhdfvXb1SSGASEo1iDmWKUiS0WWSpVGJOIk7e62fW/Xneb87ubJxYsXDgwPLJg/9sDGxprN"
                        "nZcftUClE6CGjGSm49/9Pbvh5tYf/jn31LP+c8Dzdn7B/6e2d425dbvOg54x1/ou+3Z8znF8IU5b"
                        "hYTQhOCIkqL2H3FQfwCqqKAQqWqEBIVWQKClaavQxCKy2phEIY2UBNOUi5QmTaClBZoQ1CCKFMni"
                        "B8Vuage3SbCd2D7O8bnuc/b+LmsOfoz7nPNd3/dtm1fn7G+td813zjHHHJdnjHl5v/X+xdtPTkjX"
                        "ps5zf5NiDukkz0b1DHaylZkqtPO1iYhsDYDFuUeSWWbCoKt6RdPzz5J2hy4P3sPglezMkh5oSG0p"
                        "xtReodGjyIwhGfADORFmld1GWoDL2liCiOK9emftdIJyEbcavAK8CFvUqltqzu7x88+dt3Zydo8u"
                        "r37nh/7SZ376J77pX/0Dn/vr/+urtH/uhPYPHp5+9YtfOt+f7nYHUNsRX/az1958BOx2u8M7HnKj"
                        "66sus06aXpDllrvz0xff8eSFhy8/fPikM+0IDfTqW88/vXoeaI8e0vPPnzRqp/dbv3zfn/nQr/6N"
                        "j7z/X/n2N/7mLz3enz644uvzs5OvfuElvr7YyXkxBMb5q2+98xrne3rr/H4DnTCYiJ+03/En/9zf"
                        "++//8vtfuPfq5eXT3i/2Zy/8lz/9m//c+9/7s3/paz/4w5/+zBd2tMc/+01P/uL3/P6//r88/rH/"
                        "9g2g3d9fX5xcAPvLp0//yB/cX/XrP/uDrwAv+nrLd5x//hd/6nf9vm9+/NF/cP/k5AycEAPa+Qm/"
                        "652PX3z4+fsPnhwOByLa707efHL/7Yv7wO7+aX/79Bpou3Z45fGj3/7k9dnZydWBqV0/uNf2uw6w"
                        "r3t0p0KNnzuh9774yvn5fk/XIOxbv7i+99rj54CL1nDv/gnhAr2fnNz/3Cvv+56/+Mm/9ZNf96l/"
                        "+KUDXzFdATg7O33vi6++87mX798/58M1iIlOXnn83JPLe22PFx/yO59Ho9P79/ubb7/3T33/r/yV"
                        "H3j/x3717//Krz8+O3vH3/no4w/80ud/7iO//3t/8OOf/NT+munFR5ff8QdffM97n3/r9dfb7kHv"
                        "X3ruHPt2BTy4unz8x/7Io4998u0PfeRLwAkg26SufuHvvPQzH/l9X/ezL/365672J/dYUAoR89me"
                        "3vjQ93zzFz77a//FT3/2C6/t94d73/R7nvwL/9I3fviHfosIu9MHP/qTn/+vfvSf+Csf/voP//in"
                        "PvuFe+e7y/f/bv7gn/6n//bf/c1f/vvnZ/fvX7z95vnp+Ve9yC8+/MKD+1cHviaiHeGNt9599fRL"
                        "f/Lf+p2/+Muv/Phfk3PcJM1//Sv/8LMf+jPf/Dd+/ldfefurGq5PT56+87mzLz5u5+fPffalww/8"
                        "2P/zoT/9dd/xH3z886/+Dto12xERy4MnJBH4KNsmxKpvmn4Ka5LuS1U9PS7bdUmDqC2bWS+aNqmy"
                        "WQlYSBjTcNkWuH1JcW5kphQKVvRm05NDr/QvVwOEeMVtzAxamfLqw8ruTJvVrDhwB2ai3WdfefiF"
                        "N9/ofHW4etDa9ctvvud7/sInv+uP/57/4//+5Msvt6ur3ZtvnX7ou7/lyeVpIxDtTvf9N1+998Ef"
                        "+sLTpydvXT/81OfOGp+b2dWR6L0D7bOf63/o23/XN3ztu09Odm23o344uf/CT/zsaz//S28CD37r"
                        "1YevvPm04/pwONCOvvT6u7/vhz7xnX/0/b/00U+9dXF20em11w/f9x99y5MLYrRGtNv1V58+/NB/"
                        "/pufefLgyfXJr3360YF2DY07nZ7Sp1/+qu/6/k/8p9/1jx/6OeFkT7ikr/ljf/bX/tS/+/yHv/cb"
                        "nrxxaA1nD+/91P/wG//d37o8u/e+iyevfv6Ne6+/fg/0xn7/5AP//Lf+1z/3MWrvvXd+zgdZbNVe"
                        "f8o/9z+9/IEPvP+j/+DXic7N46jX+vTndv/yt3/Nj3zwkWTZCfTg4cOf/YWLn/kf3wLd+/wrD19/"
                        "Ywd6zIx96+1s10GgwxXufeI3zp8c7s3iSA1vXZy8/pT+wp/7lusLed88n5/xx3/j5Ad+9BXQySuP"
                        "Tz/70jnRw0673g/nDx5+9BOXf/4HX/q2b3vPxfUTnDCIPvuZJ//mH/6Gf/EDoHbZe9/tGPvn/7OP"
                        "fO7//NgFn5/8o5fe+erFyx2XV1f70/P93/vV/Y/91X/0J/7t3/sf/vmPH/j+2fnzH/yRL3znv3b5"
                        "3X/in+lXl1f96vTs3ue+ePnvf++nvvDWO/Y7uqL7n/7io9fffgLwi8/tv/7rv/7DP/Lxtn/f2cn+"
                        "ms8J2LcXfutLu7/9v7/6B77t637ip36b2gMcDqzzGtfXhwff/f3/17/zR9/74e/7xsuLq7Y7uX//"
                        "0V/+b/7fn//lq5P9c53ptacvfue/98n/+I+/+wf/k3/q8etPuTXa0U/+zMs/9wuP92dfjWuA9i+9"
                        "3t/9rud/+IP/5Ol+T0y7HfX9/e/7oc+cnN+/99y7/tr//GsnJ1+730lscWB64aMfe+njn7j8vd/6"
                        "Nb/4d9+65pNPf/Edb1693Wl3ffn2yf1Hf/N/e/Obv/HV7/g3fvcP//hLtH/EB9k6XJTI1KdsIp5M"
                        "ktudQFWujzn1DMDXoHis4xOv/iilLKe3uMzcD6jIMR4AOrv3r8vXfhCbAkV1tq0KYI6XqRRDpg3Y"
                        "W0+sebbzYDxwyzSY/ZMnOg3HDXNsEvQWvR61S5OXcP5qmfPTp4eOy+tz7tSoo+2ur56cnbyJ/fNX"
                        "l2e7dnH/9PHp/rKzbIBkZhxw9vTJc513aE/37c3rwyPme6RtdVADE3U+2b95dvZ458cwEQO4uHj+"
                        "ydU9xuHe6eNDP7m6Pge449AaX12+fe/sgvHc9fU5tcuT9tr56TXzgexk8Y7904sXDv1+213u6cnF"
                        "4QTYE/bcD9T211cXJ7vHvL/Hh3NCB6Fzu758+eG9i3/sPXS4OvncS1dPrx/tTx8RQMT7/ePecX39"
                        "gFq/d/707bd2aOfN9ibrPG5//d79/ZMnp+ATAbICrokY7Y0Hp48bXXFvpOtZ2sXh0cXlQwZOT94G"
                        "cHV9n7iBqUskTiA+7Nrja74HPgH8mGEZsrbD1dnpl/atQ1EJA73z/YunL1wz7U6e7HcXl1ePgL14"
                        "CCb0y8f3zy8v+3OH3oDrk91r98+viZvsHiPwoe2eXL5DvNHpyVtPL097P2vUuHMjXF6/8o5HdHH5"
                        "6Oqw29Ge2+7q6Wtn7a33vWe/P6FXXz/89usNeGEvM5+Ek/3j6w4+PDjdXza8/fblGXb3iBnYAQc9"
                        "7rm/ev/e7u3L+91Pu4aoyO76GuDXHpxfvesdxI1/+5X92xdnJ2eyZr2h8eFA/erlR6dP3vWu/cXV"
                        "1ee/2DteOD17ofcLOTjohN56cPZ0t2NZ+dy5d5y+ffmI0Zhfvb6+T3QKD7WZGZ36m6fnp5eXDxpd"
                        "3Tt9++L6wfXhlJiBRrvrq8tXHz3cX1w+OnTyjE06lYAtk+03w3hlC2I63qD2TpYlkue3Bxdl1eal"
                        "SI3Zdpr5JNpgQIYrQxIzWFLhvfu7ZLA6uHuXfPcMA+Au51P1obbBcFgSvVvHdN7KyjYjoItkAnAk"
                        "Va21E5D7sz5SYnWxxpToIALvxPB3bpBpRGodOw4RAGR/MzFzk6PHKY5MUyPILOdA6JGadgQKA9wI"
                        "wAHMnVsj9pdrMHUCHQ4g4iZHj6J1PXyjk54CwI2YsGPq3V6Sae02omavp3Yu8452hwOurjvAp6e7"
                        "1vhw0O3Wna8IOwIYvTPtd7uSmVBPx4fDYddO3B94mc6duRETo1uWQia55d2oBz3+mLsda2c0yVJK"
                        "ezF6HlMxVHJGpdEgDBEDdQCo6SuwlI4dEffGrUPWi9GuSyoG2i6Dd7ansMubb2zGGUADX/fDru1N"
                        "Ugm7HXccLjvhQLv9bk/gg74WiFvnaxB2tGNG58OuEYP00GFxkACIer9utI9EhnezcaNdv8bhmtGI"
                        "9m2/Ax8OGrMIy1q7ur4+XDGon5y0Rns7s1Tr77wzXdAERKMd+JqJG7EmSWIejUEtCUpruPZTQJmZ"
                        "aNc7WutJgH2Y3K9zmB4CIpRLilTDHRNsGkY5lUdkk7UCIiIm9k9SqCr7tvEKGsDc793f0+n5H5a7"
                        "3HesRzqQha/NDo7cgWQPzYxrgm6fQGh2OIHtuaH0X2fuBLJTvyVRZ9YdgNTDw4pWuMEaYOSqq2ng"
                        "rRTUeIn9d5yqXLbCTUvKgfIWupO8no6ZdvAISkWgEXMDHcB66qbVKSfTE/dOLG9aupajAWR9YLdl"
                        "CaTHcvmcbBl+c1ZKoYXNHsYxNH/nExFqO8yxNtj5rUdkwjnJMl2VDghiIoAbM0OOqWKA/A1gWdqg"
                        "cyBRocH7zrzrjUkI8RdbwXKkMl5iBiGQDQSydRtMOjMjU2giNH6cmYJGiNGX7JIKLQg7xfu6O5oa"
                        "gblz73bWLluqOJaCy+0UNwW7kRIgkfchNZxEAHbAFagBO/PMaHp2qJ4Qx9hRJ6KDvLOemYkOdqip"
                        "hRHkGWWJBC2/a6cTC7qTF3g2K26IAQDLCRlJ27OBYDPuZnqY7SSMUUJYUJsMPB0QB7p4DW3ALSYM"
                        "qs0hFcwgf08KlGAG6vNAZX584PN7+31kiGyBKMQrqPA0zTXZmVKM0rHaOxUsl2MiR4+5G03LErt8"
                        "JBq1J04q6lVjbOd+ft79vBcggKCHrhHxzkxnOB/7r0FPVuHUNBnq85kCo0HPwlLra+cQOeGi+j1J"
                        "hr57QiZSWOTPRtM67rkGD9+DDjNcQkirh4G4TSclpvc4INTSq/bORyR5gKEB7Sxkb7QG+JDt0kxu"
                        "cZrNH4nsdhCIZU214dugqiGG2pWkEbO9Y6SrPBghsoJbXgIAez2EJRIMEZgN8mGKoAZ7O5BCKyTs"
                        "REq6Oi0/aJe4qU2RcjYKpKkAMUk6jgoQx8yLICR5ljvRzqlqMMMCAu/1DDXdvhcHtHOXZfQc8Qvv"
                        "OJI+XY4kk8aJmhhIOT7NFJXsPGr9j1FeQaaEJvhj6WBVasA1LiTQpvk61AaY3HG3DLorWrhDM2Q2"
                        "Gtgp1jE7Z3/hjMwWKhPtoSXpmbi0j+QZuUg14bC9RiB5GDWZMV7JJJtXZ042mEZqIj+VQzxy3gSl"
                        "yYDVACQ3baIcJlJaZdCOmdOchZokK3hky2XjeN10EE8Fj3F+hKGuUg4H10kZfagZtYH73N+4sM3w"
                        "x9MH4cnH7ki8Jaf3RcDnJomrCbA9cKMQp96Ze1fRFvhWBAE+KKTiplpt4MG0MXkyqQ/uSFmJr2Na"
                        "R4Q0dmX2V90Uork2oXY88B3DuQGgtmT54ezqlckh5O4r2IIA0QMaxqt6ZchrA1Kmhs0OsJlXUqc3"
                        "1JC8NsspUWYXdFkAPNwy48K8I/KpK07VmlV11nEyLnFl8E6JgAycwz7oMIbngwQfVHhi/fLuU7GM"
                        "heFOT/4ctpOiZhlcYs4vUnXj3gMaU4qck6qg3lF+mS3LAE89kjefihsvecVN8SZQ4zpIdm3UzGQG"
                        "cfWUG1N1OV6V4wlg4TAnTLfR3wTqzFDmGkwvt3cIWKdn3L78MMBm+LSxvh0PolKtZDb1MnsEt9qO"
                        "LkXzuxwI2uTQFDEXIYI+QO7uRBmcpC5hvhkmO3YqBLH3Lm91zbFJZlpG5dZztl9Kf8L/sxdAZY7n"
                        "bqzXvMs/C+uZsx3jkKBSM4+SWVg6OQAGmCmWTBPbgQQZO+cHWRZ8M1CPJ8vipIOlW9PgBqGPih3S"
                        "UodsEeiNd0rHBz7UUi7QCvcDzXLFWXKOfu8AYugnM7JKUwizItQILLaPKkjfTzV0vnYy/K0JlgaJ"
                        "QjkpUuyJ7721cEHq+iA422BvAvapWHF6zmVzBWEFsvpVVxH2PjHRueFwLxvytbVCFVAizeO4tgnf"
                        "LTnasgotzIcN1MDgMLnV1ZugVJjJ+pNFTLrh2a28owPmgV3Z9nkn1IWa9Bj/SVb9ob7EYZgQ92Gy"
                        "unQpb1z+8s5oa6EPWY0ViiQsX3SMZCeWnf/pcgFgUgxBlzaFbfUBYA9BOJhQMIX2xQLSlbkxmR+/"
                        "DuZp+Sz0xT+cnOzo2uGorJpOSqxBMgfmZqKdJQPtjusOme4k2VALbGJvJKi5skRHQhADeTthfjD4"
                        "ltdoZCM5EghLU1R2Gm/ulTPC0KuTpr7U/Yn8Z3YhWV5U2MXm0QzBjd2NUy+SjCZOpBaztYJrrxrh"
                        "ws8AO3kskyQNdYZhmvgZwfeKxW7axnUuZARlX2rdC0HJj/iv5h9CpZ0fpmOoQqsdbLYCOXW5FECl"
                        "xLln4pugClzxyoK41MnMlYIUkqL2VI9eAsG8a2ngBuFx3+PthVhP1LilLumbDEAIWSTYbZY35Kag"
                        "9HJa0ySXnGI8gJpsrfzZirsX2pzGaxEUwzwVLBREYrWRNwnSOGbFPNm/6ifsdY26YABxrIG4sQIy"
                        "JhvtPMg0ROPZE2dJHoBYch6Emn2UB5Dmm2Aq6Y2IS3LVElBto23LFxIYzrzgZLAdKbhRt/aKHaak"
                        "OUH64H/MNeZEG9NifDNjpUydrUA4Uu/7QIBolNl3yVcFsYlN+kRuNQuTlaOibokBK4SrCAhJFrTT"
                        "kzKnqyQKE+yt1Y4xSK6N5fXvZmYLxrnlNUlz6kUyhCHjFUmE1Lolq5qZTNKSCUt6Zhvh7qpYfTL/"
                        "g0TAjKGcHsjKHs2wBNpK7bIB1HgbnunauCYREb6E6oZ4rMKgTN7AjdxtE2OPLYZ6kGjLrg7mF4OZ"
                        "Q0OzIHnJgc5cw0wzr0KeYrCK19UOpvYCA/hEMsEXwkbsAIcY1iT72jPptZ5ZHdtvlDnZo1V7J9Zu"
                        "JiwbGDeUzh2HBpSfUotpmuHia4Z8cEThJ/Mh93kU5W98mrKJs+jwAkKSI8XFkMsicVMC9Y3Z99QH"
                        "w8EmMrMIuttENT1mGvxudxZnZg7WZ4kREiXWiaLh3s5ajkvvbVDtbzOEYfalFg9qudRQtUIpil4j"
                        "TwoJCGLjhMVsDrcMDgySQATmyACSpa6E84knye6E0A7gjsxIZiHMPsNr8B5VnVUKbdRWTHYahkGc"
                        "pd0UPMCR1z+M2+BxKQbOB8j5UBCAkxRddvqIeEZY6iEYdQdyRjfE+pJ0U69w8wQdYgkwySg/ICUv"
                        "RxXRDpCmtZijABuOyZAgdTa/9sJkNBwgbKUcx3ziaDgmKhgaqJa+pxLBLfvVZLRAGA06DLbXTKrk"
                        "8LRKyh8GsJDbMqPtcaVtNiZjNUhz5vYU28QWamRROcY+atYMSbe0rXFKLuaeTE7y6CRRqWI8KO3M"
                        "4eyo8uNeoTC5Gnp9E5IMGzN0TZ/n7pNuDK0Pn1MB5Wd18PXZ7JSS+UsGPaOnAYU58a7z0aNZ1X0f"
                        "qKuOF0gffF67eFzmTN7Y69yKzUjG766CuY8DpqnGbtPxWCUws9NlvmjIt1SDbjeNGNmPkd/8DLhn"
                        "YGZk3Qt7Xylrw0B6ZShIpw1FaLbJ1qniJajgKkoBuw9brcfMrT1tSHuTiQUmSNPsg76JGtw9CoG9"
                        "wxrKcMl0iZN+G5nZ9c9VQ9SvGgL/VRnb3KZroD45rsE0S5jipiG7zVGpJovJaTTDJSTbseEkNwxE"
                        "Md/15vJ7wsIxcBQRNLK3QORbC+hojewNnMGotIh83ljHSaJKRmJ0fgo9oi1Xk7mnGS7FzfTo5FBr"
                        "QxOH3NrmH7wXx00VkgVc+pLcF5eoYZTZYc5QcYpd8uTEkpACVxfWQf/ui3NLcskxHZvYWmaUYj+d"
                        "q66jsMQL17Fe4c9McPRkcG7J9yMvCeDR9gm9M+8GoBQMyjfYlhBPuzQXDO592OeJVXlKQlyzlMhc"
                        "LTLNauHc1XsrurFTt/TAedRMMlwc2IrH4zA7aWOabe7glnSUJ4Z5beHws7PNquj6vNLVbFi52JrK"
                        "vfLB2DdUkoTNfY/LUmEgy2Sasqj2OhuFeAp1C0G46mzlzbSVXjLDVpC5hCy47cMuVBWlnbjqfS46"
                        "uwoavDmTBKdqrDwZGjYA5zkZ562ZHrMJg2daDsdgsu0Du+AliQrGzZqbbhKhpbjPOctAvMsTdTAg"
                        "b0NJOxQKB6tMS4XsS3LIlhQglhREGphZTsJq0HcjltbloRTAU1hwXd1LLoWog4ppRCu1BdVLDMsa"
                        "mfrvPWsm9EXtS5cl9+U1EM1DYyUi/B35rpSRSHmZTUxZhnFRa518JlGuxB/xz93OJJlJdWg8+kwA"
                        "1l9Oy6kIIFhWALrfLjgzSXDpV/pVJI1dHzJAYDCIqXn3XUMb7AXoiclCTT4iDQBxlzqzxbeniIlY"
                        "333jI2F9cbbYBQkOaruz+1deaXnJKerpTvoW6Cw82tPu7wFE5t5SUPNXN3S5vGUk3AjGTKXolPci"
                        "9w0aCTXnPTi2f8iz+QRzXndfFJsHjXB4ZVCA0u66YVxKVQMHUuAFZjvTnXWWkoDIrSeHYw8DtjnD"
                        "bgpZhnwGH2JY2iuJnA6qsfdHADAN8/Ocoxuv3/UChh1GnzwPv64acygBpMh3KC6WEGrFyDB/iVQ2"
                        "bFZYz9o4UAc763b4QSsL2Soa7i43zUPhNCJKV7LCm1cuUyFD+UmX36FLtJXyJDbWqaWbVG6UrsxV"
                        "ec9WDW4U7AMpXIebs7k1GMBhorJ4NY+X2t0aCi2BuX3oLsbTSGXNlHHK0UkZ4vCmkzzXngQ8GYjM"
                        "+YREsMsnJWoX3FnwS2/urEZyI+V5CWax9WthYmYiGxIeFarSv9YXqDgtCYODB3XO9oNGFmJkqle2"
                        "YYZhmUA62V2M7Eiw3N0d86Sl9mwxz0ksiPJvVkO5ZzDEtJfdCSfh3rIhrpmcRVbuJBGfBXr+GjUk"
                        "ibFKKnonvRbjFN4eB1Afe1EvpbNIu8GzcBXRovFhhN8DYUA8K5v7DFjpZj87u5FHHDP1FC42Okg0"
                        "dyNLeb6d8XLiVPi/+uzQ0w4a5SThC0xuhYzU8p+3bOjDamDOamblqepe2GVmTvVgwCO18tGXe/1D"
                        "W7UGCD5oepps4KmhfPFGit1FhhrlnUWUFGTcmQiiFkvnQBZWlw7mQZmcbkFPg2xPuER1IB/gJ7i6"
                        "2/kBsD2f7BNYqhscCJzNVGC6zPwxUbN10nLkQ3PYZUPICeCIsfS9+FabmoyDuuE8ooYwmRWKr/wV"
                        "kBiaHPWcVliwLzNx4+JcydKfUJ2oMm/sHGheP9l0re4DaOoSloii88HMYiy8tNaDGFUkeR+7nkXR"
                        "rfTW8CGOvmD45IkoH8KjuFgPsCk+5kAjSTV7ISNaPCWtFLZQ58ZlIjizmvQ0GpLjmFuC6ixJVbKJ"
                        "JqPTWRetiztXHJEm+0FhjZjZJ9pctoPtvgWAyTYPMGLLqp9N4pFpXg6poMmoYSLRwehO79zagAw6"
                        "6eT13KPM07I8Rfac5jEMP61MckxAXLKydhMxt5MYWJ51jpkJFr7dMOQwvvhvuv8e5gbDHsO3XsZI"
                        "HL+yu84UcCR9/Vf5ryXvxy7fXC64v4LTKt4muJaNOnvhzIikJjTTCWxC3+Vd5pG52/zZwkcIQtg0"
                        "MXXKXpIe1mdAE1OdeuWeOgFk5sNMxDBArA53qjN3IeNNVntGMyVcHx9+dzppfIorD4/4iaB8vmNV"
                        "q4yZhoQtzfqzrAdhwtz0GMnu+TMGZJ4ryXX7cHv3XdRzWy5UPFfIALdh8Y+tFSgbPKfRX9WWYCNg"
                        "yVPqpousldOBcT1Q6AhAtJiZeqdZxhW+JTWpICvp9hr3IJSa04tUqXEyz/nYEti0lFfRrA7bxj/F"
                        "Si70LtlumwaI4drho+hGc6Y+9T/GPz0+WJ+1kiBGruAg09Vls1aOkB+Rz0lu3K9irogXoHrqYwk8"
                        "vXdFnbIoH3EeHIFAABzndgDYpZZu0JlE3zmpEwr5sbCqA5xM1W9RzlNycyDHe51Vfb7MrugaYbnp"
                        "+2a8VK62dpATw3NJnh5NJE2dTfafEczOM7BZswZWuwbFf9DkOtk4CnGu83MX2IXFmZC7nPolK1Ea"
                        "9yZnedq1476TFQXZrzvVzBKEOcCPaoXhiTfOB58gkBqKeG/5Zvh7CQFw9yktgHpKbjJD1yBadZ3t"
                        "K8rZWJYgFJhLumfMYQOqio6RnTI9oMHKZrkdFaCQ1/tFCxwLX0O4ZbU9gLqPF6MDj0insE/Zol1O"
                        "tqmZ3jqERmex8iVDTFsunfRIHEe7pfvK9RXu44z4VZw1RNCMhCbzWIgUGA7sJbRRF0WwQxZ8fWZu"
                        "yyWB5EeDw8wMIgXzSmg6CmawO4WfANI6XqwG2vlj8lOcAaRTVmWuauTPht8j4wVj+XsxHKxrFGCS"
                        "GaZt6KaZj1KReW6fQTrkZynC65F4+Stf6+7xsSMqQzrPEC0vDfrsfvLQ24OAZVfkZCQ/2yvV1Kts"
                        "6wGJlthiV8PkMkW8O9D0yTidbXTJg61gBijhKGZm7hXzsZET8Yn1LVjiDbDBNo8f0yCFF5qM9ADU"
                        "HQKUUAiTiJRGyZ9la5HNubnNUnOQu5w/Zwcy/OR885KDhqQusbn0QH9GfwShzooBHdvN0sFhOjnr"
                        "OaMwlry8aXXmklnVznxIqeiiA6l83qATwprCmenZVMPaDGDMeG5qoH2bez0QXYLTadRcBrzywltY"
                        "EVtEX4QqDxMWNGd/WWQ7d8p+wrCqsSxb83tjF6l4x8E3z9Jb+u51c2mLfARLd4iG5hMuk9Qw+1Jl"
                        "p1aT9Qlax2Pqz9AagQ7UDq31kT2Tm+HpziBK+eU0MJlHZaXsoorhjYZGSGn1+5L0nna/Aa2FrEyS"
                        "urhp/kcXH6lgDYuMvWTpCLLZcl64q/SnXNrmpjOp9mt2lWOx1PuwMma/R26p70opoVzhyIo6iINV"
                        "JbukeYM8wrtUR4xZl1RF7hRUrK2zNu7+9JE0eNbYuL/Cg8xlStFpnsXUBsVXe2Drqlwt0rtF7VRH"
                        "UaNk6WLblMeV/u/Y3/I5yQORin1qjleYyp1EMj2KtS2IGygfR4TT3ngTafaQjJLATw9OiViEysvU"
                        "MCdtckOGKiUowiD/deYO3oH3rCf9IkvA8Ow8dpmvzJz3Eop1OBDt5jEdNMoIIvdvCnRkOOVwKMj8"
                        "NbsDcOjkHsN1ZoXo5Qd584VoH5MuQj9mmAVFETmKt3d+NJlb6RwBIxBmZXHRJMR2p+lUCPt2bqtE"
                        "4ajYqa6AnwlAa/nlj91YaY9ZQwPoMu5n20PIq8M5onUnXEVUXzDZCL25l7EDzbjbIkcPA6mn2Kfk"
                        "WVirZZ/b4oSjsT2EMdzkBw17f1mO+nUO2CwVCZ7Q2xyWd0Omxxane208L5i6lZQGwvoXu6NCSx5q"
                        "bUpqMM2XH8YSbZSI3tdFe53uRJsDP6uBHDqnA0VmDrTULmxoJIZn8I6ZPaEhi5Y5bTZSA5r9LpHs"
                        "tyed9Wsm4aKJ3XukxFO3yXoie4OH56kSwWXn6cTwxSgkvqU8WSrqxijTnuOCqGWQnIJ4YWxNYGi2"
                        "7pKTs9dM0VQDrJV48FhWPLVLZWmejbiBCDedQedQ7SSXBdBFl4ILVL1NtuzS0BThwk7ooUEnDV8Y"
                        "6CWHTlEGAOeX7ADJb6Ue6ee0GInRWV5802R9gztwLiJb2CG9HZBsDIqLVyYxgZS0q0/dmwYUA3gM"
                        "uqEn1uubBJYGZeCG1zyNnS8yGPNLQZ1cPCjt9jVD8oTIRqpqSelNeanKrFAeW5AxQIpTBaTzEJhf"
                        "QlIEggdLIv+UOcb+mDMZKniNKFbb6B5jnZT0GQzWUBVsTo6GtW+O3K3cyKXhym5J62Tdkebrvtxu"
                        "Z8zmjju77oI15q9p4JOtEhxQ7FEZodlLW2Fa+ZOoY2njUFmfeqRx7aiNZjxiCN1MGkk9ToZIRiJH"
                        "cCYSpV1XU6cn/A5b73Z1c8nM1dC0TJIDLHssOBk8zNxK0bR6J9+XzuwDRBqvLky2FzIih3WYRK25"
                        "huXu+LoYN8vuBmXz5sLIaHa/plmLRA3uM+vneKm2rJPQpdj0e0iLcy9zMv/Ezofa/TJ4tlmn+u9s"
                        "L6RsJkrFyNufCabKE3ZRKbGcPWVDPbCIkthnU8jcu74DiN3fGxPIvKrKqt10eoooDXJFq5vDHbFN"
                        "0pO97WE23ejs/GEGMzUQk+FJM67Z0HCaWkrwgdwK2OlF0g2pQZRCm04H47mL8xcKtBxBFJNBvv2Y"
                        "iHyEG6nN1y4WtynANUxrGkMjG1kICqoiQdwzW6V5kB/LAAl8SIkp7kK4Z+8lIlsjomEkAAmd2EJO"
                        "Y5ZqIwfmd1LJsUoeCE5e3DjJgllCbgF/BQ5Z5MJWOxH5QacdPb+PVTmin9m1SXWTAF2yqSMCUxfZ"
                        "5UNEAQGS+BnbRc/Ibbv3iLLVgLE9Um4+lSleR9+kOUyDlhGfUFvSQ5ntbQYcilvNQsK6ptRjvTHC"
                        "UgYVAct2zNhgWpC33TnUQuSS2WkP8dPAViQu58iaMhA7TuHTaDiS5GsHY52TGW1iQo95VXE6iXNK"
                        "BjVTcFgW0okR9WdbxAu3fdi4iIi5dwXnadOQdq41s85dWi+G2Qx9jESdgMj3878sr2aPq0D3ZM71"
                        "Cbd3VrEbvug5mLjLf1Ibsbyw0YjlNAZwL+AiFQOfWeMEjxDD3XNKxSbBLUjGuCH4OaVC83NmnYO5"
                        "WlXeGlrHUYozjzrmHzP92Yfah/DVZEyoHnoKN1gnr33mxdYTsIyPbC1IYsvhBsLjshq0YKxhERDK"
                        "nnYhi82EcdjQOjkr4IFNVpm7SVRtgtnUdWGthIbFQNuTpMQUWcWkYOQxl7G2WkAfI1Jax+VgcUmG"
                        "PlXCPtxZp2CRdSoWvTbmkomiwRwbSholK/o+dJCR9lED1OC1wlOl6stDbcl8cJJzq8/acfq3rmw9"
                        "9Y69TjLdgTPXe2znTtihGdUZ6m8DiPAPqf8O1lXWBuIcgkGNAqXuZffIhumsWoE/ZoOMALXeVthH"
                        "wp0YOQf9p0z/3KNKZzjMbZZDUZ4JliELuF3m7BDsMWampjirtrsYxdlVOiJgd9BJYsRJsbk2FthV"
                        "L/s14CGbJgxdzhSW76m/rBWZWSoG35fhpHdS2Z5b0jVQxiPjvKKItOWFqJlcOP1szDbFmdSDBYdP"
                        "wTgQQ2wdGflc+iiP6NCM8YeZKneccmv07zayMALkBzJb0WlU/BG5+xVVM+wtxbFIhQOum6aImK7i"
                        "ZbDMEajlQxlhwDfsBCwAK1hPhr/YAU7Gzpsf+VY6RTp3AGA/+erk/XQ6QPqt1mSpopMJ6/q+W1UK"
                        "ki2oShmKlro1SVaDkj2CjS4bGWiNBLIp5gRBX7usB/qSv9XGnLqZNvmvuwez+JSA5nh7EKXBsWOS"
                        "DwA1VBwNuuu/vHHT0A2lNJbPRqkAiDJ5bTd6eGbOVieG302POkOflTTtynGsxLBs5iJ4IDDKHk9z"
                        "vmJevK2s/S60+upPkZ/4fThtUgJe3VtNIGLZuiyvcZVushGhb/IGN/cIlLgtsmvFV4rIPghb8pwm"
                        "tUHJpvdooo6vZ0sGTGTsRRJs81hwkzo4RX0k2d8IkNkCv3gnNvv6zFi1o62bRrhRcF8NVXAKsWD2"
                        "FxFFDepvAyuIgZHh7CgMZIbPqBpzDg70ExpgN5jGGoSfcJqthEoBHVrWvQwujON9Hu5ZXevYmInR"
                        "XpIPqpQaqMnPuh9jQ7l2iKrbNHO0wR8wd7LyXrPPU+TAyGmDMcpbjqLHQVOpcPxFpGoEHaYAirYM"
                        "c5gJTj0xGbXy5HM0M+7LN8uIhGdLbkHbY1tRY/YxHJ0qsNk15ZgOIqmARiQdciExHTNniKFOyqtI"
                        "LJo/xqgZDlDXlk8FMZ1mhdJqLpqX4iRLSdAjwTcMlgEf51Z4Ao5HiEySJmg5eg5z9jGsJlBkPPGu"
                        "RDve/VqPA6vB+YWVnIVwBQGR4UyGMKlqtgRRWfZfrG2YFjWXDYg05EBF8KHbsiS/mQoVdvmpamMZ"
                        "55s0FwaLE+6t1icoHTmRNDyj0zTq4tu5gw/EBx2hKJbgTwzDYMg4o+4QCxfKpJaFeEr/Dmzyr8Tc"
                        "RHuzoYySxhNK11DJdLEFYUOxYlzEz2X1ld5n/DwQ7B/8TA/jlYrfcXPLFh5SldbiDSrZLKIayBfx"
                        "jHp+db/Vqo4ED8KaGBIjxQFCowoZF7f6iSEOCLwPkOyQ0xIWInobIsrMpGgDZnlyFxZcHHpRsdWI"
                        "tlwUtQs0VDJyY9I4GmZIMwHMjAhRs5gVZ7zRBfswx4Buf8J3Fk9vAYGr8YhenRucR8d9Z3W6VTt8"
                        "aBaMzR90LyERpbx9BEE0kgQjqLzzamiAmXR5IWTpG9lWSnaX5XriViBRMngVHXibfRh2AhqHMaxW"
                        "IAPChSPVZRXAZX1pWshoHoxApo/j75aIW4wAjz9SgAnA81sG8+Td1A6YnTm52jT20Bfb1NCJzSEp"
                        "jazb/ygNWbd0ZLOBiWqjSw6aWiKGoaf80CT3zfjhgkGUgAyRvGukJRyXhUegMoDGxTqIljq/XS3V"
                        "vpiSOznxBlkCS6BLpOtoyRKJ0h+bqSH/n2HLWfkAorK8LrBeHnEDKd4jJ1THcfAx+b0SxeKTxtdj"
                        "VtHb4xQ0AQXOM8OW9bY0lCYLtpLEMzVAk6P+ivL2IsxEZDlYTffFMIGBFmNSlzoVynOoXgSY7ZAc"
                        "2IMzbBTrDCmVz8NyIaBU2L1U2JSoaKIpf4AIrWqJ1ej43woXPUkga6pQfzQigwbveu2rOwc9c4N0"
                        "8UlZa5tYGa8X1zrZjumpHEVaqmytjxZ2snFGardZVyIGN2q6FRSy+ZkBanaAr2NWA0ajawrWkWQv"
                        "PD8mzKBc0DXNbRM18gDM/QwiiyblxemgSkheWsEgaVjE3cbCtjcTLB05Hn6irZkZl+UU3kJ1P9pW"
                        "3knmiwmUfENWXcFTP5BaPc8P+MxjIB5yc5LCduMUh1U1GXCp4lyNRs1Opw+CGMJpGWWRmWr4qtg4"
                        "x0KidLo8e3FBTJNUWA+NYtU3BaSO8RnUenqQgUaIHLiDRGoUGkcEC8VdGLLmVgSjnxMScr3Dcp9m"
                        "FAB5pAPQflCtFJKwjkudRJ8dvj24KMDGL0o/ueFzKDd0wysc9NNkZtG6oxHvuBGDgdgJn+cKyjqD"
                        "ICZ9oOGpiVpFFysWQXA+93SSHIEP9pN748LJ8P5laSvcJBERurlCyVknD1GM2uBmOClE6nKoXCad"
                        "3LFTguGFEaZCw6hliOrTeLA4DiHyA6sQtVmFCd8Yn90VuZ3VnH0s2Qld9lBSGcKc4b12TaMfAoio"
                        "6QYmtVZGvj3iFhDcXVOMjdYNcwuzKPI4xeYvB1OW+KR8ldUFaGCT7Tya7H6GQ58LR81nCDm9d3Dz"
                        "kE7mXtN4AALMQc7VpO/jRJnzaabcBH7w6yp+/vqv4IwaE3vNV7EyqUuodnHrykI56bONqBULJVwF"
                        "O5l6qdOpH5UE+RMZAFNpTsjZe66OIRsFuJAGy6SVtEd64ffMYCTLUGbASnkXVVbZp/QcXLjdW5Av"
                        "nDEd0DUBySvAx9c7Q5ClkkT6KgRydOxowR6w3L+BIahwdf8sRescIsxUwS0s9JRMc5WDzxAfo7MN"
                        "zQwe4ic9Tcm4wbJNU05YLY63ynqHTiE07xmV3DYxHbxKSoYvLh8Ud0OUXwzBmj0zck3/k1DHiERu"
                        "2ABZFja1vSJ4eax9FDNZs0MdtAZAehFhlAlEJPWAiejQ0aHpS+FOev+F+Ui2cNtGnORjZ5sgMjlk"
                        "LWRaJHZdP9TVSoEEpxFUK+lixjrpz14+OytypNrL5mf35e7KyvkK1VUWBLSQhlLAEEIyagP2G64l"
                        "krQ++9CwDhuay1jTKVfEAiI26xzB4Gh8rXBhqVWedDCthxAqXafIvbf9n/tlGsp2cC2brppZ5I7Y"
                        "tNXZIbDYQcvZ1FGPzQA+sOKZe6eBvQSMyQnA02d+m4I5xm3blpAUI0slq59MGNkGV/06m81SF0mA"
                        "Rn4cS+W9d/omWKamnc4A3CC2tax9aklOErOrTwjl93/FHYJt6hahQinG9G7aOImJDz5UJwoqYa8/"
                        "zwj0UU5GdpDFzDGmOrteQEBVn8SFJGAtO1FN4RHsr2tQelZaIZZFJLEsjvjQW0NOQNuKCNLFDMw+"
                        "lj5j6DYokbqYp+K0YD510Xi4Ql6d0YiGNz8XULcEVsu60uMZpo0mKXsMHL2K5Rgp5FSgyV0Yuhat"
                        "zfvJkoItQOIaXYfUGit8UZnZQeeS9bP7D4bnzWV5kG8AhJl7Z4PiRtkSw+bMzo0cY/KZk/oTYBFO"
                        "dkpbNVdWOMJQFMs9qsiGaX4WAQ3ST2wevPreNGCqC8P96hepilJ2bwiRYZs/idPTFeUyOko4xrbB"
                        "oFqf4I9tbOqyXJUTeo1iTmT2uCYzlOokh/m1ZOztJVdUXVE44IMsotylOwkXMPvymeS+4tcZbTR7"
                        "XAaMfYdNNOU9JVLptZG1pWqiKd3GaCEM2j/jm6UyaSoTF/fORt2++qFS+1BF5WwZoQHLzfiob7xW"
                        "50bLBVPmQkPPq9V8aS1IjtpUz12cEll2t4tbMN8496jaa2nAF6i4+zSxjoVMsmGyM1WhZ9fYBMdU"
                        "fH2a2G8Pzpnl0Fa3RlJsCWmjznozelfXfalnCmYAMkEJBRCSkzGbDEmtyxpdG5UwYv7igly7fGwL"
                        "EaRusCv3Qw2o7QZLKyooDYd+yJ4VJmbpKywuhplrWJagN0E3BsZl9Bh5sX1AMMBBOiZiorvDZwUy"
                        "zl4jhAi2uQ8Or+3QWgfuPncS3fevKEoXQZP+5ILFjdkW1HL3aEDfeWTcI3X28Sx0haj9wobb9TEQ"
                        "kc7vhMQR26xDkgLlrJPtp5W4dJjVHlP146VeiDqwz1PFzuusD7OFQjU0HOhmGNHNmDE7In88W8Yj"
                        "yK4ZPpA/AnbViIB7k9FJvjgIS/mmCpQGqvy+e1+YheM0G4JykgAxqKExIttERMxUM5d+DFMjaiCw"
                        "Jt2dt2YR5GE5Agl5ni5Mw0R8DlI43eyhmdYh8ZGkW4ctNsEOYYS5EfnJR8xCBhNaK5WR8mUwlxOa"
                        "JhPSTtRZlsczRWCrTgUMgzMldzkM0wAastlaGBQBnlq6dU+VGSchyz6oB2i0zjBy9Fd6lAlwL0W6"
                        "3JwBajL0JLmAjAjEbqkp6ylP7+qQFW1WH6inkHe3EOQAZUnssa7Skqda4EpdFt9ZVxGTbLsh2wjl"
                        "YkoeT4AIzQ7I69Q92Qsm5i5rXQQOGrDKfGF1Z3UEb4NaBvvVWM9lj5CQjRdbxuVI7fnXJdrKteVK"
                        "sqnyceIk6wtzyeaZfXgVBLEN5LrzEL0nwPZl3R7uZQtbe6FowIJQSky26AkBAJPFrGEvIRFvuAYG"
                        "gsw5J95gqCF/zRI/WP5gKRuOOVqP4xLSdNYozfm5VEOJksYPXSxGc0DgtmyuCoDN95k3j1RmbiJM"
                        "26Dtdj/q006Jy9PQRroqNGj+GNQszscw+oN7HrhBluAWT+ErNzIrWqINVR285lkgx37ZDTlNv6OD"
                        "9UADUpvVCJ3RZR9b4jF55JLJyMrrnU3OAMlx+kgNSuS5MbClJL1rSwA1NDfcZINh8mHv7Rlg2cRW"
                        "+f5t0NBsEVDrv+lSLdXoIxSeJT3No1gTqqQPtMUgB+bJKCC71YEQjt9HzorVshNh4Aty5EfJi+gi"
                        "RoRpy/DTbdzAtDJHndFT7VGED1k/q3y49x6gEaUZ9yJ5SSUsTeu2K5Vi9q0zhXum5KGtQYhaPf0q"
                        "BIRjNzI8dEIBlaMXNJ9B1sRR6SLJHggEgSICm93KohA+pr4nZcZ6Wy3JgFs3bbUYBQLKZb17uEk7"
                        "8hDnr7qK0EySWVk47HPmkBpjnqz/0h9bGKiu0wWJDDWkKl0Z9MWLZrwsHTmIaJL/zavqLwHYy4Ss"
                        "Ccoa2qTaw4NVoVk1MHV+YH1GYVagD07bs6aSRGwkhyV2cxHJjJnWW1UxAKVGgOyAU0Q6PMkijVLI"
                        "mvxZwD3yJSs2ZmESBJN0gPRcJVg98LhPH5VLEXuYVnYRKeZA2t1ZsZ64jTQEiVryItkwMZu4tG5A"
                        "o7ypSfC8TIDqokE3xwTukifyJqTuLrOxROxnmcm/Xc4+BmSLGVFjn3V1m0aEIsH58xIRMyL/rbxx"
                        "9asldUxEcihvvvCxUTbLABERN3QdflrVtmlfSPbSs+44ZpVkSHwuo9pEsW2Tp3i7tZtfNODwhxCM"
                        "Fp0SnusZgXIziwcRuMV5W2k+2mpQOBA2nBV5gixaV3kXy0VE3P14S/ieJwWyYcuWPCwYY5ufEuim"
                        "iVXvQK60tdh8O8PF41dCkovC295pUcAjZwPuqXIQTaZkq0bnoCd05bmupxMyp546GYK/toCkfh54"
                        "IgPXqbwtuf68rI15wZmBpNvw80glNegQ4WrgJq5rq5L0WS005blY5LFeqpwJT9Cg29ksvT70Umvz"
                        "Cxo8mrZMXTOksEl/fF0JLwHUuQX6YXNCZgI3JHmiQR9mpDdARKukG9oHYXEakptfMGXqV24bSd2c"
                        "0sm88mRBokAmdtFZzsQWH/nMaj5fW1VJr2I1cCZi5aXv3IbjwMz9u9GedURmk02pE3kmYjzK8aq+"
                        "eJZ8xVZYwFG+BxtdLFQETU5gelYbI1igp5XxwIdQg5WVVFd1xDkEvLv7lTqopDoJ8tOSsEhez5DT"
                        "x0VNU/k1fG5kJBzgYIZFw0W2vJqeqbOVklVDMgNWpUB4ctf2mJkQB2IgaRMRSA5ECuWfHOEWhRU3"
                        "hJIOjxc2LibgBlNl92OlyPBvNEXlt6mt8euWGTliB465BADgPWx1EDn/kr10XeWjSHVw3cPN5a/L"
                        "K026Ndcl64hJjhCa/aDlRWge/HR1srBBt+Cq+lCw41gNAxPYgBPHs7qcIjm3eNY+eBf91CF2eDIw"
                        "qmkwpsjeWldQnF7Na4qxSkJhyXnFmS7KMJ6O07suDHU0dbtjLkmasYjNz2QpKg8izUdQZ2oaErI1"
                        "TZMYj7NOzY/8cpzlKUHAJjGxc9kAs2ajBUYO0xbRfVMAlqXSWoZJ8y8D81ZOPTO5aaeaRU2JRZAl"
                        "ABIgdi3uNcfyGXBnIuISnC0Cf6gZGb1d7ybaeRmA2k/JzGdF8kg82ymkO4Au3NF1zLMzG74esRhL"
                        "cIPkmqdnvf+8h8Wr2emPvvHWDS8L3KA8LjEblZtpMPZP9rQ+pnc3mJJ0TCVb00QNcbb90gPcHmxi"
                        "JcT2a3R51ddtlxWcVPM1V+W+d2b7SIa7KcV4MgQLjjlMPt6Ef1WzZapBRLagPTPEAsK7XuoTELG9"
                        "DTinRVSZ1PTd7KJaZMN2SfaontuTGbLwVYlLUwHJ+nXJL9U+GAM9O8lr3VbOI94fOeuR1CPvbZsl"
                        "xzQFoRI5H1/4CmyLvbx0euh4sZhj1LlJ7Vy/kzo9lH8yGMC896CKV4zL8nq8VU5rr25paFMrpR75"
                        "E3dU5D38mbuUWrmdHugAEBC756DC6/AXo1wOrBiomTkzApCbrrlMNhZ6A8zqDd11LmrecAwJL/Mo"
                        "fz52WUAXEnS8WkpreDWhuxgQtxpGf3bp0VUbDbEtZHufOKaIRRNt2HkFVAH48vTcBll0WkM2ioZY"
                        "270hLK98AAw16sktQ8ft3wQQVmtrQxHcyKwNyspa1e6TFtwgFrIQbENvFs5vYsWMECp4D62aoUmq"
                        "P+aIg7CejqUlANjLGuVekW+mco4ObuxY9kW3UFT2F8hY94hV3NUGQTvsDhC2bpSNWd6K93CTTtdM"
                        "ZjR98x0z9CBXlp0MBKKiinM3lXozbYNDznfSU87kNZ2FY9NUrLhc0bRmgUbXOm8I26MSQgORrVcc"
                        "hnX2N/qB3Gxk4SZ7BKbdMfupEhUH5iaeJd7YHQxqKWf1koinFmJfNy6zmnIwtq1l7V6dQ1G5GrEc"
                        "e5BmXVkL2FRDgt4x1sw8bEc4wluZBJVdvTYo+saaVGGeBxcyOsuq9DQWsihcVS4RsHBpKr5bQ09+"
                        "aDCjI0I5EW/yNWdHuhhaUJZe+8C5MPjrhZyYZiGLEB8nOwlrZ3g0c9XrATrRfngJxSa5z3ZtoehS"
                        "xhR+QBMuc6JN7m8C6CXLy/7pLlTl5IQIiruzXPdNHHgW/oxKsgohF84NmDqZ9yc0pPNIb0nDbaBf"
                        "uhymyKBYbNhmJpCZM7hpWJC/TR2q2Li5Z4bv7NG/nSX949rIsl6DsvkbdF6c3rBfqnY1ZbvuRLcJ"
                        "7fxqD7hEDbBtAAdx86YpButCKZUpd+0ocM9k3GQ+VVjdcxV+GhoaCMYKQ32FLq10NFhD9HfLWGZZ"
                        "CW6tDDmQrI/oOAqMqjhTFwLVikJGj7QcmGIBJQaTAYauMblNRwa6j9+p7c7Ccat6BWwuM1DHrrqC"
                        "9A6jrM444RgAZWpNZJrknH1SLOShG0G2hGy3NgNPZgcFNvpkNksfieaZIWuemBg8pu3dLtiKWT00"
                        "9St78SZmYSL0DnthXSaPqJrXPkndAOHz1+Xwka3w9HjCnpWfZVQ2QtH0OVW+LMzTvfUizYHa4Zel"
                        "z8596R3MvE+BVUMe0en526vEkZI2VWTpUgDcQDtw9+01lHbYEe0SjDQUqolIljkgzx8zR4bziBBm"
                        "jObKJJNy4ZYZsh6e8jkf7OfY6B+uPd1impn+XNZfc5KjTjfHYxeya5M6D9GWLhG8JbYi2TvuiD51"
                        "PTqCmLHKi9lFQNmilJaZp2VcgklY17vH7F4m6zJb+qlV7rErA8WUVvgV8sNS3DjYODE6wXIISrQp"
                        "v+xIs/a1CQOLs43xINERZB+LxNXMgepTHdMEo9jTndHb2IegBiFJ543wFQD0m93lUYMvUkBKBz/H"
                        "hfydxGGxIj1yG+1uAh1k6joG0yn3N2xFatHsCdtPZKI+ZjCHhMB0KT7fm0zcyks/G+BaXpESmQD3"
                        "cuQ8Ep6ESiR7Ry3QOO4Up00exM2h1N5yq3JOQFq+diRaWAmZ/7R+ZAuc9m3/E9J5q0vhpzOT64nP"
                        "VikAEKOPp/um7wv3LPxPZyppoFqXAiVnr/Idp/fkxuA5TbmRLVrxCpoXdxThsZce73eD39VzwdYF"
                        "vM67hjo+Lnl0Yj+FynMSiDH+1b49oySLLW4YZNsuX8+cSfUHj14MauAsQ2mzQZXwLbhE5o1uz1I1"
                        "FxESUuxszJWmJ0yBvcC64qVRq+MxVGi0lwGzeopcumSlRy27cXRT0nxtjZCZPBtPHqnyoxFnz7eF"
                        "hJfu8ZYlh6eGcUmf79D9FB2E0qytITwJTcP9eCZP4XLL1LmbKVKh7kCGnS0WIrIVC1HxKrJeMNMS"
                        "z1X9yY2mP+sZljH1YVI1wA3mUuNdbZagvLUFqPmWhcE+Vu1tczW+NlAGMnPVZCnqPKLR0x2gaqt/"
                        "XVbinEt+S4Zcqyr+LNMfyxoUp6XTGtQXeap/y9Vsql9mh1IgNqZHupXCNMvONSayVTvJOmR8zvKG"
                        "HmY0jt26gIoCAWgkW7cgU1PPaLlSb1jWD0orMD1is5NI/bnxWob0HD1d2/E7GbKhZHqbZLH4WxGr"
                        "r2NwdRU7xY0kgli5G+tayqxbi0Pfp9hSpQAK0pggL7aB7hYnIpKzB7SG3LVKB6WcmrwcJ81bsS0W"
                        "ZrZDidJpNpknqHI78NM/LVgwEaMcUACTkt61KJfyHhd7TaX5oddOqjOkaVg7BFaOAYSObnOsNO8g"
                        "XoLQwXaHNT+K+9Jsg4NiZUkyLC03tQXrUgagy7kP8dYcImLOq2OWT26RuDGWrMa9/kwJDZIue1E1"
                        "G54G+dQPdE7IV9z1Phjmrf0Md7uSC3c9s33a1hMd7K9QdJyvmwF5ovOuTyW7qU9tQcLVUwvvlyiY"
                        "H5stmNlETavYXApkxWaPJxm9d8sbLXbai1TZIQIC1NjwhKuJmQyZMGS3EUyjQVDqsqubYSzdJGBq"
                        "C4mJdR5eQ4e1Z6MAGGlu+jjmzRmSTKQwgSbKpcPajjkVVlOuLqIUTq3MPrWERJsSU9S9Cs+irdte"
                        "Ruc+Nys57EETZ6x4PFFHaYHlYiLbQL9ZdyOnWquhfj+rMPFUD0dXGRE7a9LhNdySG/PlYqMytLG2"
                        "e9nW4JTuZFkGCHbEjtzklI5Vfps6B7LX1bIdoiSwLA9pijW0QoStGem0myByM5ec8zgFZA4jvqSm"
                        "OLlDqZgjR3Yk8FEsxj7m9tVp7GplNq7BHwwJd49ugkerkGWpWaP5IMRGzgrBKiYCIirnWlWvDp7Y"
                        "oGDW7lDkxRJozj5iwc/bBa23VVIrtbc5Y0pdWredqo7wAZMaVEE0TM+em1AzRtCzcM01FFUZelv8"
                        "quwqpeYcY+hMuXzdQg0D+M9BUL5prQOWxVW7dYSZG3o+V36slgWd8W02ZLwQd97+EH3gyfj6zTX+"
                        "H+kD6Th6naIyESl40EDI8qSqRQJzTOxhxJhuKI5uti1R4U0a1jhxWxIcBOjrZMWiNG8LsOhHid+x"
                        "HJ5HLK+rMrgAimRTN/KCIZ2Kvzx+2Zlb854kpBrGpTyrAR3FUm62roG0jUKIRBEGsvX9K1yhZaDB"
                        "JFt+mOpwDNUaEpS1wgDscGyLeyrlDk2K5I90rqia2CWvl+n7VIiSh8ERDvKNGpxaG3XUgBC45zGr"
                        "/cxtVctlgNOXomuValvuiDNngpc+QZc3fLkV3h30xfgthGZB0bJyQyxHb85y6a61EEQWYol1sMMt"
                        "HRkdXJKg75eJall+IdYDX50EHTsakuLezamjte+2SNS5pcA+FI/jNdJEfqidBhNZcqi6T227Bxd4"
                        "C1DMJK5I/bIuHSMfhWQEFyl7X5eelHDlhMIfqj7VyatZYsOWjWVng87p3yPXLKL+SFgnWb7jSfdF"
                        "CmnGpVCcOeKFGWKoTwAC+Ggw3RUrT3z0qsTVM3PvuhsruTs2nibP7KFhImawDnNolhEvVgMTldwl"
                        "jT80ujT6Rx4sMMe4XY5muDUNc4sTqCy/bgz3trQRZFmTPqii1QxuRYsm35a9GlL4lI0N2V89Ya9N"
                        "PV+QJChDg0Ty6E5+yiJkcMT/GEOQltKmaWKeVmfdJtJZsm5eCHpc9uZrjvvyndHf+FM97mdw7b4h"
                        "1a//+v1lZ827LPq7FLxBu6eq7uDCibC3V8suZoKOxAU1/zDqpIV6+tIOsi8iTkMNRKTZbI6t6dF5"
                        "tsV1KnaNbekQiy3pcmLykTWTxX4PsY/HF1tSOBi+zVg1sWLL/m5TGFXlhgANeIfzQ3JDQx1WVf0u"
                        "j8Sj+rH3te4tUWHyQ/7SBFXm0A3o2t8SPZHpEvn8i94hsyAWmhEkuVJWro/Zk0ldU2Qg4E8ETk0f"
                        "mwqaKVRS7fBjEy8G5GR06ZkLDfNCAW4JlrNqPBvUcotPGJNiuczaFGr41pC7mmyE57Zc94kodllN"
                        "4DoYrpOubDBiTQ/zZpcT9+Yyy6eYGczxmi/tUzbG+d9E1q0soq+49diB41m17sY7TzCMaim2zM/w"
                        "d+Oum0ub6svWdJ2xmDdYkFq5tQjeWM/w+ThOOe6uCTKb0yI4mlJa0xO5bmD78E+I3G13Id8sJhuW"
                        "4JEWyVQBgDgSq5xZlrUc1DZxQaqiJOIuNQyT+ViTcz/wx8lYYsD8mdU+qa0HPD5V7fO5dF2UTUQS"
                        "uhbFI3/cvw7XLUXl2YzUsh6T9eI8lk2Ye4iHwfCd2UZ52BRKxll+sgdHT59aYEnzEe3C8GwktXMl"
                        "a1JXPV6WB2jv9sKij8UMxcbDi+btk+RlRWLc346A1igbnUMJi5oGbs1ORRDdvUXf8oguTAmMxYPf"
                        "xiSOc4H5WlqorQpvedn5dvZNq0/nvd0QtTGDeuDam2OZ2+ph/GXYiLBai9oKacDV5f0xNrCsJ6/C"
                        "kHNp32bca2uZgE3Gjlh401mbB/QDkMuQOfbQOm92eDMxX74LzFVR8Au+vHZuNJoG1FzbIFnY613M"
                        "OAsJf5WLbQ7EEy8Umb6RLbPpOM6BOxp0BrBPGTQncYw+lthhKoZsluZKjFWeaCeFWoCtxJLJBw54"
                        "T/BDsRVp3RLg3fE6boxuX8OWnXrW+inbBG8qfr35cckoYcW2hTCl5IV8paE56wWzK8REjVsdHfYI"
                        "ixpyclgcZDnUKJNwvHfPIgXOS+8D2arWcLUJRxiIHHcnbROzCXk2HrzhymITCeabdIBikaAiBlj8"
                        "rsjEIjtrwisd/B+ls8Ds7FgGky8t/sr4v+WjTkPqVwOwr/vKlwH7+soxrUQJDoK8wYRfoOapuc2y"
                        "s/MIAAtuCA33N8i4EPh0zk3UTfH8hMkqK3Pwe/tql/VsQZ7BhGU4tpRmq2oGGpzHcjvShIURmv6o"
                        "NY+0pUHvRs8uP5RSEg70oh04So80KAEHI5l0+01Xd++ZEAbs3cTaN+/dcpSdV8zd/Nfo0odH8oi4"
                        "5S9ca5nmIMSNvNvoLb3w2SpHLrJbm8NSf1m+MOi3lfxhXY6gGDbYSD0ZZKXIPzgM8MRKyIMdSG1L"
                        "I9oBbJA5pkkstzNed+p11QK2xDpCslS0mq90f5bGkpQDYMRLn3S3h/y7wplscBUIHqVqiexmK/dv"
                        "3fnj5YdhHgzNlkvcsjtzi8fNXy7/lUpzLFuhOPhFu0i2LAFGQbXXkl7MJuwGa84+0W6lK29J8LMs"
                        "Yyr1MJCsVWrOXd46xcbMWcGAbMh4Lj9/Xob/LoyW5FFVnP3QHPjIr8+MJ46E9lnSDCwDA8TYXtp9"
                        "pMWEuwdpH0XSGCIL6DIoCwq3KN/6adll4SHF8d8ONUIU202VH7nY/jN+atKq0JQvIkIKEfSJZNdT"
                        "0bL45TYhwI3Kf5yDt6uKb0nM1nUTkVp/YuSijhlZzK1sFxYClA5d4Fy0zb1cQXOJvDXd8TlFHJB8"
                        "r9pKKml+s2F36SADwzqDNT0zn7dH3xkuFav8un2/y0V2Es7tr2cRJ67/ua31cRwEoPZdLEWf2qXK"
                        "AaoPSGxEft2V5uW15VG2y2MPaF6N7awvNT8rC51dXOpwk1+65bHIXvPnTyXwIjfkjSmd0yaD7Ng7"
                        "65K+dqv3LBYKB6CUr9vbLFQO2q/eo23keIvrqDUcyx79enMTiSGUeyF4mIh4XL6rMULycrO1qrYA"
                        "YDmEh+GTLJIkAIE1NmSLzVNtixONjhpizRR44onNCQ8wrVxLeZgMtOt83CRbOpj5MzdRf7JA7FYu"
                        "tojQEY0bv05RWEsnWzlVzmqibIkAsL2yQ80Z6XkxxKS5Yjko3NC3QUjLAS7hyPErP3IcC3t5DNJC"
                        "zOj7tZMbH9A7tyJUIVcFTJZNd5NHtDidliTJAUqhCpLmHMtebxmLW3vasfLj1ieb1y2Ii1GaF19T"
                        "3zE5wxsovNM1ANh42zAsYCPi7gcktClWurl2342syhOZWiG7W3ULw3fEIsxNDfbgRqk4Eh/NsaET"
                        "xhp7jmHLVMPmTwMNA8FHPOtA2/AgkvjpszwVg1lfEvfDJl0TgFI4b6tnKRR4YGwj++0oQ7Y6kmsb"
                        "eFKFLdY5hYu1LUaSw0IKaL8srRg6EfTUjhHZ2VYl4WdMVi/iK2me5doyxFv0zqbqRibciUu3BF+3"
                        "r+f2rS+MKcd90sS37fYwBagsuHvYEjy0WhwcbCC1VY8YE+aqpirfGAvPFiFnvrYuE01xsXc+HXto"
                        "faWTX5ZyOa4sNx2I+B1ty5/KI+FBlf/qsY+yVDaDSvHkj+e84rErYbQbTPP8qP07eAvsZ/SaTfh2"
                        "AzRzDQGdfOUsIIaxT3Evw+0RyTtDgYNJYDPDmhLEPnGYxX1z7NNOox2UU+kAk5WqTJGF01yYnjsL"
                        "C5SmLRyl5q2rWskSm9xYfnWVDk6wIqFrSYQTwI2oN25gFy/yuuxcDdkg1VZvVWBvzTuQSVW8JXes"
                        "LPvm5BSprLrm+36akVQIMDyO1K8BT411+k+tmc+PyXnTrohUmxwC7TVDbgY/2UMJI8bbpSpOBdrY"
                        "T17VuCsuiei6zqEqdk+v++Ec0UhYTta/WXdYX2bDtj1X1bIj5eO0j81ZHdK+jO+2Aot88xaXV9JY"
                        "d6nqSvewUFH2pkn6pS0js8lZ1VHOO5zrQWA/L0BlD9Tcyu0By7NCmwwK16b5mar9//0SozPG5Cl/"
                        "zLGUNK4xVwKyE504QfQoKb6MY1DdHU/pMwVWAFmFrKdSFUQwbcr1nEAS3DWAWnEAAPnBhFMrU3Ij"
                        "8IaQ1eV0YVGMTOikJhEcfKUu5uOzLrMTUsL88fpVR8BBMw/qKfXYEl/d381RF6md1CMVM53QXxeO"
                        "Yfg62Jbt3pcOsvlR1g0QtIetTraA9yvDeubZQGmaQ38yOSBdFqHNQ5ingcl6bdpXNrza7vI6crlr"
                        "/UebeJbagOIzNrIwiwrkUf8yyGwqxAkNpZ1R9TLsI+oQh797bkXJA5DWA1PeanUDmhzd0i1D9aOV"
                        "wkyhra50zWS2Ze/MbqsB9berqpgpv3B6C0fcJg4dHyST/3UYscaPm7VNxmJIJ4n6O77W4CRVz6vG"
                        "bjMQ2ajdRW1zByUj18Cd2Y5I9pg2y8RGA92oXaf6Oc4W4NYh6Vt/xWWcTqJr0BQtixxzpFEcIywH"
                        "bLzyhAtVbUixoSHaOQxeePiAFQmbOHN6Is8PlfZxzrHAVv1+HQkH1uSJciXPNp59OMQRU536k/mJ"
                        "5vtT/FUXVSFiFFLlgUcI4C77hjUiAcmEXogEEXHXc7DYY5R0bFYj4l70gpn0dJeChDRzvORltWiM"
                        "2NuU4ziHEmis6wFN8IQo1CX5BDDHQQ/5+GlvcwYayiLHiYmqG/TW0QPbGeK5gxk7LyUqK68qIwF6"
                        "XDkBtqdQipEfCiZq2TtAzRginAHnprwjt1HPLAD1l+CDW5JUxke5mbaSHL21V3uewtvbebClzS2E"
                        "KsN0YaF5Mv0ZkTTxGY2g1o+k8eWkHmsOqOfZodZkcKNmH7+ty4Y7Aha/c6TB7aaPmLM15QM5t3xw"
                        "JKDm7AoNttzE3VhrOMoTN4t+PoKBZeEPmJrk9dFlK+6QUhWCJsY7Ek+tzBfnjYMpVlhzhv2Y5BQG"
                        "KMaSu1PVgiUlTDZ2zZ5m87oTKqxQ+kidt3k8OQD7l9LDpG9X86PlxEx5fFzV78u4nikqch8J9W5E"
                        "e7IxuGuFWxRECgMuwPPDWgNzmt+o/hXUE9+GhynZC5ixv4GwgcLBWlnWYIAhWuGAlZC04nhzCRKP"
                        "N2eSrMJNtzlXnvH+LaVKTUlya6su6Oh1+8UweEY3pVeKUCw1FYYg/sgyPdZiFPw2NIJkSWJoIytO"
                        "uZt5gOTfjG3t2TUHALekiQnJcI/sknehmXvaNIWrtr4sVRdZG0DT0fIj+BrDIIDBTdZKymCmFRJs"
                        "jVLm0cZ1G6NxE7UuVIvKBb75r/Jnr2+s6Y50b9gDlVxZEqkq9/5gr/ez5hPITxJg8d4GyaBi3wR2"
                        "rbrUI8d1B3noRm2ZbLLKF6YqPTg3Y5sbjAgf7lVtdJzUyupuhMlP8jkCQIN1X77bW66BZiLqErQJ"
                        "JgIZYu6e7JhQhr13J2KErlV2qtxTkywg244WZzVn0HP7FOOyHIEGNVytFwatWTCvk4wnmq5v1W5L"
                        "W8RAN/3VFWQKL+1VDSqYs62ESfjESccxfCf4jKLkXO/QpOGHCpgwCOqGLWiH8CMiSNTBEgkOqBNA"
                        "2uClN5MBnbB5jYWxUNIYGvdAhU5dELZitb7mKxdOm4y2GD3a7I3BCH/VwpmnrpqZ8+apZAeFiOEd"
                        "n0Pf/BWBd7rIlvXXanF7t+lDqdWN9Rf99EbvTqcjvgHLIMuls/SuiuFO1PGIpjVS/fZTz3eOe00l"
                        "KWBRBqcSayYgAG9MEhYI+Ap5mw7UaKphk8zWsps9QaRNErVpqj0hXXaUg2Iv7ZgUk/B7H7O3TrCo"
                        "gM3bXEvlcmyVMeYz+6uYLjQJRpKz29PpCOvIU8LSjdxLVHVjc2I5qkGoKDqrwZxw2ao0U5+B1daz"
                        "2XWsAqVSs9NzIyVHLou5ZjKO48rhGhundA0P+s0j4zpUbTfv1q/bF84+3PSK9fQEwuBObd9Z9Nkx"
                        "RYpkkbo5pAFCaf2nMZaMgiWVHbzWosDKXErLRjkbIthin41RxBqjhC/ZtSV4TmTiABN1kJ0G/pW5"
                        "uLXSry3TOQth/jV/mEttCP9855iyZEqWer18MIAqF320BvXr/wdIbv5QqTmmJwAAAABJRU5ErkJg"
                        "gg=="
                    )

                    # Salva logo em arquivo temporário para o FPDF
                    logo_path = None
                    try:
                        logo_bytes = base64.b64decode(LOGO_B64)
                        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                        tmp.write(logo_bytes)
                        tmp.close()
                        logo_path = tmp.name
                    except Exception:
                        logo_path = None

                    pdf = FPDF()
                    pdf.set_auto_page_break(auto=True, margin=32)
                    pdf.add_page()
                    pdf.set_margins(15, 15, 15)

                    # ── CABEÇALHO cinza claro com logo ──
                    ALTURA_CAB = 36
                    pdf.set_fill_color(235, 235, 235)   # cinza claro
                    pdf.rect(0, 0, 210, ALTURA_CAB, 'F')

                    # Logo à esquerda (se disponível)
                    if logo_path and os.path.exists(logo_path):
                        try:
                            pdf.image(logo_path, x=6, y=3, h=ALTURA_CAB - 6)
                        except Exception:
                            pass

                    # Texto da empresa à direita do logo
                    pdf.set_y(7)
                    pdf.set_x(72)
                    pdf.set_font("Helvetica", "B", 16)
                    pdf.set_text_color(20, 20, 20)           # preto
                    pdf.cell(0, 9, sem_acento(nome_empresa).upper(), ln=True, align='C')
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(40, 40, 40)
                    linha2 = []
                    if cnpj:         linha2.append(f"CNPJ: {cnpj}")
                    if endereco:     linha2.append(sem_acento(endereco))
                    if contato_fixo: linha2.append(sem_acento(contato_fixo))
                    if linha2:
                        pdf.set_x(72)
                        pdf.cell(0, 5, "  |  ".join(linha2), ln=True, align='C')
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(ALTURA_CAB - pdf.get_y() + 6)   # pula para fora do cabeçalho

                    # ── Informações do orçamento ──
                    pdf.set_font("Helvetica", "B", 11)
                    pdf.cell(95, 7, f"Orcamento: {st.session_state.id_orcamento}", ln=False)
                    pdf.cell(95, 7, f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='R')
                    pdf.set_font("Helvetica", "", 10)
                    pdf.cell(95, 6, f"Cliente: {sem_acento(st.session_state.cliente or 'Venda Direta')}", ln=False)
                    pdf.cell(95, 6, f"Prazo de Entrega: {sem_acento(prazo_str)}", ln=True, align='R')
                    if vendedor:
                        pdf.cell(95, 6, f"Vendedor: {sem_acento(vendedor)}", ln=False)
                    pdf.cell(95 if vendedor else 0, 6,
                             f"Validade: {validade_dias} dias a partir da emissao",
                             ln=True, align='R' if vendedor else 'L')
                    pdf.ln(5)

                    # ── Cabeçalho da tabela (cinza médio, texto preto) ──
                    pdf.set_fill_color(200, 200, 200)
                    pdf.set_text_color(20, 20, 20)
                    pdf.set_font("Helvetica", "B", 9)
                    pdf.cell(8,  8, "N",         border=0, fill=True, align='C')
                    pdf.cell(83, 8, "Descricao", border=0, fill=True)
                    pdf.cell(14, 8, "Un",        border=0, fill=True, align='C')
                    pdf.cell(15, 8, "Qtd",       border=0, fill=True, align='C')
                    pdf.cell(30, 8, "Preco Un.", border=0, fill=True, align='R')
                    pdf.cell(30, 8, "Total",     border=0, fill=True, align='R')
                    pdf.ln()

                    # ── Linhas da tabela ──
                    pdf.set_text_color(0, 0, 0)
                    pdf.set_font("Helvetica", "", 9)
                    alt = False
                    for i, r in enumerate(st.session_state.itens):
                        if alt:
                            pdf.set_fill_color(245, 245, 245)
                        else:
                            pdf.set_fill_color(255, 255, 255)
                        desc_safe = sem_acento(r.get('Descrição', ''))[:52]
                        preco_val = float(r.get('Preço Un.', r.get('Preco Un.', 0)))
                        total_val = float(r.get('Total', 0))
                        pdf.cell(8,  7, str(i+1),               fill=alt, align='C')
                        pdf.cell(83, 7, desc_safe,               fill=alt)
                        pdf.cell(14, 7, str(r.get('Un', '')),    fill=alt, align='C')
                        pdf.cell(15, 7, str(r.get('Qtd', 0)),    fill=alt, align='C')
                        pdf.cell(30, 7, f"R$ {preco_val:,.2f}",  fill=alt, align='R')
                        pdf.cell(30, 7, f"R$ {total_val:,.2f}",  fill=alt, align='R')
                        pdf.ln()
                        alt = not alt

                    # ── Totais ──
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
                    # Barra de total cinza médio + texto preto
                    pdf.set_fill_color(200, 200, 200)
                    pdf.set_text_color(20, 20, 20)
                    pdf.set_font("Helvetica", "B", 12)
                    pdf.cell(0, 11, f"  TOTAL ({sem_acento(selecionado)}): R$ {v_final:,.2f}  ",
                             ln=True, align='R', fill=True)
                    pdf.set_text_color(0, 0, 0)

                    # ── Observações ──
                    if obs:
                        pdf.ln(5)
                        pdf.set_font("Helvetica", "B", 9)
                        pdf.cell(0, 6, "Observacoes:", ln=True)
                        pdf.set_font("Helvetica", "", 9)
                        pdf.multi_cell(0, 5, sem_acento(obs))

                    # ── RODAPÉ cinza claro fixo na parte inferior ──
                    pdf.set_y(-30)
                    pdf.set_fill_color(235, 235, 235)
                    pdf.rect(0, pdf.get_y() - 2, 210, 35, 'F')
                    pdf.set_draw_color(180, 180, 180)
                    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
                    pdf.ln(3)
                    pdf.set_font("Helvetica", "I", 8)
                    pdf.set_text_color(30, 30, 30)   # preto suave
                    rodape = [sem_acento(nome_empresa)]
                    if cnpj:         rodape.append(f"CNPJ: {cnpj}")
                    if endereco:     rodape.append(sem_acento(endereco))
                    if contato_fixo: rodape.append(sem_acento(contato_fixo))
                    pdf.cell(0, 5, "  |  ".join(rodape), ln=True, align='C')
                    pdf.cell(0, 4,
                             f"Valido por {validade_dias} dias. Gerado em {datetime.now().strftime('%d/%m/%Y')}.",
                             ln=True, align='C')

                    result = bytes(pdf.output())

                    # Limpa arquivo temporário
                    if logo_path and os.path.exists(logo_path):
                        try:
                            os.unlink(logo_path)
                        except Exception:
                            pass

                    return result

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

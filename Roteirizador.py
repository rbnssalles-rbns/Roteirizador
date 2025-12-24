#!/usr/bin/env python
# coding: utf-8

# In[9]:


import streamlit as st
import datetime
import pandas as pd
from datetime import timedelta
from collections import Counter

# -------------------------------
# Configuração inicial
# -------------------------------
st.set_page_config(page_title="OptiMove Roteirização", page_icon="🧭", layout="wide")
st.title("🧭 Sistema de Roteirização com calendário e alertas")

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
MAPA_DIA_IDX = {dia: i for i, dia in enumerate(DIAS_SEMANA)}  # útil para ordenação / consistência

# -------------------------------
# Estado global
# -------------------------------
if "clientes" not in st.session_state:
    st.session_state.clientes = [
        {"id": 1, "nome": "Cliente A", "rota": "BR001", "dia_semana": "Segunda", "frequencia": 7},
        {"id": 2, "nome": "Cliente B", "rota": "BR001", "dia_semana": "Segunda", "frequencia": 14},
        {"id": 3, "nome": "Cliente C", "rota": "BR001", "dia_semana": "Terça", "frequencia": 30},
    ]

DEFAULTS = {
    "capacidade_por_dia": 40,
    "semanas": 6,
    "inicio": datetime.date(2025, 12, 24),  # Semana 1 sempre começa em 24/12/2025
    "rota": None,
    "limiar_desequilibrio_porcento": 0.5,
    "limiar_semana_porcento": 0.3,
}
if "parametros" not in st.session_state:
    st.session_state.parametros = DEFAULTS.copy()
else:
    for k, v in DEFAULTS.items():
        st.session_state.parametros.setdefault(k, v)

# -------------------------------
# Utilitários
# -------------------------------
def dedupe_clientes(clientes):
    """Remove duplicações por id mantendo o primeiro registro."""
    vistos = set()
    unicos = []
    for c in clientes:
        cid = c.get("id")
        if cid not in vistos:
            unicos.append(c)
            vistos.add(cid)
    return unicos

def primeira_semana_do_mes(date_obj):
    """Retorna True se a semana (seg-sex ancorada em 'date_obj') cair nos 7 primeiros dias do mês."""
    # Consideramos 'date_obj' como a segunda-feira de referência (Semana inicia em 'inicio' fornecido)
    return date_obj.day <= 7

# -------------------------------
# Função de geração de agenda (com proteção contra duplicações)
# -------------------------------
def gerar_agenda(inicio, semanas, clientes, capacidade_por_dia, rota=None,
                 limiar_dia_pct=0.5, limiar_semana_pct=0.3):
    # Dedupe clientes por id antes de usar
    base_total = dedupe_clientes(clientes)
    base = [c for c in base_total if (rota is None or c.get("rota") == rota)]

    agenda = {}
    alertas = []
    resumo = {"total_clientes": len(base), "semanas": semanas, "capacidade_por_dia": capacidade_por_dia}

    # Validação de cadastro
    for c in base:
        if not c.get("dia_semana") or not c.get("frequencia"):
            alertas.append(f"⚠️ Cadastro incompleto: {c.get('nome','(sem nome)')} (rota {c.get('rota','?')})")
        if c.get("dia_semana") not in DIAS_SEMANA:
            alertas.append(f"⚠️ Dia inválido para {c.get('nome')} (recebido: {c.get('dia_semana')})")

    # Agenda por semanas
    for sidx in range(semanas):
        semana_inicio = inicio + timedelta(weeks=sidx)
        semana_fim = semana_inicio + timedelta(days=4)  # segunda a sexta
        semana_id = f"Semana {sidx+1} ({semana_inicio.strftime('%d/%m/%Y')} - {semana_fim.strftime('%d/%m/%Y')})"
        agenda[semana_id] = {dia: [] for dia in DIAS_SEMANA}

        # Controle de inclusão por cliente/dia para garantir não-duplicação
        inclusos_id_por_dia = {dia: set() for dia in DIAS_SEMANA}

        for c in base:
            dia = c.get("dia_semana")
            freq = c.get("frequencia")
            cid = c.get("id")

            if not dia or dia not in DIAS_SEMANA or not freq:
                continue

            incluir = False
            if freq == 7:
                incluir = True
            elif freq == 14:
                # Quinzenal: primeira semana, terceira, quinta... (sidx % 2 == 0)
                incluir = (sidx % 2 == 0)
            elif freq == 30:
                # Mensal: somente se a semana cair nos primeiros 7 dias do mês
                incluir = primeira_semana_do_mes(semana_inicio)
            else:
                alertas.append(f"⚠️ Frequência desconhecida ({freq}) para {c.get('nome','(sem nome)')}")

            if incluir and cid not in inclusos_id_por_dia[dia]:
                # Usar cópia para evitar efeitos colaterais em redistribuição
                agenda[semana_id][dia].append({
                    "id": c.get("id"),
                    "nome": c.get("nome"),
                    "rota": c.get("rota"),
                    "dia_semana": c.get("dia_semana"),
                    "frequencia": c.get("frequencia"),
                })
                inclusos_id_por_dia[dia].add(cid)

        # Alertas de capacidade/desequilíbrio
        cargas = {dia: len(lst) for dia, lst in agenda[semana_id].items()}
        max_dia = max(cargas.values()) if cargas else 0
        min_dia = min(cargas.values()) if cargas else 0

        for dia, qtd in cargas.items():
            if qtd > capacidade_por_dia:
                alertas.append(
                    f"🚨 Sobrecarga em {semana_id} {dia}: {qtd} clientes (capacidade {capacidade_por_dia})"
                )
            elif qtd > 0 and qtd < int(capacidade_por_dia * limiar_dia_pct):
                alertas.append(
                    f"⚠️ Desequilíbrio em {semana_id} {dia}: apenas {qtd} clientes (<{int(limiar_dia_pct*100)}% da capacidade)"
                )

        if max_dia - min_dia > int(capacidade_por_dia * limiar_semana_pct):
            alertas.append(
                f"⚠️ Desequilíbrio semanal em {semana_id}: max {max_dia} vs min {min_dia} (capacidade {capacidade_por_dia})"
            )

        # Verificação de duplicação por segurança
        for dia, lst in agenda[semana_id].items():
            ids = [c["id"] for c in lst]
            dup = [i for i, ct in Counter(ids).items() if ct > 1]
            if dup:
                alertas.append(f"⚠️ Duplicação detectada em {semana_id} {dia}: IDs {dup}")

    return agenda, alertas, resumo

# -------------------------------
# Redistribuição balanceada (sem duplicar clientes)
# -------------------------------
def redistribuir_balanceado(agenda, capacidade_por_dia, permitir_mover_semanal=False, preservar_dia_semana=False):
    """
    Balanceia cargas dentro da semana, movendo clientes de dias sobrecarregados
    para dias com folga. Não cria duplicações (move o mesmo registro).
    Prioridade: freq 30 -> 14 -> 7 (se permitir_mover_semanal=True)
    """
    realocados = []
    for semana_id, dias in agenda.items():
        cargas = {dia: len(lst) for dia, lst in dias.items()}
        total_semana = sum(cargas.values())
        if len(DIAS_SEMANA) == 0:
            continue
        media = total_semana // len(DIAS_SEMANA) if total_semana > 0 else 0
        alvo_por_dia = min(capacidade_por_dia, max(media, 0))

        def lista_moviveis(lst):
            return sorted(lst, key=lambda c: {30: 0, 14: 1, 7: 2}.get(c.get("frequencia", 14)))

        def pode_mover(cliente):
            f = cliente.get("frequencia", 14)
            return (f in (14, 30)) or (permitir_mover_semanal and f == 7)

        for _ in range(1000):
            dias_excesso = [d for d in DIAS_SEMANA if cargas[d] > alvo_por_dia]
            dias_deficit = [d for d in DIAS_SEMANA if cargas[d] < alvo_por_dia]
            if not dias_excesso or not dias_deficit:
                break

            movido_na_iteracao = False
            for origem in dias_excesso:
                candidatos = lista_moviveis(dias[origem])
                for cliente in candidatos:
                    if not pode_mover(cliente):
                        continue
                    destinos_ordenados = sorted(dias_deficit, key=lambda d: cargas[d])
                    for destino in destinos_ordenados:
                        if preservar_dia_semana and destino == cliente.get("dia_semana"):
                            continue
                        if cargas[destino] >= capacidade_por_dia:
                            continue
                        # mover (sem duplicar)
                        dias[destino].append(cliente)
                        dias[origem].remove(cliente)
                        cargas[destino] += 1
                        cargas[origem] -= 1
                        realocados.append((cliente.get("nome"), semana_id, origem, destino))
                        movido_na_iteracao = True
                        break
                    if movido_na_iteracao:
                        break
                if movido_na_iteracao:
                    break
            if not movido_na_iteracao:
                break

    return agenda, realocados

# -------------------------------
# Interface de parâmetros
# -------------------------------
rotas = sorted(list({c["rota"] for c in st.session_state.clientes}))
colp = st.columns(6)
with colp[0]:
    rota_sel = st.selectbox("Rota", options=["(todas)"] + rotas, index=0, key="selectbox_rota")
with colp[1]:
    capacidade = st.number_input("Capacidade por dia", min_value=10, max_value=200,
                                 value=st.session_state.parametros.get("capacidade_por_dia", 40), key="num_capacidade")
with colp[2]:
    semanas = st.slider("Semanas no calendário", 1, 12, value=st.session_state.parametros.get("semanas", 6), key="slider_semanas")
with colp[3]:
    inicio = st.date_input("Data inicial", value=st.session_state.parametros.get("inicio", datetime.date.today()), key="date_inicio")
with colp[4]:
    limiar_dia_pct = st.slider("Limiar desequilíbrio/dia (%)", 10, 90,
                               value=int(st.session_state.parametros.get("limiar_desequilibrio_porcento", 0.5) * 100),
                               key="slider_limiar_dia") / 100.0
with colp[5]:
    limiar_semana_pct = st.slider("Limiar desequilíbrio semanal (%)", 10, 90,
                                  value=int(st.session_state.parametros.get("limiar_semana_porcento", 0.3) * 100),
                                  key="slider_limiar_semana") / 100.0

st.session_state.parametros.update({
    "capacidade_por_dia": int(capacidade),
    "semanas": int(semanas),
    "inicio": inicio,
    "rota": None if rota_sel == "(todas)" else rota_sel,
    "limiar_desequilibrio_porcento": float(limiar_dia_pct),
    "limiar_semana_porcento": float(limiar_semana_pct),
})

# -------------------------------
# Importação via Excel
# -------------------------------
st.subheader("📥 Importação de clientes via Excel (.xlsx)")
arquivo = st.file_uploader("Selecione o arquivo com colunas: nome, rota, dia_semana, frequencia", type=["xlsx"], key="uploader_excel")

if arquivo:
    try:
        # Força o engine para evitar erro de dependência
        df = pd.read_excel(arquivo, engine="openpyxl")
        df.columns = df.columns.str.lower()
        colunas_ok = {"nome", "rota", "dia_semana", "frequencia"}.issubset(set(df.columns))
        if not colunas_ok:
            st.error("O arquivo deve conter as colunas: nome, rota, dia_semana, frequencia.")
        else:
            inseridos = 0
            # Dedupe por nome+rota+dia+frequencia para evitar duplicações na importação
            existentes_chaves = {
                (c["nome"], c["rota"], c["dia_semana"], c["frequencia"]) for c in st.session_state.clientes
            }
            prox_id = (max([c["id"] for c in st.session_state.clientes], default=0) + 1)
            for _, row in df.iterrows():
                if not (pd.notna(row["nome"]) and pd.notna(row["rota"]) and pd.notna(row["dia_semana"]) and pd.notna(row["frequencia"])):
                    continue
                novo_chave = (str(row["nome"]).strip(), str(row["rota"]).strip(), str(row["dia_semana"]).strip(), int(row["frequencia"]))
                if novo_chave in existentes_chaves:
                    # já existe registro igual; ignora
                    continue
                novo = {
                    "id": prox_id,
                    "nome": novo_chave[0],
                    "rota": novo_chave[1],
                    "dia_semana": novo_chave[2],
                    "frequencia": novo_chave[3],
                }
                st.session_state.clientes.append(novo)
                existentes_chaves.add(novo_chave)
                prox_id += 1
                inseridos += 1
            st.success(f"{inseridos} clientes importados com sucesso!")
    except ImportError:
        st.error("Dependência 'openpyxl' não encontrada. Instale com: pip install openpyxl")
    except Exception as e:
        st.error(f"Falha ao ler o Excel: {e}")

# -------------------------------
# Cadastro de clientes manual
# -------------------------------
st.subheader("📝 Cadastro de clientes")
with st.form("cadastro_cliente", clear_on_submit=True):
    nome = st.text_input("Nome do cliente", "", key="txt_nome_cliente")
    rota = st.text_input("Rota", "BR001", key="txt_rota_cliente")
    dia = st.selectbox("Dia da semana", DIAS_SEMANA, index=0, key="selectbox_dia_cliente")
    freq_map = {"Semanal (007)": 7, "Quinzenal (014)": 14, "Mensal (030)": 30}
    freq_label = st.selectbox("Frequência", list(freq_map.keys()), index=0, key="selectbox_freq_cliente")
    submitted = st.form_submit_button("Adicionar cliente")

    if submitted:
        if not nome.strip():
            st.error("Informe o nome do cliente.")
        else:
            novo = {
                "id": (max([c["id"] for c in st.session_state.clientes], default=0) + 1),
                "nome": nome.strip(),
                "rota": rota.strip(),
                "dia_semana": dia,
                "frequencia": freq_map[freq_label],
            }
            st.session_state.clientes.append(novo)
            st.success(f"Cliente '{novo['nome']}' cadastrado com sucesso.")

st.dataframe(st.session_state.clientes, use_container_width=True)

# -------------------------------
# Geração da agenda (inicial)
# -------------------------------
agenda, alertas, resumo = gerar_agenda(
    inicio=st.session_state.parametros["inicio"],
    semanas=st.session_state.parametros["semanas"],
    clientes=st.session_state.clientes,
    capacidade_por_dia=st.session_state.parametros["capacidade_por_dia"],
    rota=st.session_state.parametros["rota"],
    limiar_dia_pct=st.session_state.parametros.get("limiar_desequilibrio_porcento", 0.5),
    limiar_semana_pct=st.session_state.parametros.get("limiar_semana_porcento", 0.3),
)

# -------------------------------
# Visualização didática por semana
# -------------------------------
st.subheader("📊 Visão didática por semana")

semanas_disponiveis = list(agenda.keys())
if semanas_disponiveis:
    semana_escolhida = st.selectbox(
        "Selecione a semana para visualizar",
        semanas_disponiveis,
        key="selectbox_semana_didatica"
    )

    if semana_escolhida:
        dados = []
        # Datas reais (extraídas do ID da semana)
        periodo = semana_escolhida.split("(")[1].split(")")[0]
        semana_inicio_str, _semana_fim_str = periodo.split(" - ")
        semana_inicio = datetime.datetime.strptime(semana_inicio_str.strip(), "%d/%m/%Y").date()

        dias = agenda[semana_escolhida]
        for i, dia in enumerate(DIAS_SEMANA):
            clientes_dia = dias[dia]
            total = len(clientes_dia)
            freq7 = sum(1 for c in clientes_dia if c.get("frequencia") == 7)
            freq14 = sum(1 for c in clientes_dia if c.get("frequencia") == 14)
            freq30 = sum(1 for c in clientes_dia if c.get("frequencia") == 30)
            data_real = semana_inicio + timedelta(days=i)
            dados.append({
                "Dia": dia,
                "Data": data_real.strftime("%d/%m/%Y"),
                "Clientes": total,
                "Frequência 7": freq7,
                "Frequência 14": freq14,
                "Frequência 30": freq30,
            })

        df_didatico = pd.DataFrame(dados)
        st.dataframe(df_didatico, use_container_width=True)
else:
    st.info("Nenhuma semana disponível na agenda.")

# -------------------------------
# Agenda compacta (antes da redistribuição)
# -------------------------------
st.subheader("📅 Agenda semanal (antes da redistribuição) — visão compacta")
linhas = []
for semana_id, dias in agenda.items():
    for dia in DIAS_SEMANA:
        linhas.append({"Semana": semana_id, "Dia": dia, "Clientes": len(dias[dia])})
df_agenda = pd.DataFrame(linhas)
st.dataframe(df_agenda, use_container_width=True)

# -------------------------------
# Botão de redistribuição balanceada
# -------------------------------
st.subheader("🔄 Redistribuição automática balanceada")
capacidade_por_dia = st.session_state.parametros.get("capacidade_por_dia", 40)
permitir_mover_semanal = st.checkbox("Permitir mover clientes semanais (007)", value=False, key="checkbox_mover_semanal")
preservar_dia = st.checkbox("Preservar dia original do cliente (não mover Segunda→Terça)", value=False, key="checkbox_preservar_dia")
executar = st.button("Executar redistribuição", key="btn_executar_redistribuicao")

agenda_ajustada = None
realocados = []

if executar:
    # Cópia superficial, mantendo registros sem duplicar
    agenda_ajustada = {sem: {dia: list(lst) for dia, lst in dias.items()} for sem, dias in agenda.items()}
    agenda_ajustada, realocados = redistribuir_balanceado(
        agenda_ajustada,
        capacidade_por_dia,
        permitir_mover_semanal=permitir_mover_semanal,
        preservar_dia_semana=preservar_dia
    )

    st.success(f"Redistribuição concluída: {len(realocados)} clientes realocados.")
    if realocados:
        with st.expander("Ver detalhes das realocações"):
            for nome, semana, origem, destino in realocados:
                st.write(f"✅ {nome} movido em {semana}: {origem} → {destino}")

# -------------------------------
# Agenda compacta após redistribuição (se executada)
# -------------------------------
if agenda_ajustada:
    st.subheader("📅 Agenda semanal (após redistribuição) — visão compacta")
    linhas2 = []
    for semana_id, dias in agenda_ajustada.items():
        for dia in DIAS_SEMANA:
            linhas2.append({"Semana": semana_id, "Dia": dia, "Clientes": len(dias[dia])})
    df_agenda2 = pd.DataFrame(linhas2)
    st.dataframe(df_agenda2, use_container_width=True)

    # Reavaliação rápida de alertas com base na agenda ajustada
    st.subheader("🚨 Alertas (reavaliação rápida da agenda ajustada)")
    limiar_dia = st.session_state.parametros.get("limiar_desequilibrio_porcento", 0.5)
    for semana_id, dias in agenda_ajustada.items():
        cargas = {dia: len(lst) for dia, lst in dias.items()}
        for dia, qtd in cargas.items():
            if qtd > capacidade_por_dia:
                st.error(f"🚨 Sobrecarga em {semana_id} {dia}: {qtd} clientes (capacidade {capacidade_por_dia})")
            elif qtd > 0 and qtd < int(capacidade_por_dia * limiar_dia):
                st.warning(f"⚠️ Desequilíbrio em {semana_id} {dia}: apenas {qtd} clientes")

# -------------------------------
# Alertas (agenda original)
# -------------------------------
st.subheader("🚨 Alertas (agenda original)")
if alertas:
    for a in alertas:
        if a.startswith("🚨"):
            st.error(a)
        else:
            st.warning(a)
else:
    st.success("Sem alertas no cenário atual.")


# In[ ]:





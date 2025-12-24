#!/usr/bin/env python
# coding: utf-8

# In[1]:


import streamlit as st
import datetime

# -------------------------------
# Configuração inicial
# -------------------------------
st.set_page_config(page_title="OptiMove Roteirização", page_icon="🧭", layout="wide")
st.title("🧭 Sistema de Roteirização com calendário e alertas")

DIAS_SEMANA = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]

# -------------------------------
# Estado global
# -------------------------------
if "clientes" not in st.session_state:
    st.session_state.clientes = [
        {"id": 1, "nome": "Cliente A", "rota": "BR001", "dia_semana": "Segunda", "frequencia": 7},
        {"id": 2, "nome": "Cliente B", "rota": "BR001", "dia_semana": "Segunda", "frequencia": 14},
        {"id": 3, "nome": "Cliente C", "rota": "BR001", "dia_semana": "Terça", "frequencia": 30},
    ]

if "parametros" not in st.session_state:
    st.session_state.parametros = {
        "capacidade_por_dia": 40,
        "semanas": 6,
        "inicio": datetime.date.today(),
        "rota": None,
    }

# -------------------------------
# Função de geração de agenda
# -------------------------------
def gerar_agenda(inicio, semanas, clientes, capacidade_por_dia, rota=None):
    agenda = {}
    alertas = []
    resumo = {"total_clientes": 0, "semanas": semanas, "capacidade_por_dia": capacidade_por_dia}

    base = [c for c in clientes if (rota is None or c.get("rota") == rota)]
    resumo["total_clientes"] = len(base)

    for c in base:
        if not c.get("dia_semana") or not c.get("frequencia"):
            alertas.append(f"⚠️ Cadastro incompleto: {c.get('nome','(sem nome)')} (rota {c.get('rota','?')})")

    for sidx in range(semanas):
        semana_id = f"Semana {sidx+1}"
        agenda[semana_id] = {dia: [] for dia in DIAS_SEMANA}

        for c in base:
            dia = c.get("dia_semana")
            freq = c.get("frequencia")
            if not dia or not freq:
                continue

            if freq == 7:  # semanal
                agenda[semana_id][dia].append(c)
            elif freq == 14:  # quinzenal
                if sidx % 2 == 0:
                    agenda[semana_id][dia].append(c)
            elif freq == 30:  # mensal
                if sidx % 4 == 0:
                    agenda[semana_id][dia].append(c)
            else:
                alertas.append(f"⚠️ Frequência desconhecida ({freq}) para {c['nome']}")

        # alertas de capacidade/desequilíbrio
        cargas = {dia: len(lst) for dia, lst in agenda[semana_id].items()}
        max_dia = max(cargas.values()) if cargas else 0
        min_dia = min(cargas.values()) if cargas else 0

        for dia, qtd in cargas.items():
            if qtd > capacidade_por_dia:
                alertas.append(f"🚨 Sobrecarga em {semana_id} {dia}: {qtd} clientes (capacidade {capacidade_por_dia})")
            elif qtd > 0 and qtd < int(capacidade_por_dia * 0.5):
                alertas.append(f"⚠️ Desequilíbrio em {semana_id} {dia}: apenas {qtd} clientes")

        if max_dia - min_dia > int(capacidade_por_dia * 0.3):
            alertas.append(f"⚠️ Desequilíbrio semanal em {semana_id}: max {max_dia} vs min {min_dia}")

    return agenda, alertas, resumo

# -------------------------------
# Interface de parâmetros
# -------------------------------
rotas = sorted(list({c["rota"] for c in st.session_state.clientes}))
colp = st.columns(4)
with colp[0]:
    rota_sel = st.selectbox("Rota", options=["(todas)"] + rotas, index=0)
with colp[1]:
    capacidade = st.number_input("Capacidade por dia", min_value=10, max_value=200,
                                 value=st.session_state.parametros["capacidade_por_dia"])
with colp[2]:
    semanas = st.slider("Semanas no calendário", 1, 12, value=st.session_state.parametros["semanas"])
with colp[3]:
    inicio = st.date_input("Data inicial", value=st.session_state.parametros["inicio"])

st.session_state.parametros.update({
    "capacidade_por_dia": int(capacidade),
    "semanas": int(semanas),
    "inicio": inicio,
    "rota": None if rota_sel == "(todas)" else rota_sel
})

# -------------------------------
# Cadastro de clientes
# -------------------------------
st.subheader("📝 Cadastro de clientes")
with st.form("cadastro_cliente", clear_on_submit=True):
    nome = st.text_input("Nome do cliente", "")
    rota = st.text_input("Rota", "BR001")
    dia = st.selectbox("Dia da semana", DIAS_SEMANA, index=0)
    freq_map = {"Semanal (007)": 7, "Quinzenal (014)": 14, "Mensal (030)": 30}
    freq_label = st.selectbox("Frequência", list(freq_map.keys()), index=0)
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
# Geração da agenda
# -------------------------------
agenda, alertas, resumo = gerar_agenda(
    inicio=st.session_state.parametros["inicio"],
    semanas=st.session_state.parametros["semanas"],
    clientes=st.session_state.clientes,
    capacidade_por_dia=st.session_state.parametros["capacidade_por_dia"],
    rota=st.session_state.parametros["rota"]
)

st.subheader("📅 Agenda semanal")
for semana_id, dias in agenda.items():
    st.markdown(f"### {semana_id}")
    cols = st.columns(len(DIAS_SEMANA))
    for i, dia in enumerate(DIAS_SEMANA):
        cols[i].write(f"**{dia}**: {len(dias[dia])} clientes")
        for c in dias[dia]:
            cols[i].write(f"- {c['nome']} (rota {c['rota']}, freq {c['frequencia']} dias)")

# -------------------------------
# Alertas
# -------------------------------
st.subheader("🚨 Alertas")
if alertas:
    for a in alertas:
        if a.startswith("🚨"):
            st.error(a)
        else:
            st.warning(a)
else:
    st.success("Sem alertas no cenário atual.")


# In[ ]:





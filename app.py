import streamlit as st
import pandas as pd
import smtplib
from email.message import EmailMessage
import random
from fpdf import FPDF

# Configurazione della pagina
st.set_page_config(page_title="Valutatore Sanatorie", page_icon="🏗️", layout="wide")

# ---- PARAMETRI E COSTI (Letti fedelmente dal tuo Excel rev1) ----
COSTI = {
    "base_cila": 1200,
    "add_pdc": 300,
    "volumi": 2500,
    "paesaggistica": 600,
    "statica": 1000,
    "involucro": 1200,
    "agibilita": 350,
    "diri": 1200,
    "mq_medio": 300,
    "mq_grande": 600,
    "cambio_uso": 800,
    "deroga_salvacasa": 500,
    "accesso_atti": 90,
    "sanzione_minima": 1032,
    "moltiplicatore_ampliamento": 124
}

DIRITTI = {
    "accesso_atti": 80,
    "cila": 80,
    "scia": 100,
    "pdc": 300,
    "catasto_per_unita": 70,
    "paesaggistica": 132,
    "agibilita": 70
}

# ---- INTERFACCIA UTENTE (UI) ----
try:
    st.image("logo.png", width=250)
except FileNotFoundError:
    pass

st.title("🏗️ Valutatore Rapido Costi Sanatoria CHIAVI IN MANO")
st.markdown("Rispondi alle seguenti domande sulla base dello stato di fatto dell'immobile.")

# Creazione del layout a due colonne
col_input, col_output = st.columns([1.3, 1])

with col_input:
    st.subheader("📋 DATI IMMOBILE E INTERVENTI")
    
    interna = st.selectbox("1. SITUAZIONE INTERNA (Scegli la casistica più impattante):", [
        "--- Seleziona un'opzione ---",
        "A - Solo lievi imprecisioni (Tolleranze < 2-5%)",
        "B - Spostamento o creazione di stanze normali",
        "C - Modifica o creazione di Bagni/Cucine",
        "D - Demolizione muri spessi o portanti o modifiche a parti strutturali"
    ], help="Considera 'lievi imprecisioni' se le differenze rispetto alla planimetria sono sotto il 5% (es. un muro spostato di 5-10 cm). Se manca una stanza intera, passa alle opzioni successive.")
    
    esterna = st.selectbox("2. SITUAZIONE ESTERNA / FACCIATE (Scegli la più impattante):", [
        "--- Seleziona un'opzione ---",
        "A - Nessuna modifica esterna",
        "B - Spostamento/Allargamento Finestre o Porte",
        "C - Chiusura Terrazze/Verande o Ampliamenti volumi"
    ])
    
    col1, col2 = st.columns(2)
    with col1:
        vincolo = st.radio("3. IMMOBILE IN ZONA VINCOLATA (Centro storico, Paesaggio, ecc.)?", ["NO", "SI"])
        superficie = st.number_input("5. SUPERFICIE COMMERCIALE TOTALE IMMOBILE (Mq):", min_value=1, value=120)
        cambio_uso = st.radio("7. C'È STATO UN CAMBIO D'USO SENZA OPERE? (es. da magazzino/sottotetto ad abitazione)?", ["NO", "SI"])
        accesso_fatto = st.radio("10. E' GIA' STATO FATTO UN ACCESSO AGLI ATTI?", ["SI", "NO"])
        
    with col2:
        dico = st.radio("4. SONO PRESENTI LE CERTIFICAZIONI DEGLI IMPIANTI (DICO)?", ["SI", "NO", "NON LO SO"])
        unita = st.number_input("6. NUMERO DI UNITÀ IMMOBILIARI COINVOLTE (Da aggiornare al Catasto):", min_value=1, value=1, step=1)
        deroga = st.radio("8. I LOCALI HANNO ALTEZZE < 2,70m O SUPERFICI RIDOTTE (Deroghe Salva Casa)?", ["NO", "SI"])
        
    mq_ampliamento = 0
    if esterna.startswith("C"):
        st.markdown("---")
        mq_ampliamento = st.number_input("9. IN CASO DI AMPLIAMENTO (Solo se Esterna = C): Quanti Mq sono stati aggiunti?", min_value=0, value=0, step=1)

    st.markdown("---")
    col_testo_11, col_input_11 = st.columns([2.5, 1])
    
    with col_testo_11:
        st.markdown("""
            <div style='background-color: #E1F5FE; padding: 9px 12px; border-radius: 5px; border: 1px solid #81D4FA;'>
                <p style='color: #0277BD; margin: 0; font-size: 14px; font-weight: 600;'>
                    11. Solo a fini statistici. QUALE È IL PREZZO DI VENDITA IPOTIZZATO?
                </p>
            </div>
        """, unsafe_allow_html=True)
        
    with col_input_11:
        prezzo_vendita = st.number

import streamlit as st
import pandas as pd

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
st.title("🏗️ Valutatore Rapido Costi Sanatoria CHIAVI IN MANO")
st.markdown("Rispondi alle seguenti domande sulla base dello stato di fatto dell'immobile.")

# Creazione del layout a due colonne
col_input, col_output = st.columns([1.3, 1])

with col_input:
    st.subheader("📋 Dati Immobile e Interventi")
    
    interna = st.selectbox("1. SITUAZIONE INTERNA (Scegli la casistica più impattante):", [
        "A - Solo lievi imprecisioni (Tolleranze < 2-5%)",
        "B - Spostamento o creazione di stanze normali",
        "C - Modifica o creazione di Bagni/Cucine",
        "D - Demolizione muri spessi o portanti o modifiche a parti strutturali"
    ])
    
    esterna = st.selectbox("2. SITUAZIONE ESTERNA / FACCIATE (Scegli la più impattante):", [
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
        unita = st.number_input("6. NUMERO DI UNITÀ IMMOBILIARI COINVOLTE (Da aggiornare al Catasto):", min_value=1, value=1)
        deroga = st.radio("8. I LOCALI HANNO ALTEZZE < 2,70m O SUPERFICI RIDOTTE (Deroghe Salva Casa)?", ["NO", "SI"])
       
  # Domanda 9 condizionale
    mq_ampliamento = 0
    if esterna.startswith("C"):
        st.markdown("---")
        mq_ampliamento = st.number_input("9. IN CASO DI AMPLIAMENTO (Solo se Esterna = C): Quanti Mq sono stati aggiunti?", min_value=0, value=0, step=1)

    # --- NUOVO BLOCCO DOMANDA 11 ---
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
        prezzo_vendita = st.number_input("Prezzo di vendita", min_value=0, value=150000, step=1000, label_visibility="collapsed")

# ---- MOTORE DI CALCOLO LATO BACKEND ----
is_pdc = esterna.startswith("C")
is_scia = not is_pdc and (interna.startswith("D") or esterna.startswith("B"))
is_cila = not is_pdc and not is_scia

titolo = "Permesso di Costruire / SCIA Alternativa" if is_pdc else "SCIA" if is_scia else "CILA in Sanatoria"

voci_preventivo = []

# Accesso agli atti
if accesso_fatto == "NO":
    voci_preventivo.append({"Voce": "Accesso agli atti", "Imponibile": COSTI["accesso_atti"], "Art. 15": DIRITTI["accesso_atti"]})
else:
    voci_preventivo.append({"Voce": "Accesso agli atti", "Imponibile": 0, "Art. 15": 0})

# Quota Base
imp_base = COSTI["base_cila"] + COSTI["add_pdc"] if is_pdc else COSTI["base_cila"]
diritti_pratica = DIRITTI["pdc"] if is_pdc else DIRITTI["scia"] if is_scia else DIRITTI["cila"]
art15_base = diritti_pratica + (DIRITTI["catasto_per_unita"] * unita)
voci_preventivo.append({"Voce": "Quota Fissa Base (Istruttoria + Diritti + Catasto moltiplicato)", "Imponibile": imp_base, "Art. 15": art15_base})

# Volumi Oltre Tolleranza
if is_pdc:
    voci_preventivo.append({"Voce": "Maggiorazione Volumi oltre Tolleranza", "Imponibile": COSTI["volumi"], "Art. 15": 0})

# Paesaggistica
if vincolo == "SI" and not esterna.startswith("A"):
    voci_preventivo.append({"Voce": "Pratica Paesaggistica Integrativa", "Imponibile": COSTI["paesaggistica"], "Art. 15": DIRITTI["paesaggistica"]})

# Statica
if interna.startswith("D") or is_pdc:
    voci_preventivo.append({"Voce": "Certificato Idoneità Statica / Sismica", "Imponibile": COSTI["statica"], "Art. 15": 0})

# Involucro/Legge 10
if esterna.startswith("B") or is_pdc:
    voci_preventivo.append({"Voce": "Verifiche Involucro (Prospetti / Legge 10)", "Imponibile": COSTI["involucro"], "Art. 15": 0})

# Agibilità & DiRi
serve_agibilita = interna.startswith("C") or interna.startswith("D") or is_pdc or cambio_uso == "SI" or deroga == "SI"
if serve_agibilita:
    voci_preventivo.append({"Voce": "Adempimenti Nuova Agibilità", "Imponibile": COSTI["agibilita"], "Art. 15": DIRITTI["agibilita"]})
    if dico in ["NO", "NON LO SO"]:
        voci_preventivo.append({"Voce": "Integrazione Oneri DiRi (Assenza DICO)", "Imponibile": COSTI["diri"], "Art. 15": 0})

# Cambio Uso & Deroghe
if cambio_uso == "SI":
    voci_preventivo.append({"Voce": "Pratica Cambio Destinazione d'Uso (Verifica Standard)", "Imponibile": COSTI["cambio_uso"], "Art. 15": 0})
if deroga == "SI":
    voci_preventivo.append({"Voce": "Asseverazione Deroghe Salva Casa (Altezze/Superfici)", "Imponibile": COSTI["deroga_salvacasa"], "Art. 15": 0})

# Maggiorazione Mq
if superficie > 300:
    voci_preventivo.append({"Voce": "Maggiorazione per Scaglione Superficie", "Imponibile": COSTI["mq_grande"], "Art. 15": 0})
elif superficie > 150:
    voci_preventivo.append({"Voce": "Maggiorazione per Scaglione Superficie", "Imponibile": COSTI["mq_medio"], "Art. 15": 0})

# Calcoli Totali Tecnici
df = pd.DataFrame(voci_preventivo)
# Filtra le voci a 0 (tranne Accesso atti se è a 0, per ricalcare l'Excel, oppure puliamo tutto)
df = df[df["Imponibile"] > 0] if accesso_fatto == "NO" else df 
# Se accesso atti è SI, nel tuo excel mostrava 0. Manteniamo la riga per fedeltà.

tot_imponibile = df["Imponibile"].sum()
tot_art15 = df["Art. 15"].sum()
cassa = tot_imponibile * 0.04
iva = (tot_imponibile + cassa) * 0.22
tot_tecnico_lordo = tot_imponibile + tot_art15 + cassa + iva

# Calcolo Sanzione (Oblazione)
if is_pdc:
    sanzione_calcolata = mq_ampliamento * COSTI["moltiplicatore_ampliamento"]
    sanzione = max(sanzione_calcolata, COSTI["sanzione_minima"])
else:
    sanzione = COSTI["sanzione_minima"]

totale_chiavi_in_mano = tot_tecnico_lordo + sanzione

# ---- OUTPUT RISULTATI (UI Destra) ----
with col_output:
    st.subheader("📊 COMPOSIZIONE DEL PREVENTIVO (SPESE TECNICHE)")
    
    st.info(f"**TIPO PRATICA STIMATA:**\n\n🎯 {titolo}", icon="ℹ️")
    
    df_display = df.copy()
    df_display["Imponibile"] = df_display["Imponibile"].apply(lambda x: f"€ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    df_display["Art. 15"] = df_display["Art. 15"].apply(lambda x: f"€ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    
    st.dataframe(df_display, hide_index=True, use_container_width=True)
    
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Imponibile", f"€ {tot_imponibile:,.2f}")
    mc2.metric("Spese Art. 15", f"€ {tot_art15:,.2f}")
    mc3.metric("IVA + Cassa", f"€ {(iva+cassa):,.2f}")
    
    st.success(f"**TOTALE PREVENTIVO SPESE TECNICHE:** € {tot_tecnico_lordo:,.2f}")
    
    st.divider()
    st.warning("⚠️ **STIMA SANZIONE AMMINISTRATIVA (OBLAZIONE COMUNALE)**\n\n*ATTENZIONE: La stima in caso di ampliamento è calcolata ex. Art. 36 DPR 380/01 sui Mq aggiunti. L'importo esatto verrà decretato definitivamente dall'Ufficio Tecnico Comunale.*")
    st.error(f"**Stima Oblazione F24 (Da versare direttamente al Comune):** € {sanzione:,.2f}")
    
    st.markdown(f"""
        <div style='background-color: #C00000; padding: 15px; border-radius: 5px; text-align: center; border: 1px solid #BFBFBF;'>
            <h4 style='color: white; margin:0;'>COSTO TOTALE STIMATO 'CHIAVI IN MANO' (Tecnico + Comune)</h4>
            <h2 style='color: white; margin:0;'>€ {totale_chiavi_in_mano:,.2f}</h2>
        </div>
    """, unsafe_allow_html=True)
    
 # Spazio per staccare il blocco
    st.write("")
    st.write("")

    # --- INCIDENZA SUL PREZZO DI VENDITA ---
    incidenza_perc = (totale_chiavi_in_mano / prezzo_vendita) * 100 if prezzo_vendita > 0 else 0
    st.markdown("**STATISTICA OPERAZIONE IMMOBILIARE**")
    st.info(f"📈 **Incidenza della Sanatoria sul Prezzo di Vendita:** {incidenza_perc:.2f}%", icon="⚖️")

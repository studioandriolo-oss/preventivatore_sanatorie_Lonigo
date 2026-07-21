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
    "moltiplicatore_ampliamento": 124,
    "CDU": 80
}

DIRITTI = {
    "accesso_atti": 80,
    "cila": 80,
    "scia": 100,
    "pdc": 300,
    "catasto_per_unita": 70,
    "paesaggistica": 132,
    "agibilita": 70,
    "CDU_diritti": 80
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
        "D - Demolizione muri spessi o portanti o modifiche a parti strutturali",
        "E - Solo variazione catastale"
    ])
    esterna = st.selectbox("2. SITUAZIONE ESTERNA / FACCIATE (Scegli la più impattante):", [
        "--- Seleziona un'opzione ---",
        "A - Nessuna modifica esterna",
        "B - Spostamento/Allargamento Finestre o Porte",
        "C - Chiusura Terrazze/Verande o Ampliamenti volumi",
        "D - Modifica di sagoma entro le tolleranze o minor volume"
    ])
    
    col1, col2 = st.columns(2)
    with col1:
        vincolo = st.radio("3. IMMOBILE IN ZONA VINCOLATA (Centro storico, Paesaggio, ecc.)?", ["NO", "SI"])
        superficie = st.number_input("5. SUPERFICIE COMMERCIALE TOTALE IMMOBILE (Mq):", min_value=1, value=120)
        cambio_uso = st.radio("7. C'È STATO UN CAMBIO D'USO SENZA OPERE? (es. da magazzino/sottotetto ad abitazione)?", ["NO", "SI"])
        accesso_fatto = st.radio("10. E' GIA' STATO FATTO UN ACCESSO AGLI ATTI?", ["SI", "NO"])
        CDU = st.radio("12. SERVE CDU?", ["NO", "SI"])
        
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
        prezzo_vendita = st.number_input("Prezzo di vendita", min_value=0, value=150000, step=1000, label_visibility="collapsed")

# ---- MOTORE DI CALCOLO LATO BACKEND ----
form_compilato = (interna != "--- Seleziona un'opzione ---") and (esterna != "--- Seleziona un'opzione ---")
voci_preventivo = []

# Inizializzazione sicura per evitare errori di NameError al primo caricamento
is_pdc = is_scia = is_cila = is_solo_catasto = is_tolleranze = False

if not form_compilato:
    titolo = "In attesa di dati..."
    tot_imponibile = tot_art15 = cassa = iva = tot_tecnico_lordo = sanzione = totale_chiavi_in_mano = 0.0
    df = pd.DataFrame(columns=["Voce", "Imponibile", "Art. 15"])
else:
    is_pdc = esterna.startswith("C")
    is_scia = not is_pdc and (interna.startswith("D") or esterna.startswith("B") or esterna.startswith("D"))
    
    is_solo_catasto = interna.startswith("E") and esterna.startswith("A")
    is_tolleranze = interna.startswith("A") and (esterna.startswith("A") or esterna.startswith("D"))
    
    is_cila = not is_pdc and not is_scia and not is_solo_catasto and not is_tolleranze

    # Definizione del titolo della pratica
    if is_solo_catasto:
        titolo = "Variazione Catastale (Docfa)"
    elif is_tolleranze:
        titolo = "Dichiarazione Stato Legittimo (Art. 34-bis)"
    else:
        titolo = "Permesso di Costruire / SCIA Alternativa" if is_pdc else "SCIA in Sanatoria" if is_scia else "CILA in Sanatoria"

    # 1. Accesso agli atti e CDU (Sempre valutabili)
    if accesso_fatto == "NO":
        voci_preventivo.append({"Voce": "Accesso agli atti", "Imponibile": COSTI["accesso_atti"], "Art. 15": DIRITTI["accesso_atti"]})
    else:
        voci_preventivo.append({"Voce": "Accesso agli atti", "Imponibile": 0, "Art. 15": 0})

    if CDU == "SI":
        voci_preventivo.append({"Voce": "Richiesta e Ritiro CDU", "Imponibile": COSTI["CDU"], "Art. 15": DIRITTI["CDU_diritti"]})

    # 2. Quota Fissa Base (Sdoppiata per il "Solo Catasto")
    if is_solo_catasto:
        imp_base = 700 + (350 * (unita - 1))
        art15_base = DIRITTI["catasto_per_unita"] * unita
        voci_preventivo.append({"Voce": "Onorario Variazione Catastale", "Imponibile": imp_base, "Art. 15": art15_base})
    else:
        imp_base = COSTI["base_cila"] + COSTI["add_pdc"] if is_pdc else COSTI["base_cila"]
        diritti_pratica = DIRITTI["pdc"] if is_pdc else DIRITTI["scia"] if is_scia else DIRITTI["cila"]
        art15_base = diritti_pratica + (DIRITTI["catasto_per_unita"] * unita)
        voci_preventivo.append({"Voce": "Quota Fissa Base (Istruttoria + Diritti + Catasto moltiplicato)", "Imponibile": imp_base, "Art. 15": art15_base})

    # 3. Maggiorazioni Pratiche Edilizie (Ignorate se "Solo Catasto")
    if not is_solo_catasto:
        if is_pdc:
            voci_preventivo.append({"Voce": "Maggiorazione Volumi oltre Tolleranza", "Imponibile": COSTI["volumi"], "Art. 15": 0})

        if vincolo == "SI" and not esterna.startswith("A"):
            voci_preventivo.append({"Voce": "Pratica Paesaggistica Integrativa", "Imponibile": COSTI["paesaggistica"], "Art. 15": DIRITTI["paesaggistica"]})

        if interna.startswith("D") or is_pdc:
            voci_preventivo.append({"Voce": "Certificato Idoneità Statica / Sismica", "Imponibile": COSTI["statica"], "Art. 15": 0})

        if esterna.startswith("B") or esterna.startswith("D") or is_pdc:
            voci_preventivo.append({"Voce": "Verifiche Involucro (Prospetti / Legge 10)", "Imponibile": COSTI["involucro"], "Art. 15": 0})

        serve_agibilita = interna.startswith("C") or interna.startswith("D") or is_pdc or cambio_uso == "SI" or deroga == "SI"
        if serve_agibilita:
            voci_preventivo.append({"Voce": "Adempimenti Nuova Agibilità", "Imponibile": COSTI["agibilita"], "Art. 15": DIRITTI["agibilita"]})
            if dico in ["NO", "NON LO SO"]:
                voci_preventivo.append({"Voce": "Integrazione Oneri DiRi (Assenza DICO)", "Imponibile": COSTI["diri"], "Art. 15": 0})

        if cambio_uso == "SI":
            voci_preventivo.append({"Voce": "Pratica Cambio Destinazione d'Uso", "Imponibile": COSTI["cambio_uso"], "Art. 15": 0})
            
        if deroga == "SI":
            voci_preventivo.append({"Voce": "Asseverazione Deroghe Salva Casa", "Imponibile": COSTI["deroga_salvacasa"], "Art. 15": 0})

    # 4. Maggiorazioni per Dimensione Immobile (Si applicano sempre)
    if superficie > 300:
        voci_preventivo.append({"Voce": "Maggiorazione Scaglione Superficie", "Imponibile": COSTI["mq_grande"], "Art. 15": 0})
    elif superficie > 150:
        voci_preventivo.append({"Voce": "Maggiorazione Scaglione Superficie", "Imponibile": COSTI["mq_medio"], "Art. 15": 0})

    # Compilazione Dataframe e Calcoli Fiscali
    df = pd.DataFrame(voci_preventivo)
    df = df[df["Imponibile"] > 0] if accesso_fatto == "NO" else df 

    tot_imponibile = df["Imponibile"].sum()
    tot_art15 = df["Art. 15"].sum()
    cassa = tot_imponibile * 0.04
    iva = (tot_imponibile + cassa) * 0.22
    tot_tecnico_lordo = tot_imponibile + tot_art15 + cassa + iva

    # Calcolo Oblazione / Sanzione (Non dovuta per Catasto o Tolleranze)
    if is_solo_catasto or is_tolleranze:
        sanzione = 0
    elif is_pdc:
        sanzione_calcolata = mq_ampliamento * COSTI["moltiplicatore_ampliamento"]
        sanzione = max(sanzione_calcolata, COSTI["sanzione_minima"])
    else:
        sanzione = COSTI["sanzione_minima"]

    totale_chiavi_in_mano = tot_tecnico_lordo + sanzione

# ---- FUNZIONE 1: PDF PREVENTIVO AGENTE ----
def genera_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "STUDIO ANDRIOLO", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, "Stima Preventiva Pratica in Sanatoria", ln=True, align='C')
    pdf.line(10, 30, 200, 30)
    pdf.ln(8)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "1. STATO DI FATTO DICHIARATO", ln=True)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 6, "Sit. Interna:", border=0)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 6, f"{interna}")
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 6, "Sit. Esterna:", border=0)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 6, f"{esterna}")
    pdf.ln(2)
    
    pdf.cell(95, 6, f"Superficie Immobile: {superficie} Mq", border=0)
    pdf.cell(95, 6, f"Unita' Coinvolte: {unita}", ln=True)
    pdf.cell(95, 6, f"Vincolo Paesaggistico: {vincolo}", border=0)
    pdf.cell(95, 6, f"Certificazioni DICO: {dico}", ln=True)
    pdf.cell(95, 6, f"Cambio d'uso: {cambio_uso}", border=0)
    pdf.cell(95, 6, f"Deroghe Salva Casa: {deroga}", ln=True)
    pdf.cell(95, 6, f"Accesso Atti Fatto: {accesso_fatto}", border=0)
    
    if mq_ampliamento > 0:
        pdf.cell(95, 6, f"Ampliamento: {mq_ampliamento} Mq", ln=True)
        pdf.cell(95, 6, f"Serve CDU: {CDU}", ln=True)
    else:
        pdf.cell(95, 6, f"Serve CDU: {CDU}", ln=True)
        
    pdf.cell(0, 6, f"Prezzo di Vendita Ipotizzato: {prezzo_vendita:,.2f} Euro", ln=True)
    pdf.ln(6)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "2. RIEPILOGO ECONOMICO STIMATO", ln=True)
    pdf.set_font("Arial", 'I', 11)
    pdf.cell(0, 8, f"Tipo Pratica Ipotizzata: {titolo}", ln=True)
    pdf.ln(2)
    
    pdf.set_font("Arial", '', 11)
    pdf.cell(120, 6, "Imponibile Professionale:", border=0)
    pdf.cell(0, 6, f"{tot_imponibile:,.2f} Euro", ln=True, align='R')
    pdf.cell(120, 6, "Spese Esenti (Art. 15 / Diritti):", border=0)
    pdf.cell(0, 6, f"{tot_art15:,.2f} Euro", ln=True, align='R')
    pdf.cell(120, 6, "IVA e Cassa Architetti:", border=0)
    pdf.cell(0, 6, f"{(iva+cassa):,.2f} Euro", ln=True, align='R')
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(120, 8, "Totale Spese Tecniche:", border=0)
    pdf.cell(0, 8, f"{tot_tecnico_lordo:,.2f} Euro", ln=True, align='R')
    pdf.ln(2)
    
    pdf.set_font("Arial", '', 11)
    pdf.cell(120, 6, "Stima Sanzione Comune (Oblazione F24):", border=0)
    pdf.cell(0, 6, f"{sanzione:,.2f} Euro", ln=True, align='R')
    pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2)
    pdf.ln(4)
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(120, 10, "COSTO TOTALE 'CHIAVI IN MANO':", border=0)
    pdf.cell(0, 10, f"{totale_chiavi_in_mano:,.2f} Euro", ln=True, align='R')
    pdf.ln(8)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "NOTE:", ln=True)
    
    # Riga 1: Grassetto
    pdf.set_font("Arial", 'B', 9) 
    pdf.cell(0, 5, "- Il rilievo dello stato di fatto viene eseguito con strumentazione laser scanner 3D SLAM.", ln=True)
    
    # Riga 2: Testo normale
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, "- E' previsto un acconto di 600,00 euro (iva inclusa) all'accettazione del preventivo formale.", ln=True)
    
    pdf.ln(3)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "ESCLUSIONI (Salvo diversa pattuizione):", ln=True)
    pdf.set_font("Arial", '', 9)
    esclusioni_testo = "- Rilievi geologici/geotecnici.\n- Autorizzazioni terzi enti.\n- Saggi murari invasivi.\n- Pratiche VIA/VAS.\n- Frazionamenti."
    pdf.multi_cell(0, 5, esclusioni_testo)
    
    return pdf.output(dest='S').encode('latin-1')

# ---- FUNZIONE 2: PDF RELAZIONE TECNICA PER LO STUDIO ----
def genera_relazione_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "RELAZIONE TECNICA PRELIMINARE - INQUADRAMENTO PRATICA", ln=True, align='C')
    pdf.line(10, 20, 200, 20)
    pdf.ln(5)
    
    # Riferimenti Generali
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "DATI PRINCIPALI:", ln=True)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 6, f"- Titolo Stimato: {titolo}", ln=True)
    pdf.cell(0, 6, f"- Superficie: {superficie} Mq | Unita' immobiliari: {unita}", ln=True)
    if mq_ampliamento > 0:
        pdf.cell(0, 6, f"- Ampliamento volume: {mq_ampliamento} Mq", ln=True)
    pdf.ln(5)

    # Costruzione logica dei paragrafi normativi
    testo_relazione = []
    
    # 1. Inquadramento Titolo
    if is_solo_catasto:
        testo_relazione.append("[VARIAZIONE CATASTALE] L'intervento richiesto si configura come pura Variazione Catastale (es. esatta rappresentazione grafica, o divisione/fusione senza opere). L'iter non prevede l'attivazione di procedimenti edilizi in sanatoria, ma l'esclusivo aggiornamento della banca dati dell'Agenzia delle Entrate tramite procedura Docfa.")
    elif is_tolleranze:
        testo_relazione.append("[TOLLERANZE ESECUTIVE E SAGOMA] Le difformita' (incluse le eventuali modifiche di sagoma o minor volume) rientrano nelle tolleranze costruttive ed esecutive ex Art. 34-bis DPR 380/01. Non costituiscono violazione edilizia. Sara' sufficiente redigere e depositare un'apposita Dichiarazione del Tecnico per l'attestazione dello Stato Legittimo.")
    elif is_cila:
        testo_relazione.append("[TITOLO IN SANATORIA] L'intervento si configura come Manutenzione Straordinaria 'leggera' ai sensi dell'Art. 6-bis comma 5 del D.P.R. 380/01. Le opere contestate non hanno interessato le parti strutturali dell'edificio ne' i prospetti esterni. La sanatoria avviene tramite CILA tardiva.")
    elif is_scia:
        testo_relazione.append("[TITOLO IN SANATORIA] L'intervento si configura come Manutenzione Straordinaria 'pesante' o Restauro/Risanamento Conservativo ai sensi dell'Art. 37 del D.P.R. 380/01. L'abuso rientra nel campo delle 'parziali difformita'. Si procedera' con SCIA in Sanatoria, includendo l'asseverazione per tolleranze ove presenti.")
    else: # PdC
        testo_relazione.append("[TITOLO IN SANATORIA] Trattandosi di intervento con impatto volumetrico o alterazione della sagoma (es. ampliamenti, chiusura di logge), l'opera si configura come Ristrutturazione Edilizia/Nuova Costruzione. La sanatoria richiedera' un Accertamento di Conformita' ex Art. 36 o Art. 36-bis del D.P.R. 380/01 (PdC in Sanatoria).")

    # 2. Normativa Salva Casa (Esclusa per Catasto)
    if not is_solo_catasto and not is_tolleranze:
        testo_relazione.append("[CRITERIO DI CONFORMITA'] Alla luce del recente D.L. 69/2024 (L. 105/2024 'Salva Casa'), si applichera' il regime semplificato dell'accertamento di conformita'. Il tecnico asseverera' la conformita' urbanistica alla disciplina vigente al momento della presentazione della domanda, e la conformita' edilizia ai requisiti prescritti all'epoca della realizzazione dell'intervento, superando il previgente vincolo rigido della 'doppia conformita'.")

    # 3. Resto delle casistiche (Solo se non e' Catasto)
    if not is_solo_catasto:
        if interna.startswith("D"):
            testo_relazione.append("[PROFILO STRUTTURALE E SISMICO] Le opere contestate hanno interessato elementi strutturali portanti. L'accertamento di conformita' e' subordinato alla redazione di un Certificato di Idoneita' Statica (CIS) o al deposito in sanatoria presso l'ex Genio Civile, ai sensi del D.P.R. 380/01 e delle NTC 2018.")
        
        if vincolo == "SI":
            testo_relazione.append("[VINCOLO PAESAGGISTICO] Ricadendo l'immobile in area sottoposta a vincolo, l'iter di sanatoria e' subordinato all'ottenimento dell'Accertamento di Compatibilita' Paesaggistica ex art. 167 del D.Lgs. 42/2004, comportante il versamento di un'autonoma sanzione paesaggistica.")
        
        if esterna.startswith("B") or esterna.startswith("C"):
            testo_relazione.append("[PROFILO ARCHITETTONICO E INVOLUCRO] La modifica delle forometrie o l'aumento di volume costituisce alterazione dei prospetti. L'intervento richiedera' la verifica dei rapporti aeroilluminanti aggiornati e le verifiche di legge sul contenimento energetico (ex L. 10/91 e D.Lgs. 192/05) per l'involucro edilizio.")
        elif esterna.startswith("D"):
            testo_relazione.append("[MODIFICHE ESTERNE / ART. 34-BIS] La modifica di sagoma rilevata e/o il minor volume rientrano nel campo di applicazione dell'Art. 34-bis del D.P.R. 380/01. L'intervento esterno sara' asseverato come tolleranza esecutiva, mantenendo i requisiti di decoro architettonico, senza configurare violazione edilizia per la porzione esterna.")
        
        if dico in ["NO", "NON LO SO"]:
            testo_relazione.append("[IMPIANTI] Stante l'assenza (o la non certezza) delle Dichiarazioni di Conformita' (DICO) originarie, ai fini della successiva SCA sara' indispensabile redigere apposite Dichiarazioni di Rispondenza (DiRi) per gli impianti presenti, avvalendosi di impiantisti abilitati.")
        
        if deroga == "SI":
            testo_relazione.append("[DEROGHE IGIENICO-SANITARIE] Le difformita' presentano locali con altezze inferiori a 2,70m e/o superfici inferiori ai minimi del D.M. 1975. Si procedera' con asseverazione specifica ai sensi delle deroghe introdotte dalla L. 105/2024, attestando in ogni caso il rispetto dei requisiti di aeroilluminazione e salubrita'.")
        
        if cambio_uso == "SI":
            testo_relazione.append("[DESTINAZIONE D'USO] E' presente un mutamento di destinazione d'uso senza opere. L'asseverazione dovra' comprovare l'ammissibilita' dell'uso attuale secondo lo strumento urbanistico vigente, tenendo conto delle agevolazioni introdotte dal Decreto Salva Casa.")
        
        if not is_tolleranze:
            testo_relazione.append(f"[AGGIORNAMENTO CATASTALE] A conclusione dell'iter edilizio di sanatoria, si rendera' necessario l'aggiornamento della planimetria catastale mediante procedura Docfa, per l'esatta rappresentazione in vista del rogito. L'aggiornamento interessera' n. {int(unita)} unita' immobiliare/i.")

    # Paragrafo CDU (indipendente dalla pratica)
    if CDU == "SI":
        testo_relazione.append("[CERTIFICATO DESTINAZIONE URBANISTICA] Ai fini della stipula dell'atto notarile, si procedera' alla richiesta del Certificato di Destinazione Urbanistica (CDU) per l'inquadramento delle aree scoperte o pertinenze interessate dal trasferimento immobiliare.")
        
    pdf.set_font("Arial", '', 10)
    for paragrafo in testo_relazione:
        pdf.multi_cell(0, 6, paragrafo)
        pdf.ln(3)

    return pdf.output(dest='S').encode('latin-1')

# ---- OUTPUT RISULTATI (UI Destra) ----
with col_output:
    st.subheader("📊 Composizione del preventivo tecnico")
    
    if not form_compilato:
        st.info("Compila i campi a sinistra per generare il preventivo.", icon="ℹ️")
        df_placeholder = pd.DataFrame([{"Voce": "In attesa di dati...", "Imponibile": "€ 0,00", "Art. 15": "€ 0,00"}])
        st.dataframe(df_placeholder, hide_index=True, use_container_width=True)
    else:
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
    if is_solo_catasto or is_tolleranze:
        st.success("✅ **Sanzione Amministrativa NON DOVUTA** (Pratica senza opere abusive in sanatoria).")
    else:
        st.warning("⚠️ **STIMA SANZIONE AMMINISTRATIVA (OBLAZIONE COMUNALE)**\n\n*ATTENZIONE: La stima in caso di ampliamento è calcolata ex. Art. 36 DPR 380/01 sui Mq aggiunti.*")
        st.error(f"**Stima Oblazione F24 (Da versare al Comune):** € {sanzione:,.2f}")
    
    st.markdown(f"""
        <div style='background-color: #10B981; padding: 15px; border-radius: 5px; text-align: center; border: 1px solid #BFBFBF;'>
            <h4 style='color: white; margin:0;'>COSTO TOTALE STIMATO 'CHIAVI IN MANO'</h4>
            <h3 style='color: white; margin:0;'>€ {totale_chiavi_in_mano:,.2f}</h3>
        </div>
    """, unsafe_allow_html=True)
    
    st.write("")

    incidenza_perc = (totale_chiavi_in_mano / prezzo_vendita) * 100 if (prezzo_vendita > 0 and form_compilato) else 0
    st.markdown("**STATISTICA OPERAZIONE IMMOBILIARE**")
    st.info(f"📈 **Incidenza della Sanatoria sul Prezzo di Vendita:** {incidenza_perc:.2f}%", icon="⚖️")
    
    # --- RIGUADRO FISSO: NOTE ED ESCLUSIONI A SCHERMO ---
    st.markdown("""
    <div style='background-color: #F8F9FA; padding: 15px; border-radius: 5px; border: 1px solid #DEE2E6;'>
        <p style='margin-bottom: 5px;'><strong>📌 NOTE:</strong></p>
        <ul style='margin-top: 0; padding-left: 20px; font-size: 14px;'>
            <li><strong>Il rilievo dello stato di fatto viene eseguito con strumentazione laser scanner 3D SLAM.</li>
            <li>E' previsto un acconto di 600,00 euro (iva inclusa) all'accettazione del preventivo formale.</li>
        </ul>
        <p style='margin-bottom: 5px;'><strong>🚫 ESCLUSIONI (Salvo diversa pattuizione):</strong></p>
        <ul style='margin-top: 0; padding-left: 20px; font-size: 14px;'>
            <li>Rilievi e indagini geologiche o geotecniche;</li>
            <li>Pratiche di allacciamento o autorizzazione con terzi enti;</li>
            <li>Eventuali saggi murari o strutturali invasivi;</li>
            <li>Pratiche VIA, VAS, VINCA;</li>
            <li>Frazionamento e/o accorpamenti immobiliari.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # --- BOTTONI DI DOWNLOAD PDF ---
    if form_compilato:
        st.write("")
        pdf_preventivo = genera_pdf()
        st.download_button(
            label="📄 Scarica Preventivo (Per il Cliente)",
            data=pdf_preventivo,
            file_name=f"Preventivo_Sanatoria_Studio_Andriolo.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="secondary"
        )
        
        pdf_relazione = genera_relazione_pdf()
        st.download_button(
            label="📘 Scarica Relazione Tecnica (Per lo Studio)",
            data=pdf_relazione,
            file_name=f"Bozza_Relazione_Tecnica_Interna.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="secondary"
        )

# --- SEZIONE MODULO DI CONDIVISIONE ---
st.markdown("---")

col_testo_cond, col_spunta_cond = st.columns([3, 1])

with col_testo_cond:
    st.markdown("<h2 style='color: #0277BD; margin-top: -10px;'>📤 Vuoi condividere con l'architetto Andriolo?</h2>", unsafe_allow_html=True)
    
with col_spunta_cond:
    st.write("") 
    condividi = st.checkbox("Sì, apri il modulo")
  
if condividi:
    st.markdown("### Modulo di Trasmissione Pratica")
    
    with st.form("form_invio_dati"):
        
        nome_rif = st.text_input("NOME DI RIFERIMENTO (Cliente o Immobile)")
        
        st.markdown("**DATI DI CONTATTO**")
        c1, c2, c3 = st.columns(3)
        agente = c1.text_input("Nome Agente")
        email_agente = c2.text_input("Mail Agente")
        telefono = c3.text_input("Telefono Agente")
        
        st.markdown("**DATI DELL'ABITAZIONE**")
        a1, a2 = st.columns(2)
        indirizzo = a1.text_input("Indirizzo Immobile")
        comune = a2.text_input("Comune")

        st.markdown("**DATI CATASTALI**")
        c1, c2, c3 = st.columns(3)
        foglio = c1.text_input("Foglio")
        mappale = c2.text_input("Mappale")
        subalterno = c3.text_input("Subalterno")
        
        st.markdown("**DOCUMENTI ALLEGATI**")
        
        doc_id = st.file_uploader("📂 CARICA documenti del proprietario (Carta d'Identità, Codice Fiscale)", type=["pdf", "jpg", "png"], accept_multiple_files=True)
        altri_file = st.file_uploader("📂 CARICA altri documenti (Planimetrie, Visure, Foto precedenti)", type=["pdf", "jpg", "png"], accept_multiple_files=True)
        
        note = st.text_area("NOTE PER LO STUDIO")
        
        st.markdown("---")
        if 'captcha_a' not in st.session_state:
            st.session_state.captcha_a = random.randint(1, 9)
            st.session_state.captcha_b = random.randint(1, 9)

        st.write(f"🤖 **Controllo Anti-Spam: quanto fa {st.session_state.captcha_a} + {st.session_state.captcha_b}?**")
        risposta_captcha = st.text_input("Inserisci il risultato numerico per sbloccare l'invio:")
        somma_corretta = str(st.session_state.captcha_a + st.session_state.captcha_b)

        inviato = st.form_submit_button("Invia Pratica allo Studio")
        
        if inviato:
            if not agente or not email_agente:
                st.error("⚠️ Attenzione: Inserisci almeno il Nome dell'Agente e la Mail prima di inviare.")
            elif "@" not in email_agente or "." not in email_agente:
                st.error("⚠️ L'indirizzo email inserito non sembra valido. Controlla la sintassi (es. nome@dominio.com).")
            elif risposta_captcha.strip() == somma_corretta:
                try:
                    msg = EmailMessage()
                    msg['Subject'] = f"Nuova Pratica da Valutatore - {nome_rif}"
                    msg['From'] = "studioandriolo@gmail.com"
                    msg['To'] = "studioandriolo@gmail.com"
                    
                    body = f"""
Nuova richiesta dal valutatore agenti immobiliari.

--- DATI DI CONTATTO E ABITAZIONE ---
Riferimento: {nome_rif}
Agente: {agente}
Mail: {email_agente}
Telefono: {telefono}
Indirizzo: {indirizzo} - {comune}
Dati Catastali: Fg.{foglio} Map.{mappale} Sub.{subalterno}

--- RISPOSTE AL QUESTIONARIO (STATO DI FATTO) ---
1. Situazione Interna: {interna}
2. Situazione Esterna: {esterna}
3. Immobile in zona vincolata: {vincolo}
4. Certificazioni DICO presenti: {dico}
5. Superficie Totale: {superficie} Mq
6. Numero Unità: {unita}
7. Cambio d'uso: {cambio_uso}
8. Deroghe Salva Casa: {deroga}
9. Mq Ampliati: {mq_ampliamento} Mq
10. Accesso agli atti fatto: {accesso_fatto}
11. Prezzo di vendita: {prezzo_vendita:,.2f} Euro
12. Serve CDU: {CDU}

--- RIEPILOGO TECNICO E COSTI ---
Titolo Edilizio Stimato: {titolo}
Totale Spese Tecniche: {tot_tecnico_lordo:,.2f} Euro
Sanzione Comune: {sanzione:,.2f} Euro
Costo Totale Lordo: {totale_chiavi_in_mano:,.2f} Euro

--- NOTE DELL'AGENTE ---
{note}
"""
                    msg.set_content(body)
                    
                    if doc_id:
                        for f in doc_id:
                            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                            
                    if altri_file:
                        for f in altri_file:
                            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                            
                    MAIL_PASSWORD = st.secrets["MAIL_PASSWORD"] 
                    
                    with smtplib.SMTP("smtp.gmail.com", 587) as server:
                        server.starttls()
                        server.login("studioandriolo@gmail.com", MAIL_PASSWORD)
                        server.send_message(msg)
                        
                    st.success("✅ Dati e documenti inviati con successo allo Studio! Verrai ricontattato a breve.")
                    
                    st.session_state.captcha_a = random.randint(1, 9)
                    st.session_state.captcha_b = random.randint(1, 9)
                
                except smtplib.SMTPAuthenticationError:
                    st.error("❌ Errore di Autenticazione: Controlla le impostazioni di Streamlit Cloud.")
                except Exception as e:
                    st.error(f"❌ Si è verificato un errore generico durante l'invio: {e}")
            else:
                st.error("⚠️ Verifica sicurezza fallita: il risultato della somma non è corretto.")

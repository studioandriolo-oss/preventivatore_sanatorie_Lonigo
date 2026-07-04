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
# Logo Studio Andriolo
try:
    st.image("logo.png", width=250)
except FileNotFoundError:
    pass # Ignora se non trova il logo in locale

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
        unita = st.number_input("6. NUMERO DI UNITÀ IMMOBILIARI COINVOLTE (Da aggiornare al Catasto):", min_value=1, value=1)
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

if not form_compilato:
    titolo = "In attesa di dati..."
    tot_imponibile = tot_art15 = cassa = iva = tot_tecnico_lordo = sanzione = totale_chiavi_in_mano = 0.0
    df = pd.DataFrame(columns=["Voce", "Imponibile", "Art. 15"])
else:
    is_pdc = esterna.startswith("C")
    is_scia = not is_pdc and (interna.startswith("D") or esterna.startswith("B"))
    is_cila = not is_pdc and not is_scia

    titolo = "Permesso di Costruire / SCIA Alternativa" if is_pdc else "SCIA in Sanatoria" if is_scia else "CILA in Sanatoria"

    if accesso_fatto == "NO":
        voci_preventivo.append({"Voce": "Accesso agli atti", "Imponibile": COSTI["accesso_atti"], "Art. 15": DIRITTI["accesso_atti"]})
    else:
        voci_preventivo.append({"Voce": "Accesso agli atti", "Imponibile": 0, "Art. 15": 0})

    imp_base = COSTI["base_cila"] + COSTI["add_pdc"] if is_pdc else COSTI["base_cila"]
    diritti_pratica = DIRITTI["pdc"] if is_pdc else DIRITTI["scia"] if is_scia else DIRITTI["cila"]
    art15_base = diritti_pratica + (DIRITTI["catasto_per_unita"] * unita)
    voci_preventivo.append({"Voce": "Quota Fissa Base (Istruttoria + Diritti + Catasto moltiplicato)", "Imponibile": imp_base, "Art. 15": art15_base})

    if is_pdc:
        voci_preventivo.append({"Voce": "Maggiorazione Volumi oltre Tolleranza", "Imponibile": COSTI["volumi"], "Art. 15": 0})

    if vincolo == "SI" and not esterna.startswith("A"):
        voci_preventivo.append({"Voce": "Pratica Paesaggistica Integrativa", "Imponibile": COSTI["paesaggistica"], "Art. 15": DIRITTI["paesaggistica"]})

    if interna.startswith("D") or is_pdc:
        voci_preventivo.append({"Voce": "Certificato Idoneità Statica / Sismica", "Imponibile": COSTI["statica"], "Art. 15": 0})

    if esterna.startswith("B") or is_pdc:
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

    if superficie > 300:
        voci_preventivo.append({"Voce": "Maggiorazione Scaglione Superficie", "Imponibile": COSTI["mq_grande"], "Art. 15": 0})
    elif superficie > 150:
        voci_preventivo.append({"Voce": "Maggiorazione Scaglione Superficie", "Imponibile": COSTI["mq_medio"], "Art. 15": 0})

    df = pd.DataFrame(voci_preventivo)
    df = df[df["Imponibile"] > 0] if accesso_fatto == "NO" else df 

    tot_imponibile = df["Imponibile"].sum()
    tot_art15 = df["Art. 15"].sum()
    cassa = tot_imponibile * 0.04
    iva = (tot_imponibile + cassa) * 0.22
    tot_tecnico_lordo = tot_imponibile + tot_art15 + cassa + iva

    if is_pdc:
        sanzione_calcolata = mq_ampliamento * COSTI["moltiplicatore_ampliamento"]
        sanzione = max(sanzione_calcolata, COSTI["sanzione_minima"])
    else:
        sanzione = COSTI["sanzione_minima"]

    totale_chiavi_in_mano = tot_tecnico_lordo + sanzione

# ---- FUNZIONE CREAZIONE PDF ----
def genera_pdf():
    pdf = FPDF()
    pdf.add_page()
    
    # Intestazione Studio
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "STUDIO ANDRIOLO", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 8, "Stima Preventiva Pratica in Sanatoria", ln=True, align='C')
    pdf.line(10, 30, 200, 30)
    pdf.ln(8)
    
    # 1. Dati Immobile (Scelte dell'Agente)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "1. STATO DI FATTO DICHIARATO", ln=True)
    pdf.set_font("Arial", '', 10)
    
    # Usa multi_cell per le frasi lunghe (Situazione Interna ed Esterna)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 6, "Sit. Interna:", border=0)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 6, f"{interna}")
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 6, "Sit. Esterna:", border=0)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 6, f"{esterna}")
    pdf.ln(2)
    
    # Griglia a due colonne per le risposte brevi
    pdf.cell(95, 6, f"Superficie Immobile: {superficie} Mq", border=0)
    pdf.cell(95, 6, f"Unita' Coinvolte: {unita}", ln=True)
    
    pdf.cell(95, 6, f"Vincolo Paesaggistico: {vincolo}", border=0)
    pdf.cell(95, 6, f"Certificazioni DICO: {dico}", ln=True)
    
    pdf.cell(95, 6, f"Cambio d'uso: {cambio_uso}", border=0)
    pdf.cell(95, 6, f"Deroghe Salva Casa: {deroga}", ln=True)
    
    pdf.cell(95, 6, f"Accesso Atti Fatto: {accesso_fatto}", border=0)
    if mq_ampliamento > 0:
        pdf.cell(95, 6, f"Ampliamento: {mq_ampliamento} Mq", ln=True)
    else:
        pdf.ln(6)
        
    pdf.cell(0, 6, f"Prezzo di Vendita Ipotizzato: {prezzo_vendita:,.2f} Euro", ln=True)
    pdf.ln(6)
    
    # 2. Riepilogo Economico
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
    
    # 3. Note ed Esclusioni
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "NOTE:", ln=True)
    pdf.set_font("Arial", '', 9)
    note_testo = (
        "- Il rilievo dello stato di fatto viene eseguito con strumentazione laser scanner 3D SLAM "
        "per garantire una restituzione grafica con precisione millimetrica.\n"
        "- E' previsto un acconto di 600,00 euro (iva inclusa) all'accettazione del preventivo formale."
    )
    pdf.multi_cell(0, 5, note_testo)
    pdf.ln(3)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 6, "ESCLUSIONI (Salvo diversa pattuizione):", ln=True)
    pdf.set_font("Arial", '', 9)
    esclusioni_testo = (
        "- Rilievi e indagini geologiche o geotecniche.\n"
        "- Pratiche di allacciamento o autorizzazione con terzi enti (es. Acque del Chiampo, Enel, ecc.).\n"
        "- Eventuali saggi murari o strutturali invasivi.\n"
        "- Pratiche VIA, VAS, VINCA.\n"
        "- Frazionamento e/o accorpamenti immobiliari.\n"
        "- Ogni altra prestazione non esplicitamente sopra descritta."
    )
    pdf.multi_cell(0, 5, esclusioni_testo)
    
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
    st.warning("⚠️ **STIMA SANZIONE AMMINISTRATIVA (OBLAZIONE COMUNALE)**\n\n*ATTENZIONE: La stima in caso di ampliamento è calcolata ex. Art. 36 DPR 380/01 sui Mq aggiunti. L'importo esatto verrà decretato definitivamente dall'Ufficio Tecnico Comunale.*")
    st.error(f"**Stima Oblazione F24 (Da versare direttamente al Comune):** € {sanzione:,.2f}")
    
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
    
    st.markdown("""
    **NOTE:**
    - Il rilievo dello stato di fatto viene eseguito con strumentazione laser scanner 3D SLAM per garantire precisione millimetrica.
    - E' previsto un acconto di 600,00 euro (iva inclusa) all'accettazione del preventivo formale.
    
    **ESCLUSIONI (Salvo diversa pattuizione):**
    - Rilievi geologici, autorizzazioni terzi enti (es. Acque del Chiampo, Enel), saggi invasivi, VIA/VAS, frazionamenti.
    """)
    
    # --- PULSANTE DI DOWNLOAD PDF PER L'AGENTE ---
    if form_compilato:
        st.write("")
        pdf_bytes = genera_pdf()
        st.download_button(
            label="📥 Scarica Riepilogo in PDF",
            data=pdf_bytes,
            file_name=f"Stima_Sanatoria_Studio_Andriolo.pdf",
            mime="application/pdf",
            use_container_width=True
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
        
        # 1. Documenti proprietario
        doc_id = st.file_uploader("📂 CARICA documenti del proprietario (Carta d'Identità, Codice Fiscale)", type=["pdf", "jpg", "png"], accept_multiple_files=True)
        
        # 2. Altri documenti
        altri_file = st.file_uploader("📂 CARICA altri documenti (Planimetrie, Visure, Foto precedenti)", type=["pdf", "jpg", "png"], accept_multiple_files=True)
        
        note = st.text_area("NOTE PER LO STUDIO")
        
        st.markdown("---")
        # --- CAPTCHA ANTI-ROBOT ---
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

--- RIEPILOGO TECNICO E COSTI ---
Titolo Edilizio Stimato: {titolo}
Totale Spese Tecniche: {tot_tecnico_lordo:,.2f} Euro
Sanzione Comune: {sanzione:,.2f} Euro
Costo Totale Lordo: {totale_chiavi_in_mano:,.2f} Euro

--- NOTE DELL'AGENTE ---
{note}
"""
                    msg.set_content(body)
                    
                    # Gestione file caricati (Documenti Proprietario)
                    if doc_id:
                        for f in doc_id:
                            msg.add_attachment(f.read(), maintype='application', subtype='octet-stream', filename=f.name)
                            
                    # Gestione file caricati (Altri Documenti)
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

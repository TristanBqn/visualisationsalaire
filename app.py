import streamlit as st
import time
from datetime import datetime, time as dt_time
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Configuration de la page
st.set_page_config(
    page_title="💰 Compteur de Revenu",
    page_icon="💰",
    layout="wide"
)

# Configuration Google Sheets
@st.cache_resource
def get_google_sheets_connection():
    """Crée et met en cache la connexion Google Sheets"""
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes
        )
        
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Erreur de connexion Google Sheets: {e}")
        return None

def log_to_google_sheet(salaire_brut, statut, timestamp):
    """Envoie les données vers Google Sheet"""
    try:
        client = get_google_sheets_connection()
        if client is None:
            return False
        
        sheet_id = st.secrets["google_sheet"]["sheet_id"]
        
        # Ouvrir le spreadsheet
        spreadsheet = client.open_by_key(sheet_id)
        
        # Ouvrir l'onglet "Logs" (créer s'il n'existe pas)
        try:
            worksheet = spreadsheet.worksheet("Logs")
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title="Logs", rows="1000", cols="4")
            # Ajouter les en-têtes
            worksheet.append_row(["Timestamp", "Salaire Brut", "Statut", "User Info"])
        
        # Ajouter la ligne de données
        row_data = [
            timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            salaire_brut,
            statut,
            "User"
        ]
        
        worksheet.append_row(row_data)
        return True
        
    except Exception as e:
        st.error(f"Erreur lors de l'envoi des logs: {e}")
        return False

# Initialisation de session_state
if 'running' not in st.session_state:
    st.session_state.running = False
if 'total_earned_today' not in st.session_state:
    st.session_state.total_earned_today = 0.0
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()
if 'last_logged_salary' not in st.session_state:
    st.session_state.last_logged_salary = None
if 'log_sent' not in st.session_state:
    st.session_state.log_sent = False
if 'start_time' not in st.session_state:
    st.session_state.start_time = None

# Fonction de calcul du salaire net
def calculate_net_salary(brut_annuel, statut):
    """Calcule le salaire net avant impôt"""
    if statut == "Cadre":
        taux_charges = 0.25  # ~25% de charges sociales
    else:
        taux_charges = 0.23  # ~23% pour non-cadre
    
    net_avant_impot = brut_annuel * (1 - taux_charges)
    return net_avant_impot

# Fonction de calcul de l'impôt
def calculate_impot(net_avant_impot, parts_fiscales, autres_revenus):
    """Calcule l'impôt sur le revenu selon le barème progressif 2024"""
    revenu_imposable = (net_avant_impot + autres_revenus) / parts_fiscales
    
    # Barème 2024
    tranches = [
        (0, 11294, 0),
        (11294, 28797, 0.11),
        (28797, 82341, 0.30),
        (82341, 177106, 0.41),
        (177106, float('inf'), 0.45)
    ]
    
    impot = 0
    for i, (min_tranche, max_tranche, taux) in enumerate(tranches):
        if revenu_imposable > min_tranche:
            base = min(revenu_imposable, max_tranche) - min_tranche
            impot += base * taux
    
    impot_total = impot * parts_fiscales
    return impot_total

# Interface utilisateur
st.title("💰 Visualisation des revenus en temps réel")

# Sidebar pour la configuration
with st.sidebar:
    # Section Salaire
    st.subheader("💼 Informations Salariales")
    salaire_brut_annuel = st.number_input(
        "Salaire brut annuel (€)",
        min_value=0,
        value=99999,
        step=1000,
        help="Votre salaire brut annuel en euros"
    )
    
    # Détection du changement et envoi au Google Sheet
    if salaire_brut_annuel != st.session_state.last_logged_salary and salaire_brut_annuel > 0:
        st.session_state.last_logged_salary = salaire_brut_annuel
        st.session_state.log_sent = False
    
    statut = st.selectbox(
        "Statut",
        ["Cadre", "Non-cadre", "Fonction publique"],
        help="Votre statut professionnel"
    )
    
    # Envoi des logs si non déjà envoyé
    if not st.session_state.log_sent and salaire_brut_annuel > 0:
        with st.spinner("📝 Enregistrement..."):
            success = log_to_google_sheet(
                salaire_brut_annuel,
                statut,
                datetime.now()
            )
            if success:
                st.session_state.log_sent = True
                st.success("✅ Données enregistrées", icon="✅")
                time.sleep(1)
                st.rerun()
    
    # Section Fiscalité
    st.subheader("📊 Fiscalité")
    mode_impot = st.radio(
        "Mode de calcul impôt",
        ["Taux de prélèvement", "Calcul automatique"]
    )
    
    if mode_impot == "Taux de prélèvement":
        taux_prelevement = st.slider(
            "Taux de prélèvement à la source (%)",
            0.0, 45.0, 10.0, 0.1
        ) / 100
    else:
        parts_fiscales = st.number_input(
            "Nombre de parts fiscales",
            min_value=1.0,
            value=1.0,
            step=0.5
        )
        autres_revenus = st.number_input(
            "Autres revenus annuels du foyer (€)",
            min_value=0,
            value=0,
            step=1000
        )
    
    # Section Temps de travail
    st.subheader("⏰ Temps de Travail")
    heures_semaine = st.number_input(
        "Heures travaillées par semaine",
        min_value=1,
        value=35,
        step=1
    )
    
    semaines_travaillees = st.number_input(
        "Semaines travaillées par an",
        min_value=1,
        max_value=52,
        value=47,
        help="Généralement 52 - 5 semaines de congés = 47"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        heure_debut = st.time_input(
            "Heure de début",
            value=dt_time(9, 0)
        )
    with col2:
        heure_fin = st.time_input(
            "Heure de fin",
            value=dt_time(18, 0)
        )
    
    # Déductions supplémentaires
    st.subheader("💳 Déductions Supplémentaires")
    mutuelle = st.number_input(
        "Mutuelle mensuelle (part salariale, €)",
        min_value=0,
        value=0,
        step=10
    )
    
    retraite_supp = st.number_input(
        "Retraite supplémentaire mensuelle (€)",
        min_value=0,
        value=0,
        step=10
    )
    
    # Transport
    st.subheader("🚇 Transport")
    abonnement_transport = st.number_input(
        "Abonnement transport mensuel (€)",
        min_value=0,
        value=0,
        step=5,
        help="Montant total de votre abonnement transport"
    )
    
    pourcentage_remboursement = st.slider(
        "% de remboursement employeur",
        0, 100, 50, 1,
        help="Pourcentage pris en charge par votre employeur"
    )
    
    # Calcul de la part salariale du transport
    part_salariale_transport = abonnement_transport * (1 - pourcentage_remboursement / 100)
    
    if abonnement_transport > 0:
        st.caption(f"Part employeur: {abonnement_transport * pourcentage_remboursement / 100:.2f} € | Part salariale: {part_salariale_transport:.2f} €")
    
    autres_deductions = st.number_input(
        "Autres déductions mensuelles (€)",
        min_value=0,
        value=0,
        step=10
    )
    
    # Signature en bas de la sidebar
    st.divider()
    st.markdown(
        "<p style='text-align: center; font-size: 11px; font-style: italic; color: #888888;'>Application créée par Tristan BANNIER.</p>",
        unsafe_allow_html=True
    )

# Calculs
net_avant_impot = calculate_net_salary(salaire_brut_annuel, statut)

if mode_impot == "Taux de prélèvement":
    impot_annuel = net_avant_impot * taux_prelevement
else:
    impot_annuel = calculate_impot(net_avant_impot, parts_fiscales, autres_revenus)

deductions_annuelles = (mutuelle + retraite_supp + part_salariale_transport + autres_deductions) * 12
net_apres_impot_annuel = net_avant_impot - impot_annuel - deductions_annuelles

# Calcul des revenus par période
heures_travaillees_annuel = heures_semaine * semaines_travaillees
secondes_travaillees_annuel = heures_travaillees_annuel * 3600

revenu_par_seconde = net_apres_impot_annuel / secondes_travaillees_annuel
revenu_par_minute = revenu_par_seconde * 60
revenu_par_heure = revenu_par_minute * 60
revenu_par_jour = revenu_par_heure * (heures_semaine / 5)  # Supposant 5 jours/semaine
revenu_mensuel = net_apres_impot_annuel / 12

# Vérification des heures de travail
now = datetime.now().time()
is_work_hours = heure_debut <= now <= heure_fin

# Affichage des métriques principales
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("💶 Salaire Net Annuel", f"{net_apres_impot_annuel:,.2f} €")
with col2:
    st.metric("📅 Revenu Mensuel", f"{revenu_mensuel:,.2f} €")
with col3:
    st.metric("⏱️ Par Heure", f"{revenu_par_heure:.2f} €")
with col4:
    st.metric("⚡ Par Seconde", f"{revenu_par_seconde:.4f} €")

# Séparateur
st.divider()

# Zone du compteur en temps réel
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🔄 Compteur en Temps Réel")
    
    if not is_work_hours:
        st.warning(f"⏸️ Vous n'êtes pas dans vos heures de travail ({heure_debut.strftime('%H:%M')} - {heure_fin.strftime('%H:%M')})")
    
    # Contrôles
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("▶️ Démarrer" if not st.session_state.running else "⏸️ Pause", use_container_width=True):
            st.session_state.running = not st.session_state.running
            st.session_state.last_update = time.time()
    
    with col_btn2:
        if st.button("🔄 Reset Journalier", use_container_width=True):
            st.session_state.total_earned_today = 0.0
            st.session_state.start_time = None
            st.session_state.last_update = time.time()
    
    with col_btn3:
        if st.button("🕐 Actualisation selon l'heure actuelle", use_container_width=True):
            # Calculer le temps écoulé depuis le début de la journée
            now = datetime.now()
            current_time = now.time()
            
            if heure_debut <= current_time <= heure_fin:
                # Calculer les secondes depuis heure_debut
                debut_seconds = heure_debut.hour * 3600 + heure_debut.minute * 60 + heure_debut.second
                current_seconds = current_time.hour * 3600 + current_time.minute * 60 + current_time.second
                elapsed_seconds = current_seconds - debut_seconds
                
                # Calculer le revenu accumulé
                st.session_state.total_earned_today = elapsed_seconds * revenu_par_seconde
                st.session_state.start_time = now
                st.session_state.last_update = time.time()
                st.success(f"✅ Actualisé à {current_time.strftime('%H:%M:%S')}")
            else:
                st.warning("⚠️ Vous n'êtes pas dans vos heures de travail")
            
            time.sleep(1)
            st.rerun()
    
    # Compteur
    counter_placeholder = st.empty()
    
    if st.session_state.running and is_work_hours:
        current_time = time.time()
        elapsed = current_time - st.session_state.last_update
        st.session_state.total_earned_today += elapsed * revenu_par_seconde
        st.session_state.last_update = current_time
        
        counter_placeholder.markdown(
            f"<h1 style='text-align: center; color: #00d26a; font-size: 4em;'>{st.session_state.total_earned_today:.2f} €</h1>",
            unsafe_allow_html=True
        )
        time.sleep(0.1)
        st.rerun()
    else:
        counter_placeholder.markdown(
            f"<h1 style='text-align: center; color: #666; font-size: 4em;'>{st.session_state.total_earned_today:.2f} €</h1>",
            unsafe_allow_html=True
        )

with col2:
    st.subheader("📈 Statistiques du Jour")
    temps_ecoule = st.session_state.total_earned_today / revenu_par_seconde if revenu_par_seconde > 0 else 0
    heures = int(temps_ecoule // 3600)
    minutes = int((temps_ecoule % 3600) // 60)
    secondes = int(temps_ecoule % 60)
    
    st.metric("⏱️ Temps travaillé", f"{heures}h {minutes}m {secondes}s")
    st.metric("🎯 Objectif journalier", f"{revenu_par_jour:.2f} €")
    
    if revenu_par_jour > 0:
        progression = (st.session_state.total_earned_today / revenu_par_jour) * 100
        progression_clamped = min(progression / 100, 1.0)
        st.progress(progression_clamped)
        st.caption(f"Progression: {progression:.1f}%")
        
        # Afficher si l'objectif est atteint
        if progression >= 100:
            st.success("🎉 Objectif journalier atteint !")

# Séparateur
st.divider()

# Section comparaisons amusantes
st.subheader("🎯 Comparaisons")

col1, col2, col3, col4 = st.columns(4)

with col1:
    cafe = revenu_par_minute * 5
    st.info(f"☕ **Pendant un café (5 min)**\n\n{cafe:.2f} €")

with col2:
    dejeuner = revenu_par_minute * 45
    st.info(f"🍽️ **Pendant le déjeuner (45 min)**\n\n{dejeuner:.2f} €")

with col3:
    reunion = revenu_par_heure
    st.info(f"👥 **Pendant une réunion (1h)**\n\n{reunion:.2f} €")

with col4:
    semaine = revenu_par_jour * 5
    st.info(f"📅 **Par semaine (5 jours)**\n\n{semaine:.2f} €")

# Détails des calculs
with st.expander("📊 Détails des Calculs"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💼 Décomposition du Salaire")
        charges_sociales = salaire_brut_annuel - net_avant_impot
        
        data = {
            "Poste": [
                "Salaire Brut",
                "Charges Sociales",
                "Net Avant Impôt",
                "Impôt sur le Revenu",
                "Déductions Supplémentaires",
                "Net Après Impôt"
            ],
            "Montant (€)": [
                f"{salaire_brut_annuel:,.2f}",
                f"-{charges_sociales:,.2f}",
                f"{net_avant_impot:,.2f}",
                f"-{impot_annuel:,.2f}",
                f"-{deductions_annuelles:,.2f}",
                f"{net_apres_impot_annuel:,.2f}"
            ]
        }
        st.dataframe(data, hide_index=True, use_container_width=True)
    
    with col2:
        st.markdown("### ⏰ Répartition Temporelle")
        data_temps = {
            "Période": ["Par Seconde", "Par Minute", "Par Heure", "Par Jour", "Par Mois", "Par An"],
            "Revenu (€)": [
                f"{revenu_par_seconde:.4f}",
                f"{revenu_par_minute:.2f}",
                f"{revenu_par_heure:.2f}",
                f"{revenu_par_jour:.2f}",
                f"{revenu_mensuel:.2f}",
                f"{net_apres_impot_annuel:,.2f}"
            ]
        }
        st.dataframe(data_temps, hide_index=True, use_container_width=True)

# Footer
st.divider()
st.caption("⚠️ Ces calculs sont des approximations. Consultez un expert-comptable pour des calculs précis. Les taux de charges sociales et le barème fiscal sont basés sur 2024.")

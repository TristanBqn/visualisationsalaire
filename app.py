import streamlit as st
import time
from datetime import datetime, time as dt_time
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Configuration de la page
st.set_page_config(
    page_title="💰 Compteur de revenu",
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

# Fonction de calcul du salaire net avant impôt
def calculate_net_avant_impot(brut_annuel, statut):
    """Calcule le salaire net avant impôt (après cotisations sociales)"""
    if statut == "Cadre":
        taux_charges = 0.255  # 25.5% de charges sociales
    else:
        taux_charges = 0.23  # 23% pour non-cadre
    
    net_avant_impot = brut_annuel * (1 - taux_charges)
    return net_avant_impot

# Fonction de calcul du net imposable
def calculate_net_imposable(net_avant_impot):
    """Calcule le net imposable (inclut CSG/CRDS non déductible)"""
    return net_avant_impot * 1.07

# Fonction de calcul de l'impôt avec barème progressif et décote
def calculate_impot(net_imposable, parts_fiscales, autres_revenus, situation_familiale):
    """Calcule l'impôt sur le revenu selon le barème progressif 2024 avec décote"""
    
    # Revenu total imposable du foyer
    revenu_total_imposable = net_imposable + autres_revenus
    
    # Quotient familial : revenu par part
    revenu_par_part = revenu_total_imposable / parts_fiscales
    
    # Barème progressif 2024
    tranches = [
        (0, 11294, 0),
        (11294, 28797, 0.11),
        (28797, 82341, 0.30),
        (82341, 177106, 0.41),
        (177106, float('inf'), 0.45)
    ]
    
    # Calcul de l'impôt par part
    impot_par_part = 0
    for i, (min_tranche, max_tranche, taux) in enumerate(tranches):
        if revenu_par_part > min_tranche:
            base = min(revenu_par_part, max_tranche) - min_tranche
            impot_par_part += base * taux
    
    # Impôt brut du foyer
    impot_brut = impot_par_part * parts_fiscales
    
    # Application de la décote
    if situation_familiale == "Célibataire":
        decote = 833 - 0.4525 * impot_brut
    else:  # Couple
        decote = 1378 - 0.4525 * impot_brut
    
    # Appliquer la décote si positive
    if decote > 0:
        impot_final = impot_brut - decote
    else:
        impot_final = impot_brut
    
    # L'impôt ne peut pas être négatif
    impot_final = max(0, impot_final)
    
    return impot_final, impot_brut, decote if decote > 0 else 0

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
        ["Calcul automatique (barème 2024)", "Taux de prélèvement manuel"]
    )
    
    if mode_impot == "Taux de prélèvement manuel":
        taux_prelevement = st.slider(
            "Taux de prélèvement à la source (%)",
            0.0, 45.0, 10.0, 0.1
        ) / 100
    else:
        situation_familiale = st.selectbox(
            "Situation familiale",
            ["Célibataire", "Couple"],
            help="Pour le calcul de la décote"
        )
        
        parts_fiscales = st.number_input(
            "Nombre de parts fiscales",
            min_value=1.0,
            value=1.0,
            step=0.5,
            help="1 pour célibataire, 2 pour couple, +0.5 par enfant (jusqu'au 2ème), +1 à partir du 3ème"
        )
        
        autres_revenus = st.number_input(
            "Autres revenus annuels du foyer (€)",
            min_value=0,
            value=0,
            step=1000,
            help="Revenus fonciers, BIC, BNC, etc."
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

# Calculs selon le pipeline correct
# 1. Net avant impôt (après cotisations sociales)
net_avant_impot = calculate_net_avant_impot(salaire_brut_annuel, statut)

# 2. Net imposable (inclut CSG/CRDS non déductible)
net_imposable = calculate_net_imposable(net_avant_impot)

# 3. Calcul de l'impôt
if mode_impot == "Taux de prélèvement manuel":
    # Mode simplifié : application du taux sur le net avant impôt
    impot_annuel = net_avant_impot * taux_prelevement
    impot_brut = impot_annuel
    decote = 0
else:
    # Mode automatique : barème progressif 2024 avec décote
    impot_annuel, impot_brut, decote = calculate_impot(
        net_imposable, 
        parts_fiscales, 
        autres_revenus,
        situation_familiale
    )

# 4. Net après impôt
net_apres_impot_annuel = net_avant_impot - impot_annuel

# 5. Déductions personnelles mensuelles
deductions_mensuelles = mutuelle + retraite_supp + part_salariale_transport + autres_deductions
deductions_annuelles = deductions_mensuelles * 12

# 6. Net cash réel (ce qui reste vraiment)
net_cash_annuel = net_apres_impot_annuel - deductions_annuelles

# Calcul des revenus par période (basé sur le net cash)
heures_travaillees_annuel = heures_semaine * semaines_travaillees
secondes_travaillees_annuel = heures_travaillees_annuel * 3600

revenu_par_seconde = net_cash_annuel / secondes_travaillees_annuel
revenu_par_minute = revenu_par_seconde * 60
revenu_par_heure = revenu_par_minute * 60
revenu_par_jour = revenu_par_heure * (heures_semaine / 5)  # Supposant 5 jours/semaine
revenu_mensuel = net_cash_annuel / 12

# Vérification des heures de travail
now = datetime.now().time()
is_work_hours = heure_debut <= now <= heure_fin

# Affichage des métriques principales
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Net Cash Annuel", f"{net_cash_annuel:,.2f} €", 
              help="Votre revenu réel après impôts et déductions")
with col2:
    st.metric("Revenu Mensuel", f"{revenu_mensuel:,.2f} €")
with col3:
    st.metric("Par Heure", f"{revenu_par_heure:.2f} €")
with col4:
    st.metric("Par Seconde", f"{revenu_par_seconde:.4f} €")

# Séparateur
st.divider()

# Zone du compteur en temps réel
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Compteur en temps réel")
    
    if not is_work_hours:
        st.warning(f"⏸️ Vous n'êtes pas dans vos heures de travail ({heure_debut.strftime('%H:%M')} - {heure_fin.strftime('%H:%M')})")
    
    # Contrôles
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("▶️ Démarrer" if not st.session_state.running else "⏸️ Pause", use_container_width=True):
            st.session_state.running = not st.session_state.running
            st.session_state.last_update = time.time()
    
    with col_btn2:
        if st.button("⌫ Reset journalier", use_container_width=True):
            st.session_state.total_earned_today = 0.0
            st.session_state.start_time = None
            st.session_state.last_update = time.time()
    
    with col_btn3:
        if st.button("🕐 Selon l'heure actuelle", use_container_width=True):
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
    st.subheader("Statistiques du jour")
    temps_ecoule = st.session_state.total_earned_today / revenu_par_seconde if revenu_par_seconde > 0 else 0
    heures = int(temps_ecoule // 3600)
    minutes = int((temps_ecoule % 3600) // 60)
    secondes = int(temps_ecoule % 60)
    
    st.metric("Temps travaillé", f"{heures}h {minutes}m {secondes}s")
    st.metric("Objectif journalier", f"{revenu_par_jour:.2f} €")
    
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
st.subheader("Comparaisons")

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
with st.expander("📊 Détails des Calculs (Pipeline fiscal 2024)"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Décomposition du salaire")
        charges_sociales = salaire_brut_annuel - net_avant_impot
        
        data = {
            "Étape": [
                "1. Salaire brut annuel",
                "2. Charges sociales salariales",
                "3. Net avant impôt",
                "4. Net imposable (×1.07)",
                "5. Impôt brut (barème)",
                "6. Décote appliquée",
                "7. Impôt final",
                "8. Net après impôt",
                "9. Déductions mensuelles",
                "10. Net cash réel"
            ],
            "Montant (€)": [
                f"{salaire_brut_annuel:,.2f}",
                f"-{charges_sociales:,.2f}",
                f"{net_avant_impot:,.2f}",
                f"{net_imposable:,.2f}",
                f"{impot_brut:,.2f}",
                f"-{decote:,.2f}" if decote > 0 else "0.00",
                f"-{impot_annuel:,.2f}",
                f"{net_apres_impot_annuel:,.2f}",
                f"-{deductions_annuelles:,.2f}",
                f"{net_cash_annuel:,.2f}"
            ]
        }
        st.dataframe(data, hide_index=True, use_container_width=True)
        
        if mode_impot != "Taux de prélèvement manuel":
            taux_effectif = (impot_annuel / net_imposable * 100) if net_imposable > 0 else 0
            st.caption(f"📌 Taux d'imposition effectif: **{taux_effectif:.2f}%**")
            st.caption(f"📌 Quotient familial: {parts_fiscales} part(s)")
    
    with col2:
        st.markdown("### Répartition temporelle")
        data_temps = {
            "Période": ["Par seconde", "Par minute", "Par heure", "Par jour", "Par mois", "Par an"],
            "Revenu net (€)": [
                f"{revenu_par_seconde:.4f}",
                f"{revenu_par_minute:.2f}",
                f"{revenu_par_heure:.2f}",
                f"{revenu_par_jour:.2f}",
                f"{revenu_mensuel:.2f}",
                f"{net_cash_annuel:,.2f}"
            ]
        }
        st.dataframe(data_temps, hide_index=True, use_container_width=True)
        
        st.markdown("### Taux de prélèvement")
        taux_total = ((salaire_brut_annuel - net_cash_annuel) / salaire_brut_annuel * 100) if salaire_brut_annuel > 0 else 0
        taux_charges = (charges_sociales / salaire_brut_annuel * 100) if salaire_brut_annuel > 0 else 0
        taux_impot = (impot_annuel / salaire_brut_annuel * 100) if salaire_brut_annuel > 0 else 0
        taux_deductions = (deductions_annuelles / salaire_brut_annuel * 100) if salaire_brut_annuel > 0 else 0
        
        st.caption(f"💰 Charges sociales: **{taux_charges:.1f}%**")
        st.caption(f"💰 Impôt sur le revenu: **{taux_impot:.1f}%**")
        st.caption(f"💰 Déductions perso: **{taux_deductions:.1f}%**")
        st.caption(f"💰 **Prélèvement total: {taux_total:.1f}%**")

# Footer
st.divider()
st.caption("✅ Calculs conformes au barème progressif 2024 avec décote • Ces calculs sont des approximations basées sur la fiscalité française 2024. Consultez un expert-comptable pour votre situation personnelle.")

import streamlit as st
import time
from datetime import datetime, time as dt_time
import pandas as pd
import plotly.graph_objects as go

# Configuration de la page
st.set_page_config(
    page_title="💰 Compteur de Revenu",
    page_icon="💰",
    layout="wide"
)

# Initialisation de session_state
if 'running' not in st.session_state:
    st.session_state.running = False
if 'total_earned_today' not in st.session_state:
    st.session_state.total_earned_today = 0.0
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()

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
st.title("💰 Compteur de Revenu en Temps Réel")
st.markdown("### Visualisez combien vous gagnez seconde après seconde")

# Sidebar pour la configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Section Salaire
    st.subheader("💼 Informations Salariales")
    salaire_brut_annuel = st.number_input(
        "Salaire brut annuel (€)",
        min_value=0,
        value=45000,
        step=1000,
        help="Votre salaire brut annuel en euros"
    )
    
    statut = st.selectbox(
        "Statut",
        ["Cadre", "Non-cadre", "Fonction publique"],
        help="Votre statut professionnel"
    )
    
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
    
    autres_deductions = st.number_input(
        "Autres déductions mensuelles (€)",
        min_value=0,
        value=0,
        step=10
    )

# Calculs
net_avant_impot = calculate_net_salary(salaire_brut_annuel, statut)

if mode_impot == "Taux de prélèvement":
    impot_annuel = net_avant_impot * taux_prelevement
else:
    impot_annuel = calculate_impot(net_avant_impot, parts_fiscales, autres_revenus)

deductions_annuelles = (mutuelle + retraite_supp + autres_deductions) * 12
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
            st.session_state.last_update = time.time()
    
    with col_btn3:
        if st.button("🔃 Actualiser", use_container_width=True):
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
        st.progress(min(progression / 100, 1.0))
        st.caption(f"Progression: {progression:.1f}%")

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

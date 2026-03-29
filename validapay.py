import streamlit as st
import pandas as pd
import io
import streamlit_folium as st_folium
import folium
import google.generativeai as genai
from PIL import Image

from validation import (
    normaliser_texte,
    nettoyer_telephone,
    valider_format_tel,
    executer_validation,
    construire_contexte_ia,
    reponse_assistant_local,
    detecter_colonne_geo,
    generer_corrections,
    generer_rapport_colore,
    generer_liste_valides,
    generer_journal_corrections,
)

# Configuration de l'IA
# Recommandation: gemini-2.5-pro (meilleure qualité d'analyse).
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('models/gemini-2.0-flash')
MODEL_OPTIONS = {
    "Assistant local (sans quota API)": None,
    "Gemini 2.5 Pro (recommandé)": "models/gemini-2.5-pro",
    "Gemini 2.5 Flash (rapide)": "models/gemini-2.5-flash",
    "Gemini 2.0 Flash (compatibilité)": "models/gemini-2.0-flash",
}

# Configuration de la page
st.set_page_config(page_title="ValidaPay Pro", page_icon="🇧🇫", layout="wide")

# 1. Affichage du Logo centré (avant le titre)
try:
    col_l1, col_l2, col_l3 = st.columns([2, 1, 2])
    with col_l2:
        logo = Image.open("logo_sante.png")
        st.image(logo, use_container_width=True)
except Exception:
    st.write("")

# 2. Titre de l'application centré
st.markdown(
    """
    <h1 style='text-align: center; color: #007BFF; margin-top: -20px;'>
        ValidPay-ASBC
    </h1>
    <p style='text-align: center; font-size: 1.2em; font-weight: bold;'>
        Direction de la Santé Communautaire
    </p>
    """,
    unsafe_allow_html=True
)

st.divider()

# 1. Chargement des fichiers
col1, col2 = st.columns(2)
with col1:
    st.subheader("1. Base de référence (PGA)")
    ref_file = st.file_uploader("Personnel de référence (Excel)", type=['xlsx'], key="ref")

with col2:
    st.subheader("2. Liste de paiement")
    pay_file = st.file_uploader("Liste à valider (Excel)", type=['xlsx'], key="pay")

if ref_file and pay_file:
    df_ref = pd.read_excel(ref_file, engine='calamine').astype(str)
    df_pay = pd.read_excel(pay_file, engine='calamine').astype(str)
    st.success("Fichiers chargés avec succès !")

    st.header("🔍 Configuration")
    colonnes_pay = df_pay.columns.tolist()

    # --- MONTANT DE L'INDEMNITÉ ---
    c_fin1, c_fin2 = st.columns([1, 2])
    with c_fin1:
        montant_indemnite = st.number_input("Indemnité par ASBC (FCFA)", value=20000, step=1000)
    with c_fin2:
        st.caption("Ce montant sera utilisé pour calculer l'impact financier des rejets (doublons, absents, etc.).")

    c_a, c_b, c_c, c_d = st.columns(4)
    with c_a:
        cols_cles = st.multiselect("Colonnes clés ID (ex: Nom, Prénom) :", colonnes_pay)
    with c_b:
        cols_doublons = st.multiselect("Colonnes pour les doublons :", colonnes_pay)
    with c_c:
        col_tel = st.selectbox("Colonne Téléphone :", ["Aucune"] + colonnes_pay)
    with c_d:
        col_village = st.selectbox("Colonne Village :", ["Aucune"] + colonnes_pay)

    if cols_cles:
        # Création de la clé unique
        df_pay['CLE_UNIQUE'] = df_pay[cols_cles].agg('-'.join, axis=1)

        if all(c in df_ref.columns for c in cols_cles):
            df_ref['CLE_UNIQUE'] = df_ref[cols_cles].agg('-'.join, axis=1)

            # Paramètres de validation
            tel_col = col_tel if col_tel != "Aucune" else None
            village_col = col_village if col_village != "Aucune" else None

            # Validation initiale
            df_pay = executer_validation(df_pay, df_ref, col_tel=tel_col, cols_doublons=cols_doublons, col_village=village_col)

            # --- CORRECTION ASSISTÉE ---
            st.subheader("🛠️ Correction assistée")
            st.caption("Aperçu des corrections proposées (normalisation texte et nettoyage téléphone) avant recalcul des statuts.")

            colonnes_texte = sorted(set(cols_cles + cols_doublons + ([col_village] if village_col else [])))
            df_preview, journal_corrections = generer_corrections(df_pay, colonnes_texte, col_tel=tel_col)

            if journal_corrections:
                df_journal = pd.DataFrame(journal_corrections)
                st.info(f"{len(df_journal)} correction(s) potentielle(s) détectée(s).")
                st.dataframe(df_journal.head(100), use_container_width=True)

                if st.button("✅ Appliquer les corrections recommandées"):
                    df_pay = df_preview.copy()
                    df_pay['CLE_UNIQUE'] = df_pay[cols_cles].agg('-'.join, axis=1)
                    df_pay = executer_validation(df_pay, df_ref, col_tel=tel_col, cols_doublons=cols_doublons, col_village=village_col)
                    st.success("Corrections appliquées et validation recalculée.")
            else:
                df_journal = pd.DataFrame()
                st.success("Aucune correction automatique suggérée.")

            # --- AFFICHAGE DES RÉSULTATS ---
            st.divider()

            # Calcul des compteurs
            nb_valides = len(df_pay[df_pay['Statut_ValidaPay'] == 'Valide'])
            nb_absents = len(df_pay[df_pay['Statut_ValidaPay'] == 'Absent'])
            nb_doublons = len(df_pay[df_pay['Statut_ValidaPay'] == 'Doublon'])
            nb_village = len(df_pay[df_pay['Statut_ValidaPay'] == 'Quota Village Dépassé'])
            nb_tel = len(df_pay[df_pay['Statut_ValidaPay'] == 'Erreur Format Tel'])

            # Calcul financier
            nb_total_rejets = len(df_pay[df_pay['Statut_ValidaPay'] != 'Valide'])
            eco_totale = nb_total_rejets * montant_indemnite

            # Affichage des indicateurs en colonnes
            st.subheader("📊 Résultats de la validation")
            res = st.columns(6)
            res[0].metric("✅ Valides", f"{nb_valides}")
            res[1].metric("❌ Absents", f"{nb_absents}")
            res[2].metric("👯 Doublons", f"{nb_doublons}")
            res[3].metric("🏘️ Quota Village", f"{nb_village}")
            res[4].metric("📞 Erreurs Tel", f"{nb_tel}")
            res[5].metric("💰 Économie (FCFA)", f"{eco_totale:,.0f}")

            # Message d'alerte si des erreurs existent
            if eco_totale > 0:
                st.info(f"💡 **Impact budgétaire :** Cette validation permet d'économiser **{eco_totale:,.0f} FCFA**.")

            # Tableau des erreurs
            st.subheader("📋 Détail des incohérences")
            anomalies = df_pay[df_pay['Statut_ValidaPay'] != 'Valide'].drop(columns=['CLE_UNIQUE'], errors='ignore')
            if not anomalies.empty:
                st.dataframe(anomalies, use_container_width=True)
            else:
                st.success("Aucune anomalie détectée sur cette liste !")

            # --- GRAPHIQUE ANALYTIQUE PAR DISTRICT ---
            st.write("")
            col_geo = detecter_colonne_geo(df_pay.columns)

            if col_geo:
                st.subheader(f"📊 Répartition des incohérences par {col_geo}")
                df_erreurs_graph = df_pay[df_pay['Statut_ValidaPay'] != 'Valide']

                if not df_erreurs_graph.empty:
                    chart_data = df_erreurs_graph.groupby(col_geo).size().reset_index(name='Nombre de rejets')
                    chart_data = chart_data.sort_values(by='Nombre de rejets', ascending=False)
                    st.bar_chart(chart_data.set_index(col_geo)['Nombre de rejets'])
                    st.caption(f"Zones où les erreurs de saisie, les doublons ou les absences sont les plus élevés.")
                else:
                    st.success("Aucune erreur à afficher sur le graphique !")

            # --- GÉNÉRATION DES EXPORTS ---
            st.divider()
            st.subheader("📥 Exportation des fichiers")

            exp1, exp2 = st.columns(2)
            with exp1:
                st.download_button(
                    label="📥 Télécharger le Rapport global avec les incohérences",
                    data=generer_rapport_colore(df_pay),
                    file_name="Rapport_ValidPay_Colore.xlsx",
                )
            with exp2:
                st.download_button(
                    label="📥 Télécharger la liste des ASBC validés",
                    data=generer_liste_valides(df_pay),
                    file_name="Liste_ASBC_Valides.xlsx",
                )

            if journal_corrections:
                journal_bytes = generer_journal_corrections(journal_corrections)
                if journal_bytes:
                    st.download_button(
                        label="📥 Télécharger le journal des corrections",
                        data=journal_bytes,
                        file_name="Journal_Corrections_ValidPay.xlsx",
                    )

        else:
            st.error("Les colonnes clés sélectionnées ne correspondent pas dans la base de référence.")
    else:
        st.info("Sélectionnez les colonnes clés pour lancer l'analyse.")

# --- SECTION CHATBOT ASSISTANT IA ---
st.divider()
st.header("🔬 Assistant IA")

c_ia_1, c_ia_2 = st.columns([2, 1])
with c_ia_1:
    modele_selectionne = st.selectbox(
        "Modèle IA",
        list(MODEL_OPTIONS.keys()),
        index=1,
        help="Choisissez Gemini 2.5 Pro pour la meilleure qualité d'analyse, ou Flash pour plus de vitesse."
    )
with c_ia_2:
    st.caption("🏆 Meilleur modèle recommandé: Gemini 2.5 Pro | ✅ Alternative sans quota: Assistant local")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ex: Quel est le taux de rejet par district ?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    contexte = construire_contexte_ia(df_pay if 'df_pay' in locals() else None)

    with st.chat_message("assistant"):
        try:
            modele_id = MODEL_OPTIONS[modele_selectionne]
            if modele_id is None:
                texte_reponse = reponse_assistant_local(df_pay if 'df_pay' in locals() else None, prompt)
            else:
                modele_ia = genai.GenerativeModel(modele_id)
                full_prompt = f"{contexte}\n\nQuestion utilisateur: {prompt}"
                response = modele_ia.generate_content(full_prompt)
                texte_reponse = response.text if hasattr(response, "text") and response.text else "Je n'ai pas pu générer de réponse exploitable."

            st.markdown(texte_reponse)
            st.session_state.messages.append({"role": "assistant", "content": texte_reponse})
        except Exception as e:
            msg = str(e)
            if "429" in msg or "quota" in msg.lower() or "rate" in msg.lower():
                st.warning("Quota IA atteint. Bascule automatique vers l'Assistant local (sans API).")
                texte_reponse = reponse_assistant_local(df_pay if 'df_pay' in locals() else None, prompt)
                st.markdown(texte_reponse)
                st.session_state.messages.append({"role": "assistant", "content": texte_reponse})
            else:
                st.error(f"Erreur IA : {msg}")

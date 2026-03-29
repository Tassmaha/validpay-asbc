"""
Core validation logic for ValidPay-ASBC.

Extracted from validapay.py to enable unit testing without Streamlit dependencies.
"""

import pandas as pd


def normaliser_texte(valeur):
    """Normalize text: strip, uppercase, collapse whitespace."""
    return " ".join(str(valeur).strip().upper().split())


def nettoyer_telephone(valeur):
    """Remove non-digit characters from a phone number."""
    return "".join(ch for ch in str(valeur) if ch.isdigit())


def valider_format_tel(val):
    """Validate phone number format: must be exactly 8 digits."""
    val_str = str(val).strip()
    if not val_str.isdigit():
        return "Alphanumérique"
    if len(val_str) != 8:
        return "Longueur Incorrecte"
    return "OK"


def executer_validation(df_pay, df_ref, col_tel=None, cols_doublons=None, col_village=None):
    """
    Run the full validation pipeline on a payment DataFrame.

    Args:
        df_pay: Payment DataFrame (must have 'CLE_UNIQUE' column).
        df_ref: Reference DataFrame (must have 'CLE_UNIQUE' column).
        col_tel: Name of the phone column, or None to skip phone validation.
        cols_doublons: List of columns for duplicate detection, or empty list.
        col_village: Name of the village column, or None to skip village quota check.

    Returns:
        The df_pay DataFrame with a 'Statut_ValidaPay' column added/updated.
    """
    if cols_doublons is None:
        cols_doublons = []

    df_pay = df_pay.copy()
    df_pay["Statut_ValidaPay"] = "Valide"

    # 1. Phone format validation (lowest priority)
    if col_tel is not None and col_tel in df_pay.columns:
        verif_tel = df_pay[col_tel].apply(valider_format_tel)
        df_pay.loc[verif_tel != "OK", "Statut_ValidaPay"] = "Erreur Format Tel"

    # 2. Absent check (overrides phone error)
    mask_absent = ~df_pay["CLE_UNIQUE"].isin(df_ref["CLE_UNIQUE"])
    df_pay.loc[mask_absent, "Statut_ValidaPay"] = "Absent"

    # 3. Duplicate check (overrides absent)
    if cols_doublons:
        mask_doublon = df_pay.duplicated(subset=cols_doublons, keep=False)
        df_pay.loc[mask_doublon, "Statut_ValidaPay"] = "Doublon"

    # 4. Village quota (overrides all — max 2 ASBC per village)
    if col_village is not None and col_village in df_pay.columns:
        serie_village = df_pay[col_village].astype(str).str.strip()
        mask_village_valide = serie_village != ""
        comptes_village = serie_village[mask_village_valide].value_counts()
        villages_satures = comptes_village[comptes_village > 2].index
        mask_sur_effectif = serie_village.isin(villages_satures)
        df_pay.loc[mask_sur_effectif, "Statut_ValidaPay"] = "Quota Village Dépassé"

    return df_pay


def construire_contexte_ia(dataframe):
    """Build AI context string from validation results."""
    if dataframe is None or "Statut_ValidaPay" not in dataframe.columns:
        return "L'analyse n'est pas encore lancée."

    total_agents = len(dataframe)
    stats_statut = dataframe["Statut_ValidaPay"].value_counts().to_dict()
    taux_anomalies = (
        (1 - (stats_statut.get("Valide", 0) / total_agents)) * 100
        if total_agents > 0
        else 0
    )

    col_geo_assistant = next(
        (
            c
            for c in dataframe.columns
            if any(x in c.lower() for x in ["district", "ds", "région", "province"])
        ),
        None,
    )

    resume_geo = "Non disponible"
    if col_geo_assistant:
        erreurs_geo = dataframe[dataframe["Statut_ValidaPay"] != "Valide"]
        if not erreurs_geo.empty:
            top_geo = erreurs_geo[col_geo_assistant].value_counts().head(3).to_dict()
            resume_geo = f"Top zones en anomalies ({col_geo_assistant}): {top_geo}"

    return f"""
    Tu es l'analyste expert de la Direction de la Santé Communautaire au Burkina Faso.
    Réponds en français, de manière professionnelle et concise.
    Donne systématiquement :
    1) un constat chiffré,
    2) une interprétation,
    3) 2 recommandations opérationnelles.

    DONNÉES:
    - Total agents: {total_agents}
    - Répartition statuts: {stats_statut}
    - Taux anomalies: {taux_anomalies:.1f}%
    - {resume_geo}
    """


def reponse_assistant_local(dataframe, question):
    """Generate a local (non-API) analysis response."""
    if dataframe is None or "Statut_ValidaPay" not in dataframe.columns:
        return (
            "L'analyse n'est pas encore lancée. Chargez les fichiers, sélectionnez les colonnes clés "
            "puis relancez votre question."
        )

    total_agents = len(dataframe)
    stats_statut = dataframe["Statut_ValidaPay"].value_counts().to_dict()
    nb_valides = stats_statut.get("Valide", 0)
    nb_rejets = total_agents - nb_valides
    taux_anomalies = (nb_rejets / total_agents) * 100 if total_agents > 0 else 0

    top_anomalies = (
        dataframe[dataframe["Statut_ValidaPay"] != "Valide"]["Statut_ValidaPay"]
        .value_counts()
        .head(3)
        .to_dict()
    )

    col_geo_assistant = next(
        (
            c
            for c in dataframe.columns
            if any(x in c.lower() for x in ["district", "ds", "région", "province"])
        ),
        None,
    )
    detail_geo = "Non disponible"
    if col_geo_assistant:
        erreurs_geo = dataframe[dataframe["Statut_ValidaPay"] != "Valide"]
        if not erreurs_geo.empty:
            detail_geo = erreurs_geo[col_geo_assistant].value_counts().head(3).to_dict()

    return f"""
**Analyse locale (sans IA de gemini)**

1) **Constat chiffré**
- Total ASBC analysés: **{total_agents}**
- Valides: **{nb_valides}**
- Rejets: **{nb_rejets}**
- Taux d'anomalies: **{taux_anomalies:.1f}%**
- Principales anomalies: **{top_anomalies if top_anomalies else 'Aucune'}**

2) **Interprétation**
La question posée était: _{question}_.
Le niveau d'anomalies observé indique une priorité de correction sur les statuts les plus fréquents.
Top zones en anomalies: **{detail_geo}**.

3) **Recommandations**
- Corriger en priorité les statuts dominants puis relancer la validation.
- Mettre en place un contrôle en amont sur la saisie téléphone et la qualité des identifiants.
"""

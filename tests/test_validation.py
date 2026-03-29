"""
Tests for ValidPay-ASBC validation logic.

These tests cover the pure functions and core validation pipeline
extracted from validapay.py.
"""

import math

import pandas as pd
import pytest

# Import functions from the extracted module
from validation import (
    construire_contexte_ia,
    executer_validation,
    nettoyer_telephone,
    normaliser_texte,
    reponse_assistant_local,
    valider_format_tel,
)


# ─── normaliser_texte ────────────────────────────────────────────────────────


class TestNormaliserTexte:
    def test_basic_uppercase(self):
        assert normaliser_texte("jean dupont") == "JEAN DUPONT"

    def test_strips_leading_trailing_whitespace(self):
        assert normaliser_texte("  jean  ") == "JEAN"

    def test_collapses_internal_whitespace(self):
        assert normaliser_texte("jean   pierre   dupont") == "JEAN PIERRE DUPONT"

    def test_already_normalized(self):
        assert normaliser_texte("JEAN") == "JEAN"

    def test_empty_string(self):
        assert normaliser_texte("") == ""

    def test_numeric_input(self):
        assert normaliser_texte(123) == "123"

    def test_none_input(self):
        assert normaliser_texte(None) == "NONE"

    def test_nan_input(self):
        assert normaliser_texte(float("nan")) == "NAN"

    def test_tabs_and_newlines(self):
        result = normaliser_texte("jean\t\n dupont")
        assert result == "JEAN DUPONT"


# ─── nettoyer_telephone ─────────────────────────────────────────────────────


class TestNettoyerTelephone:
    def test_pure_digits_unchanged(self):
        assert nettoyer_telephone("70123456") == "70123456"

    def test_removes_letters(self):
        assert nettoyer_telephone("70aa5522") == "705522"

    def test_removes_spaces(self):
        assert nettoyer_telephone("70 12 34 56") == "70123456"

    def test_removes_dashes(self):
        assert nettoyer_telephone("70-12-34-56") == "70123456"

    def test_removes_dots(self):
        assert nettoyer_telephone("70.12.34.56") == "70123456"

    def test_removes_plus_prefix(self):
        assert nettoyer_telephone("+22670123456") == "22670123456"

    def test_empty_string(self):
        assert nettoyer_telephone("") == ""

    def test_no_digits(self):
        assert nettoyer_telephone("abcdef") == ""

    def test_float_string(self):
        assert nettoyer_telephone("70123456.0") == "701234560"

    def test_numeric_input(self):
        assert nettoyer_telephone(70123456) == "70123456"


# ─── valider_format_tel ─────────────────────────────────────────────────────


class TestValiderFormatTel:
    def test_valid_8_digits(self):
        assert valider_format_tel("70123456") == "OK"

    def test_alphanumeric(self):
        assert valider_format_tel("70aa5522") == "Alphanumérique"

    def test_too_short(self):
        assert valider_format_tel("7012") == "Longueur Incorrecte"

    def test_too_long(self):
        assert valider_format_tel("701234567890") == "Longueur Incorrecte"

    def test_empty_string(self):
        assert valider_format_tel("") == "Alphanumérique"

    def test_with_spaces_stripped(self):
        assert valider_format_tel("  70123456  ") == "OK"

    def test_letters_only(self):
        assert valider_format_tel("abcdefgh") == "Alphanumérique"

    def test_special_characters(self):
        assert valider_format_tel("70-12-34") == "Alphanumérique"


# ─── executer_validation ────────────────────────────────────────────────────


class TestExecuterValidation:
    @staticmethod
    def _make_ref(names):
        """Helper to create a reference DataFrame."""
        return pd.DataFrame({"Nom": names, "CLE_UNIQUE": names})

    @staticmethod
    def _make_pay(names, phones=None, villages=None):
        """Helper to create a payment DataFrame."""
        data = {"Nom": names, "CLE_UNIQUE": names}
        if phones is not None:
            data["Telephone"] = phones
        if villages is not None:
            data["Village"] = villages
        return pd.DataFrame(data)

    def test_all_valid(self):
        df_ref = self._make_ref(["ALICE", "BOB"])
        df_pay = self._make_pay(["ALICE", "BOB"])
        result = executer_validation(df_pay, df_ref, col_tel=None, cols_doublons=[], col_village=None)
        assert (result["Statut_ValidaPay"] == "Valide").all()

    def test_absent_detected(self):
        df_ref = self._make_ref(["ALICE"])
        df_pay = self._make_pay(["ALICE", "CHARLIE"])
        result = executer_validation(df_pay, df_ref, col_tel=None, cols_doublons=[], col_village=None)
        assert result.loc[result["Nom"] == "CHARLIE", "Statut_ValidaPay"].iloc[0] == "Absent"

    def test_duplicate_detected(self):
        df_ref = self._make_ref(["ALICE", "ALICE"])
        df_pay = self._make_pay(["ALICE", "ALICE"])
        result = executer_validation(df_pay, df_ref, col_tel=None, cols_doublons=["Nom"], col_village=None)
        assert (result["Statut_ValidaPay"] == "Doublon").all()

    def test_phone_error_detected(self):
        df_ref = self._make_ref(["ALICE"])
        df_pay = self._make_pay(["ALICE"], phones=["123"])
        result = executer_validation(df_pay, df_ref, col_tel="Telephone", cols_doublons=[], col_village=None)
        assert result["Statut_ValidaPay"].iloc[0] == "Erreur Format Tel"

    def test_valid_phone_no_error(self):
        df_ref = self._make_ref(["ALICE"])
        df_pay = self._make_pay(["ALICE"], phones=["70123456"])
        result = executer_validation(df_pay, df_ref, col_tel="Telephone", cols_doublons=[], col_village=None)
        assert result["Statut_ValidaPay"].iloc[0] == "Valide"

    def test_village_quota_exceeded(self):
        df_ref = self._make_ref(["A", "B", "C"])
        df_pay = self._make_pay(["A", "B", "C"], villages=["V1", "V1", "V1"])
        result = executer_validation(df_pay, df_ref, col_tel=None, cols_doublons=[], col_village="Village")
        assert (result["Statut_ValidaPay"] == "Quota Village Dépassé").all()

    def test_village_quota_within_limit(self):
        df_ref = self._make_ref(["A", "B"])
        df_pay = self._make_pay(["A", "B"], villages=["V1", "V1"])
        result = executer_validation(df_pay, df_ref, col_tel=None, cols_doublons=[], col_village="Village")
        assert (result["Statut_ValidaPay"] == "Valide").all()

    def test_priority_absent_over_phone_error(self):
        """Absent status should override phone format error."""
        df_ref = self._make_ref(["ALICE"])
        df_pay = self._make_pay(["BOB"], phones=["bad"])
        result = executer_validation(df_pay, df_ref, col_tel="Telephone", cols_doublons=[], col_village=None)
        assert result["Statut_ValidaPay"].iloc[0] == "Absent"

    def test_priority_doublon_over_absent(self):
        """Doublon status should override absent status."""
        df_ref = self._make_ref(["ALICE"])
        df_pay = self._make_pay(["BOB", "BOB"])
        result = executer_validation(df_pay, df_ref, col_tel=None, cols_doublons=["Nom"], col_village=None)
        assert (result["Statut_ValidaPay"] == "Doublon").all()

    def test_empty_payment_dataframe(self):
        df_ref = self._make_ref(["ALICE"])
        df_pay = self._make_pay([])
        result = executer_validation(df_pay, df_ref, col_tel=None, cols_doublons=[], col_village=None)
        assert len(result) == 0


# ─── construire_contexte_ia ─────────────────────────────────────────────────


class TestConstruireContexteIA:
    def test_none_dataframe(self):
        result = construire_contexte_ia(None)
        assert "pas encore lancée" in result

    def test_missing_column(self):
        df = pd.DataFrame({"col": [1, 2]})
        result = construire_contexte_ia(df)
        assert "pas encore lancée" in result

    def test_valid_dataframe(self):
        df = pd.DataFrame({"Statut_ValidaPay": ["Valide", "Absent", "Valide"]})
        result = construire_contexte_ia(df)
        assert "Total agents: 3" in result
        assert "33.3%" in result

    def test_geo_column_detected(self):
        df = pd.DataFrame({
            "Statut_ValidaPay": ["Valide", "Absent"],
            "District": ["D1", "D1"],
        })
        result = construire_contexte_ia(df)
        assert "District" in result


# ─── reponse_assistant_local ────────────────────────────────────────────────


class TestReponseAssistantLocal:
    def test_none_dataframe(self):
        result = reponse_assistant_local(None, "test question")
        assert "pas encore lancée" in result

    def test_missing_column(self):
        df = pd.DataFrame({"col": [1]})
        result = reponse_assistant_local(df, "test")
        assert "pas encore lancée" in result

    def test_includes_question(self):
        df = pd.DataFrame({"Statut_ValidaPay": ["Valide", "Absent"]})
        result = reponse_assistant_local(df, "Quel est le taux?")
        assert "Quel est le taux?" in result

    def test_correct_counts(self):
        df = pd.DataFrame({"Statut_ValidaPay": ["Valide", "Absent", "Doublon"]})
        result = reponse_assistant_local(df, "analyse")
        assert "**3**" in result  # total
        assert "**1**" in result  # valides
        assert "**2**" in result  # rejets

    def test_zero_anomalies(self):
        df = pd.DataFrame({"Statut_ValidaPay": ["Valide", "Valide"]})
        result = reponse_assistant_local(df, "analyse")
        assert "0.0%" in result

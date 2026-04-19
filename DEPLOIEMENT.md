# Guide de déploiement — ValidPay-ASBC

## Option recommandée : Streamlit Community Cloud (gratuit)

### Prérequis
- Un compte GitHub avec ce repo accessible
- Un compte Streamlit Cloud (https://streamlit.io/cloud — connexion via GitHub)
- (Optionnel) Une clé API Google Gemini : https://aistudio.google.com/apikey

### Étapes

1. **Se connecter** à https://share.streamlit.io
2. Cliquer **"New app"**
3. Renseigner :
   - **Repository** : `Tassmaha/validpay-asbc`
   - **Branch** : `main` (ou la branche de production)
   - **Main file path** : `validapay.py`
4. Cliquer sur **"Advanced settings"** → onglet **"Secrets"**
5. Coller le contenu suivant (remplacer par votre vraie clé) :
   ```toml
   GEMINI_API_KEY = "votre-cle-gemini-ici"
   ```
   > L'app fonctionne aussi sans clé — seul l'Assistant local sera disponible.
6. Cliquer **"Deploy"**

L'URL publique sera de la forme :
`https://<nom-app>.streamlit.app`

### Mises à jour
Tout push sur la branche configurée redéploie automatiquement l'app.

---

## Alternative : déploiement local

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. (Optionnel) Configurer la clé API
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# puis éditer le fichier pour y mettre votre clé

# 3. Lancer l'app
streamlit run validapay.py
```

L'app sera accessible sur http://localhost:8501

---

## Alternative : Docker

Le repo contient déjà un `.devcontainer/` utilisable. Pour un déploiement Docker simple :

```bash
docker run -p 8501:8501 \
  -v $(pwd):/app \
  -w /app \
  -e GEMINI_API_KEY=your-key \
  python:3.11 \
  bash -c "pip install -r requirements.txt && streamlit run validapay.py"
```

---

## Lancer les tests

```bash
pip install -r requirements-test.txt
python -m pytest tests/ -v
```

Couverture actuelle : **82 tests** sur la logique métier (`validation.py`).

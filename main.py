import streamlit as st  # Importe la bibliothèque Streamlit pour créer une application web
import pandas as pd     # Importe Pandas pour lire et manipuler des fichiers Excel
import re               # Importe 're' pour utiliser des expressions régulières (utile pour extraire un ID depuis une URL)
from azure.storage.blob import BlobServiceClient  # Permet de se connecter au stockage Azure
from io import BytesIO  # Permet de lire un fichier téléchargé directement depuis la mémoire (sans l’enregistrer sur le disque)
import os

# Cette fonction charge et fusionne tous les fichiers Excel présents dans le conteneur Azure
@st.cache_data  # Évite de recharger les fichiers à chaque fois que l’utilisateur interagit avec l’interface
def load_data():
    connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")  # Récupère la chaîne de connexion Azure depuis les variables d'environnement
    container_name = os.getenv("AZURE_CONTAINER_NAME")          # Récupère le nom du conteneur Azure depuis les variables d'environnement

    if not connect_str:
        st.error("La variable d'environnement AZURE_STORAGE_CONNECTION_STRING n'est pas définie.")
        return pd.DataFrame()  # Retourne un DataFrame vide pour éviter les erreurs

    if not container_name:
        st.error("La variable d'environnement AZURE_CONTAINER_NAME n'est pas définie.")
        return pd.DataFrame()

    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    container_client = blob_service_client.get_container_client(container_name)

    all_dfs = []
    for blob in container_client.list_blobs():
        if blob.name.endswith(".xlsx"):
            blob_client = container_client.get_blob_client(blob)
            stream = blob_client.download_blob()
            df = pd.read_excel(BytesIO(stream.readall()))
            all_dfs.append(df)

    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
    else:
        final_df = pd.DataFrame()

    return final_df

df = load_data()  # Charge les données au lancement de l’application

# === Interface de l'application ===

st.title("Correspondence Table")  # Titre principal de l'application
st.markdown(
    "Please select a method to search for the new SharePoint link of your file. "
    "You can search by Name, ID, or Google Path.",
    unsafe_allow_html=True
)  # Texte d'introduction

# Initialise les états de l'application (choix du mode et champ de recherche)
if "mode_selection" not in st.session_state:
    st.session_state.mode_selection = None
if "user_input" not in st.session_state:
    st.session_state.user_input = ""

# Fonction appelée quand on clique sur un bouton de recherche
def select_mode(mode):
    st.session_state.mode_selection = mode  # Enregistre le mode sélectionné
    st.session_state.user_input = ""        # Réinitialise la saisie

# Affiche 3 boutons pour choisir le type de recherche
col1, col2, col3 = st.columns(3)
with col1:
    st.button("🔍 Name File", on_click=select_mode, args=("name",))  # Recherche par nom
with col2:
    st.button("🔗 Google Link", on_click=select_mode, args=("link",))  # Recherche par lien Google
with col3:
    st.button("🆔 ID File", on_click=select_mode, args=("id",))  # Recherche par ID

# Affiche une zone de texte selon le mode sélectionné
user_input = None
if st.session_state.mode_selection == "name":
    user_input = st.text_input("Please enter the **name** of your file  :", key="user_input")
    column_to_search = "FileName"  # Colonne à rechercher
elif st.session_state.mode_selection == "link":
    user_input = st.text_input("Please enter the **Google link** of your file :", key="user_input")
    column_to_search = "PathGoogle"
elif st.session_state.mode_selection == "id":
    user_input = st.text_input("Please enter the **ID** of your file :", key="user_input")
    column_to_search = "FileID"

# Fonction utilitaire pour extraire un ID depuis un lien Google (Sheets ou Drive)
def extract_google_file_id(link):
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", link)  # Cherche un ID après '/d/' dans l'URL
    if match:
        return match.group(1)  # Retourne l'ID trouvé
    return None  # Retourne rien si aucun ID n'est trouvé

# Quand l'utilisateur clique sur "Search"
if st.session_state.mode_selection and st.button("Search"):
    if user_input.strip() != "":  # Si l'utilisateur a bien saisi quelque chose
        user_input_clean = user_input.strip().lower()  # Nettoie et met en minuscule la saisie

        # Cas spécifique pour la recherche par lien
        if st.session_state.mode_selection == "link":
            extracted_id = extract_google_file_id(user_input_clean)  # Essaie d'extraire l'ID
            if extracted_id:
                search_series = df["PathGoogle"].astype(str).str.lower()  # Colonne de recherche en minuscule
                matches = df[search_series.str.contains(extracted_id, na=False)]  # Recherche si l’ID est présent
            else:
                matches = pd.DataFrame()  # Aucun ID trouvé → tableau vide
        else:
            search_series = df[column_to_search].astype(str).str.lower()  # Colonne de recherche
            matches = df[search_series.str.contains(user_input_clean, na=False)]  # Recherche normale

        # Affichage des résultats
        if len(matches) >= 15:
            st.warning("⚠️ Too many results. Please refine your search.")  # Trop de résultats
        elif not matches.empty:
            # Supprimer les doublons selon les colonnes clés
            matches_unique = matches.drop_duplicates(subset=["FileName", "LinkSharepoint", "PathSharepoint"])
            
            st.success(f"✅ {len(matches_unique)} unique file(s) found:")  # Résultats trouvés uniques
            for index, row in matches_unique.iterrows():  # Parcours les lignes uniques
                filename = row.get("FileName", "Nom inconnu")
                link = row.get("LinkSharepoint", "#")
                path = row.get("PathSharepoint", "Chemin inconnu")
        
                # Affiche les résultats
                st.markdown(f"**{filename}**")
                st.markdown(f"- 🔗 [Microsoft Link]({link})")
                st.markdown(f"- 📁 SharePoint Path: `{path}`")
                st.markdown("---")
        else:
            st.error("❌ No file found. Please try a different term.")  # Aucun résultat

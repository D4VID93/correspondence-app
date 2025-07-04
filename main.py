import streamlit as st
import pandas as pd
import re
from azure.storage.blob import BlobServiceClient
from io import BytesIO
import os

@st.cache_data
def load_data():
    connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_CONTAINER_NAME")

    if not connect_str:
        st.error("La variable d'environnement AZURE_STORAGE_CONNECTION_STRING n'est pas définie.")
        return pd.DataFrame()
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

def extract_google_file_id(link):
    # Patterns pour différents types de liens Google
    patterns = [
        r"/d/([a-zA-Z0-9_-]+)",      # Standard /d/ID
        r"/folders/([a-zA-Z0-9_-]+)", # Dossiers Drive
        r"id=([a-zA-Z0-9_-]+)",       # Format ?id=ID
        r"open\?id=([a-zA-Z0-9_-]+)", # Format open?id=ID
        r"spreadsheets/d/([a-zA-Z0-9_-]+)", # Google Sheets
        r"presentation/d/([a-zA-Z0-9_-]+)",  # Google Slides
        r"document/d/([a-zA-Z0-9_-]+)"       # Google Docs
    ]
    
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)
    return None

df = load_data()

st.title("Correspondence Table")
st.markdown(
    "Please select a method to search for the new SharePoint link of your file. "
    "You can search by Name, ID, or Google Path.",
    unsafe_allow_html=True
)

if "mode_selection" not in st.session_state:
    st.session_state.mode_selection = None
if "user_input" not in st.session_state:
    st.session_state.user_input = ""

def select_mode(mode):
    st.session_state.mode_selection = mode
    st.session_state.user_input = ""

col1, col2, col3 = st.columns(3)
with col1:
    st.button("🔍 Name File", on_click=select_mode, args=("name",))
with col2:
    st.button("🔗 Google Link", on_click=select_mode, args=("link",))
with col3:
    st.button("🆔 ID File", on_click=select_mode, args=("id",))

user_input = None
if st.session_state.mode_selection == "name":
    user_input = st.text_input("Please enter the **name** of your file  :", key="user_input")
    column_to_search = "FileName"
elif st.session_state.mode_selection == "link":
    user_input = st.text_input("Please enter the **Google link** of your file :", key="user_input")
    column_to_search = "PathGoogle"
elif st.session_state.mode_selection == "id":
    user_input = st.text_input("Please enter the **ID** of your file :", key="user_input")
    column_to_search = "FileID"

if st.session_state.mode_selection and st.button("Search"):
    if user_input.strip() != "":
        user_input_clean = user_input.strip().lower()

        if st.session_state.mode_selection == "link":
            extracted_id = extract_google_file_id(user_input_clean)
            if extracted_id:
                st.info(f"ℹ️ Extracted Google ID: {extracted_id}")
                search_series = df["PathGoogle"].astype(str).str.lower()
                matches = df[search_series.str.contains(extracted_id, na=False)]
                if matches.empty:
                    st.error(f"❌ No matching file found for ID: {extracted_id}")
                    st.markdown("**Possible reasons:**")
                    st.markdown("- The file hasn't been migrated to SharePoint yet")
                    st.markdown("- The Google Drive link might be incorrect")
                    st.markdown("- The link is a link to a folder and not to a file")
                    st.markdown("- The name of your file contains an accent")
                    st.markdown("👉 In those cases, please contact Basile or Rachid for assistance. ")

                    
            else:
                matches = pd.DataFrame()
                st.error("❌ Could not extract a valid Google Drive ID from the provided link")
                st.markdown("👉 If you're unable to locate your file, please contact Basile or Rachid for assistance.")


        else:
            search_series = df[column_to_search].astype(str).str.lower()
            matches = df[search_series.str.contains(user_input_clean, na=False)]

        matches = matches.drop_duplicates(subset=["FileName", "LinkSharepoint", "PathSharepoint"])

        if len(matches) >= 15:
            st.warning("⚠️ Too many results. Please refine your search.")
        elif not matches.empty:
            st.success(f"✅ {len(matches)} file(s) found:")
            for _, row in matches.iterrows():
                filename = row.get("FileName", "Nom inconnu")
                link = row.get("LinkSharepoint", "#")
                path = row.get("PathSharepoint", "Chemin inconnu")

                st.markdown(f"**{filename}**")
                st.markdown(f"- 🔗 [Microsoft Link]({link})")
                st.markdown(f"- 📁 SharePoint Path: `{path}`")
                st.markdown("---")
        else:
            st.error("❌ No file found. Please try a different term.")

import streamlit as st
import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe
from rapidfuzz import fuzz, process
from io import StringIO

# --- Config ---
FUZZY_MATCH_THRESHOLD = 80

# --- Google Auth ---
gc = gspread.service_account(filename='credentials.json')

# --- Google Sheet URLs ---
sheet_urls = {
    'Terminated Employees': 'https://docs.google.com/spreadsheets/d/1lvqwzCiT216ah5mE4KWlsSzA4SDdoriFyXMTBJh2fMo/edit?gid=0',
    'OOW Offboarding': 'https://docs.google.com/spreadsheets/d/1VRME96O2tI8yjij8st6iRQt8K8FzfwUmtC7UdALvkus/edit?gid=0',
    'IWH Offboarding South': 'https://docs.google.com/spreadsheets/d/1qbLcKRzLDuautE4ap-nI6fOH6OMAxUkj0oN1ALsG95I/edit?gid=0',
    'IWH Offboarding North': 'https://docs.google.com/spreadsheets/d/11F0oF3F6jymI0MtG1qTVzS0VG_lnbnUGx1swuUj5qmM/edit?gid=0',
    'No Show Tracker': 'https://docs.google.com/spreadsheets/d/1ejFfVVkfQOvIroZiV50OHVcjLv_8hzKinT5gTZL2wcw/edit?gid=0',
    'Failed Assessments': 'https://docs.google.com/spreadsheets/d/1ejFfVVkfQOvIroZiV50OHVcjLv_8hzKinT5gTZL2wcw/edit?gid=552972327',
}

def load_blacklist():
    blacklisted = []

    for name, url in sheet_urls.items():
        sh = gc.open_by_url(url)
        df = get_as_dataframe(sh.sheet1, evaluate_formulas=True)
        df.columns = df.columns.str.strip().str.lower()

        if 'first name' in df.columns and 'last name' in df.columns:
            df = df[['first name', 'last name']].dropna()
            df['full name'] = (df['first name'].str.strip() + ' ' + df['last name'].str.strip()).str.lower()
            for full_name in df['full name']:
                blacklisted.append({'name': full_name, 'source': name})
    return blacklisted

def get_best_match(name, blacklist, threshold=FUZZY_MATCH_THRESHOLD):
    names = [entry['name'] for entry in blacklist]
    result = process.extractOne(name, names, scorer=fuzz.token_sort_ratio)

    if result is None:
        return None, 0, ""

    match, score = result[0], result[1]
    matched_entry = next((e for e in blacklist if e['name'] == match), None)

    return match, score, matched_entry['source'] if matched_entry else ""

# --- Streamlit UI ---
st.title("🚫 Blacklist Checker")

uploaded_file = st.file_uploader("Upload a CSV file with `first name` and `last name` columns", type=["csv"])

if uploaded_file:
    user_df = pd.read_csv(uploaded_file)
    user_df.columns = user_df.columns.str.strip().str.lower()

    if 'first name' in user_df.columns and 'last name' in user_df.columns:
        user_df['full name'] = (user_df['first name'].str.strip() + ' ' + user_df['last name'].str.strip()).str.lower()
        
        with st.spinner("Checking against blacklist..."):
            blacklist = load_blacklist()
            results = user_df['full name'].apply(lambda x: get_best_match(x, blacklist))
            user_df['Best Match'] = results.apply(lambda x: x[0])
            user_df['Match Score'] = results.apply(lambda x: x[1])
            user_df['Blacklisted'] = user_df['Match Score'] >= FUZZY_MATCH_THRESHOLD
            user_df['Matched From'] = results.apply(lambda x: x[2] if x[1] >= FUZZY_MATCH_THRESHOLD else "")

        st.success("✅ Matching complete.")
# Filter for blacklisted only
        matches_df = user_df[user_df['Blacklisted']]

        if not matches_df.empty:
            st.subheader("🚨 Blacklisted Matches")
            st.dataframe(matches_df[['first name', 'last name', 'Best Match', 'Match Score', 'Matched From']])
            
            csv = matches_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Matches", csv, "blacklisted_matches.csv", "text/csv")
        else:
            st.info("✅ No blacklisted matches found.")

        csv = user_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Results", csv, "matched_names.csv", "text/csv")
    else:
        st.error("❌ CSV must contain 'first name' and 'last name' columns.")

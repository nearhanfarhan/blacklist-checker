import gspread
import pandas as pd
from gspread_dataframe import get_as_dataframe
from rapidfuzz import fuzz, process

# --- Config ---
FUZZY_MATCH_THRESHOLD = 80  # Adjust as needed

# Authenticate
gc = gspread.service_account(filename='/Users/farhan.chaudhry/Documents/Scripts/Blacklist Checker/credentials.json')

comparison_list = '/Users/farhan.chaudhry/Documents/Scripts/Blacklist Checker/Job&Talent Cyclists - potential candidates - July.csv'

terminated_employee_sheet = 'https://docs.google.com/spreadsheets/d/1lvqwzCiT216ah5mE4KWlsSzA4SDdoriFyXMTBJh2fMo/edit?gid=0#gid=0'
oow_offboarding_sheet = 'https://docs.google.com/spreadsheets/d/1VRME96O2tI8yjij8st6iRQt8K8FzfwUmtC7UdALvkus/edit?gid=0#gid=0'
iwh_offboarding_south_sheet = 'https://docs.google.com/spreadsheets/d/1qbLcKRzLDuautE4ap-nI6fOH6OMAxUkj0oN1ALsG95I/edit?gid=0#gid=0'
iwh_offboarding_north_sheet = 'https://docs.google.com/spreadsheets/d/11F0oF3F6jymI0MtG1qTVzS0VG_lnbnUGx1swuUj5qmM/edit?gid=0#gid=0'
no_show_tracker_sheet = 'https://docs.google.com/spreadsheets/d/1ejFfVVkfQOvIroZiV50OHVcjLv_8hzKinT5gTZL2wcw/edit?gid=0#gid=0'
failed_assessment_sheet = 'https://docs.google.com/spreadsheets/d/1ejFfVVkfQOvIroZiV50OHVcjLv_8hzKinT5gTZL2wcw/edit?gid=552972327#gid=552972327'

# List of Google Sheets to pull from
sheet_urls = [
    oow_offboarding_sheet, iwh_offboarding_south_sheet, iwh_offboarding_north_sheet, no_show_tracker_sheet, failed_assessment_sheet, terminated_employee_sheet
]

# --- Pull Blacklist and Normalize Names ---
blacklisted_records = []

for url in sheet_urls:
    sh = gc.open_by_url(url)
    sheet_title = sh.title
    worksheet = sh.sheet1
    df = get_as_dataframe(worksheet, evaluate_formulas=True)

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    if 'first name' in df.columns and 'last name' in df.columns:
        df = df[['first name', 'last name']].dropna()
        df['full name'] = (df['first name'].str.strip() + ' ' + df['last name'].str.strip()).str.lower()
        
        for name in df['full name'].tolist():
            blacklisted_records.append({
                'name': name,
                'source': sheet_title  # ✅ Use spreadsheet title
            })

# --- Load and Normalize Your List ---
your_list = pd.read_csv(comparison_list)
your_list.columns = your_list.columns.str.strip().str.lower()
your_list['full name'] = (your_list['first name'].str.strip() + ' ' + your_list['last name'].str.strip()).str.lower()

# --- Fuzzy Match Function with Source Info ---
def get_best_match(name, blacklist, threshold=FUZZY_MATCH_THRESHOLD):
    names = [entry['name'] for entry in blacklist]
    result = process.extractOne(name, names, scorer=fuzz.token_sort_ratio)

    if result is None:
        return {
            "Best Match": None,
            "Score": 0,
            "Source": "",
            "Blacklisted": False
        }

    match, score = result[0], result[1]
    idx = names.index(match)
    matched_entry = blacklist[idx]

    return {
        "Best Match": match,
        "Score": score,
        "Source": matched_entry['source'],
        "Blacklisted": score >= threshold
    }


# --- Apply Matching ---
match_results = your_list['full name'].apply(lambda name: get_best_match(name, blacklisted_records))

your_list['Best Match'] = match_results.apply(lambda x: x["Best Match"])
your_list['Match Score'] = match_results.apply(lambda x: x["Score"])
your_list['Blacklisted'] = match_results.apply(lambda x: x["Blacklisted"])
your_list['Matched From'] = match_results.apply(lambda x: x["Source"] if x["Blacklisted"] else "")

# --- Save Results ---
your_list.to_csv('matched_names_fuzzy_with_sources.csv', index=False)
print("✅ Fuzzy comparison complete. Results saved to 'matched_names_fuzzy_with_sources.csv'")

# --- Optional: Print Matches ---
for index, row in your_list.iterrows():
    if row['Blacklisted']:
        print(f"Name: {row['full name']}, Best Match: {row['Best Match']}, Score: {row['Match Score']}, Source: {row['Matched From']}")
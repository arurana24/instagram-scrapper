import os
import re
import time
import base64
import pandas as pd
import streamlit as st
import requests
import io
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# META GRAPH API CREDENTIAL MATRIX
# ==========================================
# Securely fetched from Streamlit Secrets Manager
ACCESS_TOKEN = st.secrets["EAAigrtOZCSv0BRpZCL6yQJ7Te3F44WuZA4LduZCpC1tGKvpg9VagsN7ScjvJuE7pqNIxBFYk0XaPC4hmklEBWg7JkS1end4BOvn1Ryi4eTJZCkPZA15RrHizv8EHZAQQjikEBhEAszIYnUQZAQb4gieT6GCHWZAicyElWymSWmBoFZB8eLgoCve6iGveOcQieJ9P2ZC"]
INSTAGRAM_ACCOUNT_ID = st.secrets["122098856799362354"]
BASE_URL = "https://graph.facebook.com/v22.0"

# ==========================================
# CUSTOM THEME & DESIGN CONFIGURATION
# ==========================================
st.set_page_config(page_title="Public Reel Analytics", page_icon="🎥", layout="wide")

def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

logo_base64 = get_base64_image("logo.jpeg") or get_base64_image("logo.jpg")

st.markdown(
    """
    <style>
    .stApp { background-color: #81d8d0; }
    h1, h2, h3, p, label, .stMarkdown, .stText, [data-testid="stHeader"] {
        color: #1e293b !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    div.stButton > button, div.stDownloadButton > button {
        background-color: #008080 !important;
        color: #ffffff !important;
        border-radius: 6px;
        border: 1px solid #005a5a !important;
        padding: 0.6rem 2.5rem;
        font-weight: bold;
        font-size: 16px;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        background-color: #005a5a !important;
        color: #ffffff !important;
    }
    .stProgress > div > div > div > div { background-color: #008080 !important; }
    .stCheckbox label p { color: #1e293b !important; }
    .stFileUploader section {
        background-color: rgba(255, 255, 255, 0.5) !important;
        border: 2px dashed #008080 !important;
    }
    .stFileUploader button {
        background-color: #008080 !important;
        color: #ffffff !important;
        border: 1px solid #005a5a !important;
    }
    .stFileUploader [data-testid="stFileUploadDropzoneInstructions"] div, 
    .stFileUploader [data-testid="stWidgetLabel"] p,
    .stFileUploader span, .stFileUploader small { color: #000000 !important; }
    .bottom-logo-container {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin-top: 50px;
        padding-top: 20px;
        margin-bottom: 20px;
    }
    .bottom-logo-container img { width: 140px; border-radius: 6px; }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================================
# DATA PROCESSING UTILITIES & ENDPOINTS
# ==========================================
def extract_shortcode(url):
    if pd.isna(url) or not isinstance(url, str):
        return None
    pattern = r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv)/([^/?#&]+)'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def extract_username_from_url(url):
    if pd.isna(url) or not isinstance(url, str):
        return None
    url_clean = url.strip().rstrip('/')
    match = re.search(r'(?:instagram\.com/|@)([a-zA-Z0-9_\.]+)', url_clean)
    return match.group(1) if match else None

def fetch_media_metrics_via_api(shortcode):
    """Queries an individual shortcode directly via the instagram_media endpoint"""
    if not shortcode:
        return {"Reel ID": "N/A", "Username": "N/A", "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "N/A", "Status": "Invalid Link"}
    
    url = f"{BASE_URL}/instagram_media"
    params = {
        "shortcode": shortcode,
        "fields": "id,username,like_count,comments_count,video_view_count,media_type",
        "access_token": ACCESS_TOKEN
    }
    try:
        res = requests.get(url, params=params).json()
        if "error" in res:
            return {"Reel ID": shortcode, "Username": "N/A", "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "N/A", "Status": f"API Error: {res['error'].get('message')}"}
        
        return {
            "Reel ID": res.get("id", shortcode),
            "Username": res.get("username", "N/A"),
            "Likes": res.get("like_count", 0),
            "Comments": res.get("comments_count", 0),
            "Views": res.get("video_view_count", 0),
            "Product Type": res.get("media_type", "Unknown"),
            "Status": "Success"
        }
    except Exception as e:
        return {"Reel ID": shortcode, "Username": "N/A", "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "N/A", "Status": "Network Fail"}

def fetch_profile_discovery_via_api(username):
    """Uses Business Discovery nested query maps to pull public stats and recent post arrays together"""
    if not username:
        return {"Username": "N/A", "Full Name": "No Public Name", "Followers": "N/A", "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "N/A", "Status": "Invalid Username"}
    
    url = f"{BASE_URL}/{INSTAGRAM_ACCOUNT_ID}"
    query = f"business_discovery.username({username}){{name,followers_count,media.limit(1){{like_count,comments_count,video_view_count,media_type}}}}"
    params = {"fields": query, "access_token": ACCESS_TOKEN}
    
    try:
        res = requests.get(url, params=params).json()
        if "error" in res:
            return {"Username": username, "Full Name": "N/A", "Followers": "N/A", "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "N/A", "Status": f"API Error: {res['error'].get('message')}"}
        
        discovery = res["business_discovery"]
        media_data = discovery.get("media", {}).get("data", [])
        latest_post = media_data[0] if media_data else {}
        
        return {
            "Username": username,
            "Full Name": discovery.get("name", "No Public Name"),
            "Followers": discovery.get("followers_count", 0),
            "Likes": latest_post.get("like_count", 0),
            "Comments": latest_post.get("comments_count", 0),
            "Views": latest_post.get("video_view_count", 0),
            "Product Type": latest_post.get("media_type", "N/A"),
            "Status": "Success"
        }
    except Exception as e:
        return {"Username": username, "Full Name": "N/A", "Followers": "N/A", "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "N/A", "Status": "Network Fail"}

# ==========================================
# STREAMLIT USER INTERFACE
# ==========================================
st.title("🎥 Advanced Influencer Marketing Metric Extraper (Official API)")
st.markdown("Upload campaign tracker sheets, configure checkboxes for customized performance frameworks, and output clean analytical tables.")

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration Matrix")
pipeline_mode = st.sidebar.radio("Data Extraction Mode Strategy:", ["Campaign Link Mode (Reels/Posts)", "Creator Profile Discovery Mode"])
url_column = st.sidebar.text_input("Link Column Header Name:", value="Video Links")

# UI Layout Columns
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### 📥 1. Data Ingestion")
    uploaded_file = st.file_uploader("Choose your input Excel file (.xlsx)", type=["xlsx"])
    
with col_right:
    st.markdown("### 🛠️ 2. Select Features to Include")
    tab1, tab2 = st.tabs(["🚀 Auto-Calculated Metrics", "📊 Campaign Analytics Framework"])
    
    with tab1:
        inc_basic = st.checkbox("Reel ID & Username Handle", value=True)
        inc_profiles = st.checkbox("Auto-Scrape Full Name & Followers Count", value=True)
        inc_likes_comments = st.checkbox("Likes & Comments Count", value=True)
        inc_views_type = st.checkbox("Views Count & Product Type", value=True)
        inc_er = st.checkbox("Auto-Calculate ER% ((Likes + Comments) / Views)", value=True)
        inc_ratio = st.checkbox("Auto-Calculate Like/Views Ratio", value=True)
        inc_roi = st.checkbox("Auto-Calculate CPV & CPE (Requires a 'Cost' column)", value=False)
        
    with tab2:
        st.caption("Check these to insert empty structural columns ready for backend campaign logging.")
        inc_reach_metrics = st.checkbox("Reach, Impressions, & Shares Tracker", value=False)
        inc_historical = st.checkbox("CPE, VTR (Last 5 Posts) & Posting Frequency", value=False)

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    st.info(f"📋 Dataset Loaded: Found {len(df)} tracking target entries ready for synchronization.")
    
    if st.button("🚀 Run Performance Matrix Pipeline", type="primary"):
        if url_column not in df.columns:
            st.error(f"❌ Could not find column '{url_column}'. Please check your column heading name.")
        elif inc_roi and "Cost" not in df.columns:
            st.error("❌ ROI metrics selected, but no column named exactly 'Cost' was found in your starting file.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_rows = len(df)
            results_map = {}
            
            status_text.text("⚡ Spinning up secure parallel background Graph API calls (Max Speed)...")
            
            # Execute without artificial delays (time.sleep completely removed)
            with ThreadPoolExecutor(max_workers=10) as executor:
                if pipeline_mode == "Campaign Link Mode (Reels/Posts)":
                    df['Shortcode_Temp'] = df[url_column].apply(extract_shortcode)
                    future_to_row = {
                        executor.submit(fetch_media_metrics_via_api, row['Shortcode_Temp']): idx 
                        for idx, row in df.iterrows()
                    }
                else:
                    df['User_Temp'] = df[url_column].apply(extract_username_from_url)
                    future_to_row = {
                        executor.submit(fetch_profile_discovery_via_api, row['User_Temp']): idx 
                        for idx, row in df.iterrows()
                    }
                
                completed = 0
                for future in as_completed(future_to_row):
                    row_idx = future_to_row[future]
                    try:
                        results_map[row_idx] = future.result()
                    except Exception:
                        results_map[row_idx] = {"Status": "Thread Fail"}
                    
                    completed += 1
                    progress_bar.progress(completed / total_rows)
                    status_text.text(f"🔄 Syncing fields with Meta: {completed}/{total_rows}...")

            # Parse array metrics arrays
            reel_ids, usernames, full_names, followers_list, likes, comments, views, products, status_list = [], [], [], [], [], [], [], [], []
            er_list, ratio_list, cpv_list, cpe_list = [], [], [], []
            
            for i in range(total_rows):
                res = results_map.get(i, {"Status": "Missing Data"})
                status_list.append(res.get("Status", "Unknown"))
                
                # Assign metrics based on mode defaults
                usernames.append(res.get("Username", "N/A"))
                full_names.append(res.get("Full Name", "No Public Name" if pipeline_mode != "Campaign Link Mode (Reels/Posts)" else "N/A"))
                followers_list.append(res.get("Followers", "N/A"))
                reel_ids.append(res.get("Reel ID", "N/A"))
                
                l_val = res.get("Likes", 0)
                c_val = res.get("Comments", 0)
                v_val = res.get("Views", 0)
                
                likes.append(l_val)
                comments.append(c_val)
                views.append(v_val)
                products.append(res.get("Product Type", "N/A"))

                # Dynamic Analytical Ratios
                try:
                    v = float(v_val)
                    l = float(l_val)
                    c = float(c_val)
                    
                    er = ((l + c) / v) * 100 if v > 0 else 0
                    er_list.append(f"{round(er, 2)}%")
                    ratio_list.append(round(l / v, 4) if v > 0 else 0.0)
                except:
                    er_list.append("0.0%")
                    ratio_list.append(0.0)

                # Cost Frameworks
                if inc_roi:
                    try:
                        cost = float(df.iloc[i]["Cost"])
                        v = float(v_val)
                        l = float(l_val)
                        c = float(c_val)
                        cpv_list.append(round(cost / v, 4) if v > 0 else 0.0)
                        cpe_list.append(round(cost / (l + c), 4) if (l + c) > 0 else 0.0)
                    except:
                        cpv_list.append("N/A")
                        cpe_list.append("N/A")

            # 🛠️ Structural Data Transformations
            if inc_basic:
                if pipeline_mode == "Campaign Link Mode (Reels/Posts)":
                    df['Reel ID'] = reel_ids
                df['Owner Username'] = usernames
            if inc_profiles:
                df['Owner Full Name'] = full_names
                df['Followers Count'] = followers_list
            if inc_likes_comments:
                df['Likes Count'] = likes
                df['Comments Count'] = comments
            if inc_views_type:
                df['Video Views and Play Count'] = views
                df['Product Type'] = products
            if inc_reach_metrics:
                df['Shares Count'] = ""
                df['Reach'] = ""
                df['Impressions/Views'] = ""
            if inc_er:
                df['ER%'] = er_list
            if inc_ratio:
                df['Like/Views Ratio'] = ratio_list
            if inc_roi:
                df['CPV'] = cpv_list
                df['CPE'] = cpe_list
            if inc_historical:
                df['CPE (last 5 posts)'] = ""
                df['VTR (last 5 posts)'] = ""
                df['Posting Frequency'] = ""
                
            df['Extraction_Status'] = status_list
            df.drop(columns=['Shortcode_Temp', 'User_Temp'], inplace=True, errors='ignore')
            
            status_text.success("🎉 Custom Marketing Performance Sheet Built Successfully via Graph API!")
            st.markdown("### 👀 Preview Output Structure")
            st.dataframe(df.head(5))
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Marketing Sheet Asset",
                data=buffer.getvalue(),
                file_name="instagram_marketing_dashboard.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if logo_base64:
    st.markdown(f'<div class="bottom-logo-container"><img src="data:image/jpeg;base64,{logo_base64}"></div>', unsafe_allow_html=True)

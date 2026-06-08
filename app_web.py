import streamlit as st
import pandas as pd
import instaloader
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import io

# Initialize Instaloader
L = instaloader.Instaloader()

def extract_shortcode(url):
    if pd.isna(url) or not isinstance(url, str):
        return None
    pattern = r'(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|tv)/([^/?#&]+)'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def fetch_all_public_metrics(shortcode, original_url):
    if not shortcode:
        return {
            "Reel ID": "N/A", "Username": "N/A", "Likes": 0, "Comments": 0, 
            "Views": 0, "Product Type": "N/A", "Status": "Invalid Link"
        }
    try:
        time.sleep(random.uniform(0.4, 0.8))
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        likes_value = post.likes
        if likes_value == -1:
            likes_value = "Likes Hidden"
            
        return {
            "Reel ID": shortcode,
            "Username": post.owner_username,
            "Likes": likes_value,
            "Comments": post.comments,
            "Views": post.video_view_count if post.is_video else 0,
            "Product Type": post.typename if post.typename else "Unknown",
            "Status": "Success"
        }
    except Exception:
        return {
            "Reel ID": shortcode, "Username": "N/A", "Likes": 0, "Comments": 0, 
            "Views": 0, "Product Type": "N/A", "Status": "Error/Private"
        }

# ==========================================
# STREAMLIT USER INTERFACE
# ==========================================
st.set_page_config(page_title="Public Reel Analytics", page_icon="🎥", layout="wide")

st.title("🎥 Advanced Influencer Marketing Metric Extraper")
st.markdown("Upload campaign tracker sheets, configure checkboxes for customized performance frameworks, and output clean analytical tables.")

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration Matrix")
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
        inc_likes_comments = st.checkbox("Likes & Comments Count", value=True)
        inc_views_type = st.checkbox("Views Count & Product Type", value=True)
        inc_er = st.checkbox("Auto-Calculate ER% ((Likes + Comments) / Views)", value=True)
        inc_ratio = st.checkbox("Auto-Calculate Like/Views Ratio", value=True)
        inc_roi = st.checkbox("Auto-Calculate CPV & CPE (Requires a 'Cost' column)", value=False)
        
    with tab2:
        st.caption("Check these to insert empty structural columns ready for backend campaign logging.")
        inc_profiles = st.checkbox("Owner Full Name & Followers Tracker", value=False)
        inc_reach_metrics = st.checkbox("Reach, Impressions, & Shares Tracker", value=False)
        inc_historical = st.checkbox("CPE, VTR (Last 5 Posts) & Posting Frequency", value=False)

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    st.info(f"📋 Dataset Loaded: Found {len(df)} tracking links ready for customization.")
    
    if st.button("🚀 Run Performance Matrix Pipeline", type="primary"):
        if url_column not in df.columns:
            st.error(f"❌ Could not find column '{url_column}'. Please check your column heading name.")
        elif inc_roi and "Cost" not in df.columns:
            st.error("❌ ROI metrics selected, but no column named exactly 'Cost' was found in your starting file.")
        else:
            progress_bar =

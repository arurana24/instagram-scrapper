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
            "Reel ID": "N/A", "Reel URL": original_url, "Username": "N/A", 
            "Likes": 0, "Comments": 0, "Views": 0, "Hashtags": "N/A", 
            "Mentions": "N/A", "Tagged Users": "N/A", "Product Type": "N/A", 
            "Status": "Invalid Link"
        }
    try:
        # Organic delay to safeguard network execution
        time.sleep(random.uniform(0.4, 0.8))
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Handle hidden likes flag (-1) safely
        likes_value = post.likes
        if likes_value == -1:
            likes_value = "Likes Hidden"
            
        # Parse caption for mentions/hashtags if available
        caption = post.caption if post.caption else ""
        hashtags = ", ".join(re.findall(r'#(\w+)', caption)) if caption else "None"
        mentions = ", ".join(re.findall(r'@(\w+)', caption)) if caption else "None"
        
        # Get tagged users in the video/photo
        tagged = ", ".join([user for user in post.tagged_users]) if post.tagged_users else "None"
        
        return {
            "Reel ID": shortcode,
            "Reel URL": original_url,
            "Username": post.owner_username,
            "Likes": likes_value,
            "Comments": post.comments,
            "Views": post.video_view_count if post.is_video else "Not a Video",
            "Hashtags": hashtags if hashtags else "None",
            "Mentions": mentions if mentions else "None",
            "Tagged Users": tagged if tagged else "None",
            "Product Type": post.typename if post.typename else "Unknown",
            "Status": "Success"
        }
    except Exception as e:
        return {
            "Reel ID": shortcode, "Reel URL": original_url, "Username": "N/A", 
            "Likes": "N/A", "Comments": "N/A", "Views": "N/A", "Hashtags": "N/A", 
            "Mentions": "N/A", "Tagged Users": "N/A", "Product Type": "N/A", 
            "Status": "Error/Private"
        }

# ==========================================
# STREAMLIT USER INTERFACE
# ==========================================
st.set_page_config(page_title="Public Reel Analytics", page_icon="🎥", layout="wide")

st.title("🎥 Custom Public Instagram Performance Tracker")
st.markdown("Upload your tracking sheets, select your data configuration layout using the checkboxes below, and pull metrics natively.")

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration Matrix")
url_column = st.sidebar.text_input("Link Column Header Name:", value="Video Links")

# UI Layout Columns for Inputs & Checkboxes
col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### 📥 1. Data Ingestion")
    uploaded_file = st.file_uploader("Choose your input Excel file (.xlsx)", type=["xlsx"])
    
with col_right:
    st.markdown("### 🛠️ 2. Select Features to Include")
    
    tab1, tab2 = st.tabs(["🚀 Auto-Scraped Public Metrics", "📊 Private Placeholder Columns"])
    
    with tab1:
        inc_id_url = st.checkbox("Reel ID & Reel URL Mapping", value=True)
        inc_username = st.checkbox("Owner Username Handle", value=True)
        inc_likes = st.checkbox("Likes Count", value=True)
        inc_comments = st.checkbox("Comments Count", value=True)
        inc_views = st.checkbox("Video Views and Play Count", value=True)
        inc_metadata = st.checkbox("Hashtags, Mentions & Tagged Users lists", value=True)
        inc_type = st.checkbox("Product Type (Video/Carousel/Image)", value=True)
        
    with tab2:
        st.caption("Check these to insert formatted empty tracking slots for metrics that require backend panel inputs.")
        inc_fullname = st.checkbox("Owner Full Name Column", value=False)
        inc_shares = st.checkbox("Shares Count Column", value=False)

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    st.info(f"📋 Dataset Loaded: Found {len(df)} tracking links ready for customization.")
    
    if st.button("🚀 Run Performance Matrix Pipeline", type="primary"):
        if url_column not in df.columns:
            st.error(f"❌ Could not find column '{url_column}'. Please check your column heading name.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Map temporary keys
            df['Shortcode_Temp'] = df[url_column].apply(extract_shortcode)
            results_map = {}
            total_rows = len(df)
            
            status_text.text("⚡ Spinning up parallel background workers...")
            
            # Concurrent processing framework
            with ThreadPoolExecutor(max_workers=5) as executor:
                future_to_row = {
                    executor.submit(fetch_all_public_metrics, row['Shortcode_Temp'], row[url_column]): idx 
                    for idx, row in df.iterrows()
                }
                
                completed = 0
                for future in as_completed(future_to_row):
                    row_idx = future_to_row[future]
                    try:
                        results_map[row_idx] = future.result()
                    except Exception:
                        results_map[row_idx] = {
                            "Reel ID": "Error", "Reel URL": df.iloc[row_idx][url_column], "Username": "N/A", 
                            "Likes": "N/A", "Comments": "N/A", "Views": "N/A", "Hashtags": "N/A", 
                            "Mentions": "N/A", "Tagged Users": "N/A", "Product Type": "N/A", "Status": "Thread Fail"
                        }
                    
                    completed += 1
                    progress_bar.progress(completed / total_rows)
                    status_text.text(f"🔄 Processing rows: {completed}/{total_rows}...")

            # Dynamic list initialization
            reel_ids, reel_urls, usernames, likes, comments, views = [], [], [], [], [], []
            hashtags_list, mentions_list, tagged_list, products, status_list = [], [], [], [], []
            
            for i in range(total_rows):
                res = results_map.get(i)
                reel_ids.append(res["Reel ID"])
                reel_urls.append(res["Reel URL"])
                usernames.append(res["Username"])
                likes.append(res["Likes"])
                comments.append(res["Comments"])
                views.append(res["Views"])
                hashtags_list.append(res["Hashtags"])
                mentions_list.append(res["Mentions"])
                tagged_list.append(res["Tagged Users"])
                products.append(res["Product Type"])
                status_list.append(res["Status"])

            # 🛠️ Append Columns Natively based on Checkbox Selections
            if inc_id_url:
                df['Reel ID'] = reel_ids
                df['Reel URL'] = reel_urls
            if inc_username:
                df['Owner Username'] = usernames
                
            if inc_fullname:
                df['Owner Full Name'] = ""  # Structured Placeholder Column
                
            if inc_likes:
                df['Likes Count'] = likes
                
            if inc_shares:
                df['Shares Count'] = ""     # Structured Placeholder Column
                
            if inc_comments:
                df['Comments Count'] = comments
            if inc_views:
                df['Video Views and Play Count'] = views
            if inc_metadata:
                df['Hashtags'] = hashtags_list
                df['Mentions'] = mentions_list
                df['Tagged Users'] = tagged_list
            if inc_type:
                df['Product Type'] = products
                
            df['Extraction_Status'] = status_list
            
            # Housekeeping
            df.drop(columns=['Shortcode_Temp'], inplace=True, errors='ignore')
            
            status_text.success("🎉 Custom Matrix Built Successfully!")
            
            # Interactive Spreadsheet Preview Component
            st.markdown("### 👀 Preview Processed Output Layout")
            st.dataframe(df.head(5))
            
            # Convert memory stack blocks out to downloadable binary data stream
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Custom Reports Sheet",
                data=buffer.getvalue(),
                file_name="instagram_custom_metrics_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

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
            "Reel ID": "N/A", "Username": "N/A", "Full Name": "N/A", "Followers": "N/A",
            "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "N/A", "Status": "Invalid Link"
        }
    try:
        # Organic staggered pacing to keep your network secure
        time.sleep(random.uniform(0.5, 1.0))
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Get public profile level metrics natively
        profile = post.owner_profile
        full_name = profile.full_name if profile.full_name else "No Public Name"
        followers = profile.followers
        
        likes_value = post.likes
        if likes_value == -1:
            likes_value = "Likes Hidden"
            
        return {
            "Reel ID": shortcode,
            "Username": post.owner_username,
            "Full Name": full_name,
            "Followers": followers,
            "Likes": likes_value,
            "Comments": post.comments,
            "Views": post.video_view_count if post.is_video else 0,
            "Product Type": post.typename if post.typename else "Unknown",
            "Status": "Success"
        }
    except Exception as e:
        return {
            "Reel ID": shortcode, "Username": "N/A", "Full Name": "N/A", "Followers": "N/A",
            "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "N/A", "Status": "Error/Private"
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
    st.info(f"📋 Dataset Loaded: Found {len(df)} tracking links ready for customization.")
    
    if st.button("🚀 Run Performance Matrix Pipeline", type="primary"):
        if url_column not in df.columns:
            st.error(f"❌ Could not find column '{url_column}'. Please check your column heading name.")
        elif inc_roi and "Cost" not in df.columns:
            st.error("❌ ROI metrics selected, but no column named exactly 'Cost' was found in your starting file.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            df['Shortcode_Temp'] = df[url_column].apply(extract_shortcode)
            results_map = {}
            total_rows = len(df)
            
            status_text.text("⚡ Spinning up parallel background profile workers...")
            
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
                            "Reel ID": "Error", "Username": "N/A", "Full Name": "N/A", "Followers": "N/A",
                            "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "N/A", "Status": "Thread Fail"
                        }
                    
                    completed += 1
                    progress_bar.progress(completed / total_rows)
                    status_text.text(f"🔄 Processing rows: {completed}/{total_rows}...")

            # Parse array lists
            reel_ids, usernames, full_names, followers_list, likes, comments, views, products, status_list = [], [], [], [], [], [], [], [], []
            er_list, ratio_list, cpv_list, cpe_list = [], [], [], []
            
            for i in range(total_rows):
                res = results_map.get(i)
                reel_ids.append(res["Reel ID"])
                usernames.append(res["Username"])
                full_names.append(res["Full Name"])
                followers_list.append(res["Followers"])
                likes.append(res["Likes"])
                comments.append(res["Comments"])
                views.append(res["Views"])
                products.append(res["Product Type"])
                status_list.append(res["Status"])

                # Dynamic Math Blocks
                try:
                    v = float(res["Views"])
                    l = float(res["Likes"]) if isinstance(res["Likes"], (int, float)) else 0
                    c = float(res["Comments"])
                    
                    # 1. ER%
                    er = ((l + c) / v) * 100 if v > 0 else 0
                    er_list.append(f"{round(er, 2)}%")
                    
                    # 2. Like/Views Ratio
                    ratio = (l / v) if v > 0 else 0
                    ratio_list.append(round(ratio, 4))
                except:
                    er_list.append("0.0%")
                    ratio_list.append(0.0)

                # 3. Cost Metrics (CPV / CPE)
                if inc_roi:
                    try:
                        cost = float(df.iloc[i]["Cost"])
                        v = float(res["Views"])
                        l = float(res["Likes"]) if isinstance(res["Likes"], (int, float)) else 0
                        c = float(res["Comments"])
                        
                        cpv = cost / v if v > 0 else 0
                        cpe = cost / (l + c) if (l + c) > 0 else 0
                        
                        cpv_list.append(round(cpv, 4))
                        cpe_list.append(round(cpe, 4))
                    except:
                        cpv_list.append("N/A")
                        cpe_list.append("N/A")

            # 🛠️ Append Generated Data Columns
            if inc_basic:
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
            df.drop(columns=['Shortcode_Temp'], inplace=True, errors='ignore')
            
            status_text.success("🎉 Custom Marketing Performance Sheet Built Successfully!")
            
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

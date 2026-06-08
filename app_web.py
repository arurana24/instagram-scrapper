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

def fetch_single_metrics(shortcode):
    if not shortcode:
        return {"Views": "N/A", "Likes": "N/A", "Comments": "N/A", "Status": "Invalid Link"}
    try:
        time.sleep(random.uniform(0.5, 1.5))
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        likes_value = post.likes
        if likes_value == -1:
            likes_value = "Likes Hidden"
            
        return {
            "Views": post.video_view_count if post.is_video else "Not a Video",
            "Likes": likes_value,
            "Comments": post.comments,
            "Status": "Success"
        }
    except Exception:
        return {"Views": "N/A", "Likes": "N/A", "Comments": "N/A", "Status": "Error/Private"}

# ==========================================
# STREAMLIT WEB INTERFACE
# ==========================================
st.set_page_config(page_title="Instagram Data Funnel", page_icon="🚀", layout="centered")

st.title("🚀 Instagram Metrics Extractor")
st.markdown("Upload your Excel sheet containing Instagram links, and pull metrics instantly without any code.")

# 1. File Upload Component
uploaded_file = st.file_uploader("Choose your input Excel file (.xlsx)", type=["xlsx"])
url_column = st.text_input("Enter the exact column name containing your links:", value="Video Links")

if uploaded_file is not None:
    # Read the file directly from memory
    df = pd.read_excel(uploaded_file)
    st.success(f"📋 File loaded successfully! Found {len(df)} rows.")
    
    if st.button("✨ Run Scraper Engine", type="primary"):
        if url_column not in df.columns:
            st.error(f"❌ Could not find column '{url_column}'. Available columns: {list(df.columns)}")
        else:
            # Setup layout components
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            df['Shortcode'] = df[url_column].apply(extract_shortcode)
            results_map = {}
            total_rows = len(df)
            
            status_text.text("⚡ Spinning up parallel worker threads...")
            
            # Run the parallel engine
            with ThreadPoolExecutor(max_workers=5) as executor: # Kept to 5 for cloud stability
                future_to_row = {
                    executor.submit(fetch_single_metrics, row['Shortcode']): idx 
                    for idx, row in df.iterrows()
                }
                
                completed = 0
                for future in as_completed(future_to_row):
                    row_idx = future_to_row[future]
                    try:
                        results_map[row_idx] = future.result()
                    except Exception:
                        results_map[row_idx] = {"Views": "N/A", "Likes": "N/A", "Comments": "N/A", "Status": "Error"}
                    
                    completed += 1
                    # Update progress UI dynamically
                    progress_bar.progress(completed / total_rows)
                    status_text.text(f"🔄 Finished processing row {completed}/{total_rows}...")

            # Compile layout data back together
            views_list, likes_list, comments_list, status_list = [], [], [], []
            for i in range(total_rows):
                res = results_map.get(i, {"Views": "N/A", "Likes": "N/A", "Comments": "N/A", "Status": "Missing"})
                views_list.append(res["Views"])
                likes_list.append(res["Likes"])
                comments_list.append(res["Comments"])
                status_list.append(res["Status"])

            df['Live_Views_Plays'] = views_list
            df['Live_Likes'] = likes_list
            df['Live_Comments'] = comments_list
            df['Scrape_Status'] = status_list
            df.drop(columns=['Shortcode'], inplace=True)
            
            status_text.success("🎉 Processing complete! Your file is ready.")
            
            # Save final file into a virtual memory buffer for downloading
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            # 2. File Download Component
            st.download_button(
                label="📥 Download Updated Excel File",
                data=buffer.getvalue(),
                file_name="instagram_metrics_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

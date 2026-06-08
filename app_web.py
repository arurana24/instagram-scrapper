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
        # Organic delay to safeguard your network execution
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

st.title("🎥 Public Instagram Reel & Post Extractor")
st.markdown("Upload your tracking sheets to compile comprehensive public metadata and performance metrics natively.")

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration Matrix")
url_column = st.sidebar.text_input("Link Column Header Name:", value="Video Links")

# Data Ingestion Layout
uploaded_file = st.file_uploader("Choose your input Excel file (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)
    st.info(f"📋 Dataset Loaded: Found {len(df)} tracking links ready for extraction.")
    
    if st.button("🚀 Run Public Metrics Engine", type="primary"):
        if url_column not in df.columns:
            st.error(f"❌ Could not find column '{url_column}'. Please check your column heading name.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Extract shortcodes to maps
            df['Shortcode_Temp'] = df[url_column].apply(extract_shortcode)
            results_map = {}
            total_rows = len(df)
            
            status_text.text("⚡ Activating multi-threaded extraction pipelines...")
            
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
                    status_text.text(f"🔄 Processing row items: {completed}/{total_rows}...")

            # Reconstruct variables array chronological alignments
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

            # Map generated metrics directly onto output frame
            df['Reel ID'] = reel_ids
            df['Reel URL'] = reel_urls
            df['Owner Username'] = usernames
            df['Owner Full Name'] = ""  # Clean placeholder framework column
            df['Likes Count'] = likes
            df['Shares Count'] = ""  # Clean placeholder framework column
            df['Comments Count'] = comments
            df['Video Views and Play Count'] = views
            df['Hashtags'] = hashtags_list
            df['Mentions'] = mentions_list
            df['Tagged Users'] = tagged_list
            df['Product Type'] = products
            df['Extraction_Status'] = status_list
            
            # Clean temporary processing keys
            df.drop(columns=['Shortcode_Temp'], inplace=True, errors='ignore')
            
            status_text.success("🎉 Matrix Sheet Compiled Cleanly!")
            
            # Display interactive dataframe presentation segment
            st.markdown("### 👀 Preview Processed Output Matrix")
            st.dataframe(df.head(5))
            
            # Map storage vectors out to virtual file stream buffer
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Public Metrics Spreadsheet",
                data=buffer.getvalue(),
                file_name="instagram_public_metrics_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

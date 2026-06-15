import os
import re
import time
import random
import logging
import io
import base64
import pandas as pd
import streamlit as st
import requests
import instaloader
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# SYSTEM SETUP & LOGGING
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

ACCESS_TOKEN = st.secrets["META_ACCESS_TOKEN"]
INSTAGRAM_ACCOUNT_ID = st.secrets["INSTAGRAM_ACCOUNT_ID"]
BASE_URL = "https://graph.facebook.com/v22.0"

L = instaloader.Instaloader()

def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    return None

logo_base64 = get_base64_image("logo.jpeg") or get_base64_image("logo.jpg")

# Advanced CSS Styling Configuration
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
    .stFileUploader section {
        background-color: rgba(255, 255, 255, 0.5) !important;
        border: 2px dashed #008080 !important;
    }
    .stFileUploader button { background-color: #008080 !important; color: #ffffff !important; }
    .stFileUploader [data-testid="stFileUploadDropzoneInstructions"] div, 
    .stFileUploader [data-testid="stWidgetLabel"] p, .stFileUploader span, .stFileUploader small {
        color: #000000 !important;
    }
    .bottom-logo-container {
        display: flex; justify-content: center; align-items: center; width: 100%;
        margin-top: 50px; padding-top: 20px; margin-bottom: 20px;
    }
    .bottom-logo-container img { width: 140px; border-radius: 6px; }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================================
# PARSING & META API DATA ENGINE WORKERS
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
    return match.group(1) if match else url_clean

def fetch_creator_metadata_via_api(username):
    if not username:
        return {"followers": 0, "full_name": "No Public Name", "status": "Invalid Handle"}
    url = f"{BASE_URL}/{INSTAGRAM_ACCOUNT_ID}"
    query = f"business_discovery.username({username}){{name,followers_count}}"
    params = {"fields": query, "access_token": ACCESS_TOKEN}
    try:
        res = requests.get(url, params=params).json()
        if "error" in res:
            return {"followers": 0, "full_name": "No Public Name", "status": "API Error"}
        discovery = res.get("business_discovery", {})
        return {"followers": discovery.get("followers_count", 0), "full_name": discovery.get("name", "No Public Name"), "status": "Success"}
    except Exception:
        return {"followers": 0, "full_name": "No Public Name", "status": "Connection Fail"}

def fetch_creator_timeline_via_api(username, profile_url):
    if not username:
        return {"followers": 0, "status": "Invalid Username", "reels_to_job": [], "skipped_pinned": []}
    url = f"{BASE_URL}/{INSTAGRAM_ACCOUNT_ID}"
    query = f"business_discovery.username({username}){{name,followers_count,media.limit(30){{id,like_count,comments_count,media_type,timestamp,permalink}}}}"
    params = {"fields": query, "access_token": ACCESS_TOKEN}
    try:
        res = requests.get(url, params=params).json()
        if "error" in res:
            return {"followers": 0, "status": "API Mismatch Error", "reels_to_job": [], "skipped_pinned": []}
        discovery = res.get("business_discovery", {})
        followers = discovery.get("followers_count", 0)
        media_data = discovery.get("media", {}).get("data", [])
        
        reels_to_job, skipped_pinned = [], []
        latest_valid_timestamp = None
        
        for item in media_data:
            if item.get("media_type") != "VIDEO":
                continue
            if len(reels_to_job) >= 10:
                break
            post_id = item.get("id")
            permalink = item.get("permalink", f"https://www.instagram.com/p/{post_id}/")
            likes = item.get("like_count", 0)
            comments = item.get("comments_count", 0)
            time_str = item.get("timestamp", "N/A")
            
            try:
                clean_time_str = re.sub(r'([+-]\d{4})$', '', time_str)
                post_time = datetime.strptime(clean_time_str, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                post_time = datetime.utcnow()
                
            er = (likes + comments) / followers * 100 if followers > 0 else 0.0
            
            if latest_valid_timestamp and (latest_valid_timestamp - post_time).days > 30:
                skipped_pinned.append({
                    "Profile Link": profile_url, "Username": username, "Reel URL": permalink,
                    "Shortcode": post_id, "Views": 0, "Likes": likes, "Comments": comments,
                    "Engagement Rate (%)": round(er, 2), "Timestamp": time_str, "Skip Reason": "Out-of-Order Pinned Post"
                })
                continue
            if latest_valid_timestamp is None:
                latest_valid_timestamp = post_time
                
            reels_to_job.append({
                "post_id": post_id, "permalink": permalink, "profile_url": profile_url, 
                "username": username, "followers": followers, "likes": likes, 
                "comments": comments, "post_time": post_time, "timestamp_str": time_str, "er": er
            })
        return {"followers": followers, "status": "Success", "reels_to_job": reels_to_job, "skipped_pinned": skipped_pinned}
    except Exception:
        return {"followers": 0, "status": "API Exception Connection", "reels_to_job": [], "skipped_pinned": []}

def fetch_single_reel_views_worker(job):
    permalink = job["permalink"]
    try:
        shortcode_match = re.search(r'/reel/([^/]+)/|/p/([^/]+)/', permalink)
        code = shortcode_match.group(1) or shortcode_match.group(2) if shortcode_match else job.get("post_id") or job.get("shortcode")
        time.sleep(random.uniform(0.1, 0.25))
        
        post = instaloader.Post.from_shortcode(L.context, code)
        views = post.video_view_count if post.is_video else 0
        coauthors = [author.username for author in post.get_coauthors()] if hasattr(post, 'get_coauthors') else []
        status = "Skipped: Collaboration" if len(coauthors) > 1 else "Success"
        
        job.update({"Views": views, "Status": status, "Shortcode": code})
        if "Timestamp" not in job or job["Timestamp"] == "N/A":
            job["Timestamp"] = post.date_utc.strftime("%Y-%m-%d %H:%M:%S") if post.date_utc else "N/A"
        if "Product Type" not in job:
            job["Product Type"] = post.typename if post.typename else "VIDEO"
        return job
    except Exception:
        job.update({"Views": 0, "Status": "Valid (Views Fallback)", "Shortcode": job.get("post_id", "Error")})
        if "Timestamp" not in job: job["Timestamp"] = "N/A"
        if "Product Type" not in job: job["Product Type"] = "VIDEO"
        return job

# ==========================================
# STREAMLIT USER INTERFACE VIEW LAYER
# ==========================================
st.title("Campaign Metric Production Matrix")
engine_selection = st.radio(
    "Select Optimization Track Mode:",
    ["Campaign Tracker", "Creator Auditor"],
    horizontal=True
)
st.markdown("---")

# ==========================================
# MODULE TRACK MODE: CAMPAIGN TRACKER
# ==========================================
if engine_selection == "Campaign Tracker":
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("### 1. Data Ingestion")
        uploaded_file = st.file_uploader("Upload Excel document (.xlsx)", type=["xlsx"], key="t1_file")
        url_column = st.text_input("Link Column Header Name:", value="Video Links", key="t1_colname")
        
    with col_right:
        st.markdown("### 2. Execution Toggles")
        inc_basic = st.checkbox("Reel ID & Username Handle", value=True)
        inc_profiles = st.checkbox("Auto-Scrape Creator Metadata (Meta API)", value=True)
        inc_likes_comments = st.checkbox("Likes & Comments Metrics", value=True)
        inc_views_type = st.checkbox("Views Count & Asset Type", value=True)
        inc_timestamp_t1 = st.checkbox("Include Video Publication Timestamp", value=True)
        inc_er = st.checkbox("Auto-Calculate View Engagement Rate (ER%)", value=True)
        inc_ratio = st.checkbox("Auto-Calculate Like/Views Ratio", value=True)
        inc_roi = st.checkbox("Auto-Calculate CPV & CPE (Requires 'Cost' column)", value=False)

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)
        st.info(f"Loaded {len(df)} lines from source configuration sheet.")
        if st.button("Run Performance Pipeline", type="primary", key="t1_run"):
            if url_column not in df.columns:
                st.error(f"Target column tracking identifier '{url_column}' not found.")
            elif inc_roi and "Cost" not in df.columns:
                st.error("ROI performance toggled, but column header exactly matching 'Cost' is missing.")
            else:
                p_bar = st.progress(0)
                status_txt = st.empty()
                df['Shortcode_Temp'] = df[url_column].apply(extract_shortcode)
                
                global_jobs = []
                profile_cache = {}
                
                status_txt.text("Querying metadata frameworks via primary Meta API...")
                for idx, row in df.iterrows():
                    u_handle = extract_username_from_url(str(row[url_column]))
                    if u_handle and u_handle not in profile_cache and inc_profiles:
                        profile_cache[u_handle] = fetch_creator_metadata_via_api(u_handle)
                    global_jobs.append({
                        "index": idx, "permalink": row[url_column], "shortcode": row['Shortcode_Temp'], "user_handle": u_handle
                    })
                    p_bar.progress((idx + 1) / len(df) * 0.3)
                
                status_txt.text(f"Extracting specific metrics across {len(global_jobs)} indices...")
                scraped_map = {}
                with ThreadPoolExecutor(max_workers=30) as exec1:
                    futures = [exec1.submit(fetch_single_reel_views_worker, job) for job in global_jobs]
                    cc = 0
                    for f in as_completed(futures):
                        res = f.result()
                        scraped_map[res["index"]] = res
                        cc += 1
                        p_bar.progress(0.3 + (cc / len(global_jobs) * 0.7))
                
                r_ids, users, f_names, followers, r_likes, r_comments, r_views, r_types, r_times, r_status = [], [], [], [], [], [], [], [], [], []
                er_list, ratio_list, cpv_list, cpe_list = [], [], [], []
                
               # Ensure this whole block stays neatly indented under the "with ThreadPoolExecutor" block above it
                r_ids, users, f_names, followers, r_likes, r_comments, r_views, r_types, r_times, r_status = [], [], [], [], [], [], [], [], [], []
                er_list, ratio_list, cpv_list, cpe_list = [], [], [], []
                
                for i in range(len(df)):
                    scr = scraped_map.get(i, {"Shortcode": "N/A", "Username": "N/A", "Likes": 0, "Comments": 0, "Views": 0, "Product Type": "VIDEO", "Timestamp": "N/A", "Status": "Fail"})
                    
                    # Safe retrieval via .get() prevents future key crashes
                    hand = scr.get("Username") if scr.get("Username") else scr.get("user_handle", "N/A")
                    c_meta = profile_cache.get(hand, {"followers": "N/A", "full_name": "No Public Name"})
                    
                    r_ids.append(scr.get("Shortcode", "N/A"))
                    users.append(hand)
                    f_names.append(c_meta.get("full_name", "No Public Name"))
                    followers.append(c_meta.get("followers", "N/A"))
                    r_likes.append(scr.get("Likes", 0))
                    r_comments.append(scr.get("Comments", 0))
                    r_views.append(scr.get("Views", 0))
                    r_types.append(scr.get("Product Type", "VIDEO"))
                    r_times.append(scr.get("Timestamp", "N/A"))
                    r_status.append(scr.get("Status", "Fail"))
                    
                    try:
                        v = float(scr["Views"])
                        l = float(scr["Likes"])
                        c = float(scr["Comments"])
                        er_list.append(f"{round(((l + c) / v * 100), 2)}%" if v > 0 else "0.0%")
                        ratio_list.append(round((l / v), 4) if v > 0 else 0.0)
                    except:
                        er_list.append("0.0%"), ratio_list.append(0.0)
                        
                    if inc_roi:
                        try:
                            cost = float(df.iloc[i]["Cost"])
                            v = float(scr["Views"])
                            cpv_list.append(round(cost / v, 4) if v > 0 else 0)
                            cpe_list.append(round(cost / (float(scr["Likes"]) + float(scr["Comments"])), 4) if (float(scr["Likes"]) + float(scr["Comments"])) > 0 else 0)
                        except:
                            cpv_list.append("N/A"), cpe_list.append("N/A")

                if inc_basic: df['Reel ID'] = r_ids; df['Owner Username'] = users
                if inc_profiles: df['Owner Full Name'] = f_names; df['Followers Count'] = followers
                if inc_likes_comments: df['Likes Count'] = r_likes; df['Comments Count'] = r_comments
                if inc_views_type: df['Video Views'] = r_views; df['Product Type'] = r_types
                if inc_timestamp_t1: df['Publication Timestamp'] = r_times
                if inc_er: df['ER%'] = er_list
                if inc_ratio: df['Like/Views Ratio'] = ratio_list
                if inc_roi: df['CPV'] = cpv_list; df['CPE'] = cpe_list
                
                df['Extraction_Status'] = r_status
                df.drop(columns=['Shortcode_Temp'], inplace=True, errors='ignore')
                status_txt.success("Campaign performance metrics matrix constructed cleanly.")
                st.dataframe(df.head(5))
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as w: df.to_excel(w, index=False)
                st.download_button(label="Download Audited Workbook", data=buf.getvalue(), file_name="campaign_tracker_analytics.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ==========================================
# MODULE TRACK MODE: CREATOR AUDITOR
# ==========================================
else:
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("### 1. Data Ingestion")
        uploaded_file = st.file_uploader("Upload Excel document (.xlsx)", type=["xlsx"], key="t2_file")
        url_column = st.text_input("Profile Column Header Name:", value="Profile Link", key="t2_colname")
        
    with col_right:
        st.markdown("### 2. Processing Notes")
        st.info("The configuration will extract the 10 most recent chronological videos per creator via Meta APIs and append corresponding real-time metric distributions.")

    if uploaded_file is not None:
        df_inputs = pd.read_excel(uploaded_file)
        st.info(f"Loaded {len(df_inputs)} profile links from source tracker sheet.")
        
        if st.button("Run Performance Pipeline", type="primary", key="t2_run"):
            p_metadata = {}
            global_jobs_pool = []
            skipped_rows = []
            
            p_bar = st.progress(0)
            status_txt = st.empty()
            
            status_txt.text("Mapping targeted channel hierarchies via Meta APIs...")
            for idx, row in df_inputs.iterrows():
                p_url = row[url_column]
                if pd.isna(p_url): continue
                hand = extract_username_from_url(str(p_url)) or "N/A"
                
                meta_res = fetch_creator_timeline_via_api(hand, p_url)
                if meta_res.get("status") != "Success":
                    p_metadata[p_url] = {"username": hand, "followers": 0, "status": meta_res.get("status", "API Mismatch")}
                else:
                    p_metadata[p_url] = {"username": hand, "followers": meta_res["followers"], "status": "Success"}
                    global_jobs_pool.extend(meta_res["reels_to_job"])
                    if meta_res["skipped_pinned"]: skipped_rows.extend(meta_res["skipped_pinned"])
                p_bar.progress(((idx + 1) / len(df_inputs)) * 0.4)
                
            total_jobs = len(global_jobs_pool)
            completed_jobs = []
            if total_jobs > 0:
                status_txt.text(f"Running high-speed processing array across {total_jobs} unique nodes...")
                with ThreadPoolExecutor(max_workers=30) as final_exec:
                    futures = [final_exec.submit(fetch_single_reel_views_worker, j) for j in global_jobs_pool]
                    jc = 0
                    for f in as_completed(futures):
                        p_job = f.result()
                        if p_job["Status"] == "Skipped: Collaboration":
                            skipped_rows.append({
                                "Profile Link": p_job["profile_url"], "Username": p_job["username"], "Reel URL": p_job["permalink"],
                                "Shortcode": p_job["Shortcode"], "Views": p_job["Views"], "Likes": p_job["likes"], "Comments": p_job["comments"],
                                "Engagement Rate (%)": round(p_job["er"], 2), "Timestamp": p_job["timestamp_str"], "Skip Reason": "Co-authored Collaboration"
                            })
                        else:
                            completed_jobs.append(p_job)
                        jc += 1
                        p_bar.progress(0.4 + ((jc / total_jobs) * 0.6))
            
            status_txt.text("Evaluating dataset outliers and executing statistical filtering...")
            df_processed_reels = pd.DataFrame(completed_jobs)
            granular_rows, summary_rows = [], []
            
            for p_url, m in p_metadata.items():
                hand = m["username"]
                followers = m["followers"]
                status = m["status"]
                org_reels = []
                
                if not df_processed_reels.empty:
                    sub = df_processed_reels[df_processed_reels["profile_url"] == p_url]
                    if not sub.empty:
                        if len(sub) >= 4:
                            q1, q3 = sub["Views"].quantile(0.25), sub["Views"].quantile(0.75)
                            upper_bound = q3 + (1.5 * (q3 - q1))
                            for _, r_row in sub.iterrows():
                                if r_row["Views"] > upper_bound and r_row["Views"] > 0:
                                    skipped_rows.append({
                                        "Profile Link": p_url, "Username": hand, "Reel URL": r_row["permalink"],
                                        "Shortcode": r_row["Shortcode"], "Views": r_row["Views"], "Likes": r_row["likes"], "Comments": r_row["comments"],
                                        "Engagement Rate (%)": round(r_row["er"], 2), "Timestamp": r_row["timestamp_str"], "Skip Reason": "Boosted Ad Outlier (IQR Filter)"
                                    })
                                else:
                                    org_reels.append(r_row)
                                    granular_rows.append({
                                        "Profile Link": p_url, "Username": hand, "Reel URL": r_row["permalink"], "Shortcode": r_row["Shortcode"],
                                        "Views": r_row["Views"], "Likes": r_row["likes"], "Comments": r_row["comments"], "Engagement Rate (%)": round(r_row["er"], 2), "Timestamp": r_row["timestamp_str"]
                                    })
                        else:
                            for _, r_row in sub.iterrows():
                                org_reels.append(r_row)
                                granular_rows.append({
                                    "Profile Link": p_url, "Username": hand, "Reel URL": r_row["permalink"], "Shortcode": r_row["Shortcode"],
                                    "Views": r_row["Views"], "Likes": r_row["likes"], "Comments": r_row["comments"], "Engagement Rate (%)": round(r_row["er"], 2), "Timestamp": r_row["timestamp_str"]
                                })
                                
                if org_reels:
                    avg_v = sum([x["Views"] for x in org_reels]) / len(org_reels)
                    avg_l = sum([x["likes"] for x in org_reels]) / len(org_reels)
                    avg_c = sum([x["comments"] for x in org_reels]) / len(org_reels)
                    avg_e = sum([x["er"] for x in org_reels]) / len(org_reels)
                else:
                    avg_v = avg_l = avg_c = avg_e = 0
                    if status == "Success": status = "No Organic Reels Found"
                    
                summary_rows.append({
                    "Profile Link": p_url, "Username": hand, "Followers": followers, "Reels Analysed": len(org_reels),
                    "Avg Views": round(avg_v, 2), "Avg Likes": round(avg_l, 2), "Avg Comments": round(avg_c, 2), "Avg Engagement Rate (%)": round(avg_e, 2), "Status": status
                })
                
            status_txt.empty()
            st.success("Targeted asset extraction execution cycle complete.")
            
            df_sum = pd.DataFrame(summary_rows)
            df_g_reels = pd.DataFrame(granular_rows)
            df_skip = pd.DataFrame(skipped_rows)
            
            if df_g_reels.empty: df_g_reels = pd.DataFrame(columns=["Profile Link", "Username", "Reel URL", "Shortcode", "Views", "Likes", "Comments", "Engagement Rate (%)", "Timestamp"])
            if df_skip.empty: df_skip = pd.DataFrame(columns=["Profile Link", "Username", "Reel URL", "Shortcode", "Views", "Likes", "Comments", "Engagement Rate (%)", "Timestamp", "Skip Reason"])
            
            t_sum, t_reel, t_skip = st.tabs(["Profile Summaries", "Individual Reel Metrics with Views", "Skipped Reels Repository"])
            with t_sum: st.dataframe(df_sum, use_container_width=True)
            with t_reel: st.dataframe(df_g_reels, use_container_width=True)
            with t_skip: st.dataframe(df_skip, use_container_width=True)
            
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df_sum.to_excel(writer, sheet_name="Profile Summary", index=False)
                df_g_reels.to_excel(writer, sheet_name="Reel Metrics", index=False)
                df_skip.to_excel(writer, sheet_name="Skipped Reels", index=False)
            st.download_button(label="Download Multi-Sheet Marketing Workbook", data=buf.getvalue(), file_name="creator_auditor_analytics.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if logo_base64:
    st.markdown(f'<div class="bottom-logo-container"><img src="data:image/jpeg;base64,{logo_base64}"></div>', unsafe_allow_html=True)

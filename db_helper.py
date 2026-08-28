import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import os
import tomllib
import pandas as pd
from datetime import datetime
import re

def load_config():
    """
    Loads Google Sheets configuration from Streamlit Secrets (for production)
    or local .streamlit/secrets.toml (for local development).
    """
    # 1. Try st.secrets (production Streamlit Cloud)
    try:
        if st.secrets and "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"]), st.secrets["spreadsheet_url"]
    except:
        pass
        
    # 2. Try local .streamlit/secrets.toml (local development)
    for path in ['.streamlit/secrets.toml', '../.streamlit/secrets.toml']:
        if os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    data = tomllib.load(f)
                    return data["gcp_service_account"], data["spreadsheet_url"]
            except Exception as e:
                print(f"Lỗi đọc secrets.toml tại {path}: {e}")
                
    # 3. Fallback check for relative paths depending on execute context
    alt_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
    if os.path.exists(alt_path):
        try:
            with open(alt_path, 'rb') as f:
                data = tomllib.load(f)
                return data["gcp_service_account"], data["spreadsheet_url"]
        except Exception as e:
            print(f"Lỗi đọc secrets.toml tại {alt_path}: {e}")

    raise ValueError("Không tìm thấy thông tin cấu hình Google Sheets trong st.secrets hoặc secrets.toml.")

def get_sheets_client():
    creds_dict, url = load_config()
    
    # Handle private key newline formatting
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client, url

def handle_sheets_errors(func):
    """
    Decorator to catch gspread APIError and display the detailed, unredacted
    error message directly in the Streamlit UI for diagnostics.
    """
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            try:
                err_msg = str(e)
                st.error(f"🔴 Lỗi liên kết Google Sheets API: {err_msg}")
                st.markdown(
                    "### 💡 Hướng dẫn kiểm tra & sửa lỗi:\n"
                    "1. **Chưa bật API hoặc quá tải hạn ngạch (429):** Bạn phải vào Google Cloud Console và đảm bảo đã bật **cả hai API** sau cho dự án:\n"
                    "   - **Google Sheets API**\n"
                    "   - **Google Drive API**\n"
                    "2. **Chưa chia sẻ quyền tệp:** Vui lòng mở file Google Sheets của bạn, bấm nút **Chia sẻ (Share)** và thêm tài khoản email dịch vụ sau với quyền **Người chỉnh sửa (Editor)**:\n"
                    "   `qbaki-tool@nhac-nho-chay-so-qbaki.iam.gserviceaccount.com`\n"
                    "3. **Kiểm tra URL:** Đảm bảo đường link `spreadsheet_url` cấu hình trong Secrets của Streamlit đã chính xác."
                )
            except Exception as display_err:
                print(f"Failed to display error in UI: {display_err}")
            st.stop()
    return wrapper

def open_spreadsheet(client, url):
    """
    Opens the spreadsheet by URL. Catches APIError and shows
    detailed instructions in Streamlit.
    """
    try:
        return client.open_by_url(url)
    except gspread.exceptions.APIError as e:
        try:
            st.error(f"🔴 Lỗi kết nối Google Sheets API: {str(e)}")
            st.markdown(
                "### 💡 Hướng dẫn khắc phục lỗi kết nối:\n"
                "1. **Chưa bật API:** Bạn phải vào Google Cloud Console và đảm bảo đã bật **cả hai API** sau cho dự án:\n"
                "   - **Google Sheets API** (Bắt buộc)\n"
                "   - **Google Drive API** (Bắt buộc)\n"
                "2. **Chưa chia sẻ quyền tệp:** Vui lòng mở file Google Sheets của bạn, bấm nút **Chia sẻ (Share)** và thêm tài khoản email dịch vụ sau với quyền **Người chỉnh sửa (Editor)**:\n"
                "   `qbaki-tool@nhac-nho-chay-so-qbaki.iam.gserviceaccount.com`\n"
                "3. **URL sai hoặc không hợp lệ:** Đảm bảo đường link `spreadsheet_url` cấu hình trong Secrets của Streamlit đã chính xác."
            )
        except Exception as display_err:
            print(f"Failed to display error in UI: {display_err}")
        raise e

def format_sheet_columns(ws, end_row):
    """Formats numeric columns in Google Sheets to show formatted numbers with thousands separator."""
    if end_row <= 1:
        return
    ranges = [
        f"E2:I{end_row}",
        f"K2:K{end_row}",
        f"O2:O{end_row}",
        f"Q2:Q{end_row}"
    ]
    for r in ranges:
        try:
            ws.format(r, {
                "numberFormat": {
                    "type": "NUMBER",
                    "pattern": "#,##0"
                }
            })
        except Exception as e:
            print(f"Lỗi format {r}: {e}")

@st.cache_data(ttl=15, show_spinner=False)
@handle_sheets_errors
def fetch_worksheet_records(sheet_name, url_str):
    """
    Cached function to fetch worksheet records.
    Prevents API Rate Limit Exceeded (HTTP 429) by caching data for 15 seconds.
    """
    client, url = get_sheets_client()
    sh = open_spreadsheet(client, url_str)
    ws = sh.worksheet(sheet_name)
    return ws.get_all_records()

@handle_sheets_errors
def init_db():
    """Initializes Google Sheets worksheets if they do not exist."""
    client, url = get_sheets_client()
    sh = open_spreadsheet(client, url)
    
    # 1. Initialize 'call_lists' worksheet
    try:
        sh.worksheet("call_lists")
    except gspread.exceptions.WorksheetNotFound:
        headers = [
            "year", "month", "username", "phone", "total_b_point", 
            "total_b_point_wf_confirm", "total_b_point_wf_payment", 
            "total_b_point_wf_processing", "total_b_point_wf_delivery", 
            "danh_hieu_chay", "b_point", "calculated_datetime", 
            "m1s_user_name", "m3s_user_name", "sum_points", 
            "final_danh_hieu", "final_sum_points", "is_achieved", "import_timestamp"
        ]
        sh.add_worksheet(title="call_lists", rows=1000, cols=20)
        ws = sh.worksheet("call_lists")
        ws.append_row(headers)
        
    # 2. Initialize 'call_history' worksheet
    try:
        sh.worksheet("call_history")
    except gspread.exceptions.WorksheetNotFound:
        headers = ["year", "month", "username", "call_date", "status", "note"]
        sh.add_worksheet(title="call_history", rows=1000, cols=10)
        ws = sh.worksheet("call_history")
        ws.append_row(headers)

@handle_sheets_errors
def save_call_list(df, year, month):
    """
    Saves or updates the filtered call list in the Google Sheet.
    Uses batch write to ensure high performance and avoid rate limits.
    """
    client, url = get_sheets_client()
    sh = open_spreadsheet(client, url)
    ws = sh.worksheet("call_lists")
    
    # Fetch existing data (uncached write preparation to ensure no overwrite conflicts)
    records = ws.get_all_records()
    headers = [
        "year", "month", "username", "phone", "total_b_point", 
        "total_b_point_wf_confirm", "total_b_point_wf_payment", 
        "total_b_point_wf_processing", "total_b_point_wf_delivery", 
        "danh_hieu_chay", "b_point", "calculated_datetime", 
        "m1s_user_name", "m3s_user_name", "sum_points", 
        "final_danh_hieu", "final_sum_points", "is_achieved", "import_timestamp"
    ]
    
    if records:
        df_existing = pd.DataFrame(records)
    else:
        df_existing = pd.DataFrame(columns=headers)
        
    import_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Standardize data types for matching
    df_existing['year'] = pd.to_numeric(df_existing['year'], errors='coerce').fillna(0).astype(int)
    df_existing['month'] = pd.to_numeric(df_existing['month'], errors='coerce').fillna(0).astype(int)
    df_existing['username'] = df_existing['username'].astype(str).str.strip()
    df_existing['phone'] = df_existing['phone'].astype(str).str.strip()
    
    # Cast float columns to float to avoid pandas type enforcement errors
    float_cols = [
        'total_b_point', 'total_b_point_wf_confirm', 'total_b_point_wf_payment', 
        'total_b_point_wf_processing', 'total_b_point_wf_delivery', 'b_point', 
        'sum_points', 'final_sum_points'
    ]
    for col in float_cols:
        if col in df_existing.columns:
            df_existing[col] = pd.to_numeric(df_existing[col], errors='coerce').fillna(0.0).astype(float)
            
    # Cast other string columns
    str_cols = ['danh_hieu_chay', 'calculated_datetime', 'm1s_user_name', 'm3s_user_name', 'final_danh_hieu', 'import_timestamp']
    for col in str_cols:
        if col in df_existing.columns:
            df_existing[col] = df_existing[col].astype(str).str.strip()
    
    df_existing.set_index(['year', 'month', 'username'], inplace=True, drop=False)
    
    for _, row in df.iterrows():
        username = str(row['Username']).strip()
        idx = (int(year), int(month), username)
        
        row_data = {
            'year': int(year),
            'month': int(month),
            'username': username,
            'phone': str(row['Phone']).strip(),
            'total_b_point': float(row['Total B Point']),
            'total_b_point_wf_confirm': float(row['Total B Point Wf Confirm']),
            'total_b_point_wf_payment': float(row['Total B Point Wf Payment']),
            'total_b_point_wf_processing': float(row['Total B Point Processing']),
            'total_b_point_wf_delivery': float(row['Total B Point Delivery']),
            'danh_hieu_chay': str(row['Danh hiệu Chạy']),
            'b_point': float(row['B Point']),
            'calculated_datetime': str(row['Calculated Datetime']),
            'm1s_user_name': str(row['M1s User Name']),
            'm3s_user_name': str(row['M3s User Name']),
            'sum_points': float(row['Sum Points']),
            'final_danh_hieu': '',
            'final_sum_points': 0.0,
            'is_achieved': 0,
            'import_timestamp': import_time
        }
        
        if idx in df_existing.index:
            # Update matching row (preserve day 5 fields & import time)
            df_existing.loc[idx, [
                'phone', 'total_b_point', 'total_b_point_wf_confirm', 
                'total_b_point_wf_payment', 'total_b_point_wf_processing', 
                'total_b_point_wf_delivery', 'danh_hieu_chay', 'b_point', 
                'calculated_datetime', 'm1s_user_name', 'm3s_user_name', 'sum_points'
            ]] = [
                row_data['phone'], row_data['total_b_point'], row_data['total_b_point_wf_confirm'],
                row_data['total_b_point_wf_payment'], row_data['total_b_point_wf_processing'],
                row_data['total_b_point_wf_delivery'], row_data['danh_hieu_chay'], row_data['b_point'],
                row_data['calculated_datetime'], row_data['m1s_user_name'], row_data['m3s_user_name'],
                row_data['sum_points']
            ]
        else:
            # Append new record
            new_row_df = pd.DataFrame([row_data])
            new_row_df.index = pd.MultiIndex.from_tuples([idx], names=['year', 'month', 'username'])
            df_existing = pd.concat([df_existing, new_row_df])
            
    df_existing.reset_index(drop=True, inplace=True)
    df_existing.fillna('', inplace=True)
    
    # Ensure exact column order
    df_existing = df_existing[headers]
    values = df_existing.values.tolist()
    
    # Batch update worksheet
    ws.clear()
    ws.update('A1', [headers] + values)
    format_sheet_columns(ws, len(values) + 1)
    
    # Invalidate cache so reads get fresh data immediately
    st.cache_data.clear()

@handle_sheets_errors
def get_call_list(year, month):
    """Retrieves call list for a given month, joined with call statistics."""
    client, url = get_sheets_client()
    
    # 1. Read call lists (cached)
    records_lists = fetch_worksheet_records("call_lists", url)
    if not records_lists:
        return pd.DataFrame()
        
    df_lists = pd.DataFrame(records_lists)
    df_lists = df_lists[
        (pd.to_numeric(df_lists['year'], errors='coerce') == int(year)) & 
        (pd.to_numeric(df_lists['month'], errors='coerce') == int(month))
    ]
    
    if df_lists.empty:
        return pd.DataFrame()
        
    # 2. Read call history (cached)
    records_history = fetch_worksheet_records("call_history", url)
    
    if records_history:
        df_history = pd.DataFrame(records_history)
        df_history = df_history[
            (pd.to_numeric(df_history['year'], errors='coerce') == int(year)) & 
            (pd.to_numeric(df_history['month'], errors='coerce') == int(month))
        ]
    else:
        df_history = pd.DataFrame(columns=["year", "month", "username", "call_date", "status", "note"])
        
    # 3. Aggregate history metrics
    if not df_history.empty:
        df_history['username'] = df_history['username'].astype(str).str.strip()
        df_history = df_history.sort_values('call_date')
        
        stats = df_history.groupby('username').agg(
            total_calls=('status', 'count'),
            success_calls=('status', lambda s: s.isin(['Thành công', 'Trả lời']).sum()),
            failed_calls=('status', lambda s: s.isin(['Không thành công', 'Không trả lời']).sum()),
            last_status=('status', 'last')
        ).reset_index()
    else:
        stats = pd.DataFrame(columns=['username', 'total_calls', 'success_calls', 'failed_calls', 'last_status'])
        
    df_lists['username'] = df_lists['username'].astype(str).str.strip()
    
    # Join lists with call metrics
    merged = pd.merge(df_lists, stats, on='username', how='left')
    merged['total_calls'] = merged['total_calls'].fillna(0).astype(int)
    merged['success_calls'] = merged['success_calls'].fillna(0).astype(int)
    merged['failed_calls'] = merged['failed_calls'].fillna(0).astype(int)
    
    return merged

@handle_sheets_errors
def add_call_log(year, month, username, status, note):
    """Appends a new call log entry to the history worksheet."""
    client, url = get_sheets_client()
    sh = open_spreadsheet(client, url)
    ws = sh.worksheet("call_history")
    
    call_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row = [int(year), int(month), str(username).strip(), call_date, str(status).strip(), str(note).strip()]
    ws.append_row(row)
    
    # Invalidate cache so reads get fresh data immediately
    st.cache_data.clear()

@handle_sheets_errors
def add_call_logs_batch(year, month, logs):
    """Appends multiple call log entries to the history worksheet in a single batch API call."""
    if not logs:
        return
    client, url = get_sheets_client()
    sh = open_spreadsheet(client, url)
    ws = sh.worksheet("call_history")
    
    call_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rows = []
    for log in logs:
        rows.append([
            int(year),
            int(month),
            str(log['username']).strip(),
            call_date,
            str(log['status']).strip(),
            str(log['note']).strip()
        ])
    
    ws.append_rows(rows)
    
    # Invalidate cache so reads get fresh data immediately
    st.cache_data.clear()


@handle_sheets_errors
def get_call_history(year, month, username):
    """Gets all historical logs for a user in a specific month."""
    client, url = get_sheets_client()
    records = fetch_worksheet_records("call_history", url)
    if not records:
        return pd.DataFrame()
        
    df = pd.DataFrame(records)
    df = df[
        (pd.to_numeric(df['year'], errors='coerce') == int(year)) & 
        (pd.to_numeric(df['month'], errors='coerce') == int(month)) & 
        (df['username'].astype(str).str.strip() == str(username).strip())
    ]
    if df.empty:
        return pd.DataFrame()
        
    return df.sort_values('call_date', ascending=False)[['call_date', 'status', 'note']]

@handle_sheets_errors
def update_final_sales(df_final, year, month):
    """
    Day 5 Final Sales Update:
    For all users currently in the calling list for this month, find their updated status in df_final.
    Updates final_danh_hieu, final_sum_points, and is_achieved.
    """
    client, url = get_sheets_client()
    sh = open_spreadsheet(client, url)
    ws = sh.worksheet("call_lists")
    
    records = ws.get_all_records()
    if not records:
        return 0
        
    df_lists = pd.DataFrame(records)
    df_lists['year'] = pd.to_numeric(df_lists['year'], errors='coerce').fillna(0).astype(int)
    df_lists['month'] = pd.to_numeric(df_lists['month'], errors='coerce').fillna(0).astype(int)
    df_lists['username'] = df_lists['username'].astype(str).str.strip()
    
    # Filter list for target month
    this_month_mask = (df_lists['year'] == int(year)) & (df_lists['month'] == int(month))
    if not this_month_mask.any():
        return 0
        
    # Map final dataframe column patterns
    col_mapping = {
        'Username': ['username', '^user$', 'tài khoản'],
        'Danh hiệu Chạy': ['danh hiệu chạy', 'danh hiệu', 'rank'],
        'Total B Point': ['^total b point$', '^b point tổng$'],
        'Total B Point Wf Confirm': ['total b point wf confirm', 'wf confirm'],
        'Total B Point Wf Payment': ['total b point wf payment', 'wf payment'],
        'Total B Point Wf Processing': ['total b point wf processing', 'total b point processing', 'wf processing'],
        'Total B Point Wf Delivery': ['total b point wf delivery', 'total b point delivery', 'wf delivery'],
    }
    
    import data_processor
    resolved_cols = {}
    for std_name, patterns in col_mapping.items():
        matched_col = data_processor.find_column_by_patterns(df_final, patterns)
        if matched_col is not None:
            resolved_cols[std_name] = matched_col
            
    if 'Username' not in resolved_cols or 'Danh hiệu Chạy' not in resolved_cols:
        raise ValueError("File doanh số cuối ngày 5 thiếu cột Username hoặc Danh hiệu.")
        
    username_col = resolved_cols['Username']
    danh_hieu_col = resolved_cols['Danh hiệu Chạy']
    
    df_final = df_final.copy()
    df_final[username_col] = df_final[username_col].astype(str).str.strip()
    final_lookup = df_final.set_index(username_col)
    
    updated_count = 0
    
    for idx, row in df_lists.iterrows():
        if row['year'] == int(year) and row['month'] == int(month):
            username = row['username']
            initial_danh_hieu = row['danh_hieu_chay']
            
            if username in final_lookup.index:
                user_data = final_lookup.loc[username]
                if isinstance(user_data, pd.DataFrame):
                    user_data = user_data.iloc[0]
                    
                final_danh_hieu = str(user_data[danh_hieu_col]).strip()
                
                def get_numeric(col_key):
                    if col_key in resolved_cols:
                        col_name = resolved_cols[col_key]
                        val = re.sub(r'[^\d\.]', '', str(user_data[col_name]))
                        try:
                            return float(val) if val else 0.0
                        except:
                            return 0.0
                    return 0.0
                    
                sum_points = (get_numeric('Total B Point') + 
                              get_numeric('Total B Point Wf Confirm') + 
                              get_numeric('Total B Point Wf Payment') + 
                              get_numeric('Total B Point Wf Processing') + 
                              get_numeric('Total B Point Wf Delivery'))
                
                is_achieved = 0
                final_danh_hieu_lower = final_danh_hieu.lower()
                
                if 'đạt' in final_danh_hieu_lower:
                    is_achieved = 1
                else:
                    if 'chạy c1' in initial_danh_hieu.lower() and sum_points >= 30000000:
                        is_achieved = 1
                    elif 'chạy c2' in initial_danh_hieu.lower() and sum_points >= 60000000:
                        is_achieved = 1
                    elif 'chạy c3' in initial_danh_hieu.lower() and sum_points >= 120000000:
                        is_achieved = 1
                        
                df_lists.loc[idx, 'final_danh_hieu'] = final_danh_hieu
                df_lists.loc[idx, 'final_sum_points'] = sum_points
                df_lists.loc[idx, 'is_achieved'] = int(is_achieved)
                updated_count += 1
                
    if updated_count > 0:
        headers = [
            "year", "month", "username", "phone", "total_b_point", 
            "total_b_point_wf_confirm", "total_b_point_wf_payment", 
            "total_b_point_wf_processing", "total_b_point_wf_delivery", 
            "danh_hieu_chay", "b_point", "calculated_datetime", 
            "m1s_user_name", "m3s_user_name", "sum_points", 
            "final_danh_hieu", "final_sum_points", "is_achieved", "import_timestamp"
        ]
        df_lists.fillna('', inplace=True)
        values = df_lists[headers].values.tolist()
        ws.clear()
        ws.update('A1', [headers] + values)
        format_sheet_columns(ws, len(values) + 1)
        
    # Invalidate cache so reads get fresh data immediately
    st.cache_data.clear()
    return updated_count

@handle_sheets_errors
def get_report_data(year, month):
    """Compiles detailed stats for reporting."""
    df_calls = get_call_list(year, month)
    if df_calls.empty:
        return None
        
    # Add alias columns to match app.py expected columns
    df_calls['call_count'] = df_calls['total_calls']
    df_calls['success_count'] = df_calls['success_calls']
    df_calls['failed_count'] = df_calls['failed_calls']
        
    total_users = len(df_calls)
    
    def categorize_call_status(row):
        if row['total_calls'] == 0:
            return 'Chưa gọi'
        elif row['success_calls'] > 0:
            return 'Trả lời'
        else:
            return 'Không trả lời'
            
    df_calls['call_status_cat'] = df_calls.apply(categorize_call_status, axis=1)
    df_calls['is_achieved'] = pd.to_numeric(df_calls['is_achieved'], errors='coerce').fillna(0).astype(int)
    
    summary = {
        'total_users': total_users,
        'total_called_success': int((df_calls['call_status_cat'] == 'Trả lời').sum()),
        'total_called_failed': int((df_calls['call_status_cat'] == 'Không trả lời').sum()),
        'total_not_called': int((df_calls['call_status_cat'] == 'Chưa gọi').sum()),
        
        'called_success_achieved': int(df_calls[(df_calls['call_status_cat'] == 'Trả lời') & (df_calls['is_achieved'] == 1)].shape[0]),
        'called_success_not_achieved': int(df_calls[(df_calls['call_status_cat'] == 'Trả lời') & (df_calls['is_achieved'] == 0)].shape[0]),
        
        'called_failed_achieved': int(df_calls[(df_calls['call_status_cat'] == 'Không trả lời') & (df_calls['is_achieved'] == 1)].shape[0]),
        'called_failed_not_achieved': int(df_calls[(df_calls['call_status_cat'] == 'Không trả lời') & (df_calls['is_achieved'] == 0)].shape[0]),
        
        'not_called_achieved': int(df_calls[(df_calls['call_status_cat'] == 'Chưa gọi') & (df_calls['is_achieved'] == 1)].shape[0]),
        'not_called_not_achieved': int(df_calls[(df_calls['call_status_cat'] == 'Chưa gọi') & (df_calls['is_achieved'] == 0)].shape[0]),
    }
    
    return {
        'summary': summary,
        'details': df_calls
    }

@handle_sheets_errors
def get_available_months():
    """Gets list of available Year-Month in database for filtering."""
    try:
        client, url = get_sheets_client()
        # Read from cached sheet
        records = fetch_worksheet_records("call_lists", url)
        if not records:
            return []
            
        df = pd.DataFrame(records)
        if df.empty or 'year' not in df.columns or 'month' not in df.columns:
            return []
            
        df['year'] = pd.to_numeric(df['year'], errors='coerce').fillna(0).astype(int)
        df['month'] = pd.to_numeric(df['month'], errors='coerce').fillna(0).astype(int)
        
        df = df[(df['year'] != 0) & (df['month'] != 0)]
        df_unique = df[['year', 'month']].drop_duplicates().sort_values(['year', 'month'], ascending=[False, False])
        
        return [{'year': int(r['year']), 'month': int(r['month']), 'label': f"Tháng {r['month']} - Năm {r['year']}"} for _, r in df_unique.iterrows()]
    except Exception as e:
        print(f"Error fetching months: {e}")
        return []

import sqlite3
import pandas as pd
from datetime import datetime
import os
import re

DB_PATH = 'sales_calls.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Table for storing call list targets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS call_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER,
            month INTEGER,
            username TEXT,
            phone TEXT,
            total_b_point REAL,
            total_b_point_wf_confirm REAL,
            total_b_point_wf_payment REAL,
            total_b_point_wf_processing REAL,
            total_b_point_wf_delivery REAL,
            danh_hieu_chay TEXT,
            b_point REAL,
            calculated_datetime TEXT,
            m1s_user_name TEXT,
            m3s_user_name TEXT,
            sum_points REAL,
            final_danh_hieu TEXT,
            final_sum_points REAL DEFAULT 0.0,
            is_achieved INTEGER DEFAULT 0,
            import_timestamp TEXT,
            UNIQUE(year, month, username)
        )
    ''')
    
    # Table for storing call history attempts
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS call_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER,
            month INTEGER,
            username TEXT,
            call_date TEXT,
            status TEXT,
            note TEXT,
            FOREIGN KEY (year, month, username) REFERENCES call_lists (year, month, username)
        )
    ''')
    
    conn.commit()
    conn.close()

def save_call_list(df, year, month):
    """
    Saves or updates the filtered call list in the database.
    Ensures existing call notes/progress are not wiped if user re-uploads.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    import_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    for _, row in df.iterrows():
        username = str(row['Username']).strip()
        phone = str(row['Phone']).strip()
        
        # Check if record already exists
        cursor.execute('''
            SELECT id, final_danh_hieu, final_sum_points, is_achieved 
            FROM call_lists 
            WHERE year = ? AND month = ? AND username = ?
        ''', (year, month, username))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update values, but preserve final day-5 results if already updated
            cursor.execute('''
                UPDATE call_lists
                SET phone = ?, total_b_point = ?, total_b_point_wf_confirm = ?, 
                    total_b_point_wf_payment = ?, total_b_point_wf_processing = ?, 
                    total_b_point_wf_delivery = ?, danh_hieu_chay = ?, b_point = ?, 
                    calculated_datetime = ?, m1s_user_name = ?, m3s_user_name = ?, 
                    sum_points = ?
                WHERE year = ? AND month = ? AND username = ?
            ''', (
                phone, 
                float(row['Total B Point']), 
                float(row['Total B Point Wf Confirm']),
                float(row['Total B Point Wf Payment']), 
                float(row['Total B Point Processing']), 
                float(row['Total B Point Delivery']), 
                str(row['Danh hiệu Chạy']), 
                float(row['B Point']), 
                str(row['Calculated Datetime']), 
                str(row['M1s User Name']), 
                str(row['M3s User Name']), 
                float(row['Sum Points']),
                year, month, username
            ))
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO call_lists (
                    year, month, username, phone, total_b_point, 
                    total_b_point_wf_confirm, total_b_point_wf_payment, 
                    total_b_point_wf_processing, total_b_point_wf_delivery, 
                    danh_hieu_chay, b_point, calculated_datetime, 
                    m1s_user_name, m3s_user_name, sum_points, import_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                year, month, username, phone, 
                float(row['Total B Point']), 
                float(row['Total B Point Wf Confirm']),
                float(row['Total B Point Wf Payment']), 
                float(row['Total B Point Processing']), 
                float(row['Total B Point Delivery']), 
                str(row['Danh hiệu Chạy']), 
                float(row['B Point']), 
                str(row['Calculated Datetime']), 
                str(row['M1s User Name']), 
                str(row['M3s User Name']), 
                float(row['Sum Points']),
                import_time
            ))
            
    conn.commit()
    conn.close()

def get_call_list(year, month):
    """
    Retrieves the call list for the given month, annotated with call statistics.
    Returns a DataFrame.
    """
    conn = get_db_connection()
    
    query = '''
        SELECT 
            cl.*,
            COUNT(ch.id) as total_calls,
            SUM(CASE WHEN ch.status = 'Thành công' THEN 1 ELSE 0 END) as success_calls,
            SUM(CASE WHEN ch.status = 'Không thành công' THEN 1 ELSE 0 END) as failed_calls,
            (SELECT status FROM call_history WHERE year = cl.year AND month = cl.month AND username = cl.username ORDER BY call_date DESC LIMIT 1) as last_status
        FROM call_lists cl
        LEFT JOIN call_history ch ON cl.year = ch.year AND cl.month = ch.month AND cl.username = ch.username
        WHERE cl.year = ? AND cl.month = ?
        GROUP BY cl.id
    '''
    
    df = pd.read_sql_query(query, conn, params=(year, month))
    conn.close()
    return df

def add_call_log(year, month, username, status, note):
    """Adds a call attempt record to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    call_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        INSERT INTO call_history (year, month, username, call_date, status, note)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (year, month, username, call_date, status, note))
    
    conn.commit()
    conn.close()

def get_call_history(year, month, username):
    """Gets call attempts history for a user in a specific month."""
    conn = get_db_connection()
    query = '''
        SELECT call_date, status, note 
        FROM call_history 
        WHERE year = ? AND month = ? AND username = ?
        ORDER BY call_date DESC
    '''
    df = pd.read_sql_query(query, conn, params=(year, month, username))
    conn.close()
    return df

def update_final_sales(df_final, year, month):
    """
    Day 5 Final Sales Update:
    For all users currently in the calling list for this month, find their updated status in df_final.
    Updates final_danh_hieu, final_sum_points, and is_achieved.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch current users in calling list
    cursor.execute('SELECT username, danh_hieu_chay FROM call_lists WHERE year = ? AND month = ?', (year, month))
    users = cursor.fetchall()
    
    if not users:
        conn.close()
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
        conn.close()
        raise ValueError("File doanh số cuối ngày 5 thiếu cột Username hoặc Danh hiệu.")
        
    username_col = resolved_cols['Username']
    danh_hieu_col = resolved_cols['Danh hiệu Chạy']
    
    # Convert final df username column to string, strip spaces for matching
    df_final = df_final.copy()
    df_final[username_col] = df_final[username_col].astype(str).str.strip()
    
    # Index for fast lookup
    final_lookup = df_final.set_index(username_col)
    
    updated_count = 0
    
    for row in users:
        username = row['username']
        initial_danh_hieu = row['danh_hieu_chay']
        
        if username in final_lookup.index:
            user_data = final_lookup.loc[username]
            
            # Handle duplicates if username is not unique in final list
            if isinstance(user_data, pd.DataFrame):
                user_data = user_data.iloc[0]
                
            final_danh_hieu = str(user_data[danh_hieu_col]).strip()
            
            # Sum final points
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
            
            # Determine if they achieved target
            # They achieve target if they are 'Đạt C1', 'Đạt C2', 'Đạt C3' or if their points exceed target
            is_achieved = 0
            final_danh_hieu_lower = final_danh_hieu.lower()
            
            # Targets based on the running rank they were called for
            # running C1 -> Đạt C1 (>=30M)
            # running C2 -> Đạt C2 (>=60M)
            # running C3 -> Đạt C3 (>=120M)
            if 'đạt' in final_danh_hieu_lower:
                is_achieved = 1
            else:
                # Fallback to points threshold
                if 'chạy c1' in initial_danh_hieu.lower() and sum_points >= 30000000:
                    is_achieved = 1
                elif 'chạy c2' in initial_danh_hieu.lower() and sum_points >= 60000000:
                    is_achieved = 1
                elif 'chạy c3' in initial_danh_hieu.lower() and sum_points >= 120000000:
                    is_achieved = 1
                    
            cursor.execute('''
                UPDATE call_lists
                SET final_danh_hieu = ?, final_sum_points = ?, is_achieved = ?
                WHERE year = ? AND month = ? AND username = ?
            ''', (final_danh_hieu, sum_points, is_achieved, year, month, username))
            updated_count += 1
            
    conn.commit()
    conn.close()
    return updated_count

def get_report_data(year, month):
    """
    Compiles detailed stats for reporting.
    Returns:
    - Summary counts
    - List of successful calls
    - List of unsuccessful calls
    - Achieved vs not achieved breakdown
    """
    conn = get_db_connection()
    
    # 1. Total targets
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM call_lists WHERE year = ? AND month = ?', (year, month))
    total_users = cursor.fetchone()[0]
    
    if total_users == 0:
        conn.close()
        return None
        
    # 2. Get call results detail
    # A user is "Gọi được" (Called successfully) if they have at least one successful call log.
    # A user is "Gọi không được" (Called unsuccessfully) if they have calls but none is successful.
    # A user is "Chưa gọi" (Not called) if they have 0 calls.
    query = '''
        SELECT 
            cl.username,
            cl.phone,
            cl.danh_hieu_chay,
            cl.sum_points,
            cl.final_danh_hieu,
            cl.final_sum_points,
            cl.is_achieved,
            COUNT(ch.id) as call_count,
            SUM(CASE WHEN ch.status = 'Thành công' THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN ch.status = 'Không thành công' THEN 1 ELSE 0 END) as failed_count
        FROM call_lists cl
        LEFT JOIN call_history ch ON cl.year = ch.year AND cl.month = ch.month AND cl.username = ch.username
        WHERE cl.year = ? AND cl.month = ?
        GROUP BY cl.id
    '''
    
    df_details = pd.read_sql_query(query, conn, params=(year, month))
    conn.close()
    
    # Categorize
    def categorize_call_status(row):
        if row['call_count'] == 0:
            return 'Chưa gọi'
        elif row['success_count'] > 0:
            return 'Gọi được (Thành công)'
        else:
            return 'Gọi không được (Thất bại)'
            
    df_details['call_status_cat'] = df_details.apply(categorize_call_status, axis=1)
    
    summary = {
        'total_users': total_users,
        'total_called_success': int((df_details['call_status_cat'] == 'Gọi được (Thành công)').sum()),
        'total_called_failed': int((df_details['call_status_cat'] == 'Gọi không được (Thất bại)').sum()),
        'total_not_called': int((df_details['call_status_cat'] == 'Chưa gọi').sum()),
        
        # Achieved stats for Called Successfully
        'called_success_achieved': int(df_details[(df_details['call_status_cat'] == 'Gọi được (Thành công)') & (df_details['is_achieved'] == 1)].shape[0]),
        'called_success_not_achieved': int(df_details[(df_details['call_status_cat'] == 'Gọi được (Thành công)') & (df_details['is_achieved'] == 0)].shape[0]),
        
        # Achieved stats for Called Unsuccessfully
        'called_failed_achieved': int(df_details[(df_details['call_status_cat'] == 'Gọi không được (Thất bại)') & (df_details['is_achieved'] == 1)].shape[0]),
        'called_failed_not_achieved': int(df_details[(df_details['call_status_cat'] == 'Gọi không được (Thất bại)') & (df_details['is_achieved'] == 0)].shape[0]),
        
        # Achieved stats for Not Called
        'not_called_achieved': int(df_details[(df_details['call_status_cat'] == 'Chưa gọi') & (df_details['is_achieved'] == 1)].shape[0]),
        'not_called_not_achieved': int(df_details[(df_details['call_status_cat'] == 'Chưa gọi') & (df_details['is_achieved'] == 0)].shape[0]),
    }
    
    return {
        'summary': summary,
        'details': df_details
    }

def get_available_months():
    """Gets list of available Year-Month in database for filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT year, month FROM call_lists ORDER BY year DESC, month DESC')
    rows = cursor.fetchall()
    conn.close()
    return [{'year': r[0], 'month': r[1], 'label': f"Tháng {r[1]} - Năm {r[0]}"} for r in rows]


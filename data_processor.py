import pandas as pd
import numpy as np
import re

def find_column_by_patterns(df, patterns):
    """
    Finds a column in the dataframe that matches any of the given regex patterns.
    Returns the actual column name or None.
    """
    for col in df.columns:
        col_lower = str(col).strip().lower()
        for pattern in patterns:
            if re.search(pattern.lower(), col_lower):
                return col
    return None

def process_partner_data(df):
    """
    Processes the raw partner sales dataframe and filters those who need to be called.
    
    Steps:
    1. Standardize columns
    2. Fill M1s User Name empty cells with '-'
    3. Fill M3s User Name empty cells hierarchically: M6s -> M9s -> M12s
    4. Calculate Total Point Sum = Total B Point + Wf Confirm + Wf Payment + Wf Processing + Wf Delivery
    5. Filter based on 'Danh hiệu Chạy' and the Point Thresholds:
       - 'Chạy C1': Sum >= 30,000,000
       - 'Chạy C2': Sum >= 60,000,000
       - 'Chạy C3': Sum >= 120,000,000
    6. Reorder and standardize columns for the call sheet output.
    """
    # Create a copy to avoid SettingWithCopyWarning
    df = df.copy()
    
    # 1. Flexible Column Mapping
    col_mapping = {
        'Username': ['username', '^user$', 'tài khoản'],
        'Phone': ['phone', 'sđt', 'điện thoại', 'số điện thoại'],
        'Year': ['year', '^năm$'],
        'Month': ['month', '^tháng$'],
        'Total B Point': ['^total b point$', '^b point tổng$'],
        'Total B Point Wf Confirm': ['total b point wf confirm', 'wf confirm'],
        'Total B Point Wf Payment': ['total b point wf payment', 'wf payment'],
        'Total B Point Wf Processing': ['total b point wf processing', 'total b point processing', 'wf processing'],
        'Total B Point Wf Delivery': ['total b point wf delivery', 'total b point delivery', 'wf delivery'],
        'Danh hiệu Chạy': ['danh hiệu chạy', 'danh hiệu', 'rank'],
        'B Point': ['^b point$', '^bpoint$'],
        'Calculated Datetime': ['calculated datetime', 'datetime', 'thời gian tính'],
        'M1s User Name': ['m1s user name', 'm1s'],
        'M3s User Name': ['m3s user name', 'm3s'],
        'M6s User Name': ['m6s user name', 'm6s'],
        'M9s User Name': ['m9s user name', 'm9s'],
        'M12s User Name': ['m12s user name', 'm12s']
    }
    
    resolved_cols = {}
    for standard_name, patterns in col_mapping.items():
        matched_col = find_column_by_patterns(df, patterns)
        if matched_col is not None:
            resolved_cols[standard_name] = matched_col

    # Check for critical columns
    critical_cols = ['Username', 'Phone', 'Danh hiệu Chạy']
    missing_critical = [c for c in critical_cols if c not in resolved_cols]
    if missing_critical:
        raise ValueError(f"Không tìm thấy các cột quan trọng sau trong file: {', '.join(missing_critical)}. "
                         "Vui lòng kiểm tra lại tiêu đề cột.")

    # Standardize data types and handle missing values for calculation
    def get_numeric_series(col_key):
        if col_key in resolved_cols:
            col_name = resolved_cols[col_key]
            # Convert to numeric, replace NaN with 0
            return pd.to_numeric(df[col_name].astype(str).str.replace(r'[^\d\.]', '', regex=True), errors='coerce').fillna(0)
        return pd.Series(0.0, index=df.index)

    # 2. Fill empty cells for M1s and M3s User Name
    # Get values or set default
    m1_col = resolved_cols.get('M1s User Name')
    m3_col = resolved_cols.get('M3s User Name')
    m6_col = resolved_cols.get('M6s User Name')
    m9_col = resolved_cols.get('M9s User Name')
    m12_col = resolved_cols.get('M12s User Name')

    # Convert to string and clean spaces/NaN
    for col_name in [m1_col, m3_col, m6_col, m9_col, m12_col]:
        if col_name and col_name in df.columns:
            df[col_name] = df[col_name].astype(str).str.strip().replace({'nan': '', 'None': '', '<NA>': '', 'NaT': ''})
            df[col_name] = df[col_name].fillna('')

    # Rule 1: M1s User Name empty -> "-"
    if m1_col:
        df[m1_col] = df[m1_col].apply(lambda x: '-' if x == '' or x == '-' else x)
    else:
        # Create a new column with '-' if not present
        df['M1s User Name'] = '-'
        resolved_cols['M1s User Name'] = 'M1s User Name'

    # Rule 2: M3s User Name empty -> M6s -> M9s -> M12s
    def resolve_m3_name(row):
        m3_val = row[m3_col] if m3_col else ''
        if m3_val and m3_val != '-':
            return m3_val
        
        m6_val = row[m6_col] if m6_col else ''
        if m6_val and m6_val != '-':
            return m6_val
            
        m9_val = row[m9_col] if m9_col else ''
        if m9_val and m9_val != '-':
            return m9_val
            
        m12_val = row[m12_col] if m12_col else ''
        if m12_val and m12_val != '-':
            return m12_val
            
        return '-'

    if m3_col:
        df[m3_col] = df.apply(resolve_m3_name, axis=1)
    else:
        df['M3s User Name'] = df.apply(resolve_m3_name, axis=1)
        resolved_cols['M3s User Name'] = 'M3s User Name'

    # 3. Summing Points
    total_b_point = get_numeric_series('Total B Point')
    wf_confirm = get_numeric_series('Total B Point Wf Confirm')
    wf_payment = get_numeric_series('Total B Point Wf Payment')
    wf_processing = get_numeric_series('Total B Point Wf Processing')
    wf_delivery = get_numeric_series('Total B Point Wf Delivery')
    
    sum_points = total_b_point + wf_confirm + wf_payment + wf_processing + wf_delivery
    df['_sum_points'] = sum_points

    # 4. Filtering criteria
    danh_hieu_col = resolved_cols['Danh hiệu Chạy']
    
    def check_keep_row(row):
        danh_hieu = str(row[danh_hieu_col]).strip().lower()
        score = row['_sum_points']
        
        if 'chạy c1' in danh_hieu:
            return score >= 30000000
        elif 'chạy c2' in danh_hieu:
            return score >= 60000000
        elif 'chạy c3' in danh_hieu:
            return score >= 120000000
        return False

    filtered_df = df[df.apply(check_keep_row, axis=1)].copy()

    # 5. Build and Reorder the Output DataFrame
    # Let's map target columns to standard names
    output_df = pd.DataFrame()
    
    # We want these columns in this order:
    target_columns = [
        ('Username', 'Username'),
        ('Phone', 'Phone'),
        ('Year', 'Year'),
        ('Month', 'Month'),
        ('Total B Point', 'Total B Point'),
        ('Total B Point Wf Confirm', 'Total B Point Wf Confirm'),
        ('Total B Point Wf Payment', 'Total B Point Wf Payment'),
        ('Total B Point Processing', 'Total B Point Wf Processing'), # standard key mapped to 'Total B Point Wf Processing'
        ('Total B Point Delivery', 'Total B Point Wf Delivery'),     # standard key mapped to 'Total B Point Wf Delivery'
        ('Danh hiệu Chạy', 'Danh hiệu Chạy'),
        ('B Point', 'B Point'),
        ('Calculated Datetime', 'Calculated Datetime'),
        ('M1s User Name', 'M1s User Name'),
        ('M3s User Name', 'M3s User Name')
    ]
    
    for display_name, std_key in target_columns:
        if std_key in resolved_cols:
            actual_col = resolved_cols[std_key]
            # Convert Year and Month to integers if possible
            if std_key in ['Year', 'Month']:
                output_df[display_name] = pd.to_numeric(filtered_df[actual_col], errors='coerce').fillna(0).astype(int)
            # Numeric columns
            elif std_key in ['Total B Point', 'Total B Point Wf Confirm', 'Total B Point Wf Payment', 
                             'Total B Point Wf Processing', 'Total B Point Wf Delivery', 'B Point']:
                output_df[display_name] = get_numeric_series(std_key).loc[filtered_df.index]
            else:
                output_df[display_name] = filtered_df[actual_col]
        else:
            # Column was not present, fill defaults
            if std_key in ['Year', 'Month']:
                output_df[display_name] = 0
            elif std_key in ['Total B Point', 'Total B Point Wf Confirm', 'Total B Point Wf Payment', 
                             'Total B Point Wf Processing', 'Total B Point Wf Delivery', 'B Point']:
                output_df[display_name] = 0.0
            elif std_key == 'M1s User Name' or std_key == 'M3s User Name':
                output_df[display_name] = '-'
            else:
                output_df[display_name] = ''

    # Add the computed sum column for internal tracking
    output_df['Sum Points'] = filtered_df['_sum_points']
    
    return output_df

import streamlit as st
import pandas as pd
import numpy as np
import os
import plotly.express as px
from datetime import datetime
import io

# Import local helpers
import db_helper
import data_processor

# Page config
st.set_page_config(
    page_title="Hệ thống Quản lý Cuộc gọi Nhắc nhở Doanh số",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Database
db_helper.init_db()

# Application Title
st.title("📞 Hệ thống Quản lý Cuộc gọi & Nhắc nhở Doanh số")
st.markdown("""
Hệ thống giúp tự động hóa quá trình lọc danh sách đối tác cần gọi điện nhắc nhở doanh số tháng, 
theo dõi lịch sử cuộc gọi và tổng hợp báo cáo hiệu quả đạt doanh số vào cuối tháng (ngày 5).
""")

# Setup Sidebar for Global Filters
st.sidebar.header("Bộ lọc Tháng/Năm làm việc")

# Get list of months from DB to populate dropdown
db_months = db_helper.get_available_months()
current_year = datetime.now().year
current_month = datetime.now().month

if db_months:
    month_options = [f"Tháng {m['month']} - Năm {m['year']}" for m in db_months]
    selected_option = st.sidebar.selectbox("Chọn Tháng/Năm hiển thị dữ liệu:", month_options)
    
    # Parse selected month and year
    # Option text format: "Tháng X - Năm Y"
    parts = selected_option.split(" - ")
    sel_month = int(parts[0].replace("Tháng ", ""))
    sel_year = int(parts[1].replace("Năm ", ""))
else:
    # Default if no data in DB yet
    sel_month = current_month
    sel_year = current_year
    st.sidebar.info("Chưa có dữ liệu tháng nào trong hệ thống. Vui lòng tải lên file dữ liệu thô ở **Tab 1**.")

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Thời gian hệ thống:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")
st.sidebar.markdown("**Phiên bản:** v1.0.0")

# Tabs definition
tab1, tab2, tab3, tab4 = st.tabs([
    "📥 Tải lên & Sàng lọc dữ liệu (Đầu tháng)",
    "📞 Ghi nhận & Quản lý Cuộc gọi",
    "📊 Báo cáo Cuộc gọi & Hiệu quả",
    "📈 Cập nhật doanh số thực tế (Ngày 5)"
])

# ----------------- TAB 1: UPLOAD & FILTER DATA -----------------
with tab1:
    st.header("Tải lên và Sàng lọc Danh sách Đối tác cần gọi")
    st.markdown("""
    **Quy trình:**
    1. Nhập Tháng/Năm của dữ liệu cần lọc.
    2. Tải lên file Excel kết quả doanh số thô được xuất ra từ hệ thống.
    3. Hệ thống sẽ tự động làm sạch tên `M1s`/`M3s` và lọc ra các đối tác có danh hiệu `Chạy C1/C2/C3` đạt điểm tối thiểu để gọi nhắc nhở.
    4. Kiểm tra trước kết quả và lưu danh sách gọi vào hệ thống.
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        import_month = st.number_input("Chọn Tháng nhập dữ liệu:", min_value=1, max_value=12, value=current_month)
    with col2:
        import_year = st.number_input("Chọn Năm nhập dữ liệu:", min_value=2020, max_value=2100, value=current_year)
        
    uploaded_file = st.file_uploader("Tải lên file Excel dữ liệu doanh số thô (.xlsx, .xls):", type=["xlsx", "xls"])
    
    if uploaded_file is not None:
        try:
            # Read excel
            df_raw = pd.read_excel(uploaded_file)
            st.success(f"Đã đọc thành công file Excel! Tổng số dòng: {len(df_raw)}, Số cột: {len(df_raw.columns)}")
            
            with st.expander("Xem trước 5 dòng dữ liệu gốc"):
                raw_preview = df_raw.head().copy()
                for col in raw_preview.columns:
                    if pd.api.types.is_numeric_dtype(raw_preview[col]):
                        raw_preview[col] = raw_preview[col].apply(
                            lambda x: f"{int(round(x)):,}".replace(",", ".") if pd.notna(x) and isinstance(x, (int, float)) else x
                        )
                st.dataframe(raw_preview)
                
            if st.button("🚀 Bắt đầu Sàng lọc dữ liệu", key="process_raw_btn"):
                with st.spinner("Đang xử lý dữ liệu..."):
                    # Process
                    processed_df = data_processor.process_partner_data(df_raw)
                    
                    # Store in session state for saving later
                    st.session_state['processed_df'] = processed_df
                    st.session_state['import_month'] = import_month
                    st.session_state['import_year'] = import_year
                    
                st.success("Sàng lọc dữ liệu thành công!")
                
                # Show quick stats
                st.subheader("📊 Thống kê sơ bộ sau sàng lọc")
                c1_cnt = len(processed_df[processed_df['Danh hiệu Chạy'].str.contains('C1', case=False, na=False)])
                c2_cnt = len(processed_df[processed_df['Danh hiệu Chạy'].str.contains('C2', case=False, na=False)])
                c3_cnt = len(processed_df[processed_df['Danh hiệu Chạy'].str.contains('C3', case=False, na=False)])
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Tổng số cần gọi nhắc", f"{len(processed_df)} user")
                m2.metric("Chạy C1 (Tổng điểm >= 30M)", f"{c1_cnt} user")
                m3.metric("Chạy C2 (Tổng điểm >= 60M)", f"{c2_cnt} user")
                m4.metric("Chạy C3 (Tổng điểm >= 120M)", f"{c3_cnt} user")
                
                # Show processed preview
                st.subheader("📝 Danh sách preview (Đã sắp xếp cột theo mẫu gọi)")
                preview_df = processed_df.copy()
                cols_to_format = [
                    "Total B Point", "Total B Point Wf Confirm", "Total B Point Wf Payment", 
                    "Total B Point Processing", "Total B Point Delivery", "B Point", "Sum Points"
                ]
                for col in cols_to_format:
                    if col in preview_df.columns:
                        preview_df[col] = preview_df[col].apply(
                            lambda x: f"{int(round(x)):,}".replace(",", ".") if pd.notna(x) and isinstance(x, (int, float)) else x
                        )
                st.dataframe(preview_df)

                
                # Let user download the filtered Excel directly
                output = io.BytesIO()
                # Create excel writer without the internal tracking sum column for the final file
                export_cols = [c for c in processed_df.columns if c != 'Sum Points']
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    processed_df[export_cols].to_excel(writer, index=False, sheet_name='Danh_sach_goi')
                processed_excel = output.getvalue()
                
                st.download_button(
                    label="📥 Tải xuống File gọi điện (.xlsx)",
                    data=processed_excel,
                    file_name=f"Danh_sach_goi_T{import_month}_{import_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
        except Exception as e:
            st.error(f"Đã xảy ra lỗi khi xử lý file: {str(e)}")
            st.info("Vui lòng đảm bảo file excel tải lên đúng định dạng và có đầy đủ các cột cần thiết.")

    # Save to Database action
    if 'processed_df' in st.session_state:
        st.markdown("---")
        st.subheader("💾 Lưu danh sách gọi vào cơ sở dữ liệu")
        st.warning(f"Lưu ý: Thao tác này sẽ lưu danh sách đối tác cần gọi của Tháng {st.session_state['import_month']} - Năm {st.session_state['import_year']} vào hệ thống. Nếu tháng này đã tồn tại, dữ liệu mới sẽ cập nhật thông tin đối tác hiện có nhưng không làm mất lịch sử các cuộc gọi trước đó.")
        
        if st.button("💾 Xác nhận lưu vào Hệ thống", key="save_db_btn"):
            try:
                db_helper.save_call_list(
                    st.session_state['processed_df'], 
                    st.session_state['import_year'], 
                    st.session_state['import_month']
                )
                st.success(f"Đã lưu danh sách gọi Tháng {st.session_state['import_month']}/{st.session_state['import_year']} thành công vào cơ sở dữ liệu! Bạn có thể chuyển sang Tab 2 để thực hiện gọi và cập nhật trạng thái.")
                # Rerun to refresh global month dropdown in sidebar
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi khi lưu vào database: {str(e)}")

# ----------------- TAB 2: CALL LOGGING & MANAGEMENT -----------------
with tab2:
    st.header(f"Quản lý & Ghi nhận Cuộc gọi - Tháng {sel_month}/{sel_year}")
    
    # Load data for selected month
    df_calls = db_helper.get_call_list(sel_year, sel_month)
    
    if df_calls.empty:
        st.warning(f"Chưa có danh sách cuộc gọi cho Tháng {sel_month}/{sel_year}. Vui lòng tạo danh sách ở **Tab 1** trước.")
    else:
        # Search & Filter widgets
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            search_query = st.text_input("🔍 Tìm kiếm theo Tài khoản (Username) hoặc Số điện thoại:", "")
        with col_f2:
            status_filter = st.selectbox("Lọc theo trạng thái cuộc gọi:", [
                "Tất cả", 
                "Chưa gọi", 
                "Gọi được (Thành công)", 
                "Gọi không được (Thất bại)"
            ])
            
        # Apply search filter
        df_filtered = df_calls.copy()
        if search_query:
            df_filtered = df_filtered[
                df_filtered['username'].str.contains(search_query, case=False, na=False) |
                df_filtered['phone'].astype(str).str.contains(search_query, na=False)
            ]
            
        # Apply status filter
        # A user is "Gọi được (Thành công)" if success_calls > 0
        # A user is "Gọi không được (Thất bại)" if failed_calls > 0 and success_calls == 0
        # A user is "Chưa gọi" if total_calls == 0
        if status_filter == "Chưa gọi":
            df_filtered = df_filtered[df_filtered['total_calls'] == 0]
        elif status_filter == "Gọi được (Thành công)":
            df_filtered = df_filtered[df_filtered['success_calls'] > 0]
        elif status_filter == "Gọi không được (Thất bại)":
            df_filtered = df_filtered[(df_filtered['failed_calls'] > 0) & (df_filtered['success_calls'] == 0)]

        # Display main Table
        st.subheader(f"Danh sách đối tác cần gọi ({len(df_filtered)} / {len(df_calls)} kết quả)")
        
        # Format df for display
        df_display = df_filtered.copy()
        df_display['Tổng cuộc gọi'] = df_display['total_calls'].astype(int)
        df_display['Gọi Thành công'] = df_display['success_calls'].astype(int)
        df_display['Gọi Không thành công'] = df_display['failed_calls'].astype(int)
        df_display['Trạng thái cuối'] = df_display['last_status'].fillna('Chưa gọi')
        df_display['Tổng điểm chạy'] = df_display['sum_points'].apply(lambda x: f"{int(round(x)):,}".replace(",", ".") + " đ" if pd.notna(x) else "")

        
        display_cols = [
            'username', 'phone', 'danh_hieu_chay', 'Tổng điểm chạy', 
            'Tổng cuộc gọi', 'Gọi Thành công', 'Gọi Không thành công', 
            'Trạng thái cuối', 'm1s_user_name', 'm3s_user_name'
        ]
        st.dataframe(df_display[display_cols].rename(columns={
            'username': 'Tài khoản',
            'phone': 'Số điện thoại',
            'danh_hieu_chay': 'Danh hiệu chạy',
            'm1s_user_name': 'M1s User',
            'm3s_user_name': 'M3s User'
        }), use_container_width=True)
        
        # Single log form vs Batch upload
        st.markdown("---")
        log_type = st.radio("Phương thức ghi nhận kết quả gọi:", ["Ghi nhận từng User (Thủ công)", "Tải lên file Kết quả gọi hàng loạt (.xlsx, .csv)"])
        
        if log_type == "Ghi nhận từng User (Thủ công)":
            st.subheader("📝 Nhập kết quả cuộc gọi")
            
            # Selectbox containing filtered usernames
            user_list = df_filtered['username'].tolist()
            if not user_list:
                st.info("Không có user nào khớp bộ lọc để chọn.")
            else:
                col_u1, col_u2, col_u3 = st.columns([2, 1, 2])
                with col_u1:
                    target_user = st.selectbox("Chọn Tài khoản đối tác:", user_list)
                    # Show user phone & details
                    user_info = df_filtered[df_filtered['username'] == target_user].iloc[0]
                    st.info(f"📞 SĐT: **{user_info['phone']}** | 🏆 Danh hiệu: **{user_info['danh_hieu_chay']}** | 💰 Điểm: **{user_info['sum_points']:,.0f}**")
                with col_u2:
                    call_status = st.selectbox("Kết quả cuộc gọi:", ["Thành công", "Không thành công"])
                with col_u3:
                    call_note = st.text_input("Ghi chú cuộc gọi (ví dụ: Thuê bao, hẹn gọi lại, hứa chạy doanh số...):")
                    
                if st.button("💾 Lưu kết quả gọi", key="save_single_call"):
                    db_helper.add_call_log(sel_year, sel_month, target_user, call_status, call_note)
                    st.success(f"Đã lưu kết quả gọi cho tài khoản **{target_user}**: {call_status}!")
                    st.rerun()
                    
                # View History for selected user
                st.markdown("**Lịch sử các cuộc gọi trước đó của đối tác này:**")
                history_df = db_helper.get_call_history(sel_year, sel_month, target_user)
                if history_df.empty:
                    st.text("Chưa có lịch sử cuộc gọi trong tháng này.")
                else:
                    st.dataframe(history_df.rename(columns={
                        'call_date': 'Thời gian gọi',
                        'status': 'Trạng thái',
                        'note': 'Ghi chú'
                    }), use_container_width=True)
                    
        else:
            # Batch upload call history
            st.subheader("📥 Tải lên File Kết quả gọi hàng loạt")
            st.markdown("""
            **Yêu cầu file tải lên:**
            - Phải có cột tên **Tài khoản** (hoặc `Username`) để khớp thông tin đối tác.
            - Phải có cột tên **Kết quả** (hoặc `Trạng thái`, `Status`) chứa một trong hai giá trị: **Thành công** / **Không thành công** (hoặc `success`/`failed`).
            - Có thể có cột **Ghi chú** (hoặc `Note`) để ghi lại thông tin chi tiết.
            """)
            
            bulk_file = st.file_uploader("Tải lên file kết quả gọi hàng loạt (.xlsx, .csv):", type=["xlsx", "xls", "csv"], key="bulk_call_uploader")
            
            if bulk_file is not None:
                try:
                    # Read file
                    if bulk_file.name.endswith('.csv'):
                        df_bulk = pd.read_csv(bulk_file)
                    else:
                        df_bulk = pd.read_excel(bulk_file)
                        
                    st.dataframe(df_bulk.head())
                    
                    # Match columns
                    user_col = data_processor.find_column_by_patterns(df_bulk, ['username', 'tài khoản', 'user'])
                    status_col = data_processor.find_column_by_patterns(df_bulk, ['kết quả', 'trạng thái', 'status', 'result'])
                    note_col = data_processor.find_column_by_patterns(df_bulk, ['ghi chú', 'note', 'comment'])
                    
                    if not user_col or not status_col:
                        st.error("Không tìm thấy cột 'Tài khoản/Username' hoặc cột 'Kết quả/Trạng thái' trong file. Vui lòng đặt lại tiêu đề cột.")
                    else:
                        if st.button("🚀 Bắt đầu Import Kết quả gọi", key="run_bulk_call_btn"):
                            success_count = 0
                            error_count = 0
                            
                            # Valid status mapper
                            def clean_status(val):
                                val_str = str(val).strip().lower()
                                if val_str in ['thành công', 'thanh cong', 'success', 'gọi được', 'ok']:
                                    return 'Thành công'
                                return 'Không thành công'
                                
                            for _, row in df_bulk.iterrows():
                                u_name = str(row[user_col]).strip()
                                # Check if this user is in our call list for this month
                                if u_name in df_calls['username'].values:
                                    status_val = clean_status(row[status_col])
                                    note_val = str(row[note_col]).strip() if note_col and not pd.isna(row[note_col]) else ''
                                    
                                    db_helper.add_call_log(sel_year, sel_month, u_name, status_val, note_val)
                                    success_count += 1
                                else:
                                    error_count += 1
                                    
                            st.success(f"Đã nhập thành công kết quả gọi của {success_count} đối tác!")
                            if error_count > 0:
                                st.warning(f"Bỏ qua {error_count} dòng do tài khoản không nằm trong danh sách cần gọi của Tháng {sel_month}/{sel_year}.")
                            st.rerun()
                            
                except Exception as e:
                    st.error(f"Đã xảy ra lỗi khi đọc file import: {str(e)}")

# ----------------- TAB 3: REPORTS & STATS -----------------
with tab3:
    st.header(f"Báo cáo thống kê hiệu quả cuộc gọi - Tháng {sel_month}/{sel_year}")
    
    report_data = db_helper.get_report_data(sel_year, sel_month)
    
    if not report_data:
        st.warning(f"Chưa có dữ liệu danh sách cuộc gọi hoặc lịch sử gọi nào cho Tháng {sel_month}/{sel_year}.")
    else:
        summary = report_data['summary']
        df_details = report_data['details']
        
        # 1. Dashboard Metrics
        st.subheader("📈 Chỉ số cuộc gọi trong tháng")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Tổng số cần gọi", f"{summary['total_users']} user")
        m_col2.metric("Gọi Thành công (Gọi được)", f"{summary['total_called_success']} user", 
                     delta=f"{(summary['total_called_success']/summary['total_users']*100):.1f}%" if summary['total_users'] > 0 else "0%")
        m_col3.metric("Gọi Thất bại (Không được)", f"{summary['total_called_failed']} user", 
                     delta=f"-{(summary['total_called_failed']/summary['total_users']*100):.1f}%" if summary['total_users'] > 0 else "0%", delta_color="inverse")
        m_col4.metric("Chưa liên hệ", f"{summary['total_not_called']} user")
        
        # 2. Charts
        st.subheader("📊 Biểu đồ trực quan")
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            # Pie Chart for Calling status distribution
            pie_data = pd.DataFrame({
                'Trạng thái': ['Gọi được (Thành công)', 'Gọi không được (Thất bại)', 'Chưa gọi'],
                'Số lượng': [summary['total_called_success'], summary['total_called_failed'], summary['total_not_called']]
            })
            # Filter zero rows
            pie_data = pie_data[pie_data['Số lượng'] > 0]
            if not pie_data.empty:
                fig_pie = px.pie(
                    pie_data, 
                    names='Trạng thái', 
                    values='Số lượng', 
                    title="Tỷ lệ trạng thái cuộc gọi",
                    color='Trạng thái',
                    color_discrete_map={
                        'Gọi được (Thành công)': '#2ca02c',
                        'Gọi không được (Thất bại)': '#d62728',
                        'Chưa gọi': '#ff7f0e'
                    }
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.text("Chưa có biểu đồ trạng thái cuộc gọi.")
                
        with chart_col2:
            # Bar Chart for target achievement (Only if day 5 final update is uploaded)
            # Check if we have final update data
            total_achieved = df_details['is_achieved'].sum()
            
            # Group by calling status and check target achievement
            ach_summary = df_details.groupby(['call_status_cat', 'is_achieved']).size().reset_index(name='Count')
            ach_summary['Kết quả doanh số'] = ach_summary['is_achieved'].map({1: 'Đạt doanh số', 0: 'Không đạt doanh số'})
            
            if total_achieved > 0:
                fig_bar = px.bar(
                    ach_summary,
                    x='call_status_cat',
                    y='Count',
                    color='Kết quả doanh số',
                    barmode='group',
                    title="Kết quả doanh số của các nhóm đối tác cuối tháng",
                    labels={'call_status_cat': 'Phân nhóm cuộc gọi', 'Count': 'Số đối tác'},
                    color_discrete_map={
                        'Đạt doanh số': '#1f77b4',
                        'Không đạt doanh số': '#7f7f7f'
                    }
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("💡 Báo cáo hiệu quả doanh số (đạt/không đạt) sẽ hiển thị sau khi bạn tải file cập nhật doanh số ngày 5 lên ở **Tab 4**.")
                
        # 3. Tables to download reports
        st.markdown("---")
        st.subheader("📋 Báo cáo danh sách chi tiết")
        
        # Categorized dataframes for download
        df_success_called = df_details[df_details['call_status_cat'] == 'Gọi được (Thành công)'].copy()
        df_failed_called = df_details[df_details['call_status_cat'] == 'Gọi không được (Thất bại)'].copy()
        
        # Clear columns for clean download
        download_cols = ['username', 'phone', 'danh_hieu_chay', 'sum_points', 'call_count', 'final_danh_hieu', 'final_sum_points', 'is_achieved']
        
        rep_col1, rep_col2 = st.columns(2)
        
        with rep_col1:
            st.markdown(f"**🟢 Danh sách đối tác Gọi Được (Thành công):** {len(df_success_called)} user")
            # Convert to displayable form
            df_success_disp = df_success_called.copy()
            df_success_disp['is_achieved'] = df_success_disp['is_achieved'].map({1: 'Đạt', 0: 'Không đạt'})
            st.dataframe(df_success_disp[['username', 'phone', 'danh_hieu_chay', 'is_achieved']].rename(columns={
                'username': 'Tài khoản', 'phone': 'Số điện thoại', 'danh_hieu_chay': 'Danh hiệu chạy', 'is_achieved': 'Đạt ngày 5'
            }), height=300)
            
            # Excel export button
            if not df_success_called.empty:
                out_success = io.BytesIO()
                df_success_called[download_cols].to_excel(out_success, index=False)
                st.download_button(
                    label="📥 Xuất file Excel gọi thành công",
                    data=out_success.getvalue(),
                    file_name=f"Bao_cao_Goi_Thanh_Cong_T{sel_month}_{sel_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
        with rep_col2:
            st.markdown(f"**🔴 Danh sách đối tác Gọi Không Được (Thất bại):** {len(df_failed_called)} user")
            df_failed_disp = df_failed_called.copy()
            df_failed_disp['is_achieved'] = df_failed_disp['is_achieved'].map({1: 'Đạt', 0: 'Không đạt'})
            st.dataframe(df_failed_disp[['username', 'phone', 'danh_hieu_chay', 'is_achieved']].rename(columns={
                'username': 'Tài khoản', 'phone': 'Số điện thoại', 'danh_hieu_chay': 'Danh hiệu chạy', 'is_achieved': 'Đạt ngày 5'
            }), height=300)
            
            # Excel export button
            if not df_failed_called.empty:
                out_failed = io.BytesIO()
                df_failed_called[download_cols].to_excel(out_failed, index=False)
                st.download_button(
                    label="📥 Xuất file Excel gọi thất bại",
                    data=out_failed.getvalue(),
                    file_name=f"Bao_cao_Goi_That_Bai_T{sel_month}_{sel_year}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        # 4. Final conversion report summary
        if df_details['is_achieved'].sum() > 0:
            st.markdown("---")
            st.subheader("📈 Thống kê chuyển đổi (Cuối ngày 5)")
            
            # Let's count conversion percentages
            success_ach_pct = (summary['called_success_achieved'] / summary['total_called_success'] * 100) if summary['total_called_success'] > 0 else 0.0
            failed_ach_pct = (summary['called_failed_achieved'] / summary['total_called_failed'] * 100) if summary['total_called_failed'] > 0 else 0.0
            not_called_ach_pct = (summary['not_called_achieved'] / summary['total_not_called'] * 100) if summary['total_not_called'] > 0 else 0.0
            
            col_c1, col_c2, col_c3 = st.columns(3)
            with col_c1:
                st.info(f"**Nhóm gọi thành công:**\n- Số lượng: {summary['total_called_success']} đối tác\n- Đạt doanh số: **{summary['called_success_achieved']}** ({success_ach_pct:.1f}%)\n- Không đạt: **{summary['called_success_not_achieved']}**")
            with col_c2:
                st.warning(f"**Nhóm gọi thất bại:**\n- Số lượng: {summary['total_called_failed']} đối tác\n- Đạt doanh số: **{summary['called_failed_achieved']}** ({failed_ach_pct:.1f}%)\n- Không đạt: **{summary['called_failed_not_achieved']}**")
            with col_c3:
                st.error(f"**Nhóm chưa gọi:**\n- Số lượng: {summary['total_not_called']} đối tác\n- Đạt doanh số: **{summary['not_called_achieved']}** ({not_called_ach_pct:.1f}%)\n- Không đạt: **{summary['not_called_not_achieved']}**")
                
            st.success(f"💡 Nhìn chung, việc gọi điện thành công giúp tăng tỷ lệ đạt doanh số từ **{failed_ach_pct:.1f}%** (nếu gọi thất bại) lên **{success_ach_pct:.1f}%**! (Chênh lệch: **{(success_ach_pct - failed_ach_pct):.1f}%**)")

# ----------------- TAB 4: DAY 5 SALES UPDATE -----------------
with tab4:
    st.header(f"Cập nhật Doanh số thực tế cuối ngày 5 - Tháng {sel_month}/{sel_year}")
    st.markdown("""
    Vào **cuối ngày 5**, sau khi đối tác đã kết thúc thời gian chạy doanh số, hãy tải file dữ liệu doanh số mới nhất từ hệ thống lên.
    Hệ thống sẽ đối chiếu và tự động cập nhật:
    - Điểm số thực tế (`final_sum_points`) của từng đối tác.
    - Danh hiệu đạt được thực tế (`final_danh_hieu`).
    - Xác định đối tác đã **Đạt doanh số** (chuyển đổi từ Chạy C1/C2/C3 lên Đạt C1/C2/C3 hoặc đạt điểm đích) để đưa vào báo cáo hiệu quả ở **Tab 3**.
    """)
    
    # Check if we have call list for this month
    df_calls_check = db_helper.get_call_list(sel_year, sel_month)
    
    if df_calls_check.empty:
        st.warning(f"Chưa có danh sách cuộc gọi cho Tháng {sel_month}/{sel_year} để cập nhật doanh số. Vui lòng tải dữ liệu thô đầu tháng ở **Tab 1** trước.")
    else:
        uploaded_day5_file = st.file_uploader("Tải lên file Excel doanh số cuối ngày 5:", type=["xlsx", "xls"], key="day5_file_uploader")
        
        if uploaded_day5_file is not None:
            try:
                df_day5 = pd.read_excel(uploaded_day5_file)
                st.success(f"Đã đọc file Excel ngày 5 thành công! Tổng dòng: {len(df_day5)}")
                
                with st.expander("Xem trước dữ liệu ngày 5"):
                    st.dataframe(df_day5.head())
                    
                if st.button("🚀 Bắt đầu Đối chiếu & Cập nhật Doanh số đạt", key="run_day5_btn"):
                    with st.spinner("Đang đối chiếu dữ liệu đối tác..."):
                        updated_rows = db_helper.update_final_sales(df_day5, sel_year, sel_month)
                        
                    st.success(f"Đã cập nhật kết quả thành công cho {updated_rows} đối tác nằm trong danh sách cuộc gọi!")
                    st.info("Vui lòng truy cập **Tab 3: Báo cáo Cuộc gọi & Hiệu quả** để xem thống kê chuyển đổi chi tiết.")
                    
                    # Refresh to show data updates
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Đã xảy ra lỗi khi xử lý file: {str(e)}")

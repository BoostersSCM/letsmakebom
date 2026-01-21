import streamlit as st
import pandas as pd
import mysql.connector
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- 1. 기본 설정 및 DB 연결 함수 ---
st.set_page_config(page_title="제품 사양서 시스템", layout="wide")

# MySQL 연결 함수 (캐싱하여 성능 최적화)
def get_db_connection():
    try:
        return mysql.connector.connect(**st.secrets["mysql"])
    except Exception as e:
        st.error(f"DB 연결 실패: {e}")
        return None

# 구글 시트 인증 및 연결 함수
def get_google_sheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"]) # secrets에서 정보 가져오기
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# --- 2. 세션 상태 관리 (데이터 불러오기/초기화 용) ---
if 'master_data' not in st.session_state:
    st.session_state.master_data = {}
if 'detail_data' not in st.session_state:
    st.session_state.detail_data = pd.DataFrame(columns=["분류", "하위분류", "재질", "규격", "단가", "협력사"])

# --- 3. 사이드바 & 데이터 불러오기 로직 ---
st.sidebar.title("🛠 기능 메뉴")
mode = st.sidebar.radio("작업 모드", ["신규 작성", "기존 DB 불러오기"])

if mode == "기존 DB 불러오기":
    search_term = st.sidebar.text_input("제품명 또는 품번 검색")
    if st.sidebar.button("검색"):
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            # 마스터 데이터 조회
            query = "SELECT * FROM product_master WHERE product_name_kr LIKE %s OR item_code LIKE %s"
            cursor.execute(query, (f"%{search_term}%", f"%{search_term}%"))
            result = cursor.fetchone()
            
            if result:
                st.session_state.master_data = result
                # 상세 데이터 조회
                query_detail = "SELECT classification as '분류', sub_classification as '하위분류', material as '재질', spec as '규격', unit_price as '단가', supplier as '협력사' FROM product_detail WHERE product_id = %s"
                cursor.execute(query_detail, (result['id'],))
                details = cursor.fetchall()
                st.session_state.detail_data = pd.DataFrame(details)
                st.sidebar.success(f"'{result['product_name_kr']}' 불러오기 성공!")
            else:
                st.sidebar.warning("검색 결과가 없습니다.")
            conn.close()

elif mode == "신규 작성":
    if st.sidebar.button("입력란 초기화"):
        st.session_state.master_data = {}
        st.session_state.detail_data = pd.DataFrame(columns=["분류", "하위분류", "재질", "규격", "단가", "협력사"])

# --- 4. 메인 입력 폼 (UI) ---
st.title("🧴 제품 사양서 관리 시스템")

# 마스터 데이터 편의를 위해 변수 할당 (없으면 빈 문자열)
md = st.session_state.master_data

st.subheader("1. 제품 기본 정보 (Master)")
with st.container():
    c1, c2, c3, c4 = st.columns(4)
    brand = c1.text_input("브랜드", value=md.get('brand', ''))
    line_name = c2.text_input("라인명", value=md.get('line_name', ''))
    distribution = c3.selectbox("유통", ["내수", "수출"], index=0 if md.get('distribution') != '수출' else 1)
    is_functional = c4.selectbox("기능성여부", ["N", "Y"], index=0 if md.get('is_functional') != 'Y' else 1)

    c1, c2, c3, c4 = st.columns(4)
    cat_large = c1.text_input("대분류", value=md.get('category_large', ''))
    cat_medium = c2.text_input("중분류", value=md.get('category_medium', ''))
    cat_small = c3.text_input("소분류", value=md.get('category_small', ''))
    manufacturer = c4.text_input("제조사", value=md.get('manufacturer', ''))

    c1, c2, c3, c4 = st.columns(4)
    prod_name_kr = c1.text_input("제품명(국문)", value=md.get('product_name_kr', ''))
    prod_name_en = c2.text_input("제품명(영문)", value=md.get('product_name_en', ''))
    item_code = c3.text_input("품번", value=md.get('item_code', ''))
    barcode = c4.text_input("바코드", value=md.get('barcode', ''))

    c1, c2, c3, c4 = st.columns(4)
    volume = c1.text_input("용량", value=md.get('volume', ''))
    price = c2.number_input("소비자가", value=int(md.get('price', 0)), step=100)
    ref_no = c3.text_input("Ref.No", value=md.get('ref_no', ''))
    
    st.markdown("**담당자 정보**")
    m1, m2, m3 = st.columns(3)
    mgr_plan = m1.text_input("담당(상품기획)", value=md.get('manager_plan', ''))
    mgr_design = m2.text_input("담당(디자인)", value=md.get('manager_design', ''))
    mgr_scm = m3.text_input("담당(SCM)", value=md.get('manager_scm', ''))

st.divider()

st.subheader("2. 구성품 상세 및 원가 (Detail)")

# Dropdown 옵션 정의
class_options = ["내용물", "포장재", "물류"]
sub_class_options = ["내용물", "임가공", "캡", "용기", "단상자", "지선대", "설명서", "봉합라벨", "인박스", "아웃박스", "직접입력"]

# Data Editor 설정
edited_df = st.data_editor(
    st.session_state.detail_data,
    column_config={
        "분류": st.column_config.SelectboxColumn(options=class_options, required=True, width="medium"),
        "하위분류": st.column_config.SelectboxColumn(options=sub_class_options, required=True, width="medium"),
        "재질": st.column_config.TextColumn(width="medium"),
        "규격": st.column_config.TextColumn(width="large"),
        "단가": st.column_config.NumberColumn(label="단가(VAT별도)", format="%d 원", min_value=0),
        "협력사": st.column_config.TextColumn(width="medium"),
    },
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True
)

# --- 5. 실시간 집계 ---
st.subheader("3. 원가 집계")
if not edited_df.empty:
    total_cost = edited_df["단가"].sum()
    
    # 분류별 합계
    grouped = edited_df.groupby("분류")["단가"].sum().reset_index()
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("총 원가 합계 (VAT별도)", f"{total_cost:,.0f} 원")
    with c2:
        st.dataframe(grouped, hide_index=True)
else:
    st.info("상세 내용을 입력하면 합계가 계산됩니다.")

st.divider()

# --- 6. 실행 버튼 및 로직 ---
col_btn1, col_btn2 = st.columns(2)

# [기능 1] DB 저장
with col_btn1:
    if st.button("💾 DB에 저장 (신규/업데이트)", type="primary"):
        if not prod_name_kr:
            st.error("제품명(국문)은 필수입니다.")
        else:
            conn = get_db_connection()
            if conn:
                try:
                    cursor = conn.cursor()
                    # 1. Master Table Insert
                    sql_master = """
                        INSERT INTO product_master 
                        (brand, line_name, distribution, category_large, category_medium, category_small, 
                        product_name_kr, product_name_en, item_code, barcode, volume, price, 
                        manager_plan, manager_design, manager_scm, manufacturer, ref_no, is_functional)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    val_master = (brand, line_name, distribution, cat_large, cat_medium, cat_small,
                                  prod_name_kr, prod_name_en, item_code, barcode, volume, price,
                                  mgr_plan, mgr_design, mgr_scm, manufacturer, ref_no, is_functional)
                    cursor.execute(sql_master, val_master)
                    new_id = cursor.lastrowid # 생성된 ID 가져오기

                    # 2. Detail Table Insert
                    if not edited_df.empty:
                        sql_detail = """
                            INSERT INTO product_detail 
                            (product_id, classification, sub_classification, material, spec, unit_price, supplier)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        val_detail = []
                        for _, row in edited_df.iterrows():
                            val_detail.append((new_id, row['분류'], row['하위분류'], row['재질'], row['규격'], row['단가'], row['협력사']))
                        
                        cursor.executemany(sql_detail, val_detail)
                    
                    conn.commit()
                    st.success(f"성공적으로 저장되었습니다! (ID: {new_id})")
                except Exception as e:
                    st.error(f"저장 중 오류 발생: {e}")
                finally:
                    conn.close()

# [기능 2] 구글 시트 생성
with col_btn2:
    if st.button("📑 구글 시트 제품사양서 생성"):
        try:
            client = get_google_sheet_client()
            # 1. 원본 템플릿 시트 ID (공유해주신 시트 ID 사용)
            SPREADSHEET_ID = '1ybfwTegu-hUKrUlGhLLkZMew2wSZcL95' 
            sh = client.open_by_key(SPREADSHEET_ID)
            
            # 2. 템플릿 시트 복사 (Template 시트 이름이 'Template'이라고 가정)
            # 만약 원본 시트에 'Template'이라는 이름의 시트가 없다면 이름을 확인하고 수정해주세요.
            try:
                template_worksheet = sh.worksheet("Template") 
            except:
                template_worksheet = sh.get_worksheet(0) # 없으면 첫번째 시트 사용

            new_worksheet = template_worksheet.duplicate()
            new_title = f"{prod_name_kr}_{datetime.now().strftime('%Y%m%d')}"
            new_worksheet.update_title(new_title)

            # 3. 데이터 매핑 (좌표는 실제 엑셀 양식을 보고 수정해야 합니다!!!)
            # 예시 좌표입니다. 실제 시트의 셀 위치를 확인하고 수정하세요.
            updates = [
                {'range': 'C3', 'values': [[brand]]},          # 브랜드
                {'range': 'C4', 'values': [[prod_name_kr]]},   # 제품명
                {'range': 'H3', 'values': [[item_code]]},      # 품번
                {'range': 'H4', 'values': [[barcode]]},        # 바코드
                {'range': 'C5', 'values': [[volume]]},         # 용량
                {'range': 'H5', 'values': [[price]]},          # 가격
                # ... 필요한 만큼 추가
            ]
            new_worksheet.batch_update(updates)
            
            # 상세 내용(BOM)을 특정 위치부터 뿌리기 (예: B10 셀부터 시작)
            if not edited_df.empty:
                # 데이터프레임 값을 리스트로 변환
                body_values = edited_df.values.tolist()
                # 범위 지정 업데이트 (시작 셀 B10)
                new_worksheet.update('B10', body_values)

            st.success(f"구글 시트 생성 완료! '{new_title}' 시트가 추가되었습니다.")
            st.markdown(f"[시트 바로가기](https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID})")

        except Exception as e:
            st.error(f"구글 시트 생성 실패: {e}")

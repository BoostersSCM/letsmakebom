import streamlit as st
import pandas as pd
import mysql.connector
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from streamlit_oauth import OAuth2Component
from datetime import datetime
import time

# ==========================================
# 0. 페이지 설정
# ==========================================
st.set_page_config(page_title="제품 사양서 관리 시스템", layout="wide", page_icon="🧴")

# ==========================================
# 1. 인증 및 유틸리티 함수
# ==========================================
def check_login():
    try:
        CLIENT_ID = st.secrets["google_oauth"]["client_id"]
        CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
        REDIRECT_URI = st.secrets["google_oauth"]["redirect_uri"]
    except KeyError:
        st.error("Secrets 설정 오류: [google_oauth] 정보가 없습니다.")
        return False

    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    REVOKE_TOKEN_URL = "https://oauth2.googleapis.com/revoke"

    oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZATION_URL, TOKEN_URL, TOKEN_URL, REVOKE_TOKEN_URL)

    if 'token' not in st.session_state:
        st.subheader("🔒 로그인이 필요합니다")
        result = oauth2.authorize_button(
            name="Google 계정으로 로그인",
            icon="https://www.google.com.tw/favicon.ico",
            redirect_uri=REDIRECT_URI,
            scope="openid email profile",
            key="google_auth",
            extras_params={"prompt": "consent", "access_type": "offline"},
            use_container_width=True,
        )
        
        if result and 'token' in result:
            st.session_state.token = result.get('token')
            st.session_state.user_email = result.get('id_token', {}).get('email', 'Unknown User')
            st.rerun()
        return False
    else:
        return True

def get_db_connection():
    try:
        conn = mysql.connector.connect(**st.secrets["mysql"])
        return conn
    except Exception as e:
        st.error(f"❌ DB 연결 실패: {e}")
        return None

def get_google_sheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# ==========================================
# 2. 메인 로직
# ==========================================
def main():
    # --- 사이드바 ---
    with st.sidebar:
        st.write(f"👤 접속: **{st.session_state.get('user_email', 'User')}**")
        if st.button("로그아웃"):
            del st.session_state.token
            st.rerun()
        
        st.divider()
        st.title("🛠 기능 메뉴")
        mode = st.radio("작업 모드", ["신규 작성", "기존 DB 불러오기"])

    # --- 데이터 초기화 ---
    if 'master_data' not in st.session_state:
        st.session_state.master_data = {}
    if 'detail_data' not in st.session_state:
        # 컬럼 순서 명확히 정의
        st.session_state.detail_data = pd.DataFrame(columns=["분류", "하위분류", "재질", "규격", "단가", "협력사"])

    # --- 모드별 동작 ---
    if mode == "기존 DB 불러오기":
        with st.sidebar:
            search_term = st.text_input("검색어 (제품명/품번)")
            if st.button("🔍 검색"):
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor(dictionary=True)
                    # Master 조회
                    query = "SELECT * FROM product_master WHERE product_name_kr LIKE %s OR item_code LIKE %s"
                    cursor.execute(query, (f"%{search_term}%", f"%{search_term}%"))
                    result = cursor.fetchone()
                    
                    if result:
                        st.session_state.master_data = result
                        # Detail 조회 (소수점 포함하여 가져옴)
                        query_detail = "SELECT classification as '분류', sub_classification as '하위분류', material as '재질', spec as '규격', unit_price as '단가', supplier as '협력사' FROM product_detail WHERE product_id = %s"
                        cursor.execute(query_detail, (result['id'],))
                        details = cursor.fetchall()
                        st.session_state.detail_data = pd.DataFrame(details)
                        st.success(f"'{result['product_name_kr']}' 로드 완료!")
                    else:
                        st.warning("검색 결과가 없습니다.")
                    conn.close()

    elif mode == "신규 작성":
        if st.sidebar.button("🧹 입력란 초기화"):
            st.session_state.master_data = {}
            st.session_state.detail_data = pd.DataFrame(columns=["분류", "하위분류", "재질", "규격", "단가", "협력사"])
            st.rerun()

    # --- 메인 입력 폼 ---
    st.title("🧴 제품 사양서 관리 시스템")
    md = st.session_state.master_data

    st.subheader("1. 제품 개요 (Master)")
    
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
        
        # [수정됨] 소비자가 소수점 2자리 입력 가능 (float, format="%.2f")
        price_val = md.get('price', 0.0)
        price = c2.number_input("소비자가", value=float(price_val) if price_val else 0.0, step=0.1, format="%.2f")
        
        ref_no = c3.text_input("Ref.No", value=md.get('ref_no', ''))
        
        st.markdown("**담당자 정보**")
        m1, m2, m3 = st.columns(3)
        mgr_plan = m1.text_input("담당(상품기획)", value=md.get('manager_plan', ''))
        mgr_design = m2.text_input("담당(디자인)", value=md.get('manager_design', ''))
        mgr_scm = m3.text_input("담당(SCM)", value=md.get('manager_scm', st.session_state.get('user_email', '')))

    st.divider()

    st.subheader("2. 구성품 상세 및 원가 (BOM)")

    class_options = ["내용물", "포장재", "물류"]
    sub_class_options = ["내용물", "임가공", "캡", "용기", "단상자", "지선대", "설명서", "봉합라벨", "인박스", "아웃박스", "직접입력"]

    # [수정됨] Data Editor: 단가도 소수점 표현 가능하도록 수정
    edited_df = st.data_editor(
        st.session_state.detail_data,
        column_config={
            "분류": st.column_config.SelectboxColumn(options=class_options, required=True),
            "하위분류": st.column_config.SelectboxColumn(options=sub_class_options, required=True),
            "단가": st.column_config.NumberColumn(label="단가(VAT별도)", format="%.2f", min_value=0.0),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True
    )

    if not edited_df.empty:
        total_cost = pd.to_numeric(edited_df["단가"]).sum()
        grouped = edited_df.groupby("분류")["단가"].sum().reset_index()
        
        c1, c2 = st.columns([1, 2])
        c1.metric("총 원가 합계 (VAT별도)", f"{total_cost:,.2f} 원") # 소수점 표현
        c2.dataframe(grouped, hide_index=True, use_container_width=True)

    st.divider()

    # --- 실행 버튼 ---
    b1, b2 = st.columns(2)

    with b1:
        if st.button("💾 DB에 저장하기", type="primary", use_container_width=True):
            if not prod_name_kr:
                st.error("제품명(국문)은 필수 입력 사항입니다.")
            else:
                conn = get_db_connection()
                if conn:
                    try:
                        cursor = conn.cursor()
                        # Master Insert
                        sql_master = """
                            INSERT INTO product_master 
                            (brand, line_name, distribution, category_large, category_medium, category_small, 
                            product_name_kr, product_name_en, item_code, barcode, volume, price, 
                            manager_plan, manager_design, manager_scm, manufacturer, ref_no, is_functional)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        # price는 float 형태로 들어감
                        val_master = (brand, line_name, distribution, cat_large, cat_medium, cat_small,
                                      prod_name_kr, prod_name_en, item_code, barcode, volume, price,
                                      mgr_plan, mgr_design, mgr_scm, manufacturer, ref_no, is_functional)
                        
                        cursor.execute(sql_master, val_master)
                        new_id = cursor.lastrowid

                        # Detail Insert
                        if not edited_df.empty:
                            sql_detail = "INSERT INTO product_detail (product_id, classification, sub_classification, material, spec, unit_price, supplier) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                            val_detail = []
                            for _, row in edited_df.iterrows():
                                val_detail.append((new_id, row['분류'], row['하위분류'], row['재질'], row['규격'], float(row['단가']), row['협력사']))
                            cursor.executemany(sql_detail, val_detail)
                        
                        conn.commit()
                        st.success(f"DB 저장 완료! (ID: {new_id})")
                        time.sleep(1)
                    except Exception as e:
                        st.error(f"DB 저장 오류: {e}")
                    finally:
                        conn.close()

    with b2:
        if st.button("📑 구글 시트 생성하기", use_container_width=True):
            try:
                client = get_google_sheet_client()
                SPREADSHEET_ID = '1ybfwTegu-hUKrUlGhLLkZMew2wSZcL95' 
                sh = client.open_by_key(SPREADSHEET_ID)
                
                # 1. 템플릿 시트 찾기
                try:
                    template_worksheet = sh.worksheet("Template")
                except:
                    # Template 시트가 없으면 첫 번째 시트를 사용
                    template_worksheet = sh.get_worksheet(0)

                # ====================================================
                # [수정된 부분] duplicate() 대신 copy_to() 사용
                # ====================================================
                # 시트를 자기 자신(SPREADSHEET_ID)에게 복사합니다.
                copied_sheet_dict = template_worksheet.copy_to(SPREADSHEET_ID)
                
                # 복사된 시트의 ID를 이용해 워크시트 객체를 다시 가져옵니다.
                new_sheet_id = copied_sheet_dict['sheetId']
                new_worksheet = sh.get_worksheet_by_id(new_sheet_id)
                
                # 이름 변경
                new_title = f"{prod_name_kr}_{datetime.now().strftime('%m%d_%H%M')}"
                new_worksheet.update_title(new_title)
                # ====================================================

                # 2. 데이터 매핑 (Master Data)
                updates = [
                    {'range': 'C3', 'values': [[brand]]},          
                    {'range': 'C4', 'values': [[prod_name_kr]]},   
                    {'range': 'H3', 'values': [[item_code]]},      
                    {'range': 'H4', 'values': [[barcode]]},
                    {'range': 'C5', 'values': [[volume]]},         
                    {'range': 'H5', 'values': [[price]]},
                ]
                new_worksheet.batch_update(updates)

                # 3. 상세 정보 (Detail Data) 순차 기입
                if not edited_df.empty:
                    final_df = edited_df[["분류", "하위분류", "재질", "규격", "단가", "협력사"]]
                    # 헤더 포함하여 리스트로 변환
                    data_with_headers = [final_df.columns.values.tolist()] + final_df.fillna("").values.tolist()
                    # B10 셀부터 업데이트
                    new_worksheet.update('B10', data_with_headers)

                st.success(f"시트 생성 완료! : {new_title}")
                st.markdown(f"👉 [구글 시트로 이동하기](https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID})")
            
            except Exception as e:
                st.error(f"구글 시트 생성 실패: {e}")

if __name__ == "__main__":
    if check_login():
        main()

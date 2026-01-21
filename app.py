import streamlit as st
import pandas as pd
# import mysql.connector # 추후 DB 연결 시 활성화
# import gspread # 추후 구글 시트 연동 시 활성화

# --- 페이지 설정 ---
st.set_page_config(page_title="제품 사양서 관리 시스템", layout="wide")

st.title("🧴 제품 사양서 생성 및 DB 관리 시스템")

# --- 사이드바: 모드 선택 (신규 등록 vs 불러오기) ---
mode = st.sidebar.radio("작업 선택", ["신규 등록", "DB에서 불러오기/수정"])

# 데이터 초기화 (신규 등록 시 빈 값, 불러오기 시 DB 값)
if mode == "신규 등록":
    st.header("📝 신규 제품 사양서 등록")
    # 기본값 설정 로직...
else:
    st.header("📂 기존 데이터 불러오기")
    search_query = st.text_input("제품명 또는 품번 검색")
    # DB 조회 로직 및 데이터 로딩...

# --- 1. 개요 정보 입력 (Form) ---
st.subheader("1. 제품 개요 (Master Info)")

col1, col2, col3 = st.columns(3)
with col1:
    brand = st.text_input("브랜드", placeholder="예: 이퀄베리")
    line_name = st.text_input("라인명")
    distribution = st.selectbox("유통", ["내수", "수출", "공통"])
    
with col2:
    cat_large = st.text_input("대분류")
    cat_medium = st.text_input("중분류")
    cat_small = st.text_input("소분류")

with col3:
    prod_name_kr = st.text_input("제품명(국문)")
    prod_name_en = st.text_input("제품명(영문)")
    functionality = st.checkbox("기능성 여부")

# ... 나머지 필드들도 비슷하게 배치 (품번, 바코드, 담당자 등)

# --- 2. 상세 분류 및 원가 입력 (Data Editor 활용) ---
st.subheader("2. 구성품 및 원가 상세 (Detail Info)")
st.info("아래 표에 내용을 입력하세요. 행을 추가하여 새로운 포장재나 내용을 기입할 수 있습니다.")

# 드롭다운 옵션 정의
class_options = ["내용물", "포장재", "물류"]
sub_class_map = {
    "내용물": ["내용물", "임가공"],
    "포장재": ["캡", "용기", "단상자", "지선대", "설명서", "봉합라벨"],
    "물류": ["인박스", "아웃박스"]
}

# 기본 데이터 프레임 구조 생성
df_schema = {
    "분류": ["내용물", "포장재"], # 예시 초기값
    "하위분류": ["내용물", "용기"],
    "재질": ["", ""],
    "규격": ["", ""],
    "단가(VAT별도)": [0, 0],
    "협력사": ["", ""]
}
df = pd.DataFrame(df_schema)

# Streamlit Data Editor로 편집 가능한 테이블 생성
edited_df = st.data_editor(
    df,
    column_config={
        "분류": st.column_config.SelectboxColumn(options=class_options, required=True),
        "단가(VAT별도)": st.column_config.NumberColumn(format="%d 원"),
    },
    num_rows="dynamic", # 행 추가/삭제 가능
    use_container_width=True
)

# --- 3. 합계 계산 (실시간 반영) ---
if not edited_df.empty:
    total_cost = edited_df["단가(VAT별도)"].sum()
    st.metric(label="총 원가 합계 (VAT별도)", value=f"{total_cost:,.0f} 원")
    
    # 그룹별 합계 계산 (내용물 합계, 포장재 합계 등)
    grouped = edited_df.groupby("분류")["단가(VAT별도)"].sum()
    st.write("분류별 합계:", grouped)

# --- 4. 실행 버튼 ---
st.divider()
col_btn1, col_btn2 = st.columns(2)

with col_btn1:
    if st.button("💾 DB에 저장하기 (Save)"):
        # 1. MySQL 연결
        # 2. product_master 테이블 insert
        # 3. 생성된 id를 받아 product_detail 테이블 insert
        st.success("DB 저장 완료!")

with col_btn2:
    if st.button("📑 구글 시트 생성 (Generate Sheet)"):
        # 1. 빈 템플릿 시트 로드
        # 2. 입력된 변수들을 시트 특정 셀에 매핑하여 쓰기
        st.success("구글 시트 생성 완료! (링크 이동)")

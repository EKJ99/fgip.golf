import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# --- 1. 페이지 설정 및 커스텀 CSS (HTML 느낌 내기) ---
st.set_page_config(page_title="스크린골프 예약 시스템", layout="wide", page_icon="⛳")

# HTML/Bootstrap 스타일 적용 (박스 디자인, 테이블 색상 등)
st.markdown("""
<style>
    /* 룸 상태 박스 스타일 */
    .room-box {
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        color: white;
        font-weight: bold;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .status-available { background-color: #28a745; } /* 초록 */
    .status-occupied { background-color: #dc3545; }  /* 빨강 */
    .status-closed { background-color: #6c757d; }    /* 회색 */
    
    /* 테이블 스타일 */
    .stDataFrame { width: 100%; }
    
    /* 텍스트 스타일 */
    h3 { text-align: center; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 2. DB 연결 및 데이터 로드 ---
def get_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # secrets가 딕셔너리가 아닌 경우를 대비해 변환
        secrets_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(secrets_dict, scope)
        client = gspread.authorize(creds)
        # *** 중요: .sheet1 대신 .get_worksheet(0) 사용 ***
        return client.open("ScreenGolf_DB").get_worksheet(0)
    except Exception as e:
        st.error(f"구글 시트 연결 오류: {e}")
        return None

def load_data():
    sheet = get_sheet()
    if sheet:
        data = sheet.get_all_values() # 모든 데이터를 리스트로 가져옴 (Display Values)
        if len(data) < 2:
            return pd.DataFrame(columns=['id', 'room', 'date', 'startTime', 'duration', 'headCount', 'mainName', 'allNames', 'password', 'status', 'timestamp'])
        
        # 헤더와 데이터 분리
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        return df
    return pd.DataFrame()

# --- 3. 로직 함수들 ---
ROOMS = ["Room 1", "Room 2", "Room 3", "Room 4", "Room 5"]
ROOM_DESC = {
    "Room 1": "일반 룸",
    "Room 2": "일반 룸",
    "Room 3": "스윙분석기/GDR+",
    "Room 4": "양손잡이용",
    "Room 5": "개인 훈련용"
}

def get_korea_time():
    # Streamlit Cloud(UTC) -> KST 변환
    return datetime.utcnow() + timedelta(hours=9)

def get_operating_hours_range(date_obj):
    weekday = date_obj.weekday() # 0:월 ~ 6:일
    if weekday == 3:   # 목요일 (17~22)
        return range(17, 22)
    elif weekday == 4: # 금요일 (06~22)
        return range(6, 22)
    else:              # 평일+주말 (19~22)
        return range(19, 22)

# --- 4. 메인 UI 구성 ---

st.title("⛳ 스크린골프 예약 시스템")

# 데이터 로드
df = load_data()
if not df.empty:
    # 취소된 예약 제외
    df = df[df['status'] != 'cancelled']

# 현재 시간 설정
now = get_korea_time()
today_str = now.strftime("%Y-%m-%d")
current_hour = now.hour

# [섹션 A] 실시간 룸 현황판 (HTML 박스 스타일)
st.subheader("실시간 룸 사용 현황")
cols = st.columns(5)

for i, room in enumerate(ROOMS):
    # 상태 결정 로직
    status_class = "status-available"
    status_text = "사용 가능"
    sub_text = ROOM_DESC[room]
    
    # 1. 운영시간 체크
    op_range = get_operating_hours_range(now)
    if current_hour not in op_range:
        status_class = "status-closed"
        status_text = "운영 시간 아님"
    else:
        # 2. 예약 확인
        if not df.empty:
            # 해당 룸, 오늘 날짜 예약 필터링
            active = df[ (df['room'] == room) & (df['date'] == today_str) ]
            for _, row in active.iterrows():
                start = int(str(row['startTime']).split(':')[0])
                dur = int(row['duration'])
                if start <= current_hour < start + dur:
                    status_class = "status-occupied"
                    status_text = f"사용 중\n({row['mainName']})"
                    break
    
    # HTML 렌더링
    cols[i].markdown(f"""
        <div class="room-box {status_class}">
            <div style="font-size: 1.2em;">{room}</div>
            <div style="margin-top: 5px;">{status_text}</div>
            <div style="font-size: 0.8em; opacity: 0.8; margin-top: 5px;">{sub_text}</div>
        </div>
    """, unsafe_allow_html=True)


# [섹션 B] 버튼 그룹 (우측 정렬 느낌)
col_spacer, col_btn1, col_btn2 = st.columns([6, 1.5, 1.5])

# --- 모달(Dialog) 기능 정의 ---

@st.dialog("새 예약하기")
def show_booking_modal():
    # 1. 날짜 선택 (오늘~7일후)
    date_options = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    date_labels = [(now + timedelta(days=i)).strftime("%m월 %d일 (%a)") for i in range(7)]
    
    # 딕셔너리로 매핑하여 라벨 표시
    date_map = dict(zip(date_labels, date_options))
    selected_label = st.selectbox("날짜 선택", date_labels)
    selected_date = date_map[selected_label]
    
    # 2. 룸 선택
    selected_room = st.selectbox("룸 선택", ROOMS)
    st.caption(f"※ {ROOM_DESC[selected_room]}")
    
    # 3. 인원 및 이름
    col_h1, col_h2 = st.columns(2)
    head_count = col_h1.selectbox("인원", ["1인", "2인", "3인 이상"])
    
    # 인원에 따른 이름 입력칸 동적 생성
    names = []
    names.append(st.text_input("참가자 1 이름 (대표자)", placeholder="필수"))
    
    if head_count == "2인":
        names.append(st.text_input("참가자 2 이름", placeholder="필수"))
        max_duration_limit = 2
    elif head_count == "3인 이상":
        names.append(st.text_input("참가자 2 이름", placeholder="필수"))
        names.append(st.text_input("참가자 3 이름", placeholder="필수"))
        extra_count = st.number_input("추가 인원 (4번째부터)", min_value=0, max_value=10, step=1)
        for i in range(extra_count):
            names.append(st.text_input(f"참가자 {i+4} 이름"))
        max_duration_limit = 3
    else: # 1인
        max_duration_limit = 1
        
    # 4. 이용 시간 (인원 제한 적용)
    duration_opts = list(range(1, max_duration_limit + 1))
    duration = st.selectbox("이용 시간", duration_opts, format_func=lambda x: f"{x}시간")
    
    # 5. 시작 시간 (스마트 필터링: 22시 마감)
    target_dt = datetime.strptime(selected_date, "%Y-%m-%d")
    op_range = get_operating_hours_range(target_dt) # 예: 19, 20, 21
    
    # 로직: 시작시간 + 이용시간 <= 22
    valid_starts = []
    for h in op_range:
        if h + duration <= 22:
            valid_starts.append(f"{h}:00")
            
    if not valid_starts:
        st.error("선택한 조건으로는 예약 가능한 시간이 없습니다. (22:00 마감)")
        start_time = None
    else:
        start_time = st.selectbox("시작 시간", valid_starts)
        
    # 6. 비밀번호
    password = st.text_input("비밀번호 (숫자 4자리)", type="password", max_chars=4)
    password_confirm = st.text_input("비밀번호 확인", type="password", max_chars=4)
    
    if st.button("예약 확정", type="primary", use_container_width=True):
        # 유효성 검사
        if not all(n.strip() for n in names):
            st.error("모든 참가자의 이름을 입력해주세요.")
            return
        if password != password_confirm or len(password) != 4:
            st.error("비밀번호가 일치하지 않거나 4자리가 아닙니다.")
            return
        if not start_time:
            return

        # 중복 검사
        s_h = int(start_time.split(':')[0])
        e_h = s_h + duration
        is_dup = False
        
        if not df.empty:
            # 같은 날, 같은 룸
            check_df = df[(df['date'] == selected_date) & (df['room'] == selected_room)]
            for _, row in check_df.iterrows():
                ex_s = int(str(row['startTime']).split(':')[0])
                ex_e = ex_s + int(row['duration'])
                # 겹침 공식
                if s_h < ex_e and e_h > ex_s:
                    is_dup = True
                    break
        
        if is_dup:
            st.error("이미 예약된 시간입니다. 다른 시간을 선택해주세요.")
            return
            
        # 저장
        try:
            sheet = get_sheet()
            new_row = [
                str(int(time.time()*1000)), # Unique ID
                selected_room,
                selected_date,
                start_time,
                duration,
                len(names),
                names[0],
                ",".join(names),
                password,
                "reserved",
                str(datetime.now())
            ]
            sheet.append_row(new_row)
            st.success("예약이 완료되었습니다!")
            time.sleep(1)
            st.rerun() # 새로고침
        except Exception as e:
            st.error(f"저장 중 오류 발생: {e}")

@st.dialog("예약 취소 / 변경")
def show_cancel_modal():
    st.info("예약 변경은 '취소 후 재예약' 방식입니다.")
    
    # 내 예약 검색
    search_name = st.text_input("예약자 이름 검색")
    
    if search_name:
        if df.empty:
            st.warning("예약 데이터가 없습니다.")
        else:
            my_list = df[ (df['mainName'] == search_name) & (df['date'] >= today_str) ]
            
            if my_list.empty:
                st.warning("예정된 예약 내역이 없습니다.")
            else:
                for idx, row in my_list.iterrows():
                    with st.container(border=True):
                        col_info, col_act = st.columns([3, 1])
                        with col_info:
                            st.markdown(f"**{row['date']} {row['startTime']}**")
                            st.caption(f"{row['room']} | {row['duration']}시간 | {row['headCount']}명")
                        with col_act:
                            if st.button("취소/변경", key=f"btn_{row['id']}"):
                                st.session_state[f"cancel_mode_{row['id']}"] = True
                        
                        # 비밀번호 입력창 (버튼 누르면 나옴)
                        if st.session_state.get(f"cancel_mode_{row['id']}"):
                            pw_input = st.text_input("비밀번호 입력", type="password", key=f"pw_{row['id']}")
                            if st.button("확인 (삭제 실행)", key=f"del_{row['id']}"):
                                if str(pw_input) == str(row['password']):
                                    # 삭제 로직
                                    sheet = get_sheet()
                                    try:
                                        # ID로 행 찾기 (ID는 첫번째 열, 즉 A열)
                                        cell = sheet.find(str(row['id']))
                                        # 상태값(J열, 10번째)을 cancelled로 변경
                                        sheet.update_cell(cell.row, 10, "cancelled")
                                        st.success("취소되었습니다.")
                                        time.sleep(1)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"삭제 오류: {e}")
                                else:
                                    st.error("비밀번호 불일치")


# 버튼 배치 및 동작
with col_btn1:
    if st.button("예약 취소/변경"):
        show_cancel_modal()

with col_btn2:
    if st.button("새 예약하기", type="primary"):
        show_booking_modal()


# [섹션 C] 주간 예약 현황표
st.divider()
st.subheader("주간 예약 현황")

week_days = [now + timedelta(days=i) for i in range(7)]
tab_titles = [d.strftime("%m/%d (%a)") for d in week_days]
tabs = st.tabs(tab_titles)

for i, day_tab in enumerate(tabs):
    with day_tab:
        target_d = week_days[i]
        target_str = target_d.strftime("%Y-%m-%d")
        op_range = get_operating_hours_range(target_d)
        
        # 테이블 데이터 생성 (행: Room, 열: 시간)
        # 1. 빈 테이블 생성
        time_slots = [f"{h}:00" for h in op_range]
        schedule_data = []
        
        for room in ROOMS:
            row_data = {"Room": room}
            for ts in time_slots:
                row_data[ts] = "" # 기본 빈칸
            schedule_data.append(row_data)
            
        # 2. 예약 채우기
        if not df.empty:
            day_books = df[ (df['date'] == target_str) ]
            for _, booking in day_books.iterrows():
                r_name = booking['room']
                s_time = int(booking['startTime'].split(':')[0])
                dur = int(booking['duration'])
                main_name = booking['mainName']
                
                # 예약된 시간 칸 채우기
                for h in range(s_time, s_time + dur):
                    col_name = f"{h}:00"
                    if col_name in row_data: # 운영시간 내라면
                         # 리스트에서 해당 룸의 행 찾기
                         for r_idx, r_data in enumerate(schedule_data):
                             if r_data["Room"] == r_name:
                                 schedule_data[r_idx][col_name] = f"{main_name}"

        # 3. DataFrame 변환 및 표시
        sch_df = pd.DataFrame(schedule_data)
        sch_df.set_index("Room", inplace=True)
        
        # 스타일링 (예약된 칸 색상 변경은 Streamlit 기본 기능으로는 제한적이나, 데이터프레임 하이라이트 활용)
        def highlight_cells(val):
            return 'background-color: #ffc107; color: black; font-weight: bold;' if val else ''
            
        st.dataframe(sch_df.style.map(highlight_cells), use_container_width=True, height=250)

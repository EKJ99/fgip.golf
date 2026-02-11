import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# --- 1. 페이지 설정 및 모바일 최적화 CSS ---
st.set_page_config(page_title="스크린골프 예약", layout="wide", page_icon="⛳")

st.markdown("""
<style>
    /* 1. 상태 박스: 모바일용 컴팩트 스타일 */
    .room-box {
        border-radius: 8px;
        padding: 8px 4px; /* 패딩을 줄임 */
        text-align: center;
        color: white;
        margin-bottom: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        font-size: 0.85rem; /* 폰트 사이즈 줄임 */
    }
    .room-title {
        font-weight: bold;
        font-size: 1rem;
        margin-bottom: 2px;
    }
    .room-desc {
        font-size: 0.7rem;
        opacity: 0.9;
        white-space: nowrap; /* 줄바꿈 방지 */
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* 상태별 색상 */
    .status-available { background-color: #28a745; }
    .status-occupied { background-color: #dc3545; }
    .status-closed { background-color: #6c757d; }
    
    /* 2. 메인 버튼 크기 키우기 (모바일 터치 용이) */
    .stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 3em; /* 버튼 높이 증가 */
        font-weight: bold;
    }
    
    /* 테이블 스타일 */
    .stDataFrame { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- 2. DB 연결 및 데이터 로드 (이전과 동일) ---
def get_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        secrets_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(secrets_dict, scope)
        client = gspread.authorize(creds)
        return client.open("ScreenGolf_DB").get_worksheet(0)
    except Exception as e:
        st.error(f"구글 시트 연결 오류: {e}")
        return None

def load_data():
    sheet = get_sheet()
    if sheet:
        data = sheet.get_all_values()
        if len(data) < 2:
            return pd.DataFrame(columns=['id', 'room', 'date', 'startTime', 'duration', 'headCount', 'mainName', 'allNames', 'password', 'status', 'timestamp'])
        headers = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=headers)
        return df
    return pd.DataFrame()

# --- 3. 로직 함수들 ---
ROOMS = ["Room 1", "Room 2", "Room 3", "Room 4", "Room 5"]
ROOM_DESC = {
    "Room 1": "일반",
    "Room 2": "일반",
    "Room 3": "스윙/GDR+",
    "Room 4": "양손잡이",
    "Room 5": "개인훈련"
}
DEFAULT_OPT = "-선택해주세요-"

def get_korea_time():
    return datetime.utcnow() + timedelta(hours=9)

def get_operating_hours_range(date_obj):
    weekday = date_obj.weekday()
    if weekday == 3: return range(17, 22)   # 목
    elif weekday == 4: return range(6, 22) # 금
    else: return range(19, 22)             # 그외

# --- 4. 메인 UI 구성 ---

st.title("⛳ 스크린골프 예약")

df = load_data()
if not df.empty:
    df = df[df['status'] != 'cancelled']

now = get_korea_time()
today_str = now.strftime("%Y-%m-%d")
current_hour = now.hour

# [섹션 A] 실시간 룸 현황판 (컴팩트 버전)
# 모바일에서 한 줄에 5개는 좁으므로, Streamlit의 cols 기능을 그대로 쓰되 CSS로 작게 만듦
cols = st.columns(5)

for i, room in enumerate(ROOMS):
    status_class = "status-available"
    status_text = "가능"
    
    op_range = get_operating_hours_range(now)
    if current_hour not in op_range:
        status_class = "status-closed"
        status_text = "마감"
    else:
        if not df.empty:
            active = df[ (df['room'] == room) & (df['date'] == today_str) ]
            for _, row in active.iterrows():
                start = int(str(row['startTime']).split(':')[0])
                dur = int(row['duration'])
                if start <= current_hour < start + dur:
                    status_class = "status-occupied"
                    status_text = f"{row['mainName']}" # 이름만 표시 (공간절약)
                    break
    
    cols[i].markdown(f"""
        <div class="room-box {status_class}">
            <div class="room-title">{room.replace('Room ', 'R')}</div>
            <div>{status_text}</div>
            <div class="room-desc">{ROOM_DESC[room]}</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# [섹션 B] 예약/취소 버튼 (크고 넓게)
# use_container_width=True를 사용하여 모바일에서 꽉 차게 표시
col_b1, col_b2 = st.columns(2)

# --- 모달(Dialog) 정의 ---

@st.dialog("새 예약하기")
def show_booking_modal():
    # 1. 날짜 선택
    date_labels = [DEFAULT_OPT] + [(now + timedelta(days=i)).strftime("%m월 %d일 (%a)") for i in range(7)]
    date_values = [None] + [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    date_map = dict(zip(date_labels, date_values))
    
    sel_label = st.selectbox("날짜", date_labels)
    
    # 날짜 미선택 시 하위 메뉴 숨김 또는 안내
    if sel_label == DEFAULT_OPT:
        st.info("먼저 날짜를 선택해주세요.")
        st.stop()
        
    selected_date = date_map[sel_label]

    # 2. 룸 선택
    room_opts = [DEFAULT_OPT] + ROOMS
    selected_room = st.selectbox("룸", room_opts)
    
    if selected_room == DEFAULT_OPT:
        st.stop()
    st.caption(f"※ {ROOM_DESC[selected_room]}")

    # 3. 인원 선택
    hc_opts = [DEFAULT_OPT, "1인", "2인", "3인 이상"]
    head_count = st.selectbox("인원", hc_opts)
    
    if head_count == DEFAULT_OPT:
        st.stop()

    # 인원에 따른 이름 입력
    names = []
    names.append(st.text_input("참가자 1 (대표자)", placeholder="필수 입력"))
    
    max_duration_limit = 1
    if head_count == "2인":
        names.append(st.text_input("참가자 2", placeholder="필수 입력"))
        max_duration_limit = 2
    elif head_count == "3인 이상":
        names.append(st.text_input("참가자 2", placeholder="필수 입력"))
        names.append(st.text_input("참가자 3", placeholder="필수 입력"))
        extra = st.number_input("추가 인원", 0, 10, 0)
        for k in range(extra):
            names.append(st.text_input(f"참가자 {k+4}"))
        max_duration_limit = 3

    # 4. 이용 시간
    # 옵션 생성 (예: ["-선택-", 1시간, 2시간...])
    dur_opts = [DEFAULT_OPT] + list(range(1, max_duration_limit + 1))
    duration_sel = st.selectbox("이용 시간", dur_opts, format_func=lambda x: f"{x}시간" if x != DEFAULT_OPT else x)
    
    if duration_sel == DEFAULT_OPT:
        st.stop()

    duration = int(duration_sel)

    # 5. 시작 시간
    target_dt = datetime.strptime(selected_date, "%Y-%m-%d")
    op_range = get_operating_hours_range(target_dt)
    
    valid_starts = [DEFAULT_OPT]
    for h in op_range:
        if h + duration <= 22:
            valid_starts.append(f"{h}:00")
            
    if len(valid_starts) == 1: # 옵션이 기본값밖에 없으면
        st.error("가능한 시간이 없습니다 (22시 마감)")
        st.stop()
        
    start_time = st.selectbox("시작 시간", valid_starts)
    
    if start_time == DEFAULT_OPT:
        st.stop()

    # 6. 비밀번호 및 확정
    password = st.text_input("비밀번호 (숫자 4자리)", type="password", max_chars=4)
    
    # 버튼을 꽉 차게 (use_container_width)
    if st.button("예약 확정", type="primary", use_container_width=True):
        if not all(n.strip() for n in names):
            st.error("이름을 모두 입력해주세요.")
            return
        if len(password) != 4 or not password.isdigit():
            st.error("비밀번호는 숫자 4자리여야 합니다.")
            return

        # 중복 검사
        s_h = int(start_time.split(':')[0])
        e_h = s_h + duration
        is_dup = False
        
        if not df.empty:
            check = df[(df['date'] == selected_date) & (df['room'] == selected_room)]
            for _, row in check.iterrows():
                ex_s = int(str(row['startTime']).split(':')[0])
                ex_e = ex_s + int(row['duration'])
                if s_h < ex_e and e_h > ex_s:
                    is_dup = True
                    break
        
        if is_dup:
            st.error("이미 예약된 시간입니다.")
            return
            
        try:
            sheet = get_sheet()
            new_row = [
                str(int(time.time()*1000)),
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
            st.success("예약 성공!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"오류: {e}")

@st.dialog("예약 취소 / 변경")
def show_cancel_modal():
    st.caption("예약 변경은 취소 후 다시 예약해주세요.")
    name = st.text_input("예약자 이름 검색")
    
    if name:
        if df.empty:
            st.warning("데이터 없음")
        else:
            # 날짜 내림차순 정렬 (최신순)
            my_list = df[ (df['mainName'] == name) & (df['date'] >= today_str) ].sort_values(by='date', ascending=True)
            
            if my_list.empty:
                st.info("예약 내역이 없습니다.")
            else:
                for _, row in my_list.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['date']} {row['startTime']}**")
                        st.text(f"{row['room']} ({row['duration']}시간)")
                        
                        # 취소 버튼도 꽉 차게
                        if st.button("취소/변경", key=f"btn_{row['id']}", use_container_width=True):
                            st.session_state[f"cancel_{row['id']}"] = True
                        
                        if st.session_state.get(f"cancel_{row['id']}"):
                            pw = st.text_input("비밀번호", type="password", key=f"pw_{row['id']}", max_chars=4)
                            if st.button("삭제 확인", key=f"del_{row['id']}", type="primary", use_container_width=True):
                                if str(pw) == str(row['password']):
                                    sheet = get_sheet()
                                    try:
                                        cell = sheet.find(str(row['id']))
                                        sheet.update_cell(cell.row, 10, "cancelled")
                                        st.success("취소됨")
                                        time.sleep(1)
                                        st.rerun()
                                    except:
                                        st.error("오류 발생")
                                else:
                                    st.error("비밀번호 불일치")

# 버튼 배치 (모바일 친화적)
with col_b1:
    if st.button("예약 취소 / 변경", use_container_width=True):
        show_cancel_modal()

with col_b2:
    if st.button("새 예약하기", type="primary", use_container_width=True):
        show_booking_modal()


# [섹션 C] 주간 시간표
st.markdown("---")
st.subheader("주간 예약 현황")

week_days = [now + timedelta(days=i) for i in range(7)]
tabs = st.tabs([d.strftime("%d(%a)") for d in week_days]) # 탭 이름도 짧게

for i, t in enumerate(tabs):
    with t:
        target_d = week_days[i]
        t_str = target_d.strftime("%Y-%m-%d")
        op_range = get_operating_hours_range(target_d)
        
        # 데이터프레임 생성
        data_rows = []
        for r in ROOMS:
            row = {"Room": r.replace("Room ", "R")} # 이름 줄임
            for h in op_range:
                row[f"{h}"] = "" # 시간만 표시 (00제외)
            data_rows.append(row)
            
        if not df.empty:
            day_books = df[df['date'] == t_str]
            for _, b in day_books.iterrows():
                r_name = b['room'].replace("Room ", "R")
                s = int(b['startTime'].split(':')[0])
                d = int(b['duration'])
                n = b['mainName']
                
                for h in range(s, s+d):
                    for row in data_rows:
                        if row["Room"] == r_name and f"{h}" in row:
                            row[f"{h}"] = n

        sch_df = pd.DataFrame(data_rows).set_index("Room")
        
        def color_map(val):
            return 'background-color: #ffc107' if val else ''
            
        st.dataframe(sch_df.style.map(color_map), use_container_width=True)

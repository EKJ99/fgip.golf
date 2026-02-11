import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import time

# ==========================================
# [설정] 테스트 모드 (실제 사용 시 False)
TEST_MODE = True
# ==========================================

# --- 1. 페이지 설정 및 CSS ---
st.set_page_config(page_title="FGIP Golf", layout="wide", page_icon="⛳")

st.markdown("""
<style>
    /* [1] 일반 박스 스타일 (div: 사용중/마감용) */
    .room-box {
        border-radius: 8px;
        padding: 0px 4px; /* 패딩 조정 */
        text-align: center;
        color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        height: 100px; /* 높이 고정 */
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        width: 100%;
        margin-bottom: 8px;
    }

    /* [2] 버튼 스타일 강제 변경 (button: 사용가능용) */
    /* Primary 버튼을 '초록색 박스'로 만듭니다. */
    div.stButton > button[kind="primary"] {
        background-color: #28a745 !important; /* 초록색 */
        border: none !important;
        height: 100px !important; /* 박스 높이와 통일 */
        width: 100% !important;
        white-space: pre-wrap !important; /* 줄바꿈 허용 */
        font-size: 1rem !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
        line-height: 1.3 !important;
        color: white !important;
    }
    
    div.stButton > button[kind="primary"]:hover {
        background-color: #218838 !important; /* 호버 시 진한 초록 */
        transform: scale(0.99);
    }
    
    /* 하단 '새 예약하기' 버튼도 Primary를 쓰지만, 디자인이 같아도 어색하지 않으므로 그대로 둡니다.
       만약 구분을 원하시면 하단 버튼에만 특수 처리가 필요하지만, 
       지금은 통일감을 위해 '중요한 액션=초록색'으로 유지합니다. */

    /* Secondary 버튼 (취소, 도움말 등) 스타일 */
    div.stButton > button[kind="secondary"] {
        background-color: white !important;
        color: #333 !important;
        border: 1px solid #ccc !important;
        height: auto !important;
        min-height: 3em !important;
    }

    /* 텍스트 스타일 */
    .room-title { font-weight: bold; font-size: 1.1rem; margin-bottom: 4px; }
    .room-status { font-size: 0.9rem; font-weight: bold; margin-bottom: 6px; line-height: 1.2; }
    .room-desc { 
        font-size: 0.75rem; 
        background-color: rgba(0,0,0,0.2); 
        padding: 2px 8px; 
        border-radius: 10px; 
        font-weight: normal; 
    }
    
    /* 상태별 색상 (div용) */
    .status-occupied { background-color: #dc3545; } /* 빨강 */
    .status-closed { background-color: #6c757d; }   /* 회색 */
    
</style>
""", unsafe_allow_html=True)

# --- 2. DB 연결 및 데이터 로드 ---
def get_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        secrets_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(secrets_dict, scope)
        client = gspread.authorize(creds)
        return client.open("ScreenGolf_DB").get_worksheet(0)
    except Exception as e:
        st.error(f"DB 연결 오류: {e}")
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
    "Room 1": "일반", "Room 2": "일반", "Room 3": "스윙/GDR+",
    "Room 4": "양손잡이", "Room 5": "개인훈련"
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

# [상단 헤더]
col_head, col_help = st.columns([7, 3], vertical_alignment="bottom")
with col_head:
    st.title("FGIP Golf")
with col_help:
    with st.popover("사용방법 ❔", use_container_width=True):
        st.markdown("""
        **📖 이용 안내**
        1. **🟩 초록색 박스 (사용 가능)**
           - **터치**하면 즉시 사용 등록이 가능합니다.
        2. **🟥 빨간색 박스 (사용 중)**
           - 현재 이용 중인 룸입니다.
        3. **⬛ 회색 박스 (운영 시간 아님)**
           - 현재 운영 시간이 아닙니다.
        """)

# 데이터 로드
df = load_data()
if not df.empty:
    df = df[df['status'] != 'cancelled']

now = get_korea_time()
today_str = now.strftime("%Y-%m-%d")
current_hour = now.hour
current_minute = now.minute

# [TEST MODE]
if TEST_MODE:
    st.warning("⚠️ 테스트 모드 (20:00 고정)")
    current_hour = 20
    current_minute = 15
    # 가짜 데이터 주입...

# =========================================================
# [섹션 A] 실시간 현황판
# =========================================================
st.subheader("사용현황")

# 즉시 사용 팝업
@st.dialog("즉시 사용 등록")
def show_walkin_modal(room_name):
    remaining_min = 60 - current_minute
    next_hour = current_hour + 1
    
    st.markdown(f"### {room_name}을(를) 사용하시겠습니까?")
    st.info(f"🕐 현재 시각 **{current_hour}:{current_minute:02d}**\n\n이용은 다음 정각인 **{next_hour}:00**까지만 가능합니다.\n(이후 시간은 '새 예약하기'를 이용해주세요)")
    
    name = st.text_input("사용자 이름", placeholder="이름을 입력하세요")
    pw = st.text_input("비밀번호 (4자리)", type="password", max_chars=4)
    
    # 이 버튼도 Primary이므로 초록색으로 나옵니다 (통일감)
    if st.button("사용 시작 (등록)", type="primary", use_container_width=True):
        if not name:
            st.error("이름을 입력해주세요.")
            return
        if len(pw) != 4 or not pw.isdigit():
            st.error("비밀번호 4자리를 입력해주세요.")
            return
            
        try:
            sheet = get_sheet()
            new_row = [
                str(int(time.time()*1000)),
                room_name,
                today_str,
                f"{current_hour}:00", # 시작시간
                1, # 1시간 슬롯
                1,
                name,
                f"{name} (즉시사용)",
                pw,
                "reserved",
                str(datetime.now())
            ]
            sheet.append_row(new_row)
            st.success(f"{room_name} 사용 등록 완료!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"등록 실패: {e}")

# 그리드 레이아웃
row1 = st.columns(2)
row2 = st.columns(2)
row3 = st.columns(2)
all_cols = row1 + row2 + row3

for idx, room in enumerate(ROOMS):
    col = all_cols[idx]
    
    with col:
        status = "available"
        display_text = "사용 가능\n(터치하여 등록)"
        desc_text = ROOM_DESC[room]
        
        op_range = get_operating_hours_range(now)
        if current_hour not in op_range:
            status = "closed"
            display_text = "운영 시간 아님"
        else:
            if not df.empty:
                active = df[ (df['room'] == room) & (df['date'] == today_str) ]
                for _, row in active.iterrows():
                    start = int(str(row['startTime']).split(':')[0])
                    dur = int(row['duration'])
                    if start <= current_hour < start + dur:
                        status = "occupied"
                        display_text = row['allNames'].replace(",", "\n")
                        break
        
        # 렌더링
        if status == "available":
            # [수정] type="primary"를 사용하여 CSS로 '초록색 박스' 디자인을 입힘
            btn_label = f"{room.replace('Room ', 'R')}\n{display_text}"
            if st.button(btn_label, key=f"btn_walkin_{room}", type="primary"):
                show_walkin_modal(room)
        else:
            # 클릭 불가 (HTML div)
            bg_class = "status-occupied" if status == "occupied" else "status-closed"
            st.markdown(f"""
                <div class="room-box {bg_class}">
                    <div class="room-title">{room.replace('Room ', 'R')}</div>
                    <div class="room-status">{display_text}</div>
                    <div class="room-desc">{desc_text}</div>
                </div>
            """, unsafe_allow_html=True)


st.markdown("---")

# [섹션 B] 하단 버튼 그룹
col_b1, col_b2 = st.columns(2)

# --- 예약 모달 ---
@st.dialog("새 예약하기")
def show_booking_modal():
    date_labels = [DEFAULT_OPT] + [(now + timedelta(days=i)).strftime("%m월 %d일 (%a)") for i in range(7)]
    date_values = [None] + [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    date_map = dict(zip(date_labels, date_values))
    sel_label = st.selectbox("날짜", date_labels)
    selected_date = date_map.get(sel_label)

    room_opts = [DEFAULT_OPT] + ROOMS
    selected_room = st.selectbox("룸", room_opts)

    hc_opts = [DEFAULT_OPT, "1인", "2인", "3인 이상"]
    head_count = st.selectbox("인원", hc_opts)

    names = []
    if head_count != DEFAULT_OPT:
        st.markdown("###### 참가자 이름 입력")
        names.append(st.text_input("참가자 1 (대표자)", placeholder="필수 입력"))
        
        max_duration = 1
        if head_count == "2인":
            names.append(st.text_input("참가자 2", placeholder="필수 입력"))
            max_duration = 2
        elif head_count == "3인 이상":
            names.append(st.text_input("참가자 2", placeholder="필수 입력"))
            names.append(st.text_input("참가자 3", placeholder="필수 입력"))
            extra = st.number_input("추가 인원", 0, 10, 0)
            for k in range(extra):
                names.append(st.text_input(f"참가자 {k+4}"))
            max_duration = 3
    else:
        max_duration = 0

    if max_duration > 0:
        dur_opts = [DEFAULT_OPT] + list(range(1, max_duration + 1))
        dur_sel = st.selectbox("이용 시간", dur_opts, format_func=lambda x: f"{x}시간" if x != DEFAULT_OPT else x)
    else:
        st.selectbox("이용 시간", [DEFAULT_OPT], disabled=True)
        dur_sel = DEFAULT_OPT

    valid_starts = [DEFAULT_OPT]
    if selected_date and dur_sel != DEFAULT_OPT:
        duration = int(dur_sel)
        target_dt = datetime.strptime(selected_date, "%Y-%m-%d")
        op_range = get_operating_hours_range(target_dt)
        for h in op_range:
            if h + duration <= 22:
                valid_starts.append(f"{h}:00")
    
    if len(valid_starts) == 1 and selected_date and dur_sel != DEFAULT_OPT:
        st.warning("선택한 조건으로 가능한 시간이 없습니다 (22시 마감)")

    start_time = st.selectbox("시작 시간", valid_starts, disabled=(len(valid_starts)==1 and not selected_date))

    st.markdown("###### 비밀번호 설정")
    pw1 = st.text_input("비밀번호 (숫자 4자리)", type="password", max_chars=4, placeholder="예약 확인/취소용")
    pw2 = st.text_input("비밀번호 확인", type="password", max_chars=4, placeholder="한 번 더 입력")

    if st.button("예약 확정", type="primary", use_container_width=True, key="btn_confirm_new"):
        if DEFAULT_OPT in [sel_label, selected_room, head_count, dur_sel, start_time]:
            st.error("모든 항목을 선택해주세요.")
            return
        if not names or not all(n.strip() for n in names):
            st.error("참가자 이름을 모두 입력해주세요.")
            return
        if not pw1 or len(pw1) != 4 or not pw1.isdigit():
            st.error("비밀번호는 숫자 4자리여야 합니다.")
            return
        if pw1 != pw2:
            st.error("비밀번호가 일치하지 않습니다.")
            return

        duration = int(dur_sel)
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
                pw1,
                "reserved",
                str(datetime.now())
            ]
            sheet.append_row(new_row)
            st.success("예약이 완료되었습니다!")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"저장 실패: {e}")

@st.dialog("예약 취소")
def show_cancel_modal():
    st.caption("예약 변경은 취소 후 다시 예약해주세요.")
    name = st.text_input("예약자 이름 검색")
    
    if name:
        if df.empty:
            st.warning("데이터 없음")
        else:
            my_list = df[ (df['mainName'] == name) & (df['date'] >= today_str) ].sort_values(by='date', ascending=True)
            
            if my_list.empty:
                st.info("예약 내역이 없습니다.")
            else:
                for _, row in my_list.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['date']} {row['startTime']}**")
                        st.text(f"{row['room']} ({row['duration']}시간)\n{row['allNames']}")
                        
                        if st.button("취소하기", key=f"btn_{row['id']}", use_container_width=True):
                            st.session_state[f"cancel_{row['id']}"] = True
                        
                        if st.session_state.get(f"cancel_{row['id']}"):
                            pw = st.text_input("비밀번호 확인", type="password", key=f"pw_{row['id']}", max_chars=4)
                            if st.button("정말 취소하시겠습니까?", key=f"del_{row['id']}", type="primary", use_container_width=True):
                                if str(pw) == str(row['password']):
                                    success = False
                                    try:
                                        sheet = get_sheet()
                                        cell = sheet.find(str(row['id']))
                                        sheet.update_cell(cell.row, 10, "cancelled")
                                        success = True
                                    except Exception as e:
                                        st.error(f"오류 발생: {e}")
                                    
                                    if success:
                                        st.success("취소 완료")
                                        time.sleep(1)
                                        st.rerun()
                                else:
                                    st.error("비밀번호가 틀렸습니다.")

# 취소 버튼은 'Secondary' (흰색)
with col_b1:
    if st.button("예약 취소", use_container_width=True, key="btn_open_cancel", type="secondary"):
        show_cancel_modal()

# 새 예약하기 버튼은 'Primary' (초록색 - 위 CSS에서 강제 변경됨)
with col_b2:
    if st.button("새 예약하기", type="primary", use_container_width=True, key="btn_open_new"):
        show_booking_modal()


# [섹션 C] 주간 예약 현황
st.markdown("---")
st.subheader("주간 예약 현황")

week_days = [now + timedelta(days=i) for i in range(7)]
tabs = st.tabs([d.strftime("%d(%a)") for d in week_days])

for i, t in enumerate(tabs):
    with t:
        target_d = week_days[i]
        t_str = target_d.strftime("%Y-%m-%d")
        op_range = get_operating_hours_range(target_d)
        
        data_rows = []
        for r in ROOMS:
            row = {"Room": r.replace("Room ", "R")}
            for h in op_range:
                row[f"{h}"] = ""
            data_rows.append(row)
            
        if not df.empty:
            day_books = df[df['date'] == t_str]
            for _, b in day_books.iterrows():
                r_name = b['room'].replace("Room ", "R")
                s = int(b['startTime'].split(':')[0])
                d = int(b['duration'])
                all_names_display = b['allNames'].replace(",", "\n") 
                
                for h in range(s, s+d):
                    for row in data_rows:
                        if row["Room"] == r_name and f"{h}" in row:
                            row[f"{h}"] = all_names_display

        sch_df = pd.DataFrame(data_rows).set_index("Room")
        
        def color_map(val):
            return 'background-color: #ffc107; white-space: pre-wrap; font-size: 0.8em;' if val else ''
            
        st.dataframe(sch_df.style.map(color_map), use_container_width=True)

import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta

# --- 1. 설정 및 연결 ---
st.set_page_config(page_title="스크린골프 예약", layout="wide")

# 구글 시트 인증 (Streamlit Secrets 사용)
# 로컬에서 테스트할 때는 secrets.toml 파일이 필요하지만, 배포 후에는 대시보드에서 설정합니다.
def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    # 스프레드시트 이름을 정확히 적어주세요
    return client.open("ScreenGolf_DB").sheet1 

# 데이터 로드 함수 (캐시 사용 안함 - 실시간성 중요)
def load_data():
    try:
        sheet = get_sheet()
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=['id', 'room', 'date', 'startTime', 'duration', 'mainName', 'status', 'password'])
        df = pd.DataFrame(data)
        # 날짜/시간 타입 변환 없이 문자열 그대로 사용하거나 필요시 변환
        return df
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return pd.DataFrame()

# --- 2. 상수 및 로직 정의 ---
ROOMS = {
    "Room 1": "일반 룸",
    "Room 2": "일반 룸",
    "Room 3": "스윙분석기/GDR+",
    "Room 4": "양손잡이용",
    "Room 5": "개인 훈련용"
}

def get_operating_hours(date_obj):
    # 월(0) ~ 일(6)
    weekday = date_obj.weekday()
    if weekday == 3: # 목요일
        return range(17, 22)
    elif weekday == 4: # 금요일
        return range(6, 22)
    else: # 나머지
        return range(19, 22)

# --- 3. UI 구성 ---
st.title("⛳ 스크린골프 예약 시스템")

df = load_data()

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📊 예약 현황", "📝 새 예약하기", "❌ 예약 취소"])

# [탭 1] 예약 현황
with tab1:
    st.subheader("실시간 룸 현황")
    
    # 현재 시간 기준 상태 표시
    now = datetime.now() # 한국 시간 처리는 배포 시 timezone 설정 필요 (여기선 서버시간 기준)
    # Streamlit Cloud는 UTC 기준이므로 한국 시간(+9) 보정 필요
    korea_now = now + timedelta(hours=9)
    current_hour = korea_now.hour
    today_str = korea_now.strftime("%Y-%m-%d")

    cols = st.columns(5)
    for i, (room_name, room_desc) in enumerate(ROOMS.items()):
        # 해당 룸의 오늘, 현재 시간 예약 찾기
        is_occupied = False
        occupant = ""
        
        if not df.empty:
            # 취소되지 않은 예약만 필터링
            active_df = df[df['status'] != 'cancelled']
            # 오늘 날짜
            today_bookings = active_df[(active_df['date'] == today_str) & (active_df['room'] == room_name)]
            
            for _, row in today_bookings.iterrows():
                start_h = int(str(row['startTime']).split(':')[0])
                duration = int(row['duration'])
                if start_h <= current_hour < start_h + duration:
                    is_occupied = True
                    occupant = row['mainName']
                    break
        
        with cols[i]:
            if is_occupied:
                st.error(f"**{room_name}**\n\n사용중\n({occupant})")
            else:
                # 운영 시간 체크
                op_hours = get_operating_hours(korea_now)
                if current_hour in op_hours:
                    st.success(f"**{room_name}**\n\n이용 가능")
                else:
                    st.secondary(f"**{room_name}**\n\n마감")
            st.caption(room_desc)

    st.divider()
    st.subheader("📅 주간 예약표")
    
    # 7일치 날짜 탭
    days = [korea_now + timedelta(days=i) for i in range(7)]
    day_tabs = st.tabs([d.strftime("%m/%d (%a)") for d in days])
    
    for i, day in enumerate(days):
        with day_tabs[i]:
            target_date = day.strftime("%Y-%m-%d")
            op_range = get_operating_hours(day)
            
            # 시간표 데이터프레임 생성
            schedule_data = {f"{h}:00": [""] * 5 for h in op_range}
            schedule_df = pd.DataFrame(schedule_data, index=ROOMS.keys())
            
            if not df.empty:
                active_df = df[df['status'] != 'cancelled']
                day_bookings = active_df[active_df['date'] == target_date]
                
                for _, row in day_bookings.iterrows():
                    r_idx = row['room']
                    s_time = int(str(row['startTime']).split(':')[0])
                    dur = int(row['duration'])
                    name = row['mainName']
                    
                    for h in range(s_time, s_time + dur):
                        if h in op_range:
                            schedule_df.at[r_idx, f"{h}:00"] = f"{name} (예약)"
            
            st.dataframe(schedule_df, use_container_width=True)

# [탭 2] 새 예약하기
with tab2:
    with st.form("booking_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            date_opts = [d.strftime("%Y-%m-%d") for d in days]
            selected_date = st.selectbox("날짜 선택", date_opts)
            selected_room = st.selectbox("룸 선택", list(ROOMS.keys()))
            head_count = st.selectbox("인원", [1, 2, 3]) # 3은 3인 이상
            
        with col2:
            # 이용 시간 제한 로직
            max_duration = 3 if head_count >= 3 else head_count
            duration = st.selectbox("이용 시간", range(1, max_duration + 1), format_func=lambda x: f"{x}시간")
            
            # 시작 시간 (동적 필터링은 폼 내부라 어려우므로 검증 로직에서 처리)
            # 일단 전체 운영시간 보여주고 선택하게 함 (단순화)
            s_date = datetime.strptime(selected_date, "%Y-%m-%d")
            op_hours = list(get_operating_hours(s_date))
            # 22시 넘기는 시간 제외
            valid_starts = [h for h in op_hours if h + duration <= 22]
            
            if not valid_starts:
                st.warning("선택한 날짜/시간으로는 예약 가능한 슬롯이 없습니다.")
                start_time_int = None
            else:
                start_time_int = st.selectbox("시작 시간", valid_starts, format_func=lambda x: f"{x}:00")

        name = st.text_input("예약자 이름 (대표자)")
        password = st.text_input("비밀번호 (숫자 4자리)", type="password", max_chars=4)
        
        submitted = st.form_submit_button("예약 확정")
        
        if submitted:
            if not name or not password or start_time_int is None:
                st.error("모든 정보를 입력해주세요.")
            else:
                # 중복 검사
                start_h = start_time_int
                end_h = start_h + duration
                
                is_duplicate = False
                if not df.empty:
                    active = df[(df['status'] != 'cancelled') & (df['date'] == selected_date) & (df['room'] == selected_room)]
                    for _, row in active.iterrows():
                        ex_start = int(str(row['startTime']).split(':')[0])
                        ex_end = ex_start + int(row['duration'])
                        # 겹침 로직: (A시작 < B끝) and (A끝 > B시작)
                        if start_h < ex_end and end_h > ex_start:
                            is_duplicate = True
                            break
                
                if is_duplicate:
                    st.error("이미 예약된 시간입니다.")
                else:
                    # 저장
                    new_row = [
                        str(datetime.now().timestamp()), # ID
                        selected_room,
                        selected_date,
                        f"{start_time_int}:00",
                        duration,
                        name,
                        "reserved",
                        password
                    ]
                    
                    try:
                        sheet = get_sheet()
                        sheet.append_row(new_row)
                        st.success("예약이 완료되었습니다! (새로고침 시 반영됩니다)")
                        st.balloons()
                    except Exception as e:
                        st.error(f"저장 실패: {e}")

# [탭 3] 예약 취소
with tab3:
    st.subheader("예약 취소")
    
    # 내 예약 찾기 (이름으로 검색 - 간단한 버전)
    search_name = st.text_input("예약자 이름으로 검색")
    
    if search_name and not df.empty:
        my_bookings = df[(df['mainName'] == search_name) & (df['status'] != 'cancelled')]
        
        if my_bookings.empty:
            st.info("예약 내역이 없습니다.")
        else:
            for idx, row in my_bookings.iterrows():
                with st.expander(f"{row['date']} {row['startTime']} - {row['room']}"):
                    del_pw = st.text_input("비밀번호 확인", key=f"pw_{row['id']}")
                    if st.button("취소하기", key=f"btn_{row['id']}"):
                        if str(del_pw) == str(row['password']):
                            # 스프레드시트 업데이트 (status -> cancelled)
                            # gspread는 셀 찾아서 업데이트해야 함. 
                            # 편의상 id가 있는 행을 찾음
                            try:
                                sheet = get_sheet()
                                cell = sheet.find(str(row['id']))
                                # status 컬럼이 G열(7번째)이라 가정하면 안됨. 헤더 보고 찾아야 안전하지만
                                # append_row 순서: id, room, date, start, dur, name, status, pw
                                # status는 7번째 열 (G열)
                                sheet.update_cell(cell.row, 7, "cancelled") 
                                st.success("취소되었습니다.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"오류: {e}")
                        else:
                            st.error("비밀번호가 틀렸습니다.")

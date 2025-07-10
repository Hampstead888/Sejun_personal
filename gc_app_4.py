import streamlit as st
import pandas as pd
import tempfile
from pathlib import Path
import snowflake.connector
import os
import time
import hashlib

# 하드코딩된 Snowflake 로그인 정보


# 페이지 설정
st.set_page_config(page_title="일본어 문법 검사기", page_icon="⛩️")

# 제목
st.markdown("### ⛩️ 일본어 문법 검사기  \n(Snowflake Cortex/Sonnet3.5기반)")

@st.cache_resource
def connect_to_snowflake():
    try:
        return snowflake.connector.connect(**SNOWFLAKE_CONFIG)
    except Exception as e:
        st.error(f"Snowflake 연결 오류: {str(e)}")
        return None

def get_valid_connection():
    """연결이 닫힌 경우 자동 재연결"""
    try:
        conn = connect_to_snowflake()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return conn
    except:
        pass
    # 재연결 시도
    try:
        return connect_to_snowflake()
    except Exception as e:
        st.error(f"❌ Snowflake 재연결 실패: {str(e)}")
        return None

def check_japanese_grammar(text, conn):
    if not conn:
        return ""

    prompt = f"""
    あなたは日本語のゲーム翻訳・校正の専門家です。以下のテキストについて、誤字脱字、文法ミス、半角文字の使用を修正してください。ただし、以下のルールを厳密に守ってください。

    【重要な指示】
    1. 誤りがある場合は、修正後の文章のみを返し、説明や補足は不要です。
    2. 原文のスタイルや語調はそのまま維持してください。
    3. 内容を追加・削除せず、誤りのある部分だけを修正してください。
    4. 以下の形式で記述されたタグ（およびその中の内容）は絶対に変更しないでください：
    - %...% の形式（例：%map,Bangor,Location_Pub%）
    - <...> の形式（例：<color=red>、<fontvar=-1>など）
    - {{...}} の形式（例：{{アイテム名}}など）
    - $...$ の形式（例：$map,Dunbarton,Location_TownOffice$）
    5. タグの**外にある半角英字・半角カタカナ**は、**全角に変換**してください。
    ※ただし、**数字（0-9）は半角のままで構いません**。
    ※タグの開始記号から終了記号までの範囲内の文字列は、全角・半角を含めて一切変更禁止です。
    6. 誤りがない場合は "NO_CHANGES" とだけ返してください。

    修正対象のテキスト:{text}

    返答:"""

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT SNOWFLAKE.CORTEX.COMPLETE('claude-3-5-sonnet', %s)", (prompt,))
        result = cursor.fetchone()
        if result and result[0]:
            return "" if result[0].strip() == "NO_CHANGES" else result[0].strip()
        return ""
    except Exception as e:
        st.error(f"Cortex API 오류: {str(e)}")
        return ""
    finally:
        cursor.close()

# 파일 업로드
uploaded_file = st.file_uploader("Excel 파일 업로드", type=['xlsx'])

if uploaded_file is not None:
    if st.button("📤 처리 시작", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("📁 파일 처리 중...")
            tmp_dir = Path(tempfile.gettempdir())
            tmp_input = tmp_dir / uploaded_file.name
            tmp_output = tmp_dir / f"{Path(uploaded_file.name).stem}_corrected.xlsx"

            with open(tmp_input, 'wb') as f:
                f.write(uploaded_file.getvalue())

            status_text.text("📊 Excel 파일을 읽는 중...")
            df = pd.read_excel(tmp_input)

            if "TransText" not in df.columns:
                st.error("❌ 'TransText' 열이 Excel 파일에 없습니다.")
                st.write(f"사용 가능한 열: {', '.join(df.columns)}")
                st.stop()

            status_text.text("🔗 Snowflake에 연결 중...")
            conn = get_valid_connection()
            if not conn:
                st.error("❌ Snowflake 연결에 실패했습니다.")
                st.stop()

            status_text.text("🔍 문법 검사를 시작합니다...")
            total = len(df)
            df['corrected'] = ''

            for i, row in df.iterrows():
                if pd.notna(row['TransText']) and str(row['TransText']).strip():
                    status_text.text(f"🔍 문법 검사 중... ({i+1}/{total})")
                    corrected_text = check_japanese_grammar(str(row['TransText']), conn)
                    df.at[i, 'corrected'] = corrected_text
                progress_bar.progress((i + 1) / total)
                time.sleep(0.1)

            conn.close()

            status_text.text("💾 결과 파일을 저장 중...")
            df.to_excel(tmp_output, index=False)
            status_text.text("✅ 처리가 완료되었습니다!")
            st.success(f"📄 처리된 행 수: {total}")

            with open(tmp_output, 'rb') as f:
                st.download_button(
                    label="📥 결과 파일 다운로드",
                    data=f.read(),
                    file_name=f"{Path(uploaded_file.name).stem}_corrected.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
            with st.expander("상세 오류 정보"):
                import traceback
                st.code(traceback.format_exc())

st.markdown("""
---
### 🗂️ 파일 양식: .xlsx(엑셀)
```bash
# 문법 및 스펠링 체크 열 Header = TransText, H열
```
""")

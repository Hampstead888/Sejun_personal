import streamlit as st
import pandas as pd
import requests
import tempfile
from pathlib import Path
import time

st.set_page_config(page_title="⛩️ 일본어 스펠링 검사기")
st.markdown("### ⛩️ 일본어 스펠링 검사기  \n(Ollama LLM 기반)")

def build_ollama_prompt(text):
    return f"""
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
6. 誤りがない場合は、何も返さず、出力を完全に省略してください。（"NO_CHANGES" なども含めず、空の文字列を返してください。）

修正対象のテキスト:{text}

返答:
"""

def check_japanese_grammar_ollama(text, model="llama3"):
    prompt = build_ollama_prompt(text)
    try:
        res = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60
        )
        result = res.json()
        return result.get("response", "").strip()
    except Exception as e:
        st.error(f"🧠 Ollama 호출 오류: {str(e)}")
        return ""

# --- 파일 업로드 ---
uploaded_file = st.file_uploader("📤 Excel 파일 업로드 (.xlsx)", type=["xlsx"])

if uploaded_file:
    if st.button("🚀 문법 검사 시작"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("📁 파일 처리 중...")
            tmp_dir = Path(tempfile.gettempdir())
            tmp_input = tmp_dir / uploaded_file.name
            tmp_output = tmp_dir / f"{Path(uploaded_file.name).stem}_corrected.xlsx"

            with open(tmp_input, 'wb') as f:
                f.write(uploaded_file.getvalue())

            df = pd.read_excel(tmp_input)

            if "TransText" not in df.columns:
                st.error("❌ 'TransText' 열이 Excel 파일에 없습니다.")
                st.stop()

            status_text.text("🧠 Ollama 문법 검사 실행 중...")
            total = len(df)
            df["corrected"] = ""

            for i, row in df.iterrows():
                if pd.notna(row['TransText']) and str(row['TransText']).strip():
                    status_text.text(f"🔍 문장 처리 중... ({i+1}/{total})")
                    df.at[i, "corrected"] = check_japanese_grammar_ollama(str(row["TransText"]))
                progress_bar.progress((i+1)/total)
                time.sleep(0.1)

            df.to_excel(tmp_output, index=False)

            st.success("✅ 문법 검사 완료!")
            st.download_button(
                "📥 결과 파일 다운로드",
                data=tmp_output.read_bytes(),
                file_name=f"{Path(uploaded_file.name).stem}_corrected.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"❌ 처리 중 오류 발생: {str(e)}")
            with st.expander("오류 상세"):
                import traceback
                st.code(traceback.format_exc())

st.markdown("""
---
### 📌 사용 방법
- .xlsx 파일 내 `"TransText"` 열이 존재해야 합니다.
- 결과는 `"corrected"` 열에 추가되어 다운로드됩니다.
""")

import streamlit as st
import random
import time
import json
from google import genai
from google.genai import types
from supabase import create_client

# ==========================================
# 1. Supabase & AI 設定
# ==========================================
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except:
    st.error("Secretsの設定がまだのようです。Manage app > Settings > Secretsを確認してください。")
    st.stop()

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ==========================================
# 2. AI関数: 問題作成 & 物語作成
# ==========================================

def generate_quiz_words(api_key, level):
    """AIに単語リストを作らせる関数"""
    if not api_key:
        # キーがない時の予備データ
        return [{"en": "NoKey", "jp": "キーなし"}, {"en": "SetKey", "jp": "設定してね"}]

    client = genai.Client(api_key=api_key)
    
    # AIへの指示書（JSON形式で返してもらう）
    prompt = f"""
    Generate 6 unique English vocabulary words for TOEIC {level} level.
    Output MUST be a JSON list of objects with 'en' (English word) and 'jp' (Japanese meaning).
    Example: [{{"en": "Profit", "jp": "利益"}}, {{"en": "Hire", "jp": "雇う"}}]
    Do not use markdown code blocks. Just the raw JSON.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json") # JSONモード
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"問題作成エラー: {e}")
        return [{"en": "Error", "jp": "エラー"}]

def get_english_story(api_key, words):
    """AIに英語の物語を作らせる関数"""
    if not api_key: return "Please set your API Key."
    
    client = genai.Client(api_key=api_key)
    word_str = ", ".join(words)
    
    prompt = f"""
    Write a short, exciting adventure story in simple English using ALL of these words: {word_str}.
    Highlight the used words in bold (e.g. **Word**).
    Keep it under 100 words.
    """
    try:
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text
    except:
        return "Story generation failed."

# ==========================================
# 3. DB操作
# ==========================================
def save_word(en, jp):
    """単語を保存"""
    try:
        # 重複チェック
        chk = supabase.table("collected_words").select("id").eq("word_en", en).execute()
        if not chk.data:
            supabase.table("collected_words").insert({"word_en": en, "word_jp": jp}).execute()
            return True # 新規保存した
    except:
        pass
    return False # すでにあった

def get_count():
    """保存済み単語数を取得"""
    try:
        # count='exact', head=True でデータの中身を取らずに件数だけ取る（高速）
        res = supabase.table("collected_words").select("id", count="exact").execute()
        return res.count
    except:
        return 0

def get_all_words_list():
    """保存済み単語リストを取得"""
    try:
        res = supabase.table("collected_words").select("word_en").execute()
        return [r['word_en'] for r in res.data]
    except:
        return []

# ==========================================
# 4. アプリ本体
# ==========================================

def main():
    st.set_page_config(page_title="Infinite English Battle", layout="wide")
    
    # --- サイドバー設定 ---
    st.sidebar.title("🛠️ Settings")
    api_key = st.sidebar.text_input("Gemini API Key", type="password")
    
    # レベル選択（AIへの指示用）
    level_options = ["Beginner (TOEIC 300-500)", "Intermediate (TOEIC 500-700)", "Advanced (TOEIC 700-900)"]
    selected_level = st.sidebar.selectbox("Difficulty", level_options)

    # ★ 通算獲得数の表示（ここなら確実に表示されます）
    total_count = get_count()
    st.sidebar.divider()
    st.sidebar.metric("📚 Total Collected", f"{total_count} words")
    
    # 図鑑機能
    if st.sidebar.checkbox("Show Collection"):
        my_words = get_all_words_list()
        st.sidebar.text_area("Your Words", ", ".join(my_words), height=150)

    # --- メイン画面 ---
    st.title("🤖 Infinite English Battle")
    st.caption("AI generates new quizzes every time!")

    # セッション初期化
    if "cards" not in st.session_state:
        st.session_state.game_state = "IDLE" # IDLE, PLAYING, FINISHED

    # --- 1. スタート画面 ---
    if st.session_state.game_state == "IDLE":
        st.info("Press Start to generate a new quiz from AI.")
        if st.button("🚀 Start New Game", type="primary"):
            if not api_key:
                st.warning("Please enter Gemini API Key first!")
            else:
                with st.spinner(f"AI is generating {selected_level} words..."):
                    # AIに問題を作らせる
                    quiz_data = generate_quiz_words(api_key, selected_level)
                    
                    # カード生成
                    cards = []
                    for item in quiz_data:
                        cards.append({"id": item["en"], "text": item["en"], "pair": item["jp"], "is_jp": False})
                        cards.append({"id": item["en"], "text": item["jp"], "pair": item["en"], "is_jp": True})
                    random.shuffle(cards)
                    
                    # ゲーム開始設定
                    st.session_state.cards = cards
                    st.session_state.flipped = []
                    st.session_state.matched = set()
                    st.session_state.collected_now = [] # 今回ゲットした分
                    st.session_state.start_time = time.time()
                    st.session_state.time_limit = 45
                    st.session_state.game_state = "PLAYING"
                    st.rerun()

    # --- 2. プレイ中 ---
    elif st.session_state.game_state == "PLAYING":
        elapsed = time.time() - st.session_state.start_time
        remaining = st.session_state.time_limit - elapsed
        
        # タイムアップ判定
        if remaining <= 0:
            st.session_state.game_state = "FINISHED"
            st.rerun()

        # UI表示
        col1, col2 = st.columns([3, 1])
        with col1:
            st.progress(max(0.0, remaining / st.session_state.time_limit))
        with col2:
            st.write(f"⏳ {remaining:.1f}s")

        # カードグリッド
        cols = st.columns(4)
        for i, card in enumerate(st.session_state.cards):
            is_open = (i in st.session_state.flipped) or (card["id"] in st.session_state.matched)
            label = card["text"] if is_open else "❓"
            
            # マッチしたカードはボタン無効化、色は変える
            if card["id"] in st.session_state.matched:
                label = f"✅ {card['text']}"
            
            with cols[i % 4]:
                if st.button(label, key=f"btn_{i}", disabled=is_open):
                    st.session_state.flipped.append(i)
                    st.rerun()

        # 判定ロジック
        if len(st.session_state.flipped) == 2:
            idx1, idx2 = st.session_state.flipped
            c1 = st.session_state.cards[idx1]
            c2 = st.session_state.cards[idx2]

            if c1["id"] == c2["id"]:
                st.toast(f"Matched! {c1['id']}")
                st.session_state.matched.add(c1["id"])
                
                # 今回獲得リストに追加
                if c1["id"] not in st.session_state.collected_now:
                    st.session_state.collected_now.append(c1["id"])
                    # DB保存 (英語テキストと日本語テキストを抽出)
                    en_txt = c1["id"]
                    jp_txt = c1["pair"] if not c1["is_jp"] else c1["text"]
                    save_word(en_txt, jp_txt)

                st.session_state.flipped = []
                
                # 全クリ判定
                if len(st.session_state.matched) * 2 == len(st.session_state.cards):
                    st.session_state.game_state = "FINISHED"
                    st.rerun()
                
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Miss...")
                time.sleep(0.8)
                st.session_state.flipped = []
                st.rerun()

    # --- 3. 結果画面 ---
    elif st.session_state.game_state == "FINISHED":
        st.header("🏁 Game Over!")
        
        got_words = st.session_state.collected_now
        if got_words:
            st.success(f"You collected: {', '.join(got_words)}")
            st.divider()
            
            st.subheader("📖 AI English Story")
            if st.button("Generate Story"):
                with st.spinner("Writing story..."):
                    story = get_english_story(api_key, got_words)
                    st.info(story)
        else:
            st.warning("No words collected this time...")

        st.divider()
        if st.button("Play Again (Generate New Words)"):
            st.session_state.game_state = "IDLE"
            st.rerun()

if __name__ == "__main__":
    main()

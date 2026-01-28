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
    st.error("Error: Supabase secrets not found. Please check Manage app > Settings > Secrets.")
    st.stop()

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ==========================================
# 2. AI関数 (フォールバック付き)
# ==========================================

def generate_quiz_words(api_key, level):
    """AIに単語リストを作らせる (APIキーがない場合は予備リストを返す)"""
    if not api_key:
        # ★ キーがない時の予備単語リスト (ここも英語メインに)
        return [
            {"en": "Galaxy", "jp": "銀河"},
            {"en": "Planet", "jp": "惑星"},
            {"en": "Rocket", "jp": "ロケット"},
            {"en": "Star",   "jp": "星"},
            {"en": "Alien",  "jp": "宇宙人"},
            {"en": "Future", "jp": "未来"}
        ]

    client = genai.Client(api_key=api_key)
    
    # JSONのみを返すように厳格に指示
    prompt = f"""
    Generate 6 unique English vocabulary words for TOEIC {level} level.
    Output MUST be a valid JSON list of objects with 'en' (English word) and 'jp' (Japanese meaning).
    Example: [{{"en": "Profit", "jp": "利益"}}, {{"en": "Hire", "jp": "雇う"}}]
    Do not include markdown formatting (like ```json). Just the raw JSON string.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        st.error(f"AI Error: {e}")
        # エラー時の予備
        return [{"en": "Error", "jp": "エラー"}, {"en": "Retry", "jp": "再試行"}]

def get_english_story(api_key, words):
    """AIに英語の物語を作らせる (APIキーがない場合は予備の英語物語を返す)"""
    
    # ★ ここがご要望の修正箇所です ★
    if not api_key:
        word_list_str = ", ".join([f"**{w}**" for w in words])
        return f"""
        (Note: AI Story generation skipped because API Key is missing. Here is a template story.)
        
        Once upon a time, there was a brave adventurer who was looking for {word_list_str}.
        
        One day, he found them all in a magical forest.
        "Finally!" he shouted. "I have collected everything!"
        
        And so, he lived happily ever after. The End.
        """
    
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
        chk = supabase.table("collected_words").select("id").eq("word_en", en).execute()
        if not chk.data:
            supabase.table("collected_words").insert({"word_en": en, "word_jp": jp}).execute()
            return True
    except:
        pass
    return False

def get_count():
    """保存済み単語数を取得"""
    try:
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
    
    level_options = ["Beginner (TOEIC 300-500)", "Intermediate (TOEIC 500-700)", "Advanced (TOEIC 700-900)"]
    selected_level = st.sidebar.selectbox("Difficulty", level_options)

    # 通算獲得数の表示
    total_count = get_count()
    st.sidebar.divider()
    st.sidebar.metric("📚 Total Collected", f"{total_count} words")
    
    if st.sidebar.checkbox("Show Collection"):
        my_words = get_all_words_list()
        st.sidebar.text_area("Your Words", ", ".join(my_words), height=150)

    # --- メイン画面 ---
    st.title("🤖 Infinite English Battle")
    
    # APIキーがない場合の警告（ただしゲームは遊べるようにする）
    if not api_key:
        st.warning("⚠️ API Key is missing. Using offline demo words & template story.")
    else:
        st.caption("AI generates new quizzes every time!")

    # セッション初期化
    if "cards" not in st.session_state:
        st.session_state.game_state = "IDLE"

    # --- 1. スタート画面 ---
    if st.session_state.game_state == "IDLE":
        if st.button("🚀 Start New Game", type="primary"):
            with st.spinner(f"Generating words..."):
                # AIに問題を作らせる（キーがなければ予備リスト）
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
                st.session_state.collected_now = []
                st.session_state.start_time = time.time()
                st.session_state.time_limit = 45
                st.session_state.game_state = "PLAYING"
                st.rerun()

    # --- 2. プレイ中 ---
    elif st.session_state.game_state == "PLAYING":
        elapsed = time.time() - st.session_state.start_time
        remaining = st.session_state.time_limit - elapsed
        
        if remaining <= 0:
            st.session_state.game_state = "FINISHED"
            st.rerun()

        col1, col2 = st.columns([3, 1])
        with col1:
            st.progress(max(0.0, remaining / st.session_state.time_limit))
        with col2:
            st.write(f"⏳ {remaining:.1f}s")

        cols = st.columns(4)
        for i, card in enumerate(st.session_state.cards):
            is_open = (i in st.session_state.flipped) or (card["id"] in st.session_state.matched)
            label = card["text"] if is_open else "❓"
            
            if card["id"] in st.session_state.matched:
                label = f"✅ {card['text']}"
            
            with cols[i % 4]:
                if st.button(label, key=f"btn_{i}", disabled=is_open):
                    st.session_state.flipped.append(i)
                    st.rerun()

        if len(st.session_state.flipped) == 2:
            idx1, idx2 = st.session_state.flipped
            c1 = st.session_state.cards[idx1]
            c2 = st.session_state.cards[idx2]

            if c1["id"] == c2["id"]:

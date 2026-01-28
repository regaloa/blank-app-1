import streamlit as st
import random
import time
import json
from google import genai
from google.genai import types
from supabase import create_client

# ==========================================
# 1. 設定 & 定数
# ==========================================
# ポケモン風ランク定義（TOEIC 700点までに制限）
RANK_MAP = {
    "モンスターボール級 (基礎: 400点)": "TOEIC score 350-450 level (Basic)",
    "スーパーボール級 (応用: 550点)": "TOEIC score 500-600 level (Intermediate)",
    "ハイパーボール級 (実戦: 700点)": "TOEIC score 600-700 level (Upper-Intermediate)",
    "マスターボール級 (難関: 700点+)": "TOEIC score 700-750 level (Advanced)"
}

try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except:
    st.error("Secretsの設定を確認してください。")
    st.stop()

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ==========================================
# 2. AI & DB関数
# ==========================================

def generate_quiz_words(api_key, rank_prompt):
    """AIに単語リストを作らせる"""
    if not api_key:
        # ★変更点: APIなし時の予備データをTOEIC単語8個に変更
        return [
            {"en": "Strategy",   "jp": "戦略"},
            {"en": "Efficiency", "jp": "効率"},
            {"en": "Deadline",   "jp": "締め切り"},
            {"en": "Negotiate",  "jp": "交渉する"},
            {"en": "Inquiry",    "jp": "問い合わせ"},
            {"en": "Expand",     "jp": "拡大する"},
            {"en": "Launch",     "jp": "立ち上げる/発売"},
            {"en": "Budget",     "jp": "予算"}
        ]

    client = genai.Client(api_key=api_key)
    
    # ★変更点: Generate 8 unique words
    prompt = f"""
    Generate 8 unique English vocabulary words specifically for {rank_prompt}.
    The words should be commonly found in TOEIC tests but NOT exceeding the 750 score level.
    Output MUST be a valid JSON list of objects with 'en' (English word) and 'jp' (Japanese meaning).
    Example: [{{"en": "Profit", "jp": "利益"}}, {{"en": "Hire", "jp": "雇う"}}]
    Just the raw JSON string.
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except:
        return [{"en": "Error", "jp": "エラー"}]

def get_english_story(api_key, words):
    """英語の物語生成"""
    if not api_key: return "Story generation skipped (No API Key)."
    
    client = genai.Client(api_key=api_key)
    prompt = f"Write a very short Pokémon-style adventure story in English using: {', '.join(words)}. Highlight words in **bold**."
    try:
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text
    except:
        return "Failed to generate story."

def save_mistake(en, jp):
    """間違えた単語をDBに保存"""
    try:
        chk = supabase.table("mistaken_words").select("id").eq("word_en", en).execute()
        if not chk.data:
            supabase.table("mistaken_words").insert({"word_en": en, "word_jp": jp}).execute()
    except:
        pass

def get_mistakes_count():
    try:
        res = supabase.table("mistaken_words").select("id", count="exact").execute()
        return res.count
    except:
        return 0

# ==========================================
# 3. ゲームロジック
# ==========================================
def init_game(word_list, time_limit):
    """ゲームの初期化"""
    cards = []
    for item in word_list:
        cards.append({"id": item["en"], "text": item["en"], "pair": item["jp"], "is_jp": False})
        cards.append({"id": item["en"], "text": item["jp"], "pair": item["en"], "is_jp": True})
    random.shuffle(cards)
    
    st.session_state.cards = cards
    st.session_state.flipped = []
    st.session_state.matched = set()
    st.session_state.collected_now = [] 
    st.session_state.mistakes_now = []  
    
    st.session_state.start_time = time.time()
    st.session_state.time_limit = time_limit
    st.session_state.game_state = "PLAYING"

# ==========================================
# 4. アプリ本体
# ==========================================
def main():
    st.set_page_config(page_title="Pokémon English Battle", layout="wide")
    
    # --- サイドバー ---
    st.sidebar.title("⚙️ トレーナー設定")
    api_key = st.sidebar.text_input("Gemini API Key", type="password")
    selected_rank_name = st.sidebar.selectbox("挑戦するランク", list(RANK_MAP.keys()))
    
    st.sidebar.divider()
    m_count = get_mistakes_count()
    st.sidebar.error(f"💀 苦手な単語: {m_count} 語")
    
    # --- メイン画面 ---
    st.title("◓ ポケモン英単語バトル")
    
    if "game_state" not in st.session_state:
        st.session_state.game_state = "IDLE"

    # ==========================
    # A. スタート画面
    # ==========================
    if st.session_state.game_state == "IDLE":
        st.write(f"**{selected_rank_name}** の野生の単語が現れた！(8匹)")
        if st.button("バトル開始！ (Start)", type="primary"):
            with st.spinner("草むらから単語を探しています..."):
                quiz_data = generate_quiz_words(api_key, RANK_MAP[selected_rank_name])
                # ★変更点: 制限時間を30秒に設定
                init_game(quiz_data, 30) 
                st.rerun()

    # ==========================
    # B. プレイ中 (通常 & エキストラ共通)
    # ==========================
    elif st.session_state.game_state in ["PLAYING", "EXTRA"]:
        if st.session_state.game_state == "EXTRA":
            st.warning("🔥 エキストラステージ（復習モード）")
        
        elapsed = time.time() - st.session_state.start_time
        remaining = st.session_state.time_limit - elapsed
        
        if remaining <= 0:
            st.session_state.game_state = "FINISHED"
            st.rerun()

        st.progress(max(0.0, remaining / st.session_state.time_limit))
        st.caption(f"残り時間: {remaining:.1f}秒")

        # カード表示 (4列 x 4行 = 16枚)
        cols = st.columns(4)
        for i, card in enumerate(st.session_state.cards):
            # 状態判定
            is_matched = card["id"] in st.session_state.matched
            is_flipped = i in st.session_state.flipped
            
            # ラベルとスタイルの決定
            if is_matched:
                label = f"✨ {card['text']}" 
            elif is_flipped:
                label = card["text"] # めくったカード
            else:
                label = "◓" # 裏面

            with cols[i % 4]:
                #

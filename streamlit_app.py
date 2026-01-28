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
        # APIなし時の予備データ (TOEIC単語8個)
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
        cards.append({"id": item["en"], "text": item["jp"], "pair": item["

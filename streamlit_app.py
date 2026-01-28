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
    """英語の物語生成 (シンプル版)"""
    # APIキーがない場合の予備ストーリー（英語）
    if not api_key: 
        return """
        (Demo Story without AI)
        Once upon a time, a young trainer went on a journey to find new words.
        He found a **Strategy** to catch them all.
        The **Deadline** was approaching, but he did not give up.
        Finally, he managed to **Expand** his collection and became a master!
        """
    
    client = genai.Client(api_key=api_key)
    
    # ★修正点: シンプルな英語を指定
    prompt = f"""
    Write a short and **simple** Pokémon-style adventure story in English using these words: {', '.join(words)}.
    The English level should be easy to read (suitable for TOEIC 600 learners).
    Highlight the used words in **bold**.
    Keep it under 100 words.
    """
    
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
        # 英語カード
        cards.append({"id": item["en"], "text": item["en"], "pair": item["jp"], "is_jp": False})
        # 日本語カード
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
                label = card["text"] 
            else:
                label = "◓" 

            with cols[i % 4]:
                if st.button(label, key=f"btn_{i}", disabled=is_matched):
                    if not is_flipped and len(st.session_state.flipped) < 2:
                        st.session_state.flipped.append(i)
                        st.rerun()

        # 判定ロジック
        if len(st.session_state.flipped) == 2:
            idx1, idx2 = st.session_state.flipped
            c1 = st.session_state.cards[idx1]
            c2 = st.session_state.cards[idx2]

            if c1["id"] == c2["id"]:
                st.toast(f"Gotcha! {c1['id']} をゲット！")
                st.session_state.matched.add(c1["id"])
                
                if c1["id"] not in st.session_state.collected_now:
                    st.session_state.collected_now.append(c1["id"])
                
                st.session_state.flipped = []
                
                if len(st.session_state.matched) * 2 == len(st.session_state.cards):
                    st.session_state.game_state = "FINISHED"
                    st.rerun()
                
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(f"ああっ！逃げられた... ({c1['text']} ≠ {c2['text']})")
                
                en_txt = c1["id"]
                jp_txt = c1["pair"] if not c1["is_jp"] else c1["text"]
                save_mistake(en_txt, jp_txt)
                
                mistake_obj = {"en": en_txt, "jp": jp_txt}
                if not any(m["en"] == en_txt for m in st.session_state.mistakes_now):
                    st.session_state.mistakes_now.append(mistake_obj)

                time.sleep(1.0)
                st.session_state.flipped = []
                st.rerun()

    # ==========================
    # C. 結果画面
    # ==========================
    elif st.session_state.game_state == "FINISHED":
        st.header("🏆 バトル終了！")
        
        if st.session_state.collected_now:
            st.success(f"ゲットした単語: {', '.join(st.session_state.collected_now)}")
            
            st.divider()
            st.subheader("📖 冒険の記録 (AI Story)")
            # ★ここで物語を生成します
            if st.button("記録を書く (Generate English Story)"):
                with st.spinner("レポート作成中 (Writing simple story)..."):
                    story = get_english_story(api_key, st.session_state.collected_now)
                    st.info(story)
        else:
            st.warning("単語を一匹も捕まえられなかった...")

        st.divider()

        mistakes = st.session_state.mistakes_now
        if mistakes:
            st.error(f"今回のミス: {len(mistakes)} 匹")
            for m in mistakes:
                st.text(f"・{m['en']} : {m['jp']}")
            
            if st.button("🔥 エキストラステージで捕まえ直す！"):
                init_game(mistakes, 30) 
                st.session_state.game_state = "EXTRA"
                st.rerun()
        else:
            st.balloons()
            st.success("素晴らしい！ノーミスでクリアだ！")

        if st.button("次の町へ進む (New Game)"):
            st.session_state.game_state = "IDLE"
            st.rerun()

if __name__ == "__main__":
    main()

import streamlit as st
from supabase import create_client

st.title("🏥 Supabase 接続診断ツール")

# 1. ライブラリチェック
st.write("1. ライブラリ読み込み: OK")

# 2. Secretsチェック
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    st.success(f"2. Secrets読み込み: OK (URL: {url[:8]}...)")
except Exception as e:
    st.error(f"2. Secrets読み込み: 失敗 ({e})")
    st.stop()

# 3. 接続チェック
try:
    supabase = create_client(url, key)
    st.success("3. クライアント作成: OK")
except Exception as e:
    st.error(f"3. クライアント作成: 失敗 ({e})")
    st.stop()

# 4. データ取得チェック
st.write("---")
st.write("4. データベース接続テスト...")

try:
    # collected_words テーブルへのアクセス
    response = supabase.table("collected_words").select("*", count="exact").limit(1).execute()
    st.success(f"✅ 'collected_words' テーブル: 接続成功 (現在のデータ数: {response.count})")
except Exception as e:
    st.error(f"❌ 'collected_words' テーブル: エラー\n\n{e}")

try:
    # mistaken_words テーブルへのアクセス
    response = supabase.table("mistaken_words").select("*", count="exact").limit(1).execute()
    st.success(f"✅ 'mistaken_words' テーブル: 接続成功 (現在のデータ数: {response.count})")
except Exception as e:
    st.error(f"❌ 'mistaken_words' テーブル: エラー\n\n{e}")

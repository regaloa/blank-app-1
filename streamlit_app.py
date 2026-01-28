import streamlit as st
import random
import time
from google import genai
from supabase import create_client, Client

# ==========================================
# 1. Supabase 接続設定
# ==========================================
# secretsから情報を読み込む
try:
    SUPABASE_URL = st.secrets["supabase"]["url"]
    SUPABASE_KEY = st.secrets["supabase"]["key"]
except Exception:
    st.error("SecretsにSupabaseの設定が見つかりません。")
    st.stop()

# クライアントの作成（キャッシュして高速化）
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# --- DB操作用関数 ---

def save_word_to_db(en, jp):
    """単語をDBに保存する"""
    try:
        # 重複チェック（既に持っているか？）
        existing = supabase.table("collected_words").select("*").eq("word_en", en).execute()
        if not existing.data:
            supabase.table("collected_words").insert({"word_en": en, "word_jp": jp}).execute()
    except Exception as e:
        st.error(f"DB保存エラー: {e}")

def get_all_collected_words():
    """DBから獲得済み単語リストを取得する"""
    try:
        response = supabase.table("collected_words").select("word_en").execute()
        # リスト形式にして返す ['Apple', 'Dog', ...]
        return [row['word_en'] for row in response.data]
    except Exception as e:
        st.error(f"DB読み込みエラー: {e}")
        return []

# ==========================================
# 2. データ定義 & AI設定
# ==========================================
VOCAB_DB = {
    "Level 1": [{"en": "Profit", "jp": "利益"}, {"en": "Hire", "jp": "雇う"}, {"en": "Bill", "jp": "請求書"}],
    "Level 2": [{"en": "Refund", "jp": "返金"}, {"en": "Agenda", "jp": "議題"}, {"en": "Supply", "jp": "備品"}],
    # 必要に応じて増やしてください
}

def get_ai_story(api_key, words):
    """AIで物語を作成（前回と同じ）"""
    if not api_key:
        return "API Keyを設定すると、ここにAIが書いた物語が表示されます。"
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"以下の英単語を使って短い物語（英語）を作って: {', '.join(words)}"
        response = client.models.generate_content(model="gemini-1.5-flash", contents=prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

# ==========================================
# 3. ゲームロジック
# ==========================================

def init_game(word_list_data, time_limit):
    """ゲームの初期化"""
    cards = []
    for item in word_list_data:
        cards.append({"id": item["en"], "text": item["en"], "pair": item["jp"], "is_jp": False})
        cards.append({"id": item["en"], "text": item["jp"], "pair": item["en"], "is_jp": True})
    
    random.shuffle(cards)
    
    st.session_state.cards = cards
    st.session_state.flipped = []
    st.session_state.matched_ids = set()
    st.session_state.start_time = time.time()
    st.session_state.time_limit = time_limit
    st.session_state.game_over = False

# ==========================================
# 4. メインアプリ
# ==========================================
def main():
    st.set_page_config(page_title="Supabase English Game")
    st.title("🗄️ 永続化対応：英単語バトル")

    # サイドバー設定
    api_key = st.sidebar.text_input("Gemini API Key", type="password")
    level = st.sidebar.selectbox("Level", list(VOCAB_DB.keys()))
    
    # DBから「これまでに集めた単語数」を表示
    db_words = get_all_collected_words()
    st.sidebar.divider()
    st.sidebar.metric("🏆 通算獲得単語数", f"{len(db_words)} 語")
    if db_words:
        with st.sidebar.expander("図鑑を見る"):
            st.write(", ".join(db_words))

    if st.sidebar.button("ゲームスタート"):
        init_game(VOCAB_DB[level], 30) # 制限時間は30秒固定
        st.session_state.game_active = True
        st.rerun()

    # --- ゲーム画面 ---
    if "game_active" in st.session_state and st.session_state.game_active:
        
        # 時間管理
        elapsed = time.time() - st.session_state.start_time
        remaining = st.session_state.time_limit - elapsed

        if remaining <= 0:
            st.error("⏰ タイムアップ！")
            st.session_state.game_active = False
            st.rerun()
        
        st.progress(max(0.0, remaining / st.session_state.time_limit))

        # カード表示
        cols = st.columns(4)
        for i, card in enumerate(st.session_state.cards):
            is_matched = card["id"] in st.session_state.matched_ids
            is_flipped = i in st.session_state.flipped
            
            label = card["text"] if (is_matched or is_flipped) else "❓"
            
            with cols[i % 4]:
                if st.button(label, key=f"c_{i}", disabled=(is_matched or is_flipped)):
                    st.session_state.flipped.append(i)
                    st.rerun()

        # 判定
        if len(st.session_state.flipped) == 2:
            idx1, idx2 = st.session_state.flipped
            c1 = st.session_state.cards[idx1]
            c2 = st.session_state.cards[idx2]

            if c1["id"] == c2["id"]:
                st.toast(f"Get! {c1['id']}")
                st.session_state.matched_ids.add(c1["id"])
                
                # ★ ここでSupabaseに保存！ ★
                # 英語の方のテキストを取得して保存
                en_text = c1["id"]
                jp_text = c1["pair"] if not c1["is_jp"] else c1["text"]
                save_word_to_db(en_text, jp_text)
                
                st.session_state.flipped = []
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("ミス！")
                time.sleep(1)
                st.session_state.flipped = []
                st.rerun()

    # --- ゲーム外（物語生成エリア） ---
    else:
        st.info("左のサイドバーからゲームを開始してください。")
        
        st.divider()
        st.subheader("📖 獲得した単語で物語を作る")
        if len(db_words) > 0:
            st.write(f"現在の持ち単語: {', '.join(db_words)}")
            if st.button("AIで物語を生成する"):
                story = get_ai_story(api_key, db_words)
                st.success(story)
        else:
            st.warning("まだ単語を持っていません。ゲームで獲得しましょう！")

if __name__ == "__main__":
    main()

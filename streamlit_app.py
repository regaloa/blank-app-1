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
# ポケモン風ランク定義
RANK_MAP = {
    "モンスターボール級 (初級)": "TOEIC 300-450 level",
    "スーパーボール級 (中級)": "TOEIC 500-700 level",
    "ハイパーボール級 (上級)": "TOEIC 750-900 level",
    "マスターボール級 (超上級)": "TOEIC 900+ level, business executive words"
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
        # キーなし時の予備データ
        return [{"en": "Pikachu", "jp": "ピカチュウ"}, {"en": "Thunder", "jp": "雷"}, {"en": "Battle", "jp": "戦う"}]

    client = genai.Client(api_key=api_key)
    
    prompt = f"""
    Generate 6 unique English vocabulary words for {rank_prompt}.
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
    """【新機能】間違えた単語をDBに保存"""
    try:
        # 重複チェック
        chk = supabase.table("mistaken_words").select("id").eq("word_en", en).execute()
        if not chk.data:
            supabase.table("mistaken_words").insert({"word_en": en, "word_jp": jp}).execute()
    except:
        pass

def get_mistakes_count():
    """保存された間違い単語数を取得"""
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
    st.session_state.collected_now = [] # 今回ゲットした単語
    st.session_state.mistakes_now = []  # ★今回間違えた単語リスト（復習ステージ用）
    
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
    
    # ランク選択
    selected_rank_name = st.sidebar.selectbox("挑戦するランク", list(RANK_MAP.keys()))
    
    # DB情報の表示
    st.sidebar.divider()
    m_count = get_mistakes_count()
    st.sidebar.error(f"💀 苦手な単語: {m_count} 語")
    
    # --- メイン画面 ---
    st.title("◓ ポケモン英単語バトル")
    
    # セッション管理
    if "game_state" not in st.session_state:
        st.session_state.game_state = "IDLE"

    # ==========================
    # A. スタート画面
    # ==========================
    if st.session_state.game_state == "IDLE":
        st.write(f"**{selected_rank_name}** の野生の単語が現れた！")
        if st.button("バトル開始！ (Start)", type="primary"):
            with st.spinner("草むらから単語を探しています..."):
                # AIから単語ゲット
                quiz_data = generate_quiz_words(api_key, RANK_MAP[selected_rank_name])
                init_game(quiz_data, 45) # 45秒
                st.rerun()

    # ==========================
    # B. プレイ中 (通常 & エキストラ共通)
    # ==========================
    elif st.session_state.game_state in ["PLAYING", "EXTRA"]:
        # ヘッダー表示（モードによって変える）
        if st.session_state.game_state == "EXTRA":
            st.warning("🔥 エキストラステージ（復習モード）")
        
        # 時間管理
        elapsed = time.time() - st.session_state.start_time
        remaining = st.session_state.time_limit - elapsed
        
        if remaining <= 0:
            st.session_state.game_state = "FINISHED"
            st.rerun()

        # プログレスバー
        st.progress(max(0.0, remaining / st.session_state.time_limit))
        st.caption(f"残り時間: {remaining:.1f}秒")

        # カード表示
        cols = st.columns(4)
        for i, card in enumerate(st.session_state.cards):
            is_open = (i in st.session_state.flipped) or (card["id"] in st.session_state.matched)
            
            # アイコン設定
            if card["id"] in st.session_state.matched:
                label = f"✨ {card['text']}" # ゲット済み
            else:
                label = card["text"] if is_open else "◓" # 裏面はボール
            
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
                # 正解！
                st.toast(f"Gotcha! {c1['id']} をゲット！")
                st.session_state.matched.add(c1["id"])
                
                # ゲットリストに追加
                if c1["id"] not in st.session_state.collected_now:
                    st.session_state.collected_now.append(c1["id"])
                
                st.session_state.flipped = []
                
                # 全クリア判定
                if len(st.session_state.matched) * 2 == len(st.session_state.cards):
                    st.session_state.game_state = "FINISHED"
                    st.rerun()
                
                time.sleep(0.5)
                st.rerun()
            else:
                # 不正解（ミス）
                st.error(f"ああっ！逃げられた... ({c1['text']} ≠ {c2['text']})")
                
                # ★ここで間違いDBに保存
                en_txt = c1["id"]
                jp_txt = c1["pair"] if not c1["is_jp"] else c1["text"]
                save_mistake(en_txt, jp_txt)
                
                # ★復習リストにも追加（エキストラステージ用）
                mistake_obj = {"en": en_txt, "jp": jp_txt}
                # すでにリストになければ追加
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
        
        # ゲットした単語
        if st.session_state.collected_now:
            st.success(f"ゲットした単語: {', '.join(st.session_state.collected_now)}")
            
            st.divider()
            st.subheader("📖 冒険の記録 (AI Story)")
            if st.button("記録を書く (Generate Story)"):
                with st.spinner("レポート作成中..."):
                    story = get_english_story(api_key, st.session_state.collected_now)
                    st.info(story)
        else:
            st.warning("単語を一匹も捕まえられなかった...")

        st.divider()

        # ★ エキストラステージへの誘導
        mistakes = st.session_state.mistakes_now
        if mistakes:
            st.error(f"今回のミス: {len(mistakes)} 匹")
            # ミスした単語の表示
            for m in mistakes:
                st.text(f"・{m['en']} : {m['jp']}")
            
            if st.button("🔥 エキストラステージで捕まえ直す！"):
                # 間違えた単語だけでゲームを再構成
                init_game(mistakes, 30) # 時間は少し短めに
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

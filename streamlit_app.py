import streamlit as st
import random
import time
import json
import requests
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
# 2. 外部API関数 (音声, PokeAPI, AI)
# ==========================================

def play_pronunciation(text):
    """【修正版】Streamlit公式プレイヤーで再生"""
    # Googleの音声URL
    sound_url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&q={text}&tl=en"
    # プレイヤーを表示して自動再生 (autoplay=True)
    # ※ブラウザによっては初回のみ手動で再生ボタンを押す必要があります
    st.audio(sound_url, format='audio/mp3', autoplay=True)

def get_random_pokemon_image(rank_index):
    """PokeAPIを使ってポケモンの画像をランダムに取得"""
    try:
        if rank_index == 0:
            poke_id = random.randint(1, 151)
        elif rank_index == 1:
            poke_id = random.randint(152, 251)
        elif rank_index == 2:
            poke_id = random.randint(252, 386)
        else:
            poke_id = random.randint(387, 1000) 

        url = f"https://pokeapi.co/api/v2/pokemon/{poke_id}"
        res = requests.get(url)
        data = res.json()
        img_url = data["sprites"]["front_default"]
        return img_url
    except:
        return None

def generate_quiz_words(api_key, rank_prompt):
    """AIに単語リストを作らせる"""
    if not api_key:
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
    if not api_key: 
        return """(Demo Story skipped)"""
    
    client = genai.Client(api_key=api_key)
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

# --- DB操作関連 ---

def save_mistake(en, jp):
    """間違えた単語をDBに保存"""
    try:
        chk = supabase.table("mistaken_words").select("id").eq("word_en", en).execute()
        if not chk.data:
            supabase.table("mistaken_words").insert({"word_en": en, "word_jp": jp}).execute()
    except:
        pass

def increment_correct_count(en):
    """正解数を+1"""
    try:
        res = supabase.table("mistaken_words").select("correct_count").eq("word_en", en).execute()
        if res.data:
            current = res.data[0]["correct_count"]
            new_val = current + 1
            supabase.table("mistaken_words").update({"correct_count": new_val}).eq("word_en", en).execute()
            return new_val
    except:
        pass
    return 0

def delete_mistake(en):
    """DBから削除"""
    try:
        supabase.table("mistaken_words").delete().eq("word_en", en).execute()
    except:
        pass

def get_mistakes_count():
    try:
        res = supabase.table("mistaken_words").select("id", count="exact").execute()
        return res.count
    except:
        return 0

def fetch_revenge_words(limit=8):
    """間違い単語を取得"""
    try:
        res = supabase.table("mistaken_words").select("*").execute()
        data = res.data
        if not data:
            return []
        
        random.shuffle(data)
        selected = data[:limit]
        return [{"en": item["word_en"], "jp": item["word_jp"], "count": item["correct_count"]} for item in selected]
    except:
        return []

# ==========================================
# 3. ゲームロジック
# ==========================================
def init_game(word_list, time_limit, mode="NORMAL", poke_img=None):
    cards = []
    for item in word_list:
        current_count = item.get("count", 0)
        cards.append({"id": item["en"], "text": item["en"], "pair": item["jp"], "is_jp": False, "count": current_count})
        cards.append({"id": item["en"], "text": item["jp"], "pair": item["en"], "is_jp": True, "count": current_count})
    
    random.shuffle(cards)
    
    st.session_state.cards = cards
    st.session_state.flipped = []
    st.session_state.matched = set()
    st.session_state.collected_now = [] 
    st.session_state.mistakes_now = []
    st.session_state.mastered_pending = []
    st.session_state.current_mode = mode
    st.session_state.current_poke_img = poke_img
    
    st.session_state.start_time = time.time()
    st.session_state.time_limit = time_limit
    st.session_state.game_state = "PLAYING"
    st.session_state.last_matched_word = None

# ==========================================
# 4. アプリ本体
# ==========================================
def main():
    st.set_page_config(page_title="Pokémon English Battle", layout="wide")
    
    # --- サイドバー ---
    st.sidebar.title("⚙️ トレーナー設定")
    api_key = st.sidebar.text_input("Gemini API Key", type="password")
    
    rank_keys = list(RANK_MAP.keys())
    rank_options = rank_keys + ["🔥 復習モード (Revenge)"]
    selected_rank_name = st.sidebar.selectbox("挑戦するランク", rank_options)
    
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
        if "復習モード" in selected_rank_name:
            if m_count == 0:
                st.info("復習する単語はありません！素晴らしい！")
            else:
                st.write(f"過去に逃げられた **{m_count}** 匹の単語が待っている...")
                if st.button("リベンジバトル開始！", type="primary"):
                    revenge_words = fetch_revenge_words(8)
                    if not revenge_words:
                        st.error("データの取得に失敗しました。")
                    else:
                        init_game(revenge_words, 40, mode="REVENGE", poke_img="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/132.png")
                        st.rerun()
        else:
            st.write(f"**{selected_rank_name}** の野生の単語が現れた！(8匹)")
            if st.button("バトル開始！ (Start)", type="primary"):
                with st.spinner("草むらから単語を探しています..."):
                    rank_idx = rank_keys.index(selected_rank_name)
                    poke_img = get_random_pokemon_image(rank_idx)
                    quiz_data = generate_quiz_words(api_key, RANK_MAP[selected_rank_name])
                    init_game(quiz_data, 30, mode="NORMAL", poke_img=poke_img) 
                    st.rerun()

    # ==========================
    # B. プレイ中
    # ==========================
    elif st.session_state.game_state == "PLAYING":
        col_info, col_img = st.columns([3, 1])
        with col_info:
            if st.session_state.current_mode == "REVENGE":
                st.warning("🔥 REVENGE BATTLE: 10回正解で卒業！")
            else:
                st.info("野生の 英単語モンスター が勝負を仕掛けてきた！")
                
            elapsed = time.time() - st.session_state.start_time
            remaining = st.session_state.time_limit - elapsed
            st.progress(max(0.0, remaining / st.session_state.time_limit))
            st.caption(f"残り時間: {remaining:.1f}秒")
        
        with col_img:
            if st.session_state.current_poke_img:
                st.image(st.session_state.current_poke_img, width=120)
            else:
                st.write("👻")

        # ★ 音声再生 (見えるプレイヤーを表示)
        if st.session_state.last_matched_word:
            st.success(f"Nice! 🔊 {st.session_state.last_matched_word}")
            play_pronunciation(st.session_state.last_matched_word)
            st.session_state.last_matched_word = None

        if remaining <= 0:
            st.session_state.game_state = "FINISHED"
            st.rerun()

        cols = st.columns(4)
        for i, card in enumerate(st.session_state.cards):
            is_matched = card["id"] in st.session_state.matched
            is_flipped = i in st.session_state.flipped
            
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

        if len(st.session_state.flipped) == 2:
            idx1, idx2 = st.session_state.flipped
            c1 = st.session_state.cards[idx1]
            c2 = st.session_state.cards[idx2]

            if c1["id"] == c2["id"]:
                st.toast(f"Gotcha! {c1['id']}")
                st.session_state.matched.add(c1["id"])
                
                # 正解時に再生する単語をセット
                st.session_state.last_matched_word = c1["id"]
                
                if c1["id"] not in st.session_state.collected_now:
                    st.session_state.collected_now.append(c1["id"])
                    if st.session_state.current_mode == "REVENGE":
                        new_count = increment_correct_count(c1["id"])
                        if new_count >= 10:
                            st.session_state.mastered_pending.append(c1["id"])
                
                st.session_state.flipped = []
                
                if len(st.session_state.matched) * 2 == len(st.session_state.cards):
                    st.session_state.game_state = "FINISHED"
                    st.rerun()
                
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(f"ああっ！逃げられた！ ({c1['text']} ≠ {c2['text']})")
                
                if st.session_state.current_mode == "NORMAL":
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
        
        if st.session_state.current_poke_img:
            st.image(st.session_state.current_poke_img, width=100)

        if st.session_state.collected_now:
            msg = "復習完了！" if st.session_state.current_mode == "REVENGE" else "ゲットした単語"
            st.success(f"{msg}: {', '.join(st.session_state.collected_now)}")
            
            st.divider()
            st.subheader("📖 冒険の記録 (AI Story)")
            if st.button("記録を書く (Generate English Story)"):
                with st.spinner("Writing story..."):
                    story = get_english_story(api_key, st.session_state.collected_now)
                    st.info(story)
        else:
            st.warning("単語を一匹も捕まえられなかった...")

        st.divider()

        pending = st.session_state.mastered_pending
        if pending:
            st.success(f"🎉 おめでとう！ 以下の単語は正解数が10回に達しました！")
            st.write(f"卒業候補: {', '.join(pending)}")
            
            col_del1, col_del2 = st.columns(2)
            with col_del1:
                if st.button("✅ リストから削除して卒業させる"):
                    for w in pending:
                        delete_mistake(w)
                    st.balloons()
                    st.success("卒業しました！")
                    st.session_state.mastered_pending = []
                    time.sleep(2)
                    st.rerun()
            with col_del2:
                if st.button("残しておく"):
                    st.info("リストに残しました。")
                    st.session_state.mastered_pending = []
                    st.rerun()
            st.divider()

        mistakes = st.session_state.mistakes_now
        if mistakes and st.session_state.current_mode == "NORMAL":
            st.error(f"今回のミス: {len(mistakes)} 匹")
            for m in mistakes:
                st.text(f"・{m['en']} : {m['jp']}")
            
            if st.button("🔥 すぐに復習する (Quick Revenge)"):
                init_game(mistakes, 30, mode="REVENGE", poke_img=st.session_state.current_poke_img) 
                st.rerun()
        
        if st.button("タイトルに戻る (Back to Title)"):
            st.session_state.game_state = "IDLE"
            st.rerun()

if __name__ == "__main__":
    main()

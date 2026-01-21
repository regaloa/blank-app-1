import streamlit as st
import random
import time

# --- 設定: 単語リスト (ID, 英単語, 日本語) ---
# ポケモンに関連しそうな単語を選んでみました
WORDS_DATA = [
    {"id": 1, "en": "Thunder", "jp": "雷"},
    {"id": 2, "en": "Water",   "jp": "水"},
    {"id": 3, "en": "Escape",  "jp": "逃げる"},
    {"id": 4, "en": "Battle",  "jp": "戦う"},
    {"id": 5, "en": "Friend",  "jp": "友達"},
    {"id": 6, "en": "Legend",  "jp": "伝説"},
]

# --- 関数: ゲームの初期化 ---
def init_game():
    # カードを生成（英単語カードと日本語カードのペアを作る）
    cards = []
    for item in WORDS_DATA:
        cards.append({"id": item["id"], "text": item["en"], "type": "en", "pair_word": item["en"]})
        cards.append({"id": item["id"], "text": item["jp"], "type": "jp", "pair_word": item["en"]})
    
    random.shuffle(cards)
    
    st.session_state.cards = cards
    st.session_state.flipped = []  # 現在めくられているカードのインデックス
    st.session_state.matched = []  # すでに揃ったカードのID
    st.session_state.collected_words = [] # 集めた英単語リスト
    st.session_state.game_over = False

# --- 関数: 物語生成 (テンプレート式) ---
def generate_story(words):
    if not words:
        return "まだ言葉を見つけていない..."
    
    # 手に入れた単語を物語に埋め込む
    story_template = [
        f"ある日、サトシは野生の **{random.choice(words)}** に出会った。",
        f"しかし、モンスターボールが **{random.choice(words)}** してしまった！",
        f"ピカチュウは **{random.choice(words)}** 技を繰り出した！",
        f"こうして二人は **{random.choice(words)}** な関係になったのだ。",
        f"旅の目的は、真の **{random.choice(words)}** を見つけることだ。"
    ]
    return " ".join(story_template)

# --- メイン処理 ---
def main():
    st.title("🎴 ポケモン英単語・神経衰弱")
    st.caption("カードを揃えて単語を集め、冒険の物語を完成させよう！")

    # 初回起動時またはリセット時に初期化
    if "cards" not in st.session_state:
        init_game()

    # リセットボタン
    if st.sidebar.button("ゲームをリセット"):
        init_game()
        st.rerun()

    # --- ゲーム盤面の表示 ---
    # Streamlitでグリッド表示 (4列で表示)
    cols = st.columns(4)
    
    for i, card in enumerate(st.session_state.cards):
        # カードの状態判定
        is_matched = card["id"] in st.session_state.matched
        is_flipped = i in st.session_state.flipped
        
        # ボタンのラベル決定（めくれているか、揃っていれば中身を表示。そうでなければ「?」）
        if is_matched or is_flipped:
            label = card["text"]
            disabled = True # めくれたら押せないようにする（またはマッチしたら無効化）
            if is_matched:
                button_style = "✅" # 揃ったマーク
            else:
                button_style = "" 
        else:
            label = "❓"
            disabled = False
            button_style = ""

        # カードボタンの配置
        with cols[i % 4]:
            # マッチしたカードは無効化ボタンとして表示、それ以外は通常ボタン
            if is_matched:
                st.success(f"{label}")
            elif is_flipped:
                st.warning(f"{label}")
            else:
                if st.button(label, key=f"card_{i}"):
                    # カードをめくる処理
                    st.session_state.flipped.append(i)
                    st.rerun()

    # --- 判定ロジック ---
    if len(st.session_state.flipped) == 2:
        idx1 = st.session_state.flipped[0]
        idx2 = st.session_state.flipped[1]
        card1 = st.session_state.cards[idx1]
        card2 = st.session_state.cards[idx2]

        # IDが一致するかチェック
        if card1["id"] == card2["id"]:
            st.toast(f"⭕ 正解！ '{card1['pair_word']}' をゲット！")
            st.session_state.matched.append(card1["id"])
            st.session_state.collected_words.append(card1["pair_word"])
            st.session_state.flipped = [] # めくり状態をリセット
            time.sleep(1) # 少し待ってから反映
            st.rerun()
        else:
            st.error("❌ 残念... 違います")
            # ユーザーが結果を見るために少し待機させてからリセットするためのボタン
            if st.button("次へ"):
                st.session_state.flipped = []
                st.rerun()

    # --- ゲームクリア＆物語生成エリア ---
    st.divider()
    st.subheader("📖 冒険の記録")
    
    # 獲得した単語の表示
    if st.session_state.collected_words:
        st.write(f"獲得した単語: {', '.join(st.session_state.collected_words)}")
    
    # 全ペア揃ったら物語を表示
    if len(st.session_state.matched) == len(WORDS_DATA):
        st.balloons()
        st.success("🎉 全問正解！物語が生成されます...")
        
        story = generate_story(st.session_state.collected_words)
        
        st.markdown(f"""
        ### 生成された物語
        > {story}
        """)
        
        if st.button("別の物語を作る"):
            st.rerun()
    else:
        st.info("すべてのカードを揃えると、集めた単語で物語が作られます！")

if __name__ == "__main__":
    main()
    

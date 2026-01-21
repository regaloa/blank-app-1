import streamlit as st
import random
import time
from google import genai
from google.genai import types

# ==========================================
# 1. データ: TOEIC 700点突破用 単語リスト
# ==========================================
VOCAB_DB = {
    "Level 1 (Basic)": [
        {"en": "Profit", "jp": "利益"},
        {"en": "Hire",   "jp": "雇う"},
        {"en": "Branch", "jp": "支店"},
        {"en": "Order",  "jp": "注文"},
        {"en": "Bill",   "jp": "請求書"},
        {"en": "Delay",  "jp": "遅延"},
    ],
    "Level 2 (Intermediate)": [
        {"en": "Refund", "jp": "返金"},
        {"en": "Agenda", "jp": "議題"},
        {"en": "Resume", "jp": "履歴書"},
        {"en": "Confirm","jp": "確認する"},
        {"en": "Supply", "jp": "供給/備品"},
        {"en": "Launch", "jp": "発売する"},
    ],
    "Level 3 (Advanced)": [
        {"en": "Inquiry",    "jp": "問い合わせ"},
        {"en": "Quarter",    "jp": "四半期"},
        {"en": "Warranty",   "jp": "保証"},
        {"en": "Deadline",   "jp": "締め切り"},
        {"en": "Proposal",   "jp": "提案"},
        {"en": "Executive",  "jp": "重役"},
    ],
    "Level 4 (Master)": [
        {"en": "Negotiation", "jp": "交渉"},
        {"en": "Incentive",   "jp": "報奨金"},
        {"en": "Merger",      "jp": "合併"},
        {"en": "Preliminary", "jp": "予備の"},
        {"en": "Subsequent",  "jp": "その後の"},
        {"en": "Mandatory",   "jp": "必須の"},
    ]
}

# ==========================================
# 2. 関数: AI物語生成 (最新版 google-genai 使用)
# ==========================================

def get_ai_story(api_key, words):
    """
    最新のSDKを使って英語の物語を生成する
    """
    if not api_key:
        return "⚠️ Please set your API Key in the sidebar to generate a story.\n\n" + \
               generate_dummy_story(words)
    
    try:
        # 最新のクライアント初期化
        client = genai.Client(api_key=api_key)
        
        word_list_str = ", ".join(words)
        
        # プロンプト：英語で物語を書くように指示
        prompt = f"""
        Write a short, creative, and funny adventure story in English using ALL of the following words.
        Highlight the used words in bold (e.g., **Word**).
        The story should be simple and easy to read for an English learner.
        
        Words to use: {word_list_str}
        """
        
        with st.spinner("AI is writing a story for you..."):
            # モデル指定 (gemini-1.5-flash は高速で安定しています)
            response = client.models.generate_content(
                model="gemini-1.5-flash", 
                contents=prompt
            )
            return response.text
            
    except Exception as e:
        return f"Error: {e}\n\n" + generate_dummy_story(words)

def generate_dummy_story(words):
    """APIキーがない場合の予備テンプレート"""
    if not words: return "No words collected..."
    word = random.choice(words) if words else "Something"
    return f"Once upon a time, a hero found a **{word}**. To be continued... (Set API Key for full story)"

# ==========================================
# 3. ゲームロジック
# ==========================================

def init_game(word_list_data, time_limit):
    """ゲームの初期化処理"""
    cards = []
    # カード生成: 英単語カードと日本語カードのペアを作る
    for item in word_list_data:
        # 英語カード
        cards.append({
            "id": item["en"],       # ペア判定用ID (英語で統一)
            "text": item["en"],     # 表示文字
            "is_jp": False,
            "pair_text": item["jp"] # ペアの文字（デバッグ/リベンジ用）
        })
        # 日本語カード
        cards.append({
            "id": item["en"], 
            "text": item["jp"], 
            "is_jp": True,
            "pair_text": item["en"]
        })
    
    random.shuffle(cards)
    
    # セッション状態のリセット
    st.session_state.cards = cards
    st.session_state.flipped = []       # 今めくっているカードのインデックスリスト
    st.session_state.matched_ids = set() # 揃ったペアのID集合
    st.session_state.collected_words = [] # ゲットした単語リスト(英語)
    
    st.session_state.start_time = time.time()
    st.session_state.time_limit = time_limit
    st.session_state.game_over = False

# ==========================================
# 4. メインアプリ (UI)
# ==========================================

def main():
    st.set_page_config(page_title="English Memory Battle", layout="wide")
    
    # --- サイドバー (設定) ---
    st.sidebar.title("⚙️ Settings")
    
    api_key = st.sidebar.text_input("Gemini API Key", type="password", help="Enter your Google AI Studio key")
    
    level = st.sidebar.selectbox("Select Level", list(VOCAB_DB.keys()))
    limit_sec = st.sidebar.slider("Time Limit (sec)", 10, 120, 45)

    # ニューゲームボタン
    if st.sidebar.button("New Game"):
        init_game(VOCAB_DB[level], limit_sec)
        st.session_state.game_mode = "NORMAL"
        st.rerun()

    # --- 初回起動チェック ---
    if "cards" not in st.session_state:
        init_game(VOCAB_DB[level], limit_sec)
        st.session_state.game_mode = "NORMAL"

    # --- メイン画面ヘッダー ---
    st.title("🧠 Memory Battle & Story Generator")
    st.caption("Match the cards before time runs out!")

    # 時間計算
    elapsed = time.time() - st.session_state.start_time
    remaining = st.session_state.time_limit - elapsed
    
    # 時間切れ判定
    if remaining <= 0 and not st.session_state.game_over:
        st.session_state.game_over = True
        remaining = 0
        st.rerun()

    # 情報表示バー
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if st.session_state.game_over:
            st.progress(0)
            st.error("⏰ TIME'S UP!")
        else:
            st.progress(remaining / st.session_state.time_limit)
            st.caption(f"Time Left: {remaining:.1f} sec")
    
    with col2:
        st.metric("Words Collected", f"{len(st.session_state.collected_words)}")
    
    with col3:
        if st.session_state.game_mode == "REVENGE":
            st.warning("🔥 REVENGE MODE")
        else:
            st.success("Normal Mode")

    st.divider()

    # --- カードグリッド表示 ---
    # 4列のカラムを作成
    grid_cols = st.columns(4)
    
    for i, card in enumerate(st.session_state.cards):
        # カードの状態を決定
        is_matched = card["id"] in st.session_state.matched_ids
        is_flipped = i in st.session_state.flipped
        
        # ボタンのラベルと状態
        if is_matched:
            label = f"✅ {card['text']}"
            disabled = True
        elif is_flipped:
            label = card['text']
            disabled = True
        elif st.session_state.game_over:
            # ゲームオーバー時は中身を見せるが、揃わなかったものはグレーアウト的な表示
            label = f"❌ {card['text']}"
            disabled = True
        else:
            label = "❓"
            disabled = False
        
        # ボタン配置
        with grid_cols[i % 4]:
            if st.button(label, key=f"card_{i}", disabled=disabled, use_container_width=True):
                # カードをめくる処理
                st.session_state.flipped.append(i)
                st.rerun()

    # --- 判定ロジック ---
    if len(st.session_state.flipped) == 2:
        idx1, idx2 = st.session_state.flipped
        card1 = st.session_state.cards[idx1]
        card2 = st.session_state.cards[idx2]

        if card1["id"] == card2["id"]:
            # 正解！
            st.toast(f"Nice match! {card1['text']} = {card2['text']}")
            st.session_state.matched_ids.add(card1["id"])
            st.session_state.collected_words.append(card1["id"])
            st.session_state.flipped = [] # めくり状態リセット
            
            # 全クリア判定
            total_pairs = len(st.session_state.cards) // 2
            if len(st.session_state.matched_ids) == total_pairs:
                st.session_state.game_over = True
            
            time.sleep(0.5)
            st.rerun()
        else:
            # 不正解
            st.toast("Not a match...", icon="⚠️")
            time.sleep

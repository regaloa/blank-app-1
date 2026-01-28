import streamlit as st
import random
import time
import google.generativeai as genai
# ==========================================
# 1. データ & 設定
# ==========================================

# TOEIC 700点レベルを意識した単語リスト
VOCAB_DB = {
    "Level 1 (初級)": [
        {"en": "Profit", "jp": "利益"},
        {"en": "Hire",   "jp": "雇う"},
        {"en": "Branch", "jp": "支店"},
        {"en": "Order",  "jp": "注文"},
        {"en": "Bill",   "jp": "請求書"},
        {"en": "Copy",   "jp": "部数/写し"},
    ],
    "Level 2 (中級)": [
        {"en": "Refund", "jp": "返金"},
        {"en": "Agenda", "jp": "議題"},
        {"en": "Resume", "jp": "履歴書"},
        {"en": "Confirm","jp": "確認する"},
        {"en": "Supply", "jp": "備品"},
        {"en": "Launch", "jp": "発売する"},
    ],
    "Level 3 (上級)": [
        {"en": "Inquiry",    "jp": "問い合わせ"},
        {"en": "Quarter",    "jp": "四半期"},
        {"en": "Warranty",   "jp": "保証"},
        {"en": "Deadline",   "jp": "締め切り"},
        {"en": "Proposal",   "jp": "提案"},
        {"en": "Executive",  "jp": "重役"},
    ]
}

# ==========================================
# 2. 関数: AI物語生成 & ゲームロジック
# ==========================================

def get_ai_story(api_key, words):
    """Gemini APIを使って物語を生成する関数"""
    if not api_key:
        return "（APIキーが設定されていないため、AI生成をスキップしました。設定するとここにAIが書いた物語が表示されます。）\n\n" + \
               generate_dummy_story(words)
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        word_list_str = ", ".join(words)
        prompt = f"""
        以下の英単語すべてを使って、短い興味深い物語（日本語）を作ってください。
        単語は英語のまま文中に埋め込み、その直後にカッコ書きで日本語の意味を補足してください。
        
        使用単語: {word_list_str}
        """
        
        with st.spinner("AIが物語を執筆中..."):
            response = model.generate_content(prompt)
            return response.text
    except Exception as e:
        return f"エラーが発生しました: {e}\n\n" + generate_dummy_story(words)

def generate_dummy_story(words):
    """APIが使えない時の予備テンプレート"""
    if not words: return "物語を作るための言葉が足りない..."
    return f"昔々、あるところに **{random.choice(words)}** を探し求める冒険者がいました。彼は旅の途中で **{random.choice(words)}** に遭遇し、最後は幸せに暮らしました。（※AIキーを設定すると、もっと凄い物語がここに生成されます）"

def init_game(word_list, time_limit):
    """ゲームの初期化（カードを配る）"""
    cards = []
    for item in word_list:
        # 識別用にIDを付与 (例: "Profit"ならID=Profit)
        # 英語カード
        cards.append({
            "id": item["en"], 
            "text": item["en"], 
            "is_jp": False,
            "pair": item["jp"]
        })
        # 日本語カード
        cards.append({
            "id": item["en"], 
            "text": item["jp"], 
            "is_jp": True,
            "pair": item["en"]
        })
    
    random.shuffle(cards)
    
    st.session_state.cards = cards
    st.session_state.flipped = []  # 現在めくっているカードのインデックス
    st.session_state.matched_ids = set()  # 揃ったペアのID
    st.session_state.collected_words = [] # ゲットした単語(英語)
    
    st.session_state.start_time = time.time()
    st.session_state.time_limit = time_limit
    st.session_state.game_over = False
    st.session_state.is_revenge = False # リベンジモードフラグ

# ==========================================
# 3. メインアプリ
# ==========================================

def main():
    st.set_page_config(page_title="AI Memory Battle", layout="wide")
    
    # --- サイドバー設定 ---
    st.sidebar.title("⚙️ 設定")
    
    # APIキー入力
    api_key = st.sidebar.text_input("Gemini APIキー (任意)", type="password", help="Google AI Studioで取得したキーを入れるとAI物語生成が有効になります。")
    
    # レベル選択
    level = st.sidebar.selectbox("レベル選択", list(VOCAB_DB.keys()))
    
    # 制限時間
    limit_sec = st.sidebar.slider("制限時間 (秒)", 15, 120, 45)

    # リセットボタン
    if st.sidebar.button("ニューゲーム"):
        init_game(VOCAB_DB[level], limit_sec)
        st.session_state.game_mode = "NORMAL" # 通常モード
        st.rerun()

    # --- アプリ起動時の初期化 ---
    if "cards" not in st.session_state:
        init_game(VOCAB_DB[level], limit_sec)
        st.session_state.game_mode = "NORMAL"

    st.title("🧠 英単語・神経衰弱バトル")
    
    # --- ヘッダー情報（残り時間・スコア） ---
    elapsed = time.time() - st.session_state.start_time
    remaining = st.session_state.time_limit - elapsed
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        if remaining > 0 and not st.session_state.game_over:
            st.progress(remaining / st.session_state.time_limit)
            st.caption(f"残り時間: {remaining:.1f} 秒")
        elif remaining <= 0 and not st.session_state.game_over:
            st.error("⏰ タイムアップ！")
            st.session_state.game_over = True
            st.rerun()
        else:
            st.progress(0)
            st.caption("終了")
            
    with col2:
        st.metric("ゲットした単語", f"{len(st.session_state.collected_words)} 語")
    with col3:
        mode_label = "🔥 リベンジ中" if st.session_state.game_mode == "REVENGE" else "通常モード"
        st.badge(mode_label)

    st.divider()

    # ==========================
    # ゲーム盤面描画
    # ==========================
    
    # カードグリッドの作成 (4列)
    cols = st.columns(4)
    
    for i, card in enumerate(st.session_state.cards):
        # カードの状態判定
        is_matched = card["id"] in st.session_state.matched_ids
        is_flipped = i in st.session_state.flipped
        
        # ボタンのラベル
        if is_matched or is_flipped or st.session_state.game_over:
            # ゲームオーバー時は全オープン（答え合わせ）
            label = card["text"]
            # スタイル調整: 揃ったものは緑、それ以外でオープンしてるものは黄色
            if is_matched:
                label = f"✅ {label}"
            elif st.session_state.game_over:
                label = f"❌ {label}" # 揃わなかったもの
        else:
            label = "❓"

        # ボタン配置
        with cols[i % 4]:
            # マッチ済み、またはゲーム終了時はボタンを押せなくする
            if is_matched or st.session_state.game_over:
                st.button(label, key=f"btn_{i}", disabled=True)
            else:
                # カードクリック処理
                if st.button(label, key=f"btn_{i}"):
                    if len(st.session_state.flipped) < 2:
                        st.session_state.flipped.append(i)
                        st.rerun()

    # ==========================
    # 判定ロジック
    # ==========================
    if len(st.session_state.flipped) == 2:
        idx1, idx2 = st.session_state.flipped
        card1 = st.session_state.cards[idx1]
        card2 = st.session_state.cards[idx2]

        if card1["id"] == card2["id"]:
            # 正解！
            st.toast(f"Nice! {card1['text']} = {card2['text']}")
            st.session_state.matched_ids.add(card1["id"])
            st.session_state.collected_words.append(card1["id"]) # 英語IDを保存
            st.session_state.flipped = []
            time.sleep(0.5)
            
            # 全部揃ったらゲームクリア
            if len(st.session_state.matched_ids) * 2 == len(st.session_state.cards):
                st.session_state.game_over = True
            
            st.rerun()
        else:
            # 不正解
            st.error("不一致...")
            # ユーザーが確認できるよう少し待ってからリセット（手動クリック待ちにしても良いがテンポ重視で自動）
            time.sleep(1) 
            st.session_state.flipped = []
            st.rerun()

    # ==========================
    # ゲーム終了後の処理 (物語 & リベンジ)
    # ==========================
    if st.session_state.game_over:
        st.divider()
        st.header("🎮 ゲームセット")
        
        # 1. 残った単語の抽出
        all_ids = set(c["id"] for c in st.session_state.cards)
        matched_ids = st.session_state.matched_ids
        unsolved_ids = list(all_ids - matched_ids)
        
        col_res1, col_res2 = st.columns(2)
        
        with col_res1:
            st.subheader("📜 獲得した単語で物語生成")
            if st.session_state.collected_words:
                if st.button("AIで物語を書く 🖋️"):
                    story = get_ai_story(api_key, st.session_state.collected_words)
                    st.success(story)
            else:
                st.write("単語を1つもゲットできませんでした...")

        with col_res2:
            st.subheader("🔥 次のステージへ")
            if unsolved_ids:
                st.warning(f"ペアにならなかった単語: {len(unsolved_ids)} 語")
                st.write(f"残った単語: {', '.join(unsolved_ids)}")
                
                # リベンジボタン
                if st.button("残った単語だけでリベンジする！"):
                    # 未解決IDから新しい単語リストを作成
                    revenge_list = []
                    # 現在のカード情報からテキスト情報を復元してリスト化
                    # （本来はVOCAB_DBから引くのが綺麗ですが、簡略化のため現在のカードから抽出）
                    seen = set()
                    for c in st.session_state.cards:
                        if c["id"] in unsolved_ids and c["id"] not in seen:
                            # 英語と日本語のペアを探す
                            pair_text = c["pair"]
                            revenge_list.append({"en": c["id"] if not c["is_jp"] else pair_text, 
                                                 "jp": c["text"] if c["is_jp"] else pair_text})
                            seen.add(c["id"])
                    
                    # リベンジステージ初期化
                    init_game(revenge_list, st.session_state.time_limit) # 時間は同じ設定で
                    st.session_state.game_mode = "REVENGE"
                    st.rerun()
            else:
                st.balloons()
                st.success("完璧です！すべての単語をクリアしました！")
                if st.button("最初のレベル選択に戻る"):
                    st.session_state.game_mode = "NORMAL"
                    # ページリロード的な挙動
                    del st.session_state.cards
                    st.rerun()

if __name__ == "__main__":
    main()

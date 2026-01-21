import streamlit as st
import time
import random

# --- データ: TOEIC 700点を目指すための単語リスト（レベル別） ---
VOCAB_DB = {
    "Level 1 (基礎)": {
        "budget": "予算",
        "delay": "遅れ",
        "accept": "受け入れる",
        "supply": "供給",
        "invite": "招待する"
    },
    "Level 2 (頻出)": {
        "negotiation": "交渉",
        "indicate": "示す",
        "candidate": "候補者",
        "frequently": "頻繁に",
        "purchase": "購入する"
    },
    "Level 3 (700点突破)": {
        "comprehensive": "包括的な",
        "incentive": "動機付け",
        "merger": "合併",
        "preliminary": "予備の",
        "subsequent": "その後の"
    }
}

# --- 関数: 物語の生成 ---
def generate_story(words):
    if not words:
        return "冒険の記録は白紙のままだ..."
    
    # 手に入れた単語を無理やり物語に組み込むテンプレート
    templates = [
        f"ジムリーダーとの **{random.choice(words)}** が始まった。",
        f"しかし、伝説のポケモンは **{random.choice(words)}** を要求してきた！",
        f"博士は言った。「真のトレーナーには **{random.choice(words)}** が必要なのじゃ」",
        f"こうして、彼らの **{random.choice(words)}** な旅は幕を閉じた。",
        f"次の町へ進むには **{random.choice(words)}** しなければならない。"
    ]
    return " ".join(templates)

# --- メイン処理 ---
def main():
    st.title("⚡ TOEIC 700 単語ラッシュ")
    st.caption("制限時間内に単語を回収し、物語を紡げ！")

    # --- セッション状態の初期化 ---
    if "game_state" not in st.session_state:
        st.session_state.game_state = "MENU" # MENU, PLAYING, RESULT, EXTRA
    if "score" not in st.session_state:
        st.session_state.score = 0
    if "collected_words" not in st.session_state:
        st.session_state.collected_words = []
    if "mistake_list" not in st.session_state:
        st.session_state.mistake_list = {} # {eng: jp}
    if "start_time" not in st.session_state:
        st.session_state.start_time = 0

    # ==========================
    # 1. メニュー画面 (レベル選択)
    # ==========================
    if st.session_state.game_state == "MENU":
        st.markdown("### 難易度を選んでください")
        level = st.selectbox("ステージ選択", list(VOCAB_DB.keys()))
        time_limit = st.slider("制限時間 (秒)", 10, 60, 30)

        if st.button("ゲームスタート！"):
            # ゲームデータのセットアップ
            words = list(VOCAB_DB[level].items())
            random.shuffle(words)
            st.session_state.current_word_queue = words
            st.session_state.current_word = st.session_state.current_word_queue.pop(0)
            
            # 状態のリセット
            st.session_state.collected_words = []
            st.session_state.mistake_list = {}
            st.session_state.score = 0
            st.session_state.limit_seconds = time_limit
            st.session_state.start_time = time.time()
            st.session_state.game_state = "PLAYING"
            st.rerun()

    # ==========================
    # 2. プレイ画面 (タイムアタック)
    # ==========================
    elif st.session_state.game_state == "PLAYING":
        # 残り時間の計算
        elapsed = time.time() - st.session_state.start_time
        remaining = st.session_state.limit_seconds - elapsed
        
        # プログレスバー表示
        progress = max(0.0, remaining / st.session_state.limit_seconds)
        st.progress(progress)
        st.write(f"残り時間: **{remaining:.1f}** 秒")

        # 時間切れ判定
        if remaining <= 0:
            st.error("⏰ タイムアップ！")
            st.session_state.game_state = "RESULT"
            time.sleep(2)
            st.rerun()

        # 問題表示
        eng_word, jp_meaning = st.session_state.current_word
        st.markdown(f"## {eng_word}")
        
        # 選択肢を作成（正解1つ + ダミー2つ）
        options = [jp_meaning]
        # 全レベルの単語からダミーを抽出
        all_meanings = [v for lvl in VOCAB_DB.values() for v in lvl.values()]
        while len(options) < 3:
            dummy = random.choice(all_meanings)
            if dummy not in options:
                options.append(dummy)
        random.shuffle(options)

        # ユーザー回答ボタン
        cols = st.columns(3)
        for i, opt in enumerate(options):
            if cols[i].button(opt, key=f"opt_{i}"):
                # 正誤判定
                if opt == jp_meaning:
                    st.toast("⭕ 正解！ゲット！")
                    st.session_state.score += 1
                    st.session_state.collected_words.append(eng_word)
                else:
                    st.toast(f"❌ ミス！正解は: {jp_meaning}")
                    # 間違いリストに追加
                    st.session_state.mistake_list[eng_word] = jp_meaning

                # 次の問題があるかチェック
                if st.session_state.current_word_queue:
                    st.session_state.current_word = st.session_state.current_word_queue.pop(0)
                    st.rerun()
                else:
                    st.success("全問クリア！")
                    st.session_state.game_state = "RESULT"
                    st.rerun()
        
        # 諦めて終了ボタン
        if st.button("リタイアして結果を見る"):
            st.session_state.game_state = "RESULT"
            st.rerun()

    # ==========================
    # 3. 結果画面 (物語 & 復習誘導)
    # ==========================
    elif st.session_state.game_state == "RESULT":
        st.markdown("## 🏆 結果発表")
        st.metric("スコア", f"{st.session_state.score} 点")
        
        st.divider()
        st.subheader("📖 生成された冒険の記録")
        if st.session_state.collected_words:
            story = generate_story(st.session_state.collected_words)
            st.info(story)
            st.caption(f"使用された単語: {', '.join(st.session_state.collected_words)}")
        else:
            st.warning("単語を1つもゲットできなかったため、冒険の記録は残らなかった...")

        st.divider()
        
        # エキストラステージ（復習）の判定
        if st.session_state.mistake_list:
            st.error(f"⚠️ 復習が必要な単語が {len(st.session_state.mistake_list)} 個あります！")
            st.write(st.session_state.mistake_list)
            
            if st.button("🔥 エキストラステージ（復習）へ"):
                # 復習モードのセットアップ
                # 辞書をタプルのリストに変換 [(eng, jp), ...]
                review_items = list(st.session_state.mistake_list.items())
                random.shuffle(review_items)
                
                st.session_state.current_word_queue = review_items
                st.session_state.current_word = st.session_state.current_word_queue.pop(0)
                
                # 復習は時間無制限にする設定
                st.session_state.limit_seconds = 999
                st.session_state.start_time = time.time()
                
                # 状態遷移
                st.session_state.game_state = "EXTRA"
                st.rerun()
        else:
            st.success("素晴らしい！復習する単語はありません。")
        
        if st.button("タイトルに戻る"):
            st.session_state.game_state = "MENU"
            st.rerun()

    # ==========================
    # 4. エキストラステージ (復習モード)
    # ==========================
    elif st.session_state.game_state == "EXTRA":
        st.markdown("## 🔥 EXTRA STAGE (復習)")
        st.caption("間違えた単語を確実に倒そう！")

        eng_word, jp_meaning = st.session_state.current_word
        st.header(f"{eng_word}")
        
        # 復習モードは選択肢ではなく「入力式」にして難易度を上げる（または確認のみ）
        # ここではシンプルに「答えを見る」形式にします
        with st.expander("答えを見る"):
            st.write(f"正解: **{jp_meaning}**")
        
        if st.button("覚えた！"):
            if st.session_state.current_word_queue:
                st.session_state.current_word = st.session_state.current_word_queue.pop(0)
                st.rerun()
            else:
                st.balloons()
                st.success("復習完了！完璧だ！")
                if st.button("タイトルへ"):
                    st.session_state.game_state = "MENU"
                    st.rerun()

if __name__ == "__main__":
    main()
    

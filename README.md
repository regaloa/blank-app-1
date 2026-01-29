# ◓ Pokémon English Battle (AI英単語バトル)

AIが無限に生成するTOEIC英単語で遊べる、神経衰弱ゲーム型学習アプリです。
Google Gemini (AI) と Supabase (データベース) を連携させ、「飽きない」「苦手をつぶせる」学習環境を実現しました。

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)

## 🚀 デモアプリ
ブラウザですぐに試せます（インストール不要）
### 👉 [ここをクリックしてアプリを開く](https://blank-app-8wk1o0gd82u.streamlit.app/#2b2e30d)

---

## 🎮 アプリの概要
「単語帳を覚えるのは退屈…」そんな悩みを解決するために開発しました。
AIがその場で問題を生成するため、毎回異なる単語が出題されます。さらに、間違えた単語はデータベースに自動保存され、徹底的に復習できます。

### ✨ 主な機能

**1. 無限・単語生成 (Gemini AI)**
* 難易度（モンスターボール級〜マスターボール級）を選ぶだけで、AIがTOEIC頻出単語から問題を即座に作成します。
* 二度と同じ問題セットは出ないので、常に新鮮な気持ちで学習できます。

**2. ゲーム感覚の学習**
* **神経衰弱 (Memory Game)** 形式で、英単語とその意味をペアにします。
* 制限時間30秒のタイムアタックで、瞬発力を鍛えます。

**3. 苦手克服システム (Supabase連携)**
* **自動保存**: マッチングに失敗した単語は、裏で自動的に「苦手リスト」に保存されます。
* **🔥 復習モード (Revenge)**: 苦手リストに溜まった単語だけが出題される専用ステージです。
* **熟練度システム**: 復習モードで「10回」正解すると、その単語は「克服（卒業）」とみなされ、リストから削除されます。

**4. 英語物語生成**
* ステージクリア後、獲得した単語すべてを使って、AIが即興で「短い英語の冒険ストーリー」を作成します。単語の使い方も同時に学べます。

---

## 🛠 使用技術

* **Frontend**: [Streamlit](https://streamlit.io/) (Python)
* **AI Model**: Google Gemini 1.5 Flash (via `google-genai` SDK)
* **Database**: Supabase (PostgreSQL)
* **Hosting**: Streamlit Community Cloud

---

## 💻 ローカルでの実行方法

開発者向けの手順です。

1. **リポジトリのクローン**
   ```bash
   git clone [あなたのリポジトリURL]
   cd [フォルダ名]

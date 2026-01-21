# 【変更点1】インポートの書き方が変わります
import streamlit as st
import random
import time
from google import genai  # ← ここが変わりました

# （...単語データなどはそのまま...）

# 【変更点2】AIを使う関数の中身を新方式に書き換え
def get_ai_story(api_key, words):
    """最新のGoogle Gen AI SDKを使って物語を生成する関数"""
    if not api_key:
        return "（APIキーが設定されていないため、AI生成をスキップしました...）\n\n" + \
               generate_dummy_story(words)
    
    try:
        # 新しい書き方: クライアントを作成
        client = genai.Client(api_key=api_key)
        
        word_list_str = ", ".join(words)
        prompt = f"""
        以下の英単語すべてを使って、短い興味深い物語（日本語）を作ってください。
        単語は英語のまま文中に埋め込み、その直後にカッコ書きで日本語の意味を補足してください。
        
        使用単語: {word_list_str}
        """
        
        with st.spinner("AIが物語を執筆中..."):
            # 新しい書き方: generate_content
            response = client.models.generate_content(
                model="gemini-1.5-flash", # または "gemini-2.0-flash-exp"
                contents=prompt
            )
            return response.text
    except Exception as e:
        return f"エラーが発生しました: {e}\n\n" + generate_dummy_story(words)

# （...これ以降の init_game や main 関数は変更なし...）

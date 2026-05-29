from app.ai.client import OpenAIClient

SYSTEM_PROMPT = """あなたはメール要約のアシスタントです。
メールの件名と本文を読み、重要なポイントを日本語で3行程度に要約してください。
挨拶や署名などの冗長な部分は省略し、目的・依頼・期限・重要な情報を簡潔にまとめてください。
要約本文のみを返してください。件名や見出しは含めないでください。"""


def format_email_summary(subject: str, summary: str) -> str:
    return f"【件名】\n{subject.strip()}\n\n【要約】\n{summary.strip()}"


def summarize_email(subject: str, body: str) -> str:
    """メールの件名と本文を受け取り、指定形式の要約テキストを返す。"""
    client = OpenAIClient()
    user_content = f"件名: {subject}\n\n本文:\n{body}"
    summary = client.summarize_text(user_content, system_prompt=SYSTEM_PROMPT)
    return format_email_summary(subject, summary)

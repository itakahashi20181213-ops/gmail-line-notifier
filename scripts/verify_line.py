"""LineClient の動作確認スクリプト。

使い方:
    .\\.venv\\Scripts\\python scripts\\verify_line.py
    .\\.venv\\Scripts\\python scripts\\verify_line.py --push Uxxxxxxxx...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.line.client import (
    LineApiError,
    LineClient,
    LineConfigurationError,
    LineValidationError,
)

LINE_BOT_INFO_URL = "https://api.line.me/v2/bot/info"


def ok(message: str) -> None:
    print(f"[OK] {message}")


def ng(message: str) -> None:
    print(f"[NG] {message}")


def verify_config() -> int:
    settings = get_settings()
    print("=== LINE 接続設定 ===")
    token = (settings.line_channel_access_token or "").strip()
    if not token or token == "your-line-channel-access-token":
        ng("LINE_CHANNEL_ACCESS_TOKEN が未設定です")
        return 1

    ok(f"アクセストークン: {token[:12]}...{token[-8:]}")
    ok(f"チャネルシークレット: {'設定済み' if settings.line_channel_secret else '未設定'}")
    if settings.line_user_id:
        ok(f"テスト用 line_user_id: {settings.line_user_id}")
    return 0


def verify_validation() -> int:
    print("\n=== 1. 入力バリデーション ===")
    client = LineClient()
    failed = 0

    cases = [
        ("", "テスト", "line_user_id が空"),
        ("U_test", "", "message が空"),
    ]
    for line_user_id, message, label in cases:
        try:
            client.push_message(line_user_id, message)
            ng(f"{label}: 例外が発生しませんでした")
            failed += 1
        except LineValidationError:
            ok(f"{label}: LineValidationError")

    return failed


def verify_bot_info() -> int:
    print("\n=== 2. トークン確認 (GET /v2/bot/info) ===")
    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.line_channel_access_token}",
    }

    try:
        with httpx.Client(timeout=30.0) as http:
            response = http.get(LINE_BOT_INFO_URL, headers=headers)
            response.raise_for_status()
            info = response.json()
    except httpx.HTTPStatusError as exc:
        ng(f"トークン検証失敗: [{exc.response.status_code}] {exc.response.text}")
        return 1
    except httpx.RequestError as exc:
        ng(f"接続失敗: {exc}")
        return 1

    ok(f"Bot 表示名: {info.get('displayName', '(不明)')}")
    ok(f"Bot userId: {info.get('userId', '(不明)')}")
    return 0


def verify_push(line_user_id: str) -> int:
    print(f"\n=== 3. Push 送信 ({line_user_id}) ===")
    client = LineClient()

    try:
        result = client.push_message(
            line_user_id,
            "LineClient 動作確認テストメッセージです。",
        )
        ok(f"送信成功: {result or '(空レスポンス)'}")
        return 0
    except LineConfigurationError as exc:
        ng(str(exc))
        return 1
    except LineValidationError as exc:
        ng(str(exc))
        return 1
    except LineApiError as exc:
        ng(str(exc))
        if exc.response_body:
            print(f"     response_body: {exc.response_body}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="LineClient 動作確認")
    parser.add_argument(
        "--push",
        metavar="LINE_USER_ID",
        help="指定した line_user_id へテスト Push を送信する",
    )
    args = parser.parse_args()

    failed = verify_config()
    if failed:
        return 1

    failed += verify_validation()
    failed += verify_bot_info()

    push_target = args.push or get_settings().line_user_id
    if push_target:
        failed += verify_push(push_target)
    else:
        print("\n=== 3. Push 送信 ===")
        ok("スキップ (.env の LINE_USER_ID または --push を指定)")

    print("\n=== 結果 ===")
    if failed:
        ng(f"{failed} 件のテストが失敗しました")
        return 1

    ok("すべてのテストが成功しました")
    return 0


if __name__ == "__main__":
    sys.exit(main())

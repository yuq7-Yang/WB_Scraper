from __future__ import annotations

from getpass import getpass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def quote_env(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_env_content(scrapfly_key: str, cookies: list[str]) -> str:
    clean_cookies = [cookie.strip() for cookie in cookies if cookie.strip()]
    if not scrapfly_key.strip():
        raise ValueError("Scrapfly API Key 不能为空")
    if not clean_cookies:
        raise ValueError("至少需要 1 个微博 Cookie")

    return "\n".join(
        [
            f"SCRAPFLY_KEY={quote_env(scrapfly_key.strip())}",
            f"WEIBO_COOKIES={quote_env('||'.join(clean_cookies))}",
            'DRY_RUN_REPLIES="true"',
            "",
        ]
    )


def main() -> None:
    print("本脚本只把凭据写入本机 .env，不会上传。")
    scrapfly_key = getpass("Scrapfly API Key: ").strip()
    first_cookie = getpass("?? Cookie 1: ").strip()
    second_cookie = getpass("微博 Cookie 2（可空，建议后续补上）: ").strip()

    try:
        content = build_env_content(scrapfly_key, [first_cookie, second_cookie])
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    ENV_PATH.write_text(content, encoding="utf-8")
    print(f"已写入 {ENV_PATH}")
    if not second_cookie:
        print("提示：当前只有 1 个微博 Cookie，可以小范围测试；长期使用建议补第 2 个账号 Cookie。")
    print("当前仍是 dry-run 回复预演模式，不会真实发送微博回复。")


if __name__ == "__main__":
    main()

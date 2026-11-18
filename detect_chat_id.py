import time
import subprocess
import json
import os
import re

TOKEN = "9070316228:AAFZp3jxXXsD8P9sM4nCfrREccOy1CHNyeM"

def get_updates():
    try:
        cmd = ["curl.exe", "-s", f"https://api.telegram.org/bot{TOKEN}/getUpdates"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(res.stdout)
        if data.get("ok"):
            return data.get("result", [])
    except Exception as e:
        print("Error fetching updates:", e)
    return []

def send_test_msg(chat_id):
    text = (
        "✅ *Koneksi Telegram Berhasil!*\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Bot `XAUUSD Decision Assistant` telah terhubung dengan akun Telegram kamu.\n"
        "Setiap ada sinyal setup trading baru (*Trend Following*, *Liquidity Sweep*, *Breakout Retest*), "
        "notifikasi real-time beserta level Entry, SL, TP, dan R:R akan dikirimkan ke sini."
    )
    cmd = [
        "curl.exe", "-s", "-X", "POST",
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        "-d", f"chat_id={chat_id}",
        "-d", f"text={text}",
        "-d", "parse_mode=Markdown"
    ]
    subprocess.run(cmd, capture_output=True, text=True)

def main():
    print("Mengecek pesan masuk dari bot...")
    updates = get_updates()
    if not updates:
        print("Belum ada pesan masuk. Pastikan kamu sudah klik tombol START pada bot: t.me/trade_assistant_drkns_bot")
        return False

    last_update = updates[-1]
    chat = last_update.get("message", {}).get("chat", {})
    chat_id = chat.get("id")
    username = chat.get("username", "User")
    first_name = chat.get("first_name", "")

    if chat_id:
        print(f"Ditemukan Chat ID: {chat_id} (dari: {first_name} @{username})")
        
        # Update .env
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()

        new_content = re.sub(r"TELEGRAM_CHAT_ID=.*", f"TELEGRAM_CHAT_ID={chat_id}", content)
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print("Berhasil menyimpan TELEGRAM_CHAT_ID ke file .env!")
        send_test_msg(chat_id)
        print("Pesan tes berhasil dikirim ke Telegram kamu!")
        return True

    return False

if __name__ == "__main__":
    main()

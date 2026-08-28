import asyncio
import os
import gradio as gr
from app.core.database import init_db
from app.telegram_bot import start_polling_task

# 1. Initialize SQLite Database & Launch Telegram Bot Polling in Background
init_db()
task = start_polling_task()

# 2. Status Web UI on Port 7860
with gr.Blocks(title="Personal AI OS - Telegram Bot") as demo:
    gr.Markdown("# 🤖 Personal AI OS is Running 24/7!")
    gr.Markdown("🟢 **Telegram Bot:** Online & Listening for Commands")
    gr.Markdown("📰 **Daily News Digest:** Scheduled for 07:00 AM IST")
    gr.Markdown("⏰ **Productivity Reminders:** Active")
    gr.Markdown("⚡ **AI Fast Answers (/ask):** Multi-LLM Active")

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)

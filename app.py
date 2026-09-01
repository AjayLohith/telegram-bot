import asyncio
import os
import gradio as gr
from app.core.database import init_db
from app.telegram_bot import start_polling_task

# 1. Initialize SQLite Database & Launch Telegram Bot Polling in Background
init_db()
task = start_polling_task()

# 2. Status Web UI on Port 7860
with gr.Blocks(title="J.A.R.V.I.S. // Personal AI OS") as demo:
    gr.Markdown("# 🤖 J.A.R.V.I.S. Mark VII Protocols Active")
    gr.Markdown("🟢 **Telegram Interface:** Online & Listening for Directives")
    gr.Markdown("📰 **Daily Intelligence Briefing:** Scheduled for 07:00 AM IST")
    gr.Markdown("⏰ **Directive Reminders Engine:** Active")
    gr.Markdown("⚡ **Neural Quick Intel (/ask):** Multi-LLM Active")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)


import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load variables from Render Environment Variables
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g., https://your-app.onrender.com
PORT = int(os.environ.get("PORT", 8080))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I am running on Render via Webhook.")

def main():
    # Check if the token is set
    if not TOKEN:
        print("ERROR: BOT_TOKEN environment variable is missing!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print(f"Starting webhook server on port {PORT}...")
    
    # Start the webhook server
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook" if WEBHOOK_URL else None,
    )

if __name__ == "__main__":
    main()

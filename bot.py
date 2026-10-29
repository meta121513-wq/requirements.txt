"""
A small Telegram dashboard for practicing with fictional portfolio data.
Updated with Flask server for Render compatibility.
"""

import json
import os
import sys
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from flask import Flask

# Flask setup for Render Web Service compatibility
app = Flask(__name__)


@app.route('/')
def home():
  return 'Telegram Bot is running smoothly on Render!'


BOT_TOKEN = (
    os.environ.get('BOT_TOKEN')
    or os.environ.get('TELEGRAM_BOT_TOKEN', '')
).strip()
API_BASE = f'https://api.telegram.org/bot{BOT_TOKEN}'

# Sample fictional data
SAMPLE_POSITIONS = [
    ('DEMO-ALPHA', '12.5 units', '$1,250.00'),
    ('DEMO-BETA', '3 units', '$875.00'),
    ('DEMO-GAMMA', '40 units', '$480.00'),
]

SAMPLE_TRADES = [
    'SIM BUY · 2 DEMO-ALPHA · practice example',
    'SIM SELL · 1 DEMO-BETA · practice example',
    'SIM BUY · 10 DEMO-GAMMA · practice example',
]

chat_settings = {}


class TelegramRequestError(Exception):
  """A safe-to-display error that never includes the bot token."""


def get_settings(chat_id):
  if chat_id not in chat_settings:
    chat_settings[chat_id] = {
        'paused': False,
        'practice_alerts': False,
    }
  return chat_settings[chat_id]


def telegram_request(method, payload):
  request = Request(
      f'{API_BASE}/{method}',
      data=json.dumps(payload).encode('utf-8'),
      headers={'Content-Type': 'application/json'},
      method='POST',
  )

  try:
    with urlopen(request, timeout=45) as response:
      result = json.loads(response.read().decode('utf-8'))
  except HTTPError as error:
    if error.code == 401:
      raise TelegramRequestError(
          'Telegram rejected the bot token. Check the BOT_TOKEN secret.'
      ) from None
    raise TelegramRequestError(
        'Telegram returned an error. Check your connection and try again.'
    ) from None
  except (URLError, TimeoutError, OSError):
    raise TelegramRequestError(
        'Could not reach Telegram. Check your connection and try again.'
    ) from None
  except (json.JSONDecodeError, UnicodeDecodeError):
    raise TelegramRequestError(
        'Telegram returned an unreadable response. Try again.'
    ) from None

  if not result.get('ok'):
    description = result.get('description', '')
    if 'message is not modified' in description.lower():
      return None
    raise TelegramRequestError(
        'Telegram could not complete that request. Try /start to reopen the'
        ' dashboard.'
    )

  return result.get('result')


def dashboard_keyboard(settings):
  pause_label = 'Resume Bot' if settings['paused'] else 'Pause Bot'
  return {
      'inline_keyboard': [
          [
              {'text': 'Track Wallet', 'callback_data': 'track_wallet'},
              {'text': 'View Positions', 'callback_data': 'view_positions'},
          ],
          [
              {'text': 'Trade History', 'callback_data': 'trade_history'},
              {'text': 'Settings', 'callback_data': 'settings'},
          ],
          [{'text': pause_label, 'callback_data': 'toggle_pause'}],
      ]
  }


def settings_keyboard(settings):
  alert_label = (
      'Turn Practice Alerts Off'
      if settings['practice_alerts']
      else 'Turn Practice Alerts On'
  )
  return {
      'inline_keyboard': [
          [{'text': alert_label, 'callback_data': 'toggle_alerts'}],
          [{'text': 'Back to Dashboard', 'callback_data': 'dashboard'}],
      ]
  }


def dashboard_text(settings):
  status = 'PAUSED' if settings['paused'] else 'RUNNING'
  return (
      'Practice Simulator Dashboard\n\n'
      f'Bot status: {status}\n'
      'Practice mode only. No wallet, exchange, blockchain, or real-money '
      'connection is used.\n\n'
      'Choose an option:'
  )


def view_text(action, settings):
  if action == 'track_wallet':
    if settings['paused']:
      return (
          'Practice Wallet\n\n'
          'The bot is paused, so it did not refresh the sample wallet view.\n'
          'Resume the bot to view the fictional balance.'
      )
    return (
        'Practice Wallet\n\n'
        'Label: Demo wallet\n'
        'Simulated cash: $10,000.00\n\n'
        'This is made-up practice data. No wallet address is requested or '
        'connected.'
    )

  if action == 'view_positions':
    lines = ['Practice Positions', '', 'Fictional sample values:']
    for name, quantity, value in SAMPLE_POSITIONS:
      lines.append(f'• {name}: {quantity} · sample value {value}')
    lines.extend(
        [
            '',
            'These are invented demo assets, not live prices or holdings.',
        ]
    )
    return '\n'.join(lines)

  if action == 'trade_history':
    lines = ['Practice Trade History', '', *SAMPLE_TRADES]
    lines.extend(
        [
            '',
            'These are example entries only. No trades were placed.',
        ]
    )
    return '\n'.join(lines)

  if action == 'settings':
    alert_status = 'On' if settings['practice_alerts'] else 'Off'
    return (
        'Practice Settings\n\n'
        f'Practice alerts preference: {alert_status}\n'
        'This simulator does not send alerts. The preference is kept only '
        'while the bot is running.\n\n'
        'Settings reset when the bot stops. Sample positions and history are'
        ' fixed examples.'
    )

  return dashboard_text(settings)


def edit_dashboard(chat_id, message_id, text, keyboard):
  telegram_request(
      'editMessageText',
      {
          'chat_id': chat_id,
          'message_id': message_id,
          'text': text,
          'reply_markup': keyboard,
      },
  )


def show_dashboard(chat_id):
  settings = get_settings(chat_id)
  telegram_request(
      'sendMessage',
      {
          'chat_id': chat_id,
          'text': dashboard_text(settings),
          'reply_markup': dashboard_keyboard(settings),
      },
  )


def handle_callback(callback):
  callback_id = callback.get('id')
  message = callback.get('message', {})
  chat = message.get('chat', {})
  chat_id = chat.get('id')
  message_id = message.get('message_id')

  if callback_id:
    telegram_request('answerCallbackQuery', {'callback_query_id': callback_id})
  if chat_id is None or message_id is None:
    return

  settings = get_settings(chat_id)
  action = callback.get('data', '')

  if action == 'toggle_pause':
    settings['paused'] = not settings['paused']
    text = dashboard_text(settings)
    keyboard = dashboard_keyboard(settings)
  elif action == 'toggle_alerts':
    settings['practice_alerts'] = not settings['practice_alerts']
    text = view_text('settings', settings)
    keyboard = settings_keyboard(settings)
  elif action == 'settings':
    text = view_text('settings', settings)
    keyboard = settings_keyboard(settings)
  elif action == 'dashboard':
    text = dashboard_text(settings)
    keyboard = dashboard_keyboard(settings)
  elif action in {'track_wallet', 'view_positions', 'trade_history'}:
    text = view_text(action, settings)
    keyboard = dashboard_keyboard(settings)
  else:
    text = dashboard_text(settings)
    keyboard = dashboard_keyboard(settings)

  edit_dashboard(chat_id, message_id, text, keyboard)


def handle_message(message):
  chat = message.get('chat', {})
  chat_id = chat.get('id')
  text = message.get('text', '').strip()
  if chat_id is None:
    return

  command = text.split(maxsplit=1)[0].split('@', maxsplit=1)[0].lower() if text else ''
  if command in {'/start', '/help'}:
    show_dashboard(chat_id)
    return

  telegram_request(
      'sendMessage',
      {
          'chat_id': chat_id,
          'text': (
              'Use /start to open the practice dashboard. No wallet address is'
              ' needed.'
          ),
      },
  )


def handle_update(update):
  if 'callback_query' in update:
    handle_callback(update['callback_query'])
  elif 'message' in update:
    handle_message(update['message'])


def run_telegram_loop():
  if not BOT_TOKEN:
    print('Missing BOT_TOKEN environment variable.', file=sys.stderr)
    return

  try:
    bot_info = telegram_request('getMe', {})
    print(
        f"Practice bot is running as @{bot_info.get('username', 'unknown')}."
    )
  except TelegramRequestError as error:
    print(f'Could not start the bot: {error}', file=sys.stderr)
    return

  next_update_id = None
  while True:
    payload = {'timeout': 30, 'allowed_updates': ['message', 'callback_query']}
    if next_update_id is not None:
      payload['offset'] = next_update_id

    try:
      updates = telegram_request('getUpdates', payload) or []
      for update in updates:
        next_update_id = update['update_id'] + 1
        try:
          handle_update(update)
        except TelegramRequestError as error:
          print(f'Could not handle an update: {error}', file=sys.stderr)
    except TelegramRequestError as error:
      print(f'Telegram connection issue: {error}', file=sys.stderr)
      time.sleep(3)
    except Exception as e:
      print(f'Unexpected error: {e}', file=sys.stderr)
      time.sleep(3)


if __name__ == '__main__':
  # Start Telegram polling loop in background thread
  bot_thread = threading.Thread(target=run_telegram_loop, daemon=True)
  bot_thread.start()

  # Run Flask server to keep Render Web Service happy
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)

from calendar import weekday
import logging
import this
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from click import option
from env import get_api_key, get_port
import telebot
from telebot import types
from telegram import CallbackQuery, ParseMode
import ast
from dbhelper import DBHelper

PORT = get_port()
API_KEY = get_api_key()
if API_KEY == None:
    raise Exception("Please update API Key")


# -----------------------------------------------------------------------------------------------------
# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Initialise bot
bot = telebot.TeleBot(API_KEY, parse_mode = None)

# Makes Inline Keyboard
# TODO Change callbakc_data values
def makeInlineKeyboard(lst, optionID):
    markup = types.InlineKeyboardMarkup()
    for key, value in lst.items():
        markup.add(types.InlineKeyboardButton(text = value,
                                            callback_data = "['optionID', '" + optionID + "', 'value', '" + value + "']"))
    return markup

# Specific Inline Keyboard for showing time slots
# TODO Change callbakc_data values
def makeTimeInlineKeyboard(lst, optionID, dayPicked):
    markup = types.InlineKeyboardMarkup()
    for key, value in lst.items():
        markup.add(types.InlineKeyboardButton(text = value,
                                            callback_data = "['optionID', '" + optionID + "', 'value', '" + value + "', 'day', '" + dayPicked + "']"))
    return markup

# TODO: DB to main file converters


# Command Handlers
def start(update, context):
    """Send a message when the command /start is issued."""
    txt1 = "Hi! Welcome to the Shan Royale Bot\n\n"
    txt2 = "Type <b>/help</b> for more info\n"
    fullText = txt1 + txt2
    update.message.reply_text(text = fullText, parse_mode = ParseMode.HTML)

def help(update, context):
    """Send a message when the command /help is issued."""
    txt1 = "Here are the suppported individual commands:\n"
    txt2 = "<b>/setpoints</b> - Set your points for the rounds in Shan Royale\n\n"
    txt3 = "Here are the support admin commands:\n"
    txt4 = "<b>/allpoints</b> - See points of all players"
    fullText = txt1 + txt2 + txt3 + txt4
    update.message.reply_text(text = fullText, parse_mode = ParseMode.HTML)

def mainCallBackHandler(update, context):
    dataClicked = ast.literal_eval(update.callback_query.data)
    optionID = dataClicked[1]
    value = dataClicked[3]
    user = update.callback_query.message.chat.username

    # Create database (this is required to ensure multiple ppl dont use the same db object)
    db = DBHelper("userData.sqlite")
    db.setup()
    db.handleUsername(user)

def stop(update, context):
    """Stops"""
    update.message.reply_text(update.message.text)

def echo(update, context):
    """Echo the user message."""
    update.message.reply_text(update.message.text)

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def main():
    # Start the bot.
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(API_KEY, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

    # Handle all callback
    dp.add_handler(CallbackQueryHandler(callback=mainCallBackHandler, pattern=str))


    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    # updater.start_webhook(listen="0.0.0.0",
    #                     port=int(PORT),
    #                     url_path=str(API_KEY))
    # updater.bot.setWebhook('https://whispering-dawn-13866.herokuapp.com/' + str(API_KEY))

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.start_polling()

if __name__ == '__main__':
    main()
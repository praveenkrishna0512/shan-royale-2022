from calendar import weekday
import enum
import logging
import this
from tracemalloc import BaseFilter
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

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Initialise bot
bot = telebot.TeleBot(API_KEY, parse_mode = None)

#============================Constants======================================
minPoints = 5
maxTeamPoints = 200

#============================Tracking State===================================
# Possible optionIDs
class StateEnum(enum.Enum):
    setPoints1 = "setPoints1"
    setPoints2 = "setPoints2"
    setPoints3 = "setPoints3"

# Handles state of the bot for each user
# Key: username
# Value: dynamic dictionary
userTracker = {}

def setState(username, state):
    userTracker[username].update({"state": state})
    print("State updated for " + username + ": " + str(userTracker[username]))

#============================Key boards===================================
# Makes Inline Keyboard
def makeInlineKeyboard(lst, optionID):
    markup = types.keybo
    for key, value in lst.items():
        markup.add(types.InlineKeyboardButton(text = value,
                                            callback_data = "['optionID', '" + optionID + "', 'value', '" + value + "']"))
    return markup

# Makes Inline Keyboard
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

#============================DB to file converters?===========================
# TODO: DB to main file converters (maybe put in dbhelper.py)


#========================Command Handlers==================================
# Sends start command and registers new usernames
def start(update, context):
    username = update.message.chat.username
    txt1 = "Hi! Welcome to the Shan Royale Bot\n"
    txt2 = "Type <b>/help</b> for more info\n\n"
    txt3 = "Registered username: " + username + "\n\n"
    txt4 = "IMPT: Please <b>do NOT change your username</b> after starting the bot"
    fullText = txt1 + txt2 + txt3 + txt4
    update.message.reply_text(text = fullText, parse_mode = ParseMode.HTML)

    # Create database (this is required to ensure multiple ppl dont use the same db object)
    db = DBHelper("shan-royale.sqlite")
    userExists = db.handleUsername(username)
    # Add new user to userTracker
    if username not in userTracker.keys():
        newUserTracker = {
            "state": None,
            "db": db
        }
        userTracker[username] = newUserTracker
    print("User Tracker: " + str(userTracker))

def help(update, context):
    """Send a message when the command /help is issued."""
    txt1 = "Here are the suppported individual commands:\n"
    txt2 = """<b>/setpoints1</b> - Set/Reset your points for Round 1 in Shan Royale
<b>/setpoints2</b> - Set/Reset your points for Round 2 in Shan Royale\n\n"""
    txt3 = "Here are the support admin commands:\n"
    txt4 = "<b>/allpoints</b> - See points of all players"
    fullText = txt1 + txt2 + txt3 + txt4
    update.message.reply_text(text = fullText, parse_mode = ParseMode.HTML)

def promptSetPoints1(update, context):
    username = update.message.chat.username
    setState(username, StateEnum.setPoints1)

    fullText = """Type in the points allocated to you in <b>Round 1</b>\n
Take Note:<em>
- Everyone must be allocated at least <b>5 points</b>
- <b>Do not exceed</b> your total team points of 200!
</em>
"""
    bot.send_message(chat_id = update.message.chat.id,
        text = fullText,
        parse_mode = 'HTML')

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

#===================Message and Callback Handlers==============================
def handleSetPoints1(chat_id, username, text):
    points = int(text)
    invalid = invalidPoints(chat_id, points, round_no=1)
    if invalid: 
        return

    db = userTracker[username]["db"]
    db.updateRound1Points(username, points)

    fullText = f"""Allocated {points} points to you for <b>Round 1</b>\n
Click <b>/setpoints1</b> again to <b>reset</b> points for Round 1!\n
Click <b>/setpoints2</b> to set points for Round 2!
"""
    bot.send_message(chat_id = chat_id,
        text = fullText,
        parse_mode = 'HTML')
    return

def mainMessageHandler(update, context):
    chat_id = update.message.chat.id
    username = update.message.chat.username
    text = update.message.text
    currentState = userTracker[username]["state"]
    match currentState:
        case StateEnum.setPoints1:
            handleSetPoints1(chat_id, username, text)
            return
        case _:
            print(f'ERROR IN MSGHANDLER: No such state defined ({currentState})')
            return
    # dataClicked = ast.literal_eval(update.callback_query.data)
    # optionID = dataClicked[1]
    # value = dataClicked[3]
    # user = update.callback_query.message.chat.username

#====================Other helpers=========================
def invalidPoints(chat_id, points, round_no):
    #TODO ADD CHECKS FOR TEAM POINTS TOO!
    if points >= minPoints:
        return False

    fullText = f"""Too little points for <b>Round {round_no}</b>!
Everyone must be allocated at least <b>5 points</b>.\n
Please enter your points for this round again"""
    bot.send_message(chat_id = chat_id,
        text = fullText,
        parse_mode = 'HTML')
    return True

#===================Main Method============================
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
    dp.add_handler(CommandHandler("setpoints1", promptSetPoints1))

    # Handle all messages
    dp.add_handler(MessageHandler(callback=mainMessageHandler, filters=Filters.all))


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
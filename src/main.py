from calendar import weekday
import enum
import json
import logging
from os import kill
from tabnanny import check
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
from game import Game
import adminCommands as adminCmd
import excel2json
import pandas

PORT = get_port()
API_KEY = get_api_key()
if API_KEY == None:
    raise Exception("Please update API Key")

# Excel to Database
mainDb = DBHelper()
excelFilePath = "./excel/shanRoyale2022Data1.xlsx"
playerDataRound1JSONArr = json.loads(pandas.read_excel(excelFilePath, sheet_name="playerDataRound1").to_json(orient='records'))
playerDataRound2JSONArr = json.loads(pandas.read_excel(excelFilePath, sheet_name="playerDataRound2").to_json(orient='records'))
factionDataJSONArr = json.loads(pandas.read_excel(excelFilePath, sheet_name="factionData").to_json(orient='records'))
mainDb.processPlayerDataJSONArr(playerDataRound1JSONArr, 1)
mainDb.processPlayerDataJSONArr(playerDataRound2JSONArr, 2)
mainDb.processFactionDataJSONArr(factionDataJSONArr)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Initialise bot
bot = telebot.TeleBot(API_KEY, parse_mode = None)

#============================Constants======================================
minPoints = 5
maxTeamPoints = 200
factionsMap = {
    "1": "Sparta",
    "2": "Hades",
    "3": "Aphrodite",
    "4": "Nemesis"
}
highestAllowedSafetyBreach = 2

roundList = [1, 2]
yesNoList = ["Yes", "No"]

currentGame = Game(0)

admins = ["praveeeenk"]
gameMasters = ["praveeeenk"]
safetyOfficers = ["praveeeenk"]

#=============================Texts==========================================
dontWasteMyTimeText = """\"<b>Don't waste my time...</b> You aren't allowed to use this command now.\"
~ Message by Caserplz"""

#============================Tracking State===================================
# Possible states
class StateEnum(enum.Enum):
    setPoints = "setPoints"

class OptionIDEnum(enum.Enum):
    beginRound = "beginRound"
    endSetPoints = "endSetPoints"

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
    markup = types.InlineKeyboardMarkup()
    for value in lst:
        markup.add(types.InlineKeyboardButton(text = value,
                                            callback_data = f"['optionID', '{optionID}', 'value', '{value}']"))
    return markup

#============================DB to file converters?===========================
# TODO: DB to main file converters (maybe put in dbhelper.py)

# ====================== Admin Commands ===============================
def adminBeginRound(update, context):
    username = update.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        bot.send_message(chat_id = update.message.chat.id,
                     text = dontWasteMyTimeText,
                     parse_mode = 'HTML')
        return

    text = """You are about to begin a round!\n
Which round to you want to begin?"""
    bot.send_message(chat_id = update.message.chat.id,
                     text = text,
                     reply_markup = makeInlineKeyboard(roundList, OptionIDEnum.beginRound),
                     parse_mode = 'HTML')

def handleAdminBeginRound(update, context, round_no):
    global currentGame
    currentGame = adminCmd.adminBeginGame(round_no)

    adminText = f"""Thanks sir! Set Points phase for Round {round_no} has begun!!

Make sure to type /adminEndSetPoints to begin the Killing Phase."""
    bot.edit_message_text(chat_id = update.callback_query.message.chat.id,
                     text = adminText,
                     message_id = update.callback_query.message.message_id,
                     parse_mode = 'HTML')

    blastText = f"""<b>NOTICE</b>
Round {round_no} is about to begin!!

You are now in the <b>Set Points</b> phase

<b>Details of phase:</b>
- Duration: <b>about 10 mins</b>
- Make sure to /setpoints <b>individually</b> and assign yourselves some points!
- Do not exceed your team cumulative points of <b>200</b>
- Everyone must be assigned at least <b>5 points</b>
- Killing is now <b>disabled</b>. You will be notified when the Killing phase begins

Enjoy!"""
    blastMessageToAll(blastText)

def adminEndSetPoints(update, context):
    username = update.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return

    setPointsPhase = checkSetPointsPhase(update, context)
    if not setPointsPhase:
        return

    adminDb = userTracker[username]["db"]
    factionPointsMap = getAllFactionPoints(adminDb)
    pointsText = ""
    for faction, points in factionPointsMap.items():
        pointsText += f"""Faction {faction} ({factionsMap[faction]}) - {points}pts\n"""

    fullText = f"""You are about to <b>end Set Points</b> for Round {currentGame.currentRound}.
Here are the points assigned for each faction.

{pointsText}
Are you okay with this?"""
    bot.send_message(chat_id = update.message.chat.id,
                     text = fullText,
                     reply_markup = makeInlineKeyboard(yesNoList, OptionIDEnum.endSetPoints),
                     parse_mode = 'HTML')

#TODO HERE NOW
def handleAdminEndSetPoints(update, context, yesNo):
    global currentGame
    chat_id = update.callback_query.message.chat.id
    message_id = update.callback_query.message.message_id
    if yesNo == yesNoList[1]:
        # "No" was pressed
        adminText = f"""No worries, Set Points phase has not ended. Please ask the respective OGL to make amends.\n
Once that is done, please type /adminEndSetPoints again.\n\n{dontWasteMyTimeText}"""
        bot.edit_message_text(chat_id = chat_id,
                     text = adminText,
                     message_id = message_id,
                     parse_mode = 'HTML')
        return

    # "Yes" was pressed
    currentGame = adminCmd.adminEndSetPoints(currentGame)
    print(f"Admin End Set Points Game State:\n{currentGame.toString()}")
    adminText = f"""You have ended Set Points phase for Round {currentGame.currentRound}! Killing has now been enabled :)"""
    bot.edit_message_text(chat_id = chat_id,
                    text = adminText,
                    message_id = message_id,
                    parse_mode = 'HTML')

    for username, user in userTracker.items():
        # TODO Add in pic of play area
        targetFaction = getTargetFaction(username)
        text = f"""<b>NOTICE</b>
Round {currentGame.currentRound} has begun!!

You are now in the <b>Killing</b> phase

<b>Details of phase:</b>
- Duration: <b>45 mins</b>
- Your target Faction is <b>{targetFaction}</b>
- Picture of play area is attached!

Stay safe while playing! Don't run on stairs + high areas and not into people. Remember that this is <b>just a game</b>\n
Enjoy!"""
        bot.send_message(chat_id = user["chat_id"],
                     text = text,
                     parse_mode = 'HTML')

#========================Player Command Handlers===============================================
# Sends start command and registers new usernames
def start(update, context):
    username = update.message.chat.username

    # Create database (this is required to ensure multiple ppl dont use the same db object)
    db = DBHelper("shan-royale.sqlite")
    userExists = db.checkUsernameInDB(username)
    if not userExists:
        errorText = """Your username is <b>NOT in the database</b>. If you have changed your username after registering for TSE, please change your username back and try /start again.\n\n
Please contact @praveeeenk if the problem persists."""
        bot.send_message(chat_id = update.message.chat.id,
                     text = errorText,
                     parse_mode = 'HTML')
        return
    
    txt1 = "Hi! Welcome to the Shan Royale Bot\n"
    txt2 = "Type <b>/help</b> for more info\n\n"
    txt3 = "Registered username: " + username + "\n\n"
    txt4 = "IMPT: Please <b>do NOT change your username</b> after starting the bot"
    fullText = txt1 + txt2 + txt3 + txt4
    update.message.reply_text(text = fullText, parse_mode = ParseMode.HTML)

    # Add new user to userTracker
    if username not in userTracker.keys():
        newUserTracker = {
            "state": None,
            "db": db,
            "chat_id": update.message.chat.id
        }
        userTracker[username] = newUserTracker
    print("User Tracker: " + str(userTracker))

def help(update, context):
    """Send a message when the command /help is issued."""
    txt1 = "Here are the suppported individual commands:\n"
    txt2 = """<b>/setpoints</b> - Set/Reset your points for current round in Shan Royale
<b>/listpoints</b> - List your faction members' points for current round in Shan Royale
\n"""
    txt3 = "Here are the support admin commands:\n"
    txt4 = """<b>/adminBeginRound</b> - Begin the Set Points phase for a round!
<b>/adminEndSetPoints</b> - End the Set Points phase and begin Killing phase for the current round!"""
    fullText = txt1 + txt2 + txt3 + txt4
    update.message.reply_text(text = fullText, parse_mode = ParseMode.HTML)

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

#===========================Set points==============================
def promptSetPoints(update, context):
    setPointsPhase = checkSetPointsPhase(update, context)
    if not setPointsPhase:
        return

    safe = checkSafetyBreaches(update, context)
    if not safe:
        return

    username = update.message.chat.username
    setState(username, StateEnum.setPoints)

    fullText = f"""Type in the points allocated to you in <b>Round {currentGame.currentRound}</b>\n
Take Note:<em>
- Everyone must be allocated at least <b>5 points</b>
- <b>Do not exceed</b> your total team points of 200!
</em>
"""
    bot.send_message(chat_id = update.message.chat.id,
        text = fullText,
        parse_mode = 'HTML')

def handleSetPoints(update, context, text):
    chat_id = update.message.chat.id
    username = update.message.chat.username
    text = update.message.text
    setPointsPhase = checkSetPointsPhase(update, context)
    if not setPointsPhase:
        return

    points = int(text)
    invalid = invalidPoints(chat_id, points)
    if invalid: 
        return

    db = userTracker[username]["db"]
    db.updateRoundPoints(username, points, currentGame.currentRound)

    fullText = f"""Allocated {points} points to you for <b>Round {currentGame.currentRound}</b>\n\n
Click <b>/setpoints</b> again to <b>reset</b> points for this round!
"""
    bot.send_message(chat_id = chat_id,
        text = fullText,
        parse_mode = 'HTML')
    
    setState(username, None)

def handleListPoints(update, context):
    playPhase = checkPlayPhase(update, context)
    if not playPhase:
        return

    username = update.message.chat.username
    userDb = userTracker[username]["db"]
    playerFaction = userDb.getPlayerFaction(username, currentGame.currentRound)
    factionMembersPointsMap = userDb.getFactionMemberPoints(playerFaction, currentGame.currentRound)

    txt1 = "Here are the current updated points held by your faction members\n"
    txt2 = ""
    for username, points in factionMembersPointsMap.items():
        txt2 += f"\n@{username}: {points}pts"
    fullText = txt1 + txt2

    bot.send_message(chat_id = update.message.chat.id,
        text = fullText,
        parse_mode = 'HTML')

def invalidPoints(chat_id, points):
    #TODO ADD CHECKS FOR TEAM POINTS TOO!
    if points >= minPoints:
        return False

    fullText = f"""Too little points for <b>Round {currentGame.currentRound}</b>!
Everyone must be allocated at least <b>5 points</b>.\n
Please enter your points for this round again"""
    bot.send_message(chat_id = chat_id,
        text = fullText,
        parse_mode = 'HTML')
    return True


#===================Message and Callback Handlers==============================
def mainMessageHandler(update, context):
    username = update.message.chat.username
    text = update.message.text
    currentState = userTracker[username]["state"]
    match currentState:
        case StateEnum.setPoints:
            handleSetPoints(update, context, text)
            return
        case _:
            print(f'ERROR IN MSGHANDLER: No such state defined ({currentState})\nText: {text}')
            return

def mainCallBackHandler(update, context):
    dataClicked = ast.literal_eval(update.callback_query.data)
    optionID = dataClicked[1]
    value = dataClicked[3]

    if optionID == str(OptionIDEnum.beginRound):
        handleAdminBeginRound(update, context, value)
        return
    if optionID == str(OptionIDEnum.endSetPoints):
        handleAdminEndSetPoints(update, context, value)
        return
    else:
        print(f'ERROR IN CALLBACKHANDLER: No such optionID defined ({optionID})\nValue: {value}')
        return

#=========================Game Phase Checkers=========================
def checkSetPointsPhase(update, context):
    if (not currentGame.play) or currentGame.killEnabled:
        fullText = f"Set points phase has not started yet!\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id = update.message.chat.id,
            text = fullText,
            parse_mode = 'HTML')
        return False
    return True

def checkKillingPhase(update, context):
    if (not currentGame.play) or (not currentGame.killEnabled):
        fullText = f"Killing phase has not started yet!\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id = update.message.chat.id,
            text = fullText,
            parse_mode = 'HTML')
        return False
    return True

def checkPlayPhase(update, context):
    if not currentGame.play:
        fullText = f"Round has not started yet!\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id = update.message.chat.id,
            text = fullText,
            parse_mode = 'HTML')
        return False
    return True

#=========================Authentication helpers=======================
def checkAdmin(update, context, username):
    if username in admins:
        return True
    
    fullText = f"You are not admin!\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id = update.message.chat.id,
                     text = fullText,
                     parse_mode = 'HTML')
    return False

def checkGameMaster(update, context, username):
    if username in gameMasters:
        return True

    fullText = f"You are not GameMaster!\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id = update.message.chat.id,
                     text = fullText,
                     parse_mode = 'HTML')
    return False

def checkSafety(update, context, username):
    if username in safetyOfficers:
        return True

    fullText = f"You are not Safety!\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id = update.message.chat.id,
                     text = fullText,
                     parse_mode = 'HTML')
    return False

def checkSafetyBreaches(update, context):
    username = update.message.chat.username
    cumulativePlayerSafetyBreaches = getPlayerSafetyBreaches(username)
    if cumulativePlayerSafetyBreaches < highestAllowedSafetyBreach:
        return True
    
    fullText = f"You have a total of {cumulativePlayerSafetyBreaches} Safety Breaches! You may not play the game.\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id = update.message.chat.id,
                     text = fullText,
                     parse_mode = 'HTML')
    return False

#======================Getters=================================
def getTargetFaction(username):
    userDb = userTracker[username]["db"]
    return userDb.getTargetFaction(username, currentGame.currentRound)

def getAllFactionPoints(adminDb):
    factionPointsMap = {}
    for faction in factionsMap.keys():
        factionPoints = adminDb.getFactionPoints(faction, currentGame.currentRound)
        factionPointsMap[faction] = factionPoints
    return factionPointsMap

def getAllUsernames(db):
    return db.getAllUsernames(currentGame.currentRound)

def getPlayerSafetyBreaches(username):
    userDb = userTracker[username]["db"]
    cumulativeSafetyBreach = 0
    for round_num in roundList:
        roundSafetyBreach = userDb.getPlayerSafetyBreaches(username, round_num)
        cumulativeSafetyBreach += roundSafetyBreach
    return cumulativeSafetyBreach

#====================Other helpers=========================

def blastMessageToAll(text):
    for user in userTracker.values():
        bot.send_message(chat_id = user["chat_id"],
                     text = text,
                     parse_mode = 'HTML')

#===================Main Method============================
def main():
    # Start the bot.
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(API_KEY, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Admin commands
    dp.add_handler(CommandHandler("adminBeginRound", adminBeginRound))
    dp.add_handler(CommandHandler("adminEndSetPoints", adminEndSetPoints))

    # Player commands
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(CommandHandler("setpoints", promptSetPoints))
    dp.add_handler(CommandHandler("listpoints", handleListPoints))

    # Handle all messages
    dp.add_handler(MessageHandler(callback=mainMessageHandler, filters=Filters.all))

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
from calendar import weekday
from datetime import datetime, timezone
from email import message
import enum
import json
import logging
from os import kill
import random
from sqlite3 import Time
from tabnanny import check
import time
from tracemalloc import BaseFilter
from numpy import broadcast, full
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from env import get_api_key, get_port
from telebot import types, telebot
from telegram import CallbackQuery, ParseMode
import ast
from dbhelper import DBHelper, DBKeysMap, factionDataKeys, playerDataKeys
from game import Game
import adminCommands as adminCmd
import pandas

PORT = get_port()
API_KEY = get_api_key()
if API_KEY == None:
    raise Exception("Please update API Key")

# Excel to Database
# TODO: CHANGE TO ACTUAL EXCEL SHEET
excelFilePath = "./excel/test/shanRoyale2022Data1.xlsx"
playerDataRound1JSONArr = json.loads(pandas.read_excel(excelFilePath, sheet_name="playerDataRound1").to_json(orient='records'))
playerDataRound2JSONArr = json.loads(pandas.read_excel(excelFilePath, sheet_name="playerDataRound2").to_json(orient='records'))
factionDataJSONArr = json.loads(pandas.read_excel(excelFilePath, sheet_name="factionData").to_json(orient='records'))

mainDb = DBHelper("shan-royale.sqlite")
# Clear DB first, then setup
mainDb.purgeData()
mainDb.setup()
mainDb.playerDataJSONArrToDB(playerDataRound1JSONArr, 1)
mainDb.playerDataJSONArrToDB(playerDataRound2JSONArr, 2)
mainDb.factionDataJSONArrToDB(factionDataJSONArr)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Backup Excel file paths
saveStateExcelFilePath = "./excel/backup/ShanRoyale2022DataBackup.xlsx"

# Initialise bot
bot = telebot.TeleBot(API_KEY, parse_mode=None)

# ============================Constants======================================
# excel sheet names
playerDataRound1SheetName = "playerDataRound1"
playerDataRound2SheetName = "playerDataRound2"
factionDataSheetName = "factionData"


roundList = [1, 2]
yesNoList = ["Yes", "No"]

# TODO: LOAD UPON RESUME
# Game: currentRound, play, killEnabled, stickRound1, stickRound2
currentGame = Game(roundList[0])
factionsMap = {
    "1": "Sparta",
    "2": "Hades",
    "3": "Aphrodite",
    "4": "Nemesis"
}

# TODO: UPDATE
admins = ["praveeeenk", "Casperplz"]
gameMasters = ["praveeeenk", "Casperplz", "ddannyiel"]
safetyOfficers = ["praveeeenk", "Casperplz", "ddannyiel", "Jobeet"]

# TODO: LOAD UPON RESUME
# "username": { <state>: <text> }
adminQuery = {}

minPoints = 5
maxTeamPoints = 200
highestAllowedSafetyBreach = 2
immuneSecondsUponDeath = 90
wrongKillPenalty = 50

# TODO: ASK CASPER IF OKAY, INFORM CASPER IF NEED BE SHORTER
tier1bNumToSelect = 2
tier1bTopCut = 5
tier2bNumToSelect = 10
tier2bTopCut = 5
tier3bNumToSelect = 3
maxStickPerRound = 10
stickExpiryInSecs = 600

# =============================Texts==========================================
dontWasteMyTimeText = """\"<b>Don't waste my time...</b> You aren't allowed to use this command now.\"
~ Message by Caserplz"""

# ============================Tracking State===================================
# Possible states


class StateEnum(enum.Enum):
    setPoints = "setPoints"
    kill = "kill"
    giveStick = "giveStick"
    elimination = "elimination"
    adminAddPoints = "adminAddPoints"
    adminBroadcast = "adminBroadcast"
    yellowCard = "yellowCard"
    redCard = "redCard"


class OptionIDEnum(enum.Enum):
    beginRound = "beginRound"
    endSetPoints = "endSetPoints"
    endRound = "endRound"
    dying = "dying"
    visitSpyStation = "visitSpyStation"
    tier1a = "tier1a"
    tier1b = "tier1b"
    tier2a = "tier2a"
    tier2b = "tier2b"
    tier3a = "tier3a"
    tier3b = "tier3b"
    eliminationAskFaction = "eliminationAskFaction"
    adminAddPoints = "adminAddPoints"
    adminBroadcast = "adminBroadcast"


# Handles state of the bot for each user
# Key: username
# Value: dynamic dictionary
# <username>: { "state": , "db": , "chat_id": , "elimination_target": ,}
# TODO: LOAD UPON RESUME
userTracker = {}


def setState(username, state):
    userTracker[username].update({"state": state})
    print("State updated for " + username + ": " + str(userTracker[username]))

# ============================Key boards===================================
# Makes Inline Keyboard


def makeInlineKeyboard(lst, optionID):
    markup = types.InlineKeyboardMarkup()
    for value in lst:
        markup.add(types.InlineKeyboardButton(text=value,
                                              callback_data=f"['optionID', '{optionID}', 'value', '{value}']"))
    return markup

# ============================DB to file converters?===========================

def saveGameState():
    allPlayerData1Dict = mainDb.getALLPlayerDataJSON(1)
    allPlayerData2Dict = mainDb.getALLPlayerDataJSON(2)
    allFactionDataDict = mainDb.getALLFactionDataJSON()

    allPlayerData1JSON = pandas.DataFrame.from_dict(allPlayerData1Dict, orient="index")
    allPlayerData2JSON = pandas.DataFrame.from_dict(allPlayerData2Dict, orient="index")
    allFactionDataJSON = pandas.DataFrame.from_dict(allFactionDataDict, orient="index")
    with pandas.ExcelWriter(saveStateExcelFilePath) as writer:  
        allPlayerData1JSON.to_excel(writer, sheet_name=playerDataRound1SheetName)
        allPlayerData2JSON.to_excel(writer, sheet_name=playerDataRound2SheetName)
        allFactionDataJSON.to_excel(writer, sheet_name=factionDataSheetName)
    return

def reloadGameState():
    return

# ====================== Admin Commands ===============================

def adminBeginRoundCmd(update, context):
    username = update.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return

    text = """You are about to begin a round!\n
Which round to you want to begin?"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=text,
                     reply_markup=makeInlineKeyboard(
                         roundList, OptionIDEnum.beginRound),
                     parse_mode='HTML')


def handleAdminBeginRound(update, context, round_no):
    global currentGame
    currentGame = adminCmd.beginRound(round_no)

    adminText = f"""Thanks sir! Set Points phase for Round {currentGame.currentRound} has begun!!

Make sure to type /adminEndSetPoints to begin the Killing Phase."""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          text=adminText,
                          message_id=update.callback_query.message.message_id,
                          parse_mode='HTML')

    blastText = f"""<b>NOTICE</b>
Round {round_no} is about to begin!!

You are now in the <b>Set Points</b> phase

<b>Details of phase:</b>
- Duration: <b>about 10 mins</b>
- Make sure to /setpoints <b>individually</b> and assign yourselves some points!
- Enter /listpoints to see the <b>points of all members</b> in your faction
- Do not exceed your team cumulative points of <b>200</b>
- Everyone must be assigned at least <b>5 points</b>
- Killing is now <b>disabled</b>. You will be notified when the Killing phase begins

Enjoy!"""
    blastMessageToAll(blastText)


def adminEndSetPointsCmd(update, context):
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
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         yesNoList, OptionIDEnum.endSetPoints),
                     parse_mode='HTML')


def handleAdminEndSetPoints(update, context, yesNo):
    global currentGame
    chat_id = update.callback_query.message.chat.id
    message_id = update.callback_query.message.message_id
    if yesNo == yesNoList[1]:
        # "No" was pressed
        adminText = f"""No worries, Set Points phase has not ended. Please ask the respective OGL to make amends.\n
Once that is done, please type /adminEndSetPoints again.\n\n{dontWasteMyTimeText}"""
        bot.edit_message_text(chat_id=chat_id,
                              text=adminText,
                              message_id=message_id,
                              parse_mode='HTML')
        return

    # "Yes" was pressed
    currentGame = adminCmd.endSetPoints(currentGame)
    print(f"Admin End Set Points Game State:\n{currentGame.toString()}")
    adminText = f"""You have ended Set Points phase for Round {currentGame.currentRound}! Killing has now been enabled :)"""
    bot.edit_message_text(chat_id=chat_id,
                          text=adminText,
                          message_id=message_id,
                          parse_mode='HTML')

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
        bot.send_message(chat_id=user["chat_id"],
                         text=text,
                         parse_mode='HTML')


def adminEndRoundCmd(update, context):
    username = update.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return

    isPlayPhase = checkPlayPhase(update, context)
    if not isPlayPhase:
        return

    text = f"""You are about to end Round {currentGame.currentRound}!\n
Are you sure you want to do this?"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=text,
                     reply_markup=makeInlineKeyboard(
                         yesNoList, OptionIDEnum.endRound),
                     parse_mode='HTML')


def handleAdminEndRound(update, context, yesNo):
    global currentGame
    chat_id = update.callback_query.message.chat.id
    message_id = update.callback_query.message.message_id
    if yesNo == yesNoList[1]:
        # "No" was pressed
        adminText = f"""No worries, Round {currentGame.currentRound} has not ended.\n\n{dontWasteMyTimeText}"""
        bot.edit_message_text(chat_id=chat_id,
                              text=adminText,
                              message_id=message_id,
                              parse_mode='HTML')
        return

    # "Yes" was pressed
    currentGame = adminCmd.endRound(currentGame)
    print(f"Admin End Round Game State:\n{currentGame.toString()}")
    adminText = f"""You have ended Round {currentGame.currentRound}!
Please type /adminBeginRound to start another round."""
    bot.edit_message_text(chat_id=chat_id,
                          text=adminText,
                          message_id=message_id,
                          parse_mode='HTML')

    blastText = f"""<b>NOTICE</b>
Round {currentGame.currentRound} has ended!!

You may strategize your points distribution for the next round (if there is)

If not, wait for the admin to begin another round!

If there are no more round, hope you enjoyed the game and please gather at your next location!"""
    blastMessageToAll(blastText)

#TODO SORT VALUES
def adminFactionDetails(update, context):
    username = update.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return

    userDb = userTracker[username]["db"]
    summaryText = "<b>Factions Summary</b>"
    bankText = "\n\n<b>Banks</b>"
    totalPointsTxt = "\n\n<b>Points</b>"
    totalKillsTxt = "\n\n<b>Kills</b>"
    totalDeathsTxt = "\n\n<b>Deaths</b>"
    playerText = "\n\n"
    for playerFaction in factionsMap.keys():
        factionBank = userDb.getBank(playerFaction)
        factionMembersPointsMap = userDb.getFactionMemberPoints(
            playerFaction, currentGame.currentRound)
        factionKDArrMap = userDb.getFactionMemberKD(
            playerFaction, currentGame.currentRound)

        totalPoints = 0
        totalKills = 0
        totalDeaths = 0

        header = f"""---------------------------------------
<b>{factionsMap[str(playerFaction)]} Faction Individual Stats (ID: {playerFaction})</b>"""
        pointsTxt = "\n\n<b>Current Points:</b>"
        killCountTxt = "\n\n<b>Kill Count:</b>"
        deathCountTxt = "\n\n<b>Death Count:</b>"
        for username, points in factionMembersPointsMap.items():
            totalPoints += points
            pointsTxt += f"\n@{username}: {points}pts"
        for username, KDArr in factionKDArrMap.items():
            totalKills += KDArr[0]
            totalDeaths += KDArr[1]
            killCountTxt += f"\n@{username}: {KDArr[0]}"
            deathCountTxt += f"\n@{username}: {KDArr[1]}"

        bankText += f"\n- {factionsMap[str(playerFaction)]}: {factionBank}"
        totalPointsTxt += f"\n- {factionsMap[str(playerFaction)]}: {totalPoints}"
        totalKillsTxt += f"\n- {factionsMap[str(playerFaction)]}: {totalKills}"
        totalDeathsTxt += f"\n- {factionsMap[str(playerFaction)]}: {totalDeaths}"
        playerText += header + pointsTxt + killCountTxt + deathCountTxt + """
-------END OF FACTION'S INDIV PLAYER DEETS-------\n\n"""

    summaryText += bankText + totalPointsTxt + totalKillsTxt + totalDeathsTxt
    bot.send_message(chat_id=update.message.chat.id,
                     text=summaryText,
                     parse_mode='HTML')


def adminAddPoints(update, context):
    username = update.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return
    fullText = f"""You are about to <b>add points</b> for a faction

Please press the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    fullText += f"\n\n Note: If pressed wrongly, just add 0 points bodoh."
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.adminAddPoints),
                     parse_mode='HTML')
    return


def askAdminAddPoints(update, context, faction):
    username = update.callback_query.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return

    # Store faction data
    adminQuery[username] = {
        OptionIDEnum.adminAddPoints: faction
    }

    setState(username, StateEnum.adminAddPoints)

    fullText = f"""Please state the <b>number of points to add</b> for {factionsMap[str(faction)]} (ID: {faction})

~ Shan Royale 2022 Team"""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          text=fullText,
                          message_id=update.callback_query.message.message_id,
                          parse_mode='HTML')


def handleAdminAddPoints(update, context, points):
    username = update.message.chat.username
    chat_id = update.message.chat.id
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return

    try:
        points = int(points)
    except:
        txt = "<b>Wrong Input! Please type in an integer value only!</b>"
        bot.send_message(chat_id=chat_id,
                         text=txt,
                         parse_mode='HTML')
        return

    faction = adminQuery[username][OptionIDEnum.adminAddPoints]
    if faction not in factionsMap.keys():
        txt = f"<b>Faction specified is wrong!! (Value: {faction})</b>. Try /adminAddPoints again."
        bot.send_message(chat_id=chat_id,
                         text=txt,
                         parse_mode='HTML')
        return

    userDb = userTracker[username]["db"]
    factionBankBalance = userDb.getBank(faction)
    factionBankBalance += points
    userDb.setBank(factionBankBalance, faction)

    fullText = f"""Due to the good will of the game admin, <b>{factionsMap[str(faction)]} Faction has received {points}pts!</b>

Current bank balance: {factionBankBalance}

~ Shan Royale 2022 Team"""
    blastMessageToAll(fullText)

    adminQuery[username][OptionIDEnum.adminAddPoints] = ""
    setState(username, None)


def adminBroadcast(update, context):
    username = update.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return
    setState(username, StateEnum.adminBroadcast)
    fullText = f"""Please type in your message!

To cancel, type in /cancelBroadcast"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def handleAdminBroadcast(update, context, text):
    username = update.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return

    if text == "/cancelBroadcast":
        setState(username, None)
        fullText = f"Broadcast has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    # Store faction data
    adminQuery[username] = {
        StateEnum.adminBroadcast: text
    }

    fullText = f"Is this okay sir/maam?\n\n{text}'"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         yesNoList, OptionIDEnum.adminBroadcast),
                     parse_mode='HTML')


def pumpAdminBroadcast(update, context, yesNo):
    username = update.callback_query.message.chat.username
    chat_id = update.callback_query.message.chat.id
    message_id = update.callback_query.message.message_id
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return

    if yesNo == yesNoList[1]:
        # "No" was pressed
        bot.edit_message_text(chat_id=chat_id,
                              text=dontWasteMyTimeText,
                              message_id=message_id,
                              parse_mode='HTML')
        return
    # "Yes" was pressed
    broadcastText = adminQuery[username][StateEnum.adminBroadcast]
    if broadcastText == "":
        fullText = "No text was detected. Try /adminBroadcast again."
        bot.send_message(chat_id=chat_id,
                         text=fullText,
                         parse_mode='HTML')
        return

    blastMessageToAll(broadcastText)

    # Store faction data
    adminQuery[username][StateEnum.adminBroadcast] = ""
    setState(username, None)
    return

# ===========================Safety Officer Comands===========================================


def yellowCardCmd(update, context):
    username = update.message.chat.username
    isSafety = checkSafety(update, context, username)
    if not isSafety:
        return

    setState(username, StateEnum.yellowCard)

    fullText = f"""<b>You are about to award someone a yellow card (1 Safety Breach)</b>

If you wish to <b>proceed</b>, type in the <b>telegram handle of the offender</b>.

You must:
1) type in their handle <b>exactly as is</b> (with caps, special characters etc.)
2) <b>not put "@"</b> in front of their handle (eg. type in praveeeenk instead of @praveeeenk)

If you wish to <b>cancel</b>, type in /cancelCard"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def handleYellowCard(update, context, offenderUsername):
    print(f"HANDLING YELLOW CARD OF {offenderUsername}")
    username = update.message.chat.username
    isSafety = checkSafety(update, context, username)
    if not isSafety:
        return

    if offenderUsername == "/cancelCard":
        setState(username, None)
        fullText = f"Yellow/Red Card has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    valid = validUsername(update, context, offenderUsername)
    if not valid:
        return

    userDb = userTracker[username]["db"]
    currentSafetyBreaches = userDb.getPlayerSafetyBreaches(
        offenderUsername, currentGame.currentRound)
    currentSafetyBreaches += 1
    userDb.setPlayerSafetyBreaches(
        offenderUsername, currentGame.currentRound, currentSafetyBreaches)

    fullText = f"""@{offenderUsername} has been given a yellow Card, and now has {currentSafetyBreaches} safety breaches!

2 Safety Breaches, and you are out!"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')
    bot.send_message(chat_id=userTracker[offenderUsername]["chat_id"],
                     text=fullText,
                     parse_mode='HTML')

    setState(username, None)


def redCardCmd(update, context):
    username = update.message.chat.username
    isSafety = checkSafety(update, context, username)
    if not isSafety:
        return

    setState(username, StateEnum.redCard)

    fullText = f"""<b>You are about to award someone a red card (2 Safety Breaches)</b>

If you wish to <b>proceed</b>, type in the <b>telegram handle of the offender</b>

You must:
1) type in their handle <b>exactly as is</b> (with caps, special characters etc.)
2) <b>not put "@"</b> in front of their handle (eg. type in praveeeenk instead of @praveeeenk)

If you wish to <b>cancel</b>, type in /cancelCard"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def handleRedCard(update, context, offenderUsername):
    print(f"HANDLING RED CARD OF {offenderUsername}")
    username = update.message.chat.username
    isSafety = checkSafety(update, context, username)
    if not isSafety:
        return

    if offenderUsername == "/cancelCard":
        setState(username, None)
        fullText = f"Yellow/Red Card has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    valid = validUsername(update, context, offenderUsername)
    if not valid:
        return

    userDb = userTracker[username]["db"]
    currentSafetyBreaches = userDb.getPlayerSafetyBreaches(
        offenderUsername, currentGame.currentRound)
    currentSafetyBreaches += 2
    userDb.setPlayerSafetyBreaches(
        offenderUsername, currentGame.currentRound, currentSafetyBreaches)

    fullText = f"""@{offenderUsername} has been given a Red Card, and now has {currentSafetyBreaches} safety breaches!

2 Safety Breaches, and you are out!"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')
    bot.send_message(chat_id=userTracker[offenderUsername]["chat_id"],
                     text=fullText,
                     parse_mode='HTML')

    setState(username, None)

#========================Player Command Handlers===============================================
def startCmd(update, context):
    username = update.message.chat.username

    # Create database (this is required to ensure multiple ppl dont use the same db object)
    db = DBHelper()
    userExists = db.checkUsernameInDB(username)
    if not userExists:
        errorText = """Your username is <b>NOT in the database</b>. If you have changed your username after registering for TSE, please change your username back and try /start again.\n\n
Please contact @praveeeenk if the problem persists."""
        bot.send_message(chat_id=update.message.chat.id,
                         text=errorText,
                         parse_mode='HTML')
        return

    txt1 = "Hi! Welcome to the Shan Royale Bot\n"
    txt2 = "Type <b>/help</b> for more info\n\n"
    txt3 = "Registered username: " + username + "\n\n"
    txt4 = "IMPT: Please <b>do NOT change your username</b> after starting the bot"
    fullText = txt1 + txt2 + txt3 + txt4
    update.message.reply_text(text=fullText, parse_mode=ParseMode.HTML)

    # Add new user to userTracker
    if username not in userTracker.keys():
        newUserTracker = {
            "state": None,
            "db": db,
            "chat_id": update.message.chat.id,
            "elimination_target": ""
        }
        userTracker[username] = newUserTracker
    print("User Tracker: " + str(userTracker))


def helpCmd(update, context):
    playerCmds = """<b>Here are the suppported player commands:</b>\n
<b>/start</b> - Register yourself and start playing!
<b>/help</b> - List all available commands
<b>/faction</b> - See details about your faction
<b>/listbanks</b> - List the bank balances of all factions
<b>/setpoints</b> - Set/Reset your points for current round in Shan Royale
<b>/listpoints</b> - List your faction members' points for current round in Shan Royale
<b>/dying</b> - Set yourself as dying
<b>/kill</b> - Initiate a kill on someone
<b>/stick</b> - Use your stick to initiate a kill on someone
<b>/visitspystation</b> - Record your visit to the spy station
"""

    gamemasterCmds = """<b>Here are the suppported game master commands:</b>\n
<b>/tier1a</b> - Get Tier 1a information
<b>/tier1b</b> - Get Tier 1b information
<b>/tier2a</b> - Get Tier 2a information
<b>/tier2b</b> - Get Tier 2b information
<b>/tier3a</b> - Get Tier 3a information
<b>/tier3b</b> - Get Tier 3b information
<b>/givestick</b> - Give stick to a player
<b>/checkstick</b> - Check how many sticks have been given out
<b>/elimination</b> - Eliminate a player upon request
"""

    safetyCmds = """<b>Here are the suppported safety officer commands:</b>\n
<b>/yellowcard</b> - Give a player a yellow card
<b>/redcard</b> - Give a player a red card
"""

    adminCmds = """<b>Here are the supported admin commands:</b>\n
<b>/adminbeginround</b> - Begin the Set Points phase for a round
<b>/adminendsetpoints</b> - End the Set Points phase and begin Killing phase for the current round
<b>/adminendround</b> - End the Round despite the phase
<b>/adminfactiondetails</b> - Get summary of all faction details
<b>/adminaddpoints</b> - Add points to a faction's bank
<b>/adminbroadcast</b> - Broadcast a message
"""

    fullText = "<b>COMMANDS</b>"

    username = update.message.chat.username
    if username in admins:
        fullText += "\n\n" + adminCmds + "\n\n" + gamemasterCmds + "\n\n" + safetyCmds + "\n\n" + playerCmds
        update.message.reply_text(text = fullText, parse_mode = ParseMode.HTML)
        return
    
    if username in gameMasters:
        fullText += "\n\n" + gamemasterCmds + "\n\n" + safetyCmds + "\n\n" + playerCmds
        update.message.reply_text(text=fullText, parse_mode=ParseMode.HTML)
        return
    
    if username in safetyOfficers:
        fullText += "\n\n" + safetyCmds + "\n\n" + playerCmds
        update.message.reply_text(text=fullText, parse_mode=ParseMode.HTML)
        return

    fullText += "\n\n" + playerCmds
    update.message.reply_text(text=fullText, parse_mode=ParseMode.HTML)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

#===========================General Player Cmds======================
def factionCmd(update, context):
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return

    username = update.message.chat.username
    userDb = userTracker[username]["db"]
    playerFaction = userDb.getPlayerFaction(username, currentGame.currentRound)
    factionBank = userDb.getBank(playerFaction)
    factionMembersPointsMap = userDb.getFactionMemberPoints(playerFaction, currentGame.currentRound)
    factionKDArrMap = userDb.getFactionMemberKD(playerFaction, currentGame.currentRound)
    
    sortedMemberPointsArr = sorted(factionMembersPointsMap.items(), key=lambda memberPoints: memberPoints[1], reverse=True)
    sortedKillsMemberKDArr = sorted(factionKDArrMap.items(), key=lambda memberKD: memberKD[1][0], reverse=True)
    sortedDeathsMemberKDArr = sorted(factionKDArrMap.items(), key=lambda memberKD: memberKD[1][1], reverse=True)

    header = f"<b>{factionsMap[str(playerFaction)]} Faction Stats (id: {playerFaction})</b>"
    bankTxt = f"\n\n<b>Bank:</b> {factionBank}"
    pointsTxt = "\n\n<b>Current Points:</b>"
    killCountTxt = "\n\n<b>Kill Count:</b>"
    deathCountTxt = "\n\n<b>Death Count:</b>"
    for memberPoints in sortedMemberPointsArr:
        username = memberPoints[0]
        points = memberPoints[1]
        pointsTxt += f"\n@{username}: {points}pts"
    for memberKD in sortedKillsMemberKDArr:
        username = memberKD[0]
        kills = memberKD[1][0]
        killCountTxt += f"\n@{username}: {kills}"
    for memberKD in sortedDeathsMemberKDArr:
        username = memberKD[0]
        death = memberKD[1][1]
        deathCountTxt += f"\n@{username}: {death}"
    fullText = header + bankTxt + pointsTxt + killCountTxt + deathCountTxt

    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')

def listBanksCmd(update, context):
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return

    username = update.message.chat.username
    userDb = userTracker[username]["db"]
    factionBankMap = {}
    for faction, name in factionsMap.items():
        factionBank = userDb.getBank(faction)
        factionBankMap[name] = factionBank
    sortedArr = sorted(factionBankMap.items(), key=lambda factionBank: factionBank[1], reverse=True)

    bankTxt = "<b>Faction Banks</b> (Sorted Order)\n"
    for factionBank in sortedArr:
        name = factionBank[0]
        bank = factionBank[1]
        bankTxt += f"\n<b>{name}:</b> {bank}pts"
    
    bot.send_message(chat_id = update.message.chat.id,
        text = bankTxt,
        parse_mode = 'HTML')

#===========================Set points==============================
def setPointsCmd(update, context):
    setPointsPhase = checkSetPointsPhase(update, context)
    if not setPointsPhase:
        return

    safe = checkSafetyBreaches(update, context)
    if not safe:
        return

    username = update.message.chat.username
    db = userTracker[username]["db"]
    playerFaction = db.getPlayerFaction(username, currentGame.currentRound)
    currentFactionPoints = db.getFactionPoints(playerFaction, currentGame.currentRound)
    playerCurrentPoints = db.getRoundPoints(username, currentGame.currentRound)
    setState(username, StateEnum.setPoints)

    fullText = f"""Type in the points allocated to you in <b>Round {currentGame.currentRound}</b>\n

Your Current Points: <b>{playerCurrentPoints}pts</b>
Points Assigned Faction-wide so far: <b>{currentFactionPoints}pts</b>

Take Note:<em>
- Everyone must be allocated at least <b>5 points</b>
- <b>Do not exceed</b> your total team points of 200!
</em>
"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')

def handleSetPoints(update, context, text):
    chat_id = update.message.chat.id
    username = update.message.chat.username
    text = update.message.text
    setPointsPhase = checkSetPointsPhase(update, context)
    if not setPointsPhase:
        setState(username, None)
        return

    safe = checkSafetyBreaches(update, context)
    if not safe:
        return

    db = userTracker[username]["db"]
    playerFaction = db.getPlayerFaction(username, currentGame.currentRound)
    currentFactionPoints = db.getFactionPoints(playerFaction, currentGame.currentRound)
    playerCurrentPoints = db.getRoundPoints(username, currentGame.currentRound)
    invalid = invalidPoints(chat_id, text, currentFactionPoints - playerCurrentPoints)
    if invalid:
        return
    points = int(text)

    db.updateRoundPoints(username, points, currentGame.currentRound)
    updatedFactionPoints = db.getFactionPoints(playerFaction, currentGame.currentRound)

    fullText = f"""Allocated <b>{points} points</b> to you for <b>Round {currentGame.currentRound}</b>

Points Assigned Faction-wide so far: <b>{updatedFactionPoints}pts</b>

Click <b>/setpoints</b> again to <b>reset</b> points for this round!
"""
    bot.send_message(chat_id=chat_id,
                     text=fullText,
                     parse_mode='HTML')

    setState(username, None)


def listPointsCmd(update, context):
    playPhase = checkPlayPhase(update, context)
    if not playPhase:
        return

    safe = checkSafetyBreaches(update, context)
    if not safe:
        return

    username = update.message.chat.username
    userDb = userTracker[username]["db"]
    playerFaction = userDb.getPlayerFaction(username, currentGame.currentRound)
    factionMembersPointsMap = userDb.getFactionMemberPoints(playerFaction, currentGame.currentRound)
    sortedArr = sorted(factionMembersPointsMap.items(), key=lambda memberPoints: memberPoints[1], reverse=True)

    txt1 = f"Here are the current updated points held by your {factionsMap[str(playerFaction)]} faction members\n"
    txt2 = ""
    totalPoints = 0
    for memberPoints in sortedArr:
        username = memberPoints[0]
        points = memberPoints[1]
        totalPoints += int(points)
        txt2 += f"\n@{username}: {points}pts"
    header = f"<b>{factionsMap[str(playerFaction)]} Points Summary</b>\n\n<b>Total: {totalPoints}pts</b>\n\n"
    fullText = header + txt1 + txt2

    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def invalidPoints(chat_id, text, currentFactionPoints):
    try:
        points = int(text)
    except:
        txt = "<b>Wrong Input! Please type in a value from 5 - 200 only!</b>"
        bot.send_message(chat_id=chat_id,
                         text=txt,
                         parse_mode='HTML')
        return True

    if points < minPoints:
        fullText = f"""Too little points for <b>Round {currentGame.currentRound}</b>!
Everyone must be allocated at least <b>5 points</b>.\n
Please enter your points for this round again"""
        bot.send_message(chat_id = chat_id,
            text = fullText,
            parse_mode = 'HTML')
        return True
    
    proposedPoints = currentFactionPoints + points
    if proposedPoints > maxTeamPoints:
        fullText = f"""You <b>may not add {points}pts</b> to yourself, as that will bring your faction's total points assigned to <b>{proposedPoints}pts</b>!

Enter /listpoints to see the distribution of points within your faction, and ensure that it tallies to <b>{maxTeamPoints}pts</b>.

Please enter your points for this round again."""
        bot.send_message(chat_id = chat_id,
            text = fullText,
            parse_mode = 'HTML')
        return True
    
    return False

# =========================Killing Mechanism================================


def dyingCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return
    username = update.message.chat.username
    immune = checkImmunity(update, context, username)
    if immune:
        return

    fullText = f"""/dying should only be entered <b>once you have been "killed" in person by someone else.</b>

Press yes if you wish to proceed."""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         yesNoList, OptionIDEnum.dying),
                     parse_mode='HTML')


def handleDying(update, context, yesNo):
    chat_id = update.callback_query.message.chat.id
    message_id = update.callback_query.message.message_id
    safe = checkSafetyBreaches(update, context, callback=True)
    if not safe:
        return
    killingPhase = checkKillingPhase(update, context, callback=True)
    if not killingPhase:
        setState(username, None)
        return
    username = update.callback_query.message.chat.username
    immune = checkImmunity(update, context, username)
    if immune:
        return
    if yesNo == yesNoList[1]:
        # "No" was pressed
        bot.edit_message_text(chat_id=chat_id,
                              text=dontWasteMyTimeText,
                              message_id=message_id,
                              parse_mode='HTML')
        return
    # "Yes" was pressed
    userDb = userTracker[username]["db"]
    userDb.setPlayerDying(username, currentGame.currentRound, True)

    fullText = f"""<b>You have registered yourself as dying.</b> The killer must now /kill to confirm the kill.

You will be informed on the changes in points once the kill is validated."""
    bot.edit_message_text(chat_id=chat_id,
                          text=fullText,
                          message_id=message_id,
                          parse_mode='HTML')


def killCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return
    username = update.message.chat.username
    immune = checkImmunity(update, context, username)
    if immune:
        return

    setState(username, StateEnum.kill)

    fullText = f"""/kill should only be entered <b>once you have "killed" someone else in person.</b>

If you wish to <b>proceed</b>, type in the <b>telegram handle of the victim</b>

You must:
1) type in their handle <b>exactly as is</b> (with caps, special characters etc.)
2) <b>not put "@"</b> in front of their handle (eg. type in praveeeenk instead of @praveeeenk)

If you wish to <b>cancel</b>, type in /cancelkill"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def handleKill(update, context, victimUsername):
    print(f"HANDLING KILL OF {victimUsername}")
    username = update.message.chat.username
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        setState(username, None)
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return

    if victimUsername == "/cancelkill":
        setState(username, None)
        fullText = f"Kill has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    valid = validUsername(update, context, victimUsername)
    if not valid:
        return

    victimDying = checkVictimDying(update, context, victimUsername)
    if not victimDying:
        setState(username, None)
        return

    victimInPreyFaction = checkVictimInPreyFaction(username, victimUsername)
    if victimInPreyFaction:
        rightKill(update, context, username, victimUsername)
    else:
        wrongKill(update, context, username, victimUsername)

    setState(username, None)


def stickCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return
    username = update.message.chat.username
    immune = checkImmunity(update, context, username)
    if immune:
        return
    stick = checkStick(update, context, username)
    if not stick:
        return

    setState(username, StateEnum.kill)

    fullText = f"""You are about to use your stick to initiate a kill.

/stick should only be entered <b>once you have "killed" someone else in person.</b>

If you wish to <b>proceed</b>, type in the <b>telegram handle of the victim</b>

You must:
1) type in their handle <b>exactly as is</b> (with caps, special characters etc.)
2) <b>not put "@"</b> in front of their handle (eg. type in praveeeenk instead of @praveeeenk)

If you wish to <b>cancel</b>, type in /cancelkill"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def checkImmunity(update, context, username):
    userDb = userTracker[username]["db"]
    currentTime = time.time()
    playerImmunityExpiry = userDb.getImmunityExpiry(
        username, currentGame.currentRound)
    remainingTime = playerImmunityExpiry - currentTime
    if remainingTime > 0:
        fullText = f"You are still immune for {remainingTime} seconds!\n\nYou may not be killed or kill!"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return True
    return False


def checkStick(update, context, username):
    userDb = userTracker[username]["db"]
    currentTime = time.time()
    playerStickExpiry = userDb.getStickExpiry(
        username, currentGame.currentRound)
    expiredForTime = currentTime - playerStickExpiry
    if expiredForTime > 0:
        fullText = f"Your stick <b>expired at {datetime.fromtimestamp(playerStickExpiry)}</b>!\n\n(If the time seems inaccurate, its because it may be in GMT+0. If so, add 8 hours to the stated time.)"
        bot.send_message(chat_id=update.message.chat.id,
                         text=fullText,
                         parse_mode='HTML')
        return False
    return True


def validUsername(update, context, username):
    chat_id = update.message.chat.id
    if not username in userTracker.keys():
        txt = "The victim has not started the game! <b>Ask them to press /start</b>"
        bot.send_message(chat_id=chat_id,
                         text=txt,
                         parse_mode='HTML')
        return False

    return True


def checkVictimDying(update, context, username):
    userDb = userTracker[username]["db"]
    victimDying = userDb.getPlayerDying(username, currentGame.currentRound)

    if not victimDying:
        fullText = f"""Victim has not declared themselves dying!

<b>Ask the victim to enter /dying</b> on their phone first! After which, you may type <b>/kill</b> again."""
        bot.send_message(chat_id=update.message.chat.id,
                         text=fullText,
                         parse_mode='HTML')
        return False
    return True


def checkVictimInPreyFaction(killerUsername, victimUsername):
    userDb = userTracker[killerUsername]["db"]
    killerTargetFaction = getTargetFaction(killerUsername)
    victimFaction = userDb.getPlayerFaction(
        victimUsername, currentGame.currentRound)
    if int(killerTargetFaction) == int(victimFaction):
        return True
    return False


def rightKill(update, context, killerUsername, victimUsername):
    userDb = userTracker[killerUsername]["db"]
    killerData = userDb.getPlayerDataJSON(
        killerUsername, currentGame.currentRound)
    victimData = userDb.getPlayerDataJSON(
        victimUsername, currentGame.currentRound)

    killerFaction = killerData[playerDataKeys.faction]
    victimFaction = victimData[playerDataKeys.faction]
    killerFactionData = userDb.getFactionDataJSON(killerFaction)

    # Update faction data
    pointsToAdd = victimData[playerDataKeys.points]
    killerFactionData[factionDataKeys.bank] += pointsToAdd
    userDb.replaceFactionDataFromJSON(killerFactionData)

    # Update victim data
    victimData[playerDataKeys.immunityExpiry] = time.time() + \
                                                          immuneSecondsUponDeath
    victimData[playerDataKeys.points] = 5
    victimData[playerDataKeys.dying] = 0
    victimData[playerDataKeys.deathCount] += 1
    userDb.replacePlayerDataFromJSON(victimData, currentGame.currentRound)

    # Update killer data
    killerData[playerDataKeys.killCount] += 1
    userDb.replacePlayerDataFromJSON(killerData, currentGame.currentRound)

    # Blast message to killer's faction
    killerFactionText = f"""<b>{factionsMap[str(killerFaction)]} Faction Update</b>

{killerData[playerDataKeys.fullname]} (@{killerData[playerDataKeys.username]}) has <b>successfully killed</b> {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]})!

Points added to faction bank: <b>{pointsToAdd}pts</b>
Current faction bank balance: <b>{killerFactionData[factionDataKeys.bank]}pts</b>

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is now <b>immune from kills</b> for the next {immuneSecondsUponDeath}s."""
    killerFactionMembers = userDb.getFactionMemberUsernames(
        killerFaction, currentGame.currentRound)
    for username in killerFactionMembers:
        if username not in userTracker.keys():
            continue
        chat_id = userTracker[username]["chat_id"]
        bot.send_message(chat_id=chat_id,
                         text=killerFactionText,
                         parse_mode='HTML')

    # Blast message to victim's faction
    victimFactionText = f"""<b>{factionsMap[str(victimFaction)]} Faction Update</b>

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>killed</b>! Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is now <b>immune from kills</b> for the next {immuneSecondsUponDeath}s."""
    victimFactionMembers = userDb.getFactionMemberUsernames(
        victimFaction, currentGame.currentRound)
    for username in victimFactionMembers:
        if username not in userTracker.keys():
            continue
        chat_id = userTracker[username]["chat_id"]
        bot.send_message(chat_id=chat_id,
                         text=victimFactionText,
                         parse_mode='HTML')


def wrongKill(update, context, killerUsername, victimUsername):
    userDb = userTracker[killerUsername]["db"]
    killerFullname = userDb.getFullname(
        killerUsername, currentGame.currentRound)
    victimFullname = userDb.getFullname(
        victimUsername, currentGame.currentRound)
    killerFaction = userDb.getPlayerFaction(
        killerUsername, currentGame.currentRound)
    victimFaction = userDb.getPlayerFaction(
        victimUsername, currentGame.currentRound)

    if killerFaction == victimFaction:
        txt = f"""<b>{factionsMap[str(killerFaction)]} Faction Update</b>

Ummmmmm...

{killerFullname} (@{killerUsername}) tried to <b>wrongly kill</b> their faction mate, {victimFullname} (@{victimUsername})!

Please settle your internal rivalry guys..."""
        killerFactionMembers = userDb.getFactionMemberUsernames(
            killerFaction, currentGame.currentRound)
        for username in killerFactionMembers:
            if username not in userTracker.keys():
                continue
            chat_id = userTracker[username]["chat_id"]
            bot.send_message(chat_id=chat_id,
                             text=txt,
                             parse_mode='HTML')
        return

    # Update faction banks
    killerBankBalance = userDb.getBank(killerFaction)
    victimBankBalance = userDb.getBank(victimFaction)
    killerBankBalance -= wrongKillPenalty
    victimBankBalance += wrongKillPenalty
    userDb.setBank(killerBankBalance, killerFaction)
    userDb.setBank(victimBankBalance, victimFaction)

    # Update victim dying to false
    userDb.setPlayerDying(victimUsername, currentGame.currentRound, False)

    # Blast message to killer's faction
    killerFactionText = f"""<b>{factionsMap[str(killerFaction)]} Faction Update</b>

BOOOOOOOOOOOOOOOOOO!

{killerFullname} (@{killerUsername}) has <b>wrongly killed</b> {victimFullname} (@{victimUsername})!

Thus, <b>{wrongKillPenalty}pts</b> have been transferred from your faction bank to the victim's faction bank.
Current faction bank balance: <b>{killerBankBalance}pts</b>

Don't noob and anyhow kill can?"""
    killerFactionMembers = userDb.getFactionMemberUsernames(
        killerFaction, currentGame.currentRound)
    for username in killerFactionMembers:
        if username not in userTracker.keys():
            continue
        chat_id = userTracker[username]["chat_id"]
        bot.send_message(chat_id=chat_id,
                         text=killerFactionText,
                         parse_mode='HTML')

    # Blast message to victim's faction
    victimFactionText = f"""<b>{factionsMap[str(victimFaction)]} Faction Update</b>

{victimFullname} (@{victimUsername}) has been <b>wrongly killed</b> by {killerFullname} (@{killerUsername})!

Thus, <b>{wrongKillPenalty}pts</b> have been transferred from the killer's faction bank to your faction bank.
Current faction bank balance: <b>{victimBankBalance}pts</b>

<b>Note:</b> The victim, {victimFullname} (@{victimUsername}), is NOT given immunity from kills."""
    victimFactionMembers = userDb.getFactionMemberUsernames(
        victimFaction, currentGame.currentRound)
    for username in victimFactionMembers:
        if username not in userTracker.keys():
            continue
        chat_id = userTracker[username]["chat_id"]
        bot.send_message(chat_id=chat_id,
                         text=victimFactionText,
                         parse_mode='HTML')

# =========================Spystation Mechanism================================


def visitSpyStationCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return
    username = update.message.chat.username
    visited = visitedSpyStation(update, context, username)
    if visited:
        return

    fullText = f"""/visitSpyStation should only be entered <b>once you are going to engage with the game master at the spy station</b>

You may only visit the spy station <b>once per round</b>.

Are you sure you are visiting the spy station?"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         yesNoList, OptionIDEnum.visitSpyStation),
                     parse_mode='HTML')


def handleVisitSpyStation(update, context, yesNo):
    killingPhase = checkKillingPhase(update, context, callback=True)
    if not killingPhase:
        return
    safe = checkSafetyBreaches(update, context, callback=True)
    if not safe:
        return

    chat_id = update.callback_query.message.chat.id
    message_id = update.callback_query.message.message_id
    if yesNo == yesNoList[1]:
        # "No" was pressed
        bot.edit_message_text(chat_id=chat_id,
                              text=dontWasteMyTimeText,
                              message_id=message_id,
                              parse_mode='HTML')
        return
    # "Yes" was pressed
    username = update.callback_query.message.chat.username
    userDb = userTracker[username]["db"]
    userDb.setPlayerVisitSpyStation(username, currentGame.currentRound, True)
    playerFaction = userDb.getPlayerFaction(username, currentGame.currentRound)

    fullText = f"""<b>You (@{username}) have registered yourself at the Spy Station</b>

Faction Name (ID): {factionsMap[str(playerFaction)]} ({playerFaction})

Show this pass to the game master to proceed with the station activities."""
    bot.edit_message_text(chat_id=chat_id,
                          text=fullText,
                          message_id=message_id,
                          parse_mode='HTML')


def visitedSpyStation(update, context, username):
    userDb = userTracker[username]["db"]
    visitedSpyStation = userDb.getPlayerVisitSpyStation(
        username, currentGame.currentRound)

    if visitedSpyStation:
        fullText = f"""You have visited the spy station in this round!\n\n{dontWasteMyTimeText}"""
        bot.send_message(chat_id=update.message.chat.id,
                         text=fullText,
                         parse_mode='HTML')
        return True
    return False

# ========================Spy Master Commands==================================


def tier1aCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for <b>1 Faction that is NOT the predator faction</b> of the requested faction

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.tier1a),
                     parse_mode='HTML')


def handleTier1a(update, context, faction):
    killingPhase = checkKillingPhase(update, context, callback=True)
    if not killingPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    userDb = userTracker[username]["db"]
    predatorFaction = userDb.getPredatorFaction(
        faction, currentGame.currentRound)
    nonPredatorFactions = []
    for factionID in factionsMap.keys():
        if factionID == str(faction) or factionID == str(predatorFaction):
            continue
        nonPredatorFactions.append(factionID)
    random_num = random.randint(0, len(factionsMap) - 1 - 2)
    selectedFaction = nonPredatorFactions[int(random_num)]

    gameMasterText = f"""{factionsMap[selectedFaction]} (ID: {selectedFaction}) is <b>not</b> the predator faction of {factionsMap[faction]}!

~ Shan Royale 2022 Team"""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          text=gameMasterText,
                          message_id=update.callback_query.message.message_id,
                          parse_mode='HTML')


def tier1bCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for <b>{tier1bNumToSelect} people from the prey faction</b> of the requested faction, who <b>do not</b> possess the most number of points.

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.tier1b),
                     parse_mode='HTML')


def handleTier1b(update, context, faction):
    killingPhase = checkKillingPhase(update, context, callback=True)
    if not killingPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    userDb = userTracker[username]["db"]
    preyFaction = userDb.getTargetFactionFromFaction(
        faction, currentGame.currentRound)
    preyMemberPointsMap = userDb.getFactionMemberPoints(
        preyFaction, currentGame.currentRound)
    sortedArr = sorted(preyMemberPointsMap.items(),
                       key=lambda memberPoints: memberPoints[1], reverse=True)
    print(f"Tier 1b Prey Faction Arr: {sortedArr}")

    numPreyLeft = len(sortedArr) - tier1bTopCut
    if numPreyLeft <= 0:
        print("ERROR: TOO LITTLE PREY LEFT ")
        return

    if numPreyLeft > tier1bNumToSelect:
        numPreyToSelect = tier1bNumToSelect
    else:
        numPreyToSelect = numPreyLeft

    # RAndom num avoids top ppl specified by tier1bTopCut
    # TODO: If num left < tier1bTopCut, this results in a loop
    randomNumArray = []
    for i in range(numPreyToSelect):
        random_num = random.randint(tier1bTopCut, numPreyToSelect)
        while random_num in randomNumArray:
            random_num = random.randint(tier1bTopCut, numPreyToSelect)
        randomNumArray.append(random_num)
    print(randomNumArray)

    pointsTxt = ""
    for preyIndex in randomNumArray:
        selectedPreyTuple = sortedArr[preyIndex]
        pointsTxt += f"@{selectedPreyTuple[0]} - {selectedPreyTuple[1]}pts\n"

    gameMasterText = f"""Here are the details of <b>{numPreyToSelect}</b> people from the <b>prey faction of {factionsMap[faction]}</b>, who <b>do not</b> possess the most number of points.

{pointsTxt}
~ Shan Royale 2022 Team"""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          text=gameMasterText,
                          message_id=update.callback_query.message.message_id,
                          parse_mode='HTML')


def tier2aCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for <b>the predator faction</b> of the requested faction

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.tier2a),
                     parse_mode='HTML')


def handleTier2a(update, context, faction):
    killingPhase = checkKillingPhase(update, context, callback=True)
    if not killingPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    userDb = userTracker[username]["db"]
    predatorFaction = userDb.getPredatorFaction(
        faction, currentGame.currentRound)

    gameMasterText = f"""<b>{factionsMap[str(predatorFaction)]} (ID: {predatorFaction})</b> is the predator faction of {factionsMap[str(faction)]}!

~ Shan Royale 2022 Team"""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          text=gameMasterText,
                          message_id=update.callback_query.message.message_id,
                          parse_mode='HTML')


def tier2bCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for <b>{tier2bNumToSelect} people from the prey faction</b> of the requested faction, who <b>do not</b> possess the most number of points.

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.tier2b),
                     parse_mode='HTML')


def handleTier2b(update, context, faction):
    killingPhase = checkKillingPhase(update, context, callback=True)
    if not killingPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    userDb = userTracker[username]["db"]
    preyFaction = userDb.getTargetFactionFromFaction(
        faction, currentGame.currentRound)
    preyMemberPointsMap = userDb.getFactionMemberPoints(
        preyFaction, currentGame.currentRound)
    sortedArr = sorted(preyMemberPointsMap.items(),
                       key=lambda memberPoints: memberPoints[1], reverse=True)
    print(f"Tier 2b Prey Faction Arr: {sortedArr}")

    numPreyLeft = len(sortedArr) - tier2bTopCut
    if numPreyLeft <= 0:
        print("ERROR: TOO LITTLE PREY LEFT ")
        return

    if numPreyLeft > tier2bNumToSelect:
        numPreyToSelect = tier2bNumToSelect
    else:
        numPreyToSelect = numPreyLeft

    # RAndom num avoids top ppl specified by tier2bTopCut
    # TODO: If num left < tier1bTopCut, this results in a loop
    randomNumArray = []
    for i in range(numPreyToSelect):
        random_num = random.randint(tier2bTopCut, numPreyToSelect)
        while random_num in randomNumArray:
            random_num = random.randint(tier2bTopCut, numPreyToSelect)
        randomNumArray.append(random_num)
    print(randomNumArray)

    pointsTxt = ""
    for preyIndex in randomNumArray:
        selectedPreyTuple = sortedArr[preyIndex]
        pointsTxt += f"@{selectedPreyTuple[0]} - {selectedPreyTuple[1]}pts\n"

    gameMasterText = f"""Here are the details of <b>{numPreyToSelect}</b> people from the <b>prey faction of {factionsMap[faction]}</b>, who <b>do not</b> possess the most number of points.

{pointsTxt}
~ Shan Royale 2022 Team"""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          text=gameMasterText,
                          message_id=update.callback_query.message.message_id,
                          parse_mode='HTML')


def tier3aCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for:
1) <b>The predator faction</b> of the requested faction AND
2) The player from the predator faction with the <b>most kills</b>

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.tier3a),
                     parse_mode='HTML')


def handleTier3a(update, context, faction):
    killingPhase = checkKillingPhase(update, context, callback=True)
    if not killingPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    userDb = userTracker[username]["db"]
    predatorFaction = userDb.getPredatorFaction(
        faction, currentGame.currentRound)
    predatorFactionKDMap = userDb.getFactionMemberKD(
        faction, currentGame.currentRound)
    sortedArr = sorted(predatorFactionKDMap.items(
    ), key=lambda memberPoints: memberPoints[1][0], reverse=True)
    predatorMostKillsTuple = sortedArr[0]

    gameMasterText = f"""<b>{factionsMap[str(predatorFaction)]} (ID: {predatorFaction})</b> is the predator faction of {factionsMap[str(faction)]}!

The player in the predator faction with most kills is @{predatorMostKillsTuple[0]}, with {predatorMostKillsTuple[1][0]} kills.

~ Shan Royale 2022 Team"""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          text=gameMasterText,
                          message_id=update.callback_query.message.message_id,
                          parse_mode='HTML')


def tier3bCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for <b>{tier3bNumToSelect} people from the prey faction</b> of the requested faction, who possess the <b>most number of points</b>.

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.tier3b),
                     parse_mode='HTML')


def handleTier3b(update, context, faction):
    killingPhase = checkKillingPhase(update, context, callback=True)
    if not killingPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    userDb = userTracker[username]["db"]
    preyFaction = userDb.getTargetFactionFromFaction(
        faction, currentGame.currentRound)
    preyMemberPointsMap = userDb.getFactionMemberPoints(
        preyFaction, currentGame.currentRound)
    sortedArr = sorted(preyMemberPointsMap.items(),
                       key=lambda memberPoints: memberPoints[1], reverse=True)
    print(f"Tier 3b Prey Faction Arr: {sortedArr}")

    numPreyToSelect = tier3bNumToSelect
    if len(sortedArr) <= tier3bNumToSelect:
        numPreyToSelect = len(sortedArr)

    indexArray = [x for x in range(numPreyToSelect)]
    print(indexArray)

    pointsTxt = ""
    for preyIndex in indexArray:
        selectedPreyTuple = sortedArr[preyIndex]
        pointsTxt += f"@{selectedPreyTuple[0]} - {selectedPreyTuple[1]}pts\n"

    gameMasterText = f"""Here are the details of <b>{numPreyToSelect}</b> people from the <b>prey faction of {factionsMap[faction]}</b>, who possess the <b>most number of points</b>.

{pointsTxt}
~ Shan Royale 2022 Team"""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          text=gameMasterText,
                          message_id=update.callback_query.message.message_id,
                          parse_mode='HTML')


def giveStickCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return
    canGive = canGiveStick(update, context)
    if not canGive:
        return

    setState(username, StateEnum.giveStick)

    fullText = f"""/giveStick should only be entered when the player has <b>completed their required task at the spy station.</b>

If you wish to <b>proceed</b>, type in the <b>telegram handle of the victim</b>

You must:
1) type in their handle <b>exactly as is</b> (with caps, special characters etc.)
2) <b>not put "@"</b> in front of their handle (eg. type in praveeeenk instead of @praveeeenk)

If you wish to <b>cancel</b>, type in /cancelGiveStick"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def handleGiveStick(update, context, giveStickUsername):
    print(f"HANDLING GIVE STICK OF {giveStickUsername}")
    username = update.message.chat.username
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        setState(username, None)
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return

    if giveStickUsername == "/cancelGiveStick":
        setState(username, None)
        fullText = f"Give Stick has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    valid = validUsername(update, context, giveStickUsername)
    if not valid:
        return

    canGive = canGiveStick(update, context)
    if not canGive:
        setState(username, None)
        return

    addStick(giveStickUsername)
    fullText = f"""<b>Stick has been given to {giveStickUsername}</b>! It will expire in about <b>{stickExpiryInSecs}s</b>.

Sticks given in Round 1: {currentGame.stickRound1}
Sticks given in Round 2: {currentGame.stickRound2}"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')
    setState(username, None)


def canGiveStick(update, context):
    cannotGiveText = f"""You may not give sticks as the round's stick count has been maxed out!\n\n{dontWasteMyTimeText}"""
    currentStick = getStick()
    if currentStick == None:
        print("ERR: Current Stick is None.")
        return

    canGive = currentStick < maxStickPerRound
    if not canGive:
        bot.send_message(chat_id=update.message.chat.id,
                         text=cannotGiveText,
                         parse_mode='HTML')
        return False
    return True


def checkStickCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return
    canGive = canGiveStick(update, context)
    if not canGive:
        return

    fullText = f"""Sticks left for:
Round 1 - {currentGame.stickRound1}
Round 2 - {currentGame.stickRound2}"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


#TODO: Add in elimination tiers
def eliminationCmd(update, context):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    setState(username, StateEnum.elimination)

    fullText = f"""/elimination should only be entered when a player has <b>turned in the "death note"</b> at the spy station.

If you wish to <b>proceed</b>, type in the <b>telegram handle of the victim</b>, as requested by the player.

You must:
1) type in their handle <b>exactly as is</b> (with caps, special characters etc.)
2) <b>not put "@"</b> in front of their handle (eg. type in praveeeenk instead of @praveeeenk)

If you wish to <b>cancel</b>, type in /cancelElimination"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def eliminationAskFaction(update, context, victimUsername):
    killingPhase = checkKillingPhase(update, context)
    if not killingPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    if victimUsername == "/cancelElimination":
        setState(username, None)
        fullText = f"Elimination has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    valid = validUsername(update, context, victimUsername)
    if not valid:
        return

    # Store victimUsername
    userTracker[username]["elimination_target"] = victimUsername

    fullText = f"""Please state the <b>ID of the faction</b> of the player requesting the elimination.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.eliminationAskFaction),
                     parse_mode='HTML')


def handleElimination(update, context, killerFaction):
    username = update.callback_query.message.chat.username
    victimUsername = userTracker[username]["elimination_target"]
    if victimUsername == "":
        print(f"Victim Username is empty string! Request by {username}")
        return

    print(f"HANDLING ELIMINATION OF {victimUsername}")
    killingPhase = checkKillingPhase(update, context, callback=True)
    if not killingPhase:
        setState(username, None)
        return
    safe = checkSafetyBreaches(update, context, callback=True)
    if not safe:
        setState(username, None)
        return

    if victimUsername == "/cancelElimination":
        setState(username, None)
        fullText = f"Kill has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    eliminationKill(update, context, killerFaction, victimUsername)

    userTracker[username]["elimination_target"] = ""
    setState(username, None)


def eliminationKill(update, context, killerFaction, victimUsername):
    username = update.callback_query.message.chat.username
    userDb = userTracker[username]["db"]
    victimData = userDb.getPlayerDataJSON(
        victimUsername, currentGame.currentRound)

    victimFaction = victimData[playerDataKeys.faction]
    killerFactionData = userDb.getFactionDataJSON(killerFaction)

    # Update faction data
    pointsToAdd = victimData[playerDataKeys.points]
    killerFactionData[factionDataKeys.bank] += pointsToAdd
    userDb.replaceFactionDataFromJSON(killerFactionData)

    # Update victim data
    victimData[playerDataKeys.points] = 5
    victimData[playerDataKeys.deathCount] += 1
    userDb.replacePlayerDataFromJSON(victimData, currentGame.currentRound)

    # Update killer data - NOT FOR ELIMINATION
    # killerData[playerDataKeys.killCount] += 1
    # userDb.replacePlayerDataFromJSON(killerData, currentGame.currentRound)

    # Blast message to killer's faction
    killerFactionText = f"""<b>{factionsMap[str(killerFaction)]} Faction Update</b>

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>eliminated</b> by one of your faction members!!

Points added to faction bank: <b>{pointsToAdd}pts</b>
Current faction bank balance: <b>{killerFactionData[factionDataKeys.bank]}pts</b>."""
    killerFactionMembers = userDb.getFactionMemberUsernames(
        killerFaction, currentGame.currentRound)
    for killerUsername in killerFactionMembers:
        if killerUsername not in userTracker.keys():
            continue
        chat_id = userTracker[username]["chat_id"]
        bot.send_message(chat_id=chat_id,
                         text=killerFactionText,
                         parse_mode='HTML')

    # Blast message to victim's faction
    victimFactionText = f"""<b>{factionsMap[str(victimFaction)]} Faction Update</b>

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>eliminated</b> by {factionsMap[str(killerFaction)]} Faction!

Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is <b>NOT immune from subsequent kills</b>."""
    victimFactionMembers = userDb.getFactionMemberUsernames(
        victimFaction, currentGame.currentRound)
    for victimUsername in victimFactionMembers:
        if victimUsername not in userTracker.keys():
            continue
        chat_id = userTracker[victimUsername]["chat_id"]
        bot.send_message(chat_id=chat_id,
                         text=victimFactionText,
                         parse_mode='HTML')


    GMtext = f"""<b>Gamemaster Update</b>

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>eliminated</b> by {factionsMap[str(killerFaction)]} Faction!

Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is <b>NOT immune from subsequent kills</b>."""
    chat_id = userTracker[username]["chat_id"]
    bot.send_message(chat_id=chat_id,
                        text=GMtext,
                        parse_mode='HTML')

# ===================Message and Callback Handlers==============================


def mainMessageHandler(update, context):
    username = update.message.chat.username
    text = update.message.text
    currentState = userTracker[username]["state"]
    if currentState == StateEnum.setPoints:
        handleSetPoints(update, context, text)
        return
    elif currentState == StateEnum.kill:
        handleKill(update, context, text)
        return
    elif currentState == StateEnum.giveStick:
        handleGiveStick(update, context, text)
        return
    elif currentState == StateEnum.elimination:
        eliminationAskFaction(update, context, text)
        return
    elif currentState == StateEnum.adminAddPoints:
        handleAdminAddPoints(update, context, text)
        return
    elif currentState == StateEnum.adminBroadcast:
        handleAdminBroadcast(update, context, text)
        return
    elif currentState == StateEnum.yellowCard:
        handleYellowCard(update, context, text)
        return
    elif currentState == StateEnum.redCard:
        handleRedCard(update, context, text)
        return
    else:
        print(
            f'ERROR IN MSGHANDLER: No such state defined ({currentState})\nText: {text}')
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
    if optionID == str(OptionIDEnum.endRound):
        handleAdminEndRound(update, context, value)
        return
    if optionID == str(OptionIDEnum.dying):
        handleDying(update, context, value)
        return
    if optionID == str(OptionIDEnum.visitSpyStation):
        handleVisitSpyStation(update, context, value)
        return
    if optionID == str(OptionIDEnum.tier1a):
        handleTier1a(update, context, value)
        return
    if optionID == str(OptionIDEnum.tier1b):
        handleTier1b(update, context, value)
        return
    if optionID == str(OptionIDEnum.tier2a):
        handleTier2a(update, context, value)
        return
    if optionID == str(OptionIDEnum.tier2b):
        handleTier2b(update, context, value)
        return
    if optionID == str(OptionIDEnum.tier3a):
        handleTier3a(update, context, value)
        return
    if optionID == str(OptionIDEnum.tier3b):
        handleTier3b(update, context, value)
        return
    if optionID == str(OptionIDEnum.eliminationAskFaction):
        handleElimination(update, context, value)
        return
    if optionID == str(OptionIDEnum.adminAddPoints):
        askAdminAddPoints(update, context, value)
        return
    if optionID == str(OptionIDEnum.adminBroadcast):
        pumpAdminBroadcast(update, context, value)
        return
    else:
        print(
            f'ERROR IN CALLBACKHANDLER: No such optionID defined ({optionID})\nValue: {value}')
        return

# =========================Game Phase Checkers=========================

def checkSetPointsPhase(update, context):
    if (not currentGame.play) or currentGame.killEnabled:
        fullText = f"Set points phase has not started yet!\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id= update.message.chat.id,
                         text = fullText,
                         parse_mode = 'HTML')
        return False
    return True


def checkKillingPhase(update, context, callback=False):
    if callback:
        chat_id = update.callback_query.message.chat.id
    else:
        chat_id = update.message.chat.id
    if (not currentGame.play) or (not currentGame.killEnabled):
        fullText = f"Killing phase has not started yet!\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id= chat_id,
                         text = fullText,
                         parse_mode = 'HTML')
        return False
    return True


def checkPlayPhase(update, context, callback=False):
    if callback:
        chat_id = update.callback_query.message.chat.id
    else:
        chat_id = update.message.chat.id
    if not currentGame.play:
        fullText = f"Round has not started yet!\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id= chat_id,
                         text = fullText,
                         parse_mode = 'HTML')
        return False
    return True

# =========================Authentication helpers=======================

def checkAdmin(update, context, username):
    if username in admins:
        return True

    fullText = f"You are not admin!\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id= update.message.chat.id,
                     text= fullText,
                     parse_mode= 'HTML')
    return False


def checkGameMaster(update, context, username):
    if username in gameMasters:
        return True

    fullText = f"You are not GameMaster!\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id= update.message.chat.id,
                     text= fullText,
                     parse_mode= 'HTML')
    return False


def checkSafety(update, context, username):
    if username in safetyOfficers:
        return True

    fullText = f"You are not Safety!\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id= update.message.chat.id,
                     text= fullText,
                     parse_mode= 'HTML')
    return False


def checkSafetyBreaches(update, context, callback=False):
    if callback:
        chat_id = update.callback_query.message.chat.id
        username = update.callback_query.message.chat.username
    else:
        chat_id = update.message.chat.id
        username = update.message.chat.username
    cumulativePlayerSafetyBreaches = getPlayerSafetyBreaches(username)
    if cumulativePlayerSafetyBreaches < highestAllowedSafetyBreach:
        return True

    fullText = f"You have a total of {cumulativePlayerSafetyBreaches} Safety Breaches! You may not play the game.\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id= chat_id,
                     text= fullText,
                     parse_mode= 'HTML')
    return False

# ======================Getters=================================

def getTargetFaction(username):
    userDb = userTracker[username]["db"]
    return userDb.getTargetFaction(username, currentGame.currentRound)


def getAllFactionPoints(adminDb):
    factionPointsMap = {}
    for faction in factionsMap.keys():
        factionPoints = adminDb.getFactionPoints(
            faction, currentGame.currentRound)
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


def getStick():
    if currentGame.currentRound == str(1):
        return currentGame.stickRound1
    if currentGame.currentRound == str(2):
        return currentGame.stickRound2
    print(f"Round {currentGame.currentRound} does not exist!")


def addStick(username):
    if currentGame.currentRound != str(1) and currentGame.currentRound != str(2):
        print(f"Round {currentGame.currentRound} does not exist!")
        return
    if currentGame.currentRound == str(1):
        currentGame.stickRound1 += 1
    if currentGame.currentRound == str(2):
        currentGame.stickRound2 += 1

    userDb = userTracker[username]["db"]
    userStickExpiry = time.time() + stickExpiryInSecs
    print(userStickExpiry)
    userDb.setStickExpiry(username, currentGame.currentRound, userStickExpiry)

    print(f"Added Stick, Game State:\n{currentGame.toString()}")

# ====================Other helpers=========================

def blastMessageToAll(text):
    for user in userTracker.values():
        bot.send_message(chat_id= user["chat_id"],
                         text = text,
                         parse_mode = 'HTML')

# ===================Main Method============================

def main():
    #TODO: REMOVE
    saveGameState()

    # Start the bot.
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(API_KEY, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Admin commands
    dp.add_handler(CommandHandler("adminbeginround", adminBeginRoundCmd))
    dp.add_handler(CommandHandler("adminendsetpoints", adminEndSetPointsCmd))
    dp.add_handler(CommandHandler("adminendround", adminEndRoundCmd))
    dp.add_handler(CommandHandler("adminfactiondetails", adminFactionDetails))
    dp.add_handler(CommandHandler("adminaddpoints", adminAddPoints))
    dp.add_handler(CommandHandler("adminbroadcast", adminBroadcast))

    # Player commands - general
    dp.add_handler(CommandHandler("start", startCmd))
    dp.add_handler(CommandHandler("help", helpCmd))
    dp.add_handler(CommandHandler("faction", factionCmd))
    dp.add_handler(CommandHandler("listbanks", listBanksCmd))

    # Player commands - set points phase
    dp.add_handler(CommandHandler("setpoints", setPointsCmd))
    dp.add_handler(CommandHandler("listpoints", listPointsCmd))

    # Player commands - killing phase
    dp.add_handler(CommandHandler("dying", dyingCmd))
    dp.add_handler(CommandHandler("kill", killCmd))
    dp.add_handler(CommandHandler("stick", stickCmd))

    # Player commands - spystation
    dp.add_handler(CommandHandler("visitspystation", visitSpyStationCmd))

    # Game Master commands - spystation
    dp.add_handler(CommandHandler("tier1a", tier1aCmd))
    dp.add_handler(CommandHandler("tier1b", tier1bCmd))
    dp.add_handler(CommandHandler("tier2a", tier2aCmd))
    dp.add_handler(CommandHandler("tier2b", tier2bCmd))
    dp.add_handler(CommandHandler("tier3a", tier3aCmd))
    dp.add_handler(CommandHandler("tier3b", tier3bCmd))
    dp.add_handler(CommandHandler("givestick", giveStickCmd))
    dp.add_handler(CommandHandler("checkstick", checkStickCmd))
    dp.add_handler(CommandHandler("elimination", eliminationCmd))

    # Safety commands
    dp.add_handler(CommandHandler("yellowcard", yellowCardCmd))
    dp.add_handler(CommandHandler("redcard", redCardCmd))

    # Handle all messages
    dp.add_handler(MessageHandler(
        callback=mainMessageHandler, filters=Filters.all))

    # Handle all callback
    dp.add_handler(CallbackQueryHandler(
        callback=mainCallBackHandler, pattern=str))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    # updater.start_webhook(listen="0.0.0.0",
    #                   port=int(PORT),
    #                   url_path=str(API_KEY),
    #                   webhook_url='https://radiant-inlet-41935.herokuapp.com/' + str(API_KEY))

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.start_polling()

    # TODO: Update Excel sheet every once in a while


if __name__ == '__main__':
    main()

from calendar import weekday
from datetime import datetime, timezone
from email import message
import enum
import json
import logging
from operator import index
from os import kill
import os
import random
from sqlite3 import Time
from subprocess import call
from tabnanny import check
import time
from tracemalloc import BaseFilter
from xml.etree.ElementPath import get_parent_map
from click import get_current_context
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
import atexit
from twisted.internet import task, reactor

PORT = get_port()
API_KEY = get_api_key()
if API_KEY == None:
    raise Exception("Please update API Key")

#==========================Logging===========================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

# Initialise bot
bot = telebot.TeleBot(API_KEY, parse_mode=None)

#====================Other Keys=============================
class gameDataKeys:
    currentRound = "currentRound"
    play = "play"
    killEnabled = "killEnabled"
    stickRound1 = "stickRound1"
    stickRound2 = "stickRound2"

    allKeys = [currentRound, play, killEnabled, stickRound1, stickRound2]

class userTrackerDataKeys:
    username = "username"
    state = "state"
    db = "db"
    chat_id = "chat_id"
    smite_target = "smite_target"
    smite_tier = "smite_tier"

    allKeys = [username, state, db, chat_id, smite_target, smite_tier]

class adminQueryDataKeys:
    username = "username"
    state = "state"
    text = "text"

    allKeys = [username, state, text]

# excel sheet names
class SheetName:
    playerDataRound1 = "playerDataRound1"
    playerDataRound2 = "playerDataRound2"
    factionData = "factionData"
    gameData = "gameData"
    userTrackerData = "userTrackerData"
    adminQueryData = "adminQueryData"

# ============================Constants======================================

roundList = [1, 2]
yesNoList = ["Yes", "No"]

factionsMap = {
    "1": "Sparta",
    "2": "Hades",
    "3": "Aphrodite",
    "4": "Nemesis"
}
smiteTiersArr = ["Orange", "Green", "Pink", "Cancel"]
playAreaImagePath = "./images/shan-royale-playarea-round-"
imageExtension = ".jpg"

# TODO: UPDATE
admins = ["praveeeenk", "Casperplz"]
gameMasters = ["buttermebuns", "vigonometry", "kelsomebody", "jacindatsen", "keziakhoo", "jodytng"]
safetyOfficers = ["kelsykoh", "ddannyiel", "Jobeet"]

minPoints = 5
maxTeamPoints = 200
highestAllowedSafetyBreach = 2
immuneSecondsUponDeath = 90
wrongKillPenalty = 50

# TODO: ASK CASPER IF OKAY, INFORM CASPER IF NEED BE SHORTER
easyPreyNumToSelect = 2
easyPreyTopCut = 3
mediumPreyNumToSelect = 6
mediumPreyTopCut = 3
hardPreyNumToSelect = 3
maxStickPerRound = 10
stickExpiryInSecs = 600

# =============================Texts==========================================
dontWasteMyTimeText = """\"<b>Don't waste my time...</b> You aren't allowed to use this command now.\"
~ Message by Caserplz"""

# ============================Tracking State===================================
# Possible states
class StateEnum(enum.Enum):
    setPoints = "setPoints"
    eliminate = "eliminate"
    giveStick = "giveStick"
    smite = "smite"
    adminAddPoints = "adminAddPoints"
    adminBroadcast = "adminBroadcast"
    # adminPause = "adminPause"
    # adminResume = "adminResume"
    yellowCard = "yellowCard"
    redCard = "redCard"


class OptionIDEnum(enum.Enum): 
    beginRound = "beginRound"
    endSetPoints = "endSetPoints"
    endRound = "endRound"
    dying = "dying"
    visitInfoCentre = "visitInfoCentre"
    easyPredator = "easyPredator"
    easyPrey = "easyPrey"
    mediumPredator= "mediumPredator"
    mediumPrey = "mediumPrey"
    hardPredator = "hardPredator"
    hardPrey = "hardPrey"
    smiteAskFaction = "eliminationAskFaction"
    adminAddPoints = "adminAddPoints"
    adminBroadcast = "adminBroadcast"
    adminExit = "adminExit"
    smiteAskTier = "smiteAskTier"

# ======================LOAD GAME STATE================================
# TODO: CHANGE TO ACTUAL EXCEL SHEET
liveExcelFilePath = "./excel/test/shanRoyale2022Data1.xlsx"
playerDataRound1JSONArr = json.loads(pandas.read_excel(liveExcelFilePath, sheet_name=SheetName.playerDataRound1).to_json(orient='records'))
playerDataRound2JSONArr = json.loads(pandas.read_excel(liveExcelFilePath, sheet_name=SheetName.playerDataRound2).to_json(orient='records'))
factionDataJSONArr = json.loads(pandas.read_excel(liveExcelFilePath, sheet_name=SheetName.factionData).to_json(orient='records'))
gameDataJSONArr = json.loads(pandas.read_excel(liveExcelFilePath, sheet_name=SheetName.gameData).to_json(orient='records'))
userTrackerDataJSONArr = json.loads(pandas.read_excel(liveExcelFilePath, sheet_name=SheetName.userTrackerData).to_json(orient='records'))
adminQueryDataJSONArr = json.loads(pandas.read_excel(liveExcelFilePath, sheet_name=SheetName.adminQueryData).to_json(orient='records'))

# Load Database
mainDb = DBHelper("shan-royale.sqlite")
# Clear DB first, then setup
mainDb.purgeData()
mainDb.setup()
mainDb.playerDataJSONArrToDB(playerDataRound1JSONArr, 1)
mainDb.playerDataJSONArrToDB(playerDataRound2JSONArr, 2)
mainDb.factionDataJSONArrToDB(factionDataJSONArr)

#TODO: Update this again after all states are accounted for.
def stringToState(stateString) -> StateEnum:
    if stateString == 'StateEnum.setPoints':
        return StateEnum.setPoints
    elif stateString == 'StateEnum.kill':
        return StateEnum.eliminate
    elif stateString == 'StateEnum.giveStick':
        return StateEnum.giveStick
    elif stateString == 'StateEnum.smite':
        return StateEnum.smite
    elif stateString == 'StateEnum.adminAddPoints':
        return StateEnum.adminAddPoints
    elif stateString == 'StateEnum.adminBroadcast':
        return StateEnum.adminBroadcast
    elif stateString == 'StateEnum.yellowCard':
        return StateEnum.yellowCard
    elif stateString == 'StateEnum.redCard':
        return StateEnum.redCard
    elif stateString == '' or stateString == None:
        return None
    else:
        print(f'ERROR IN stringToState: No such state defined ({stateString})')
        return None

# Load Game object
def loadGameObject() -> Game:
    gameDict = gameDataJSONArr[0]
    currentRound = gameDict[gameDataKeys.currentRound]
    play = gameDict[gameDataKeys.play]
    killEnabled = gameDict[gameDataKeys.killEnabled]
    stickRound1 = gameDict[gameDataKeys.stickRound1]
    stickRound2 = gameDict[gameDataKeys.stickRound2]
    return Game(currentRound=currentRound, play=play, killEnabled=killEnabled, stickRound1=stickRound1, stickRound2=stickRound2)

currentGame = loadGameObject()
print(currentGame.toString())

# Load User Tracker
def loadUserTracker() -> dict:
    userTracker = {}
    for userTrackerDataDict in userTrackerDataJSONArr:
        username = userTrackerDataDict[userTrackerDataKeys.username]
        newDict = {}
        state = stringToState(userTrackerDataDict[userTrackerDataKeys.state])
        newDict[userTrackerDataKeys.state] = state
        newDict[userTrackerDataKeys.db] = None
        newDict[userTrackerDataKeys.chat_id] = userTrackerDataDict[userTrackerDataKeys.chat_id]
        newDict[userTrackerDataKeys.smite_target] = userTrackerDataDict[userTrackerDataKeys.smite_target]
        newDict[userTrackerDataKeys.smite_tier] = userTrackerDataDict[userTrackerDataKeys.smite_tier]
        userTracker[username] = newDict
    return userTracker

userTracker = loadUserTracker()
print(userTracker)

# Load User Tracker
def loadAdminQuery() -> dict:
    adminQuery = {}
    for adminQueryDataDict in adminQueryDataJSONArr:
        username = adminQueryDataDict[adminQueryDataKeys.username]
        newDict = {}
        state = stringToState(adminQueryDataDict[adminQueryDataKeys.state])
        text = adminQueryDataDict[adminQueryDataKeys.text]
        newDict[state] = text
        adminQuery[username] = newDict
    return adminQuery

adminQuery = loadAdminQuery()
print(adminQuery)

# ========================== State functions ======================================

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
    db = DBHelper("shan-royale.sqlite")
    currentTime = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
    print(f"SAVING GAME STATE AT: {currentTime}")
    allPlayerData1Dict = db.getALLPlayerDataJSON(1)
    allPlayerData2Dict = db.getALLPlayerDataJSON(2)
    allFactionDataDict = db.getALLFactionDataJSON()
    
    gameDataDict = {}
    dummyDict = {}
    for key in gameDataKeys.allKeys:
        dummyDict[key] = getattr(currentGame, key)
    gameDataDict["game"] = dummyDict

    dummyTrackerDict = {}
    for username, dictionary in userTracker.items():
        temp = {}
        temp[userTrackerDataKeys.username] = username
        for key, value in dictionary.items():
            temp[key] = value
        dummyTrackerDict[username] = temp

    dummyAdminDict = {}
    for username, dictionary in adminQuery.items():
        temp = {}
        for state, text in dictionary.items():
            temp[adminQueryDataKeys.username] = username
            temp[adminQueryDataKeys.state] = state
            temp[adminQueryDataKeys.text] = text
        dummyAdminDict[username] = temp

    allPlayerData1JSON = pandas.DataFrame.from_dict(allPlayerData1Dict, orient="index")
    allPlayerData2JSON = pandas.DataFrame.from_dict(allPlayerData2Dict, orient="index")
    allFactionDataJSON = pandas.DataFrame.from_dict(allFactionDataDict, orient="index")
    gameDataJSON = pandas.DataFrame.from_dict(gameDataDict, orient="index")
    userTrackerJSON = pandas.DataFrame.from_dict(dummyTrackerDict, orient="index")
    adminQueryJSON = pandas.DataFrame.from_dict(dummyAdminDict, orient="index")

    # Save to backup sheet
    saveBackupFilePath = f"./excel/backup/shanRoyale2022-{currentTime}.xlsx"
    with pandas.ExcelWriter(saveBackupFilePath) as writer:
        allPlayerData1JSON.to_excel(writer, sheet_name=SheetName.playerDataRound1)
        allPlayerData2JSON.to_excel(writer, sheet_name=SheetName.playerDataRound2)
        allFactionDataJSON.to_excel(writer, sheet_name=SheetName.factionData)
        gameDataJSON.to_excel(writer, sheet_name=SheetName.gameData)
        userTrackerJSON.to_excel(writer, sheet_name=SheetName.userTrackerData)
        adminQueryJSON.to_excel(writer, sheet_name=SheetName.adminQueryData)

    # Save to live excel sheet too
    with pandas.ExcelWriter(liveExcelFilePath) as writer:
        allPlayerData1JSON.to_excel(writer, sheet_name=SheetName.playerDataRound1)
        allPlayerData2JSON.to_excel(writer, sheet_name=SheetName.playerDataRound2)
        allFactionDataJSON.to_excel(writer, sheet_name=SheetName.factionData)
        gameDataJSON.to_excel(writer, sheet_name=SheetName.gameData)
        userTrackerJSON.to_excel(writer, sheet_name=SheetName.userTrackerData)
        adminQueryJSON.to_excel(writer, sheet_name=SheetName.adminQueryData)

    print(f"DONE SAVING GAME STATE")
 
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

Make sure to type /adminEndSetPoints to begin the EliminaSHAN Phase."""
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
- Elimination is now <b>disabled</b>. You will be notified when the Elimination phase begins

Enjoy!"""
    blastImageToAll(f"{playAreaImagePath}{round_no}{imageExtension}")
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
    adminText = f"""You have ended Set Points phase for Round {currentGame.currentRound}! Elimination has now been enabled :)"""
    bot.edit_message_text(chat_id=chat_id,
                          text=adminText,
                          message_id=message_id,
                          parse_mode='HTML')

    
    blastImageToAll(f"{playAreaImagePath}{currentGame.currentRound}{imageExtension}")
    for username, user in userTracker.items():
        # TODO Add in pic of play area
        targetFaction = getTargetFaction(username)
        text = f"""<b>NOTICE</b>
Round {currentGame.currentRound} has begun!!

You are now in the <b>Elimination</b> phase

<b>Details of phase:</b>
- Duration: <b>45 mins</b>
- Your target Faction is <b>{targetFaction}</b>
- <b>Picture of play area is attached!</b>

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
    totalKillsTxt = "\n\n<b>Eliminations</b>"
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
        killCountTxt = "\n\n<b>Elimination Count:</b>"
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

    fullText = f"Is this okay sir/maam?\n\n{text}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         yesNoList, OptionIDEnum.adminBroadcast),
                     parse_mode='HTML')


def pumpAdminBroadcast(update, context, yesNo):
    username = update.callback_query.message.chat.username
    chat_id = update.callback_query.message.chat.id
    message_id = update.callback_query.message.message_id
    isAdmin = checkAdmin(update, context, username, callback=True)
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

def adminExit(update, context):
    username = update.message.chat.username
    isAdmin = checkAdmin(update, context, username)
    if not isAdmin:
        return

    fullText = f"""You are about to END the bot.

Are you sure you want to continue?"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         yesNoList, OptionIDEnum.adminExit),
                     parse_mode='HTML')

def handleAdminExit(update, context, yesNo):
    username = update.callback_query.message.chat.username
    chat_id = update.callback_query.message.chat.id
    message_id = update.callback_query.message.message_id
    isAdmin = checkAdmin(update, context, username, callback=True)
    if not isAdmin:
        return

    if yesNo == yesNoList[1]:
        # "No" was pressed
        bot.edit_message_text(chat_id=chat_id,
                              text=dontWasteMyTimeText,
                              message_id=message_id,
                              parse_mode='HTML')
        return

    fullText = "<b>Bot will now shut down. :(</b>"
    bot.edit_message_text(chat_id=chat_id,
                            text=fullText,
                            message_id=message_id,
                            parse_mode='HTML')

    saveGameState()
    os._exit(0)

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
            "smite_target": "",
            "smite_tier": ""
        }
        userTracker[username] = newUserTracker
    else:
        newUserTracker = userTracker[username]
        newUserTracker["db"] = db
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
<b>/eliminate</b> - Initiate an elimination on someone
<b>/stick</b> - Use your stick to initiate an elimination on someone
<b>/visitinfocentre</b> - Record your visit to the information centre
"""

    gamemasterCmds = """<b>Here are the suppported game master commands:</b>\n
<b>/easyPredator</b> - Get easy predator information
<b>/easyPrey</b> - Get easy prey information
<b>/mediumPredator</b> - Get medium predator information
<b>/mediumPrey</b> - Get medium prey information
<b>/hardPredator</b> - Get hard predator information
<b>/hardPrey</b> - Get hard prey information
<b>/givestick</b> - Give stick to a player
<b>/checkstick</b> - Check how many sticks have been given out
<b>/smite</b> - Smite a player upon request
"""

    safetyCmds = """<b>Here are the suppported safety officer commands:</b>\n
<b>/yellowcard</b> - Give a player a yellow card
<b>/redcard</b> - Give a player a red card
"""

    adminCmds = """<b>Here are the supported admin commands:</b>\n
<b>/adminbeginround</b> - Begin the Set Points phase for a round
<b>/adminendsetpoints</b> - End the Set Points phase and begin Elimination phase for the current round
<b>/adminendround</b> - End the Round despite the phase
<b>/adminfactiondetails</b> - Get summary of all faction details
<b>/adminaddpoints</b> - Add points to a faction's bank
<b>/adminbroadcast</b> - Broadcast a message
<b>/adminexit</b> - Shut down the bot :O
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
    killCountTxt = "\n\n<b>Elimination Count:</b>"
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

# =========================Elimination Mechanism================================

def dyingCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return
    username = update.message.chat.username
    immune = checkImmunity(update, context, username)
    if immune:
        return

    fullText = f"""/dying should only be entered <b>once you have been "eliminated" in person by someone else.</b>

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
    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
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

    fullText = f"""<b>You have registered yourself as dying.</b> The eliminater must now /eliminate to confirm the elimination.

You will be informed on the changes in points once the elimination is validated."""
    bot.edit_message_text(chat_id=chat_id,
                          text=fullText,
                          message_id=message_id,
                          parse_mode='HTML')


def killCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return
    username = update.message.chat.username
    immune = checkImmunity(update, context, username)
    if immune:
        return

    setState(username, StateEnum.eliminate)

    fullText = f"""/eliminate should only be entered <b>once you have "eliminated" someone else in person.</b>

If you wish to <b>proceed</b>, type in the <b>telegram handle of the victim</b>

You must:
1) type in their handle <b>exactly as is</b> (with caps, special characters etc.)
2) <b>not put "@"</b> in front of their handle (eg. type in praveeeenk instead of @praveeeenk)

If you wish to <b>cancel</b>, type in /canceleliminate"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def handleKill(update, context, victimUsername):
    print(f"HANDLING KILL OF {victimUsername}")
    username = update.message.chat.username
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        setState(username, None)
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return

    if victimUsername == "/canceleliminate":
        setState(username, None)
        fullText = f"Elimination has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    if victimUsername == username:
        setState(username, None)
        fullText = f"You may not eliminate yourself using stick or sash!\n\n{dontWasteMyTimeText}"
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


def stickCmd(update, context ):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
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

    setState(username, StateEnum.eliminate)

    fullText = f"""You are about to use your stick to initiate an elimination.

/stick should only be entered <b>once you have "eliminated" someone else in person.</b>

If you wish to <b>proceed</b>, type in the <b>telegram handle of the victim</b>

You must:
1) type in their handle <b>exactly as is</b> (with caps, special characters etc.)
2) <b>not put "@"</b> in front of their handle (eg. type in praveeeenk instead of @praveeeenk)

If you wish to <b>cancel</b>, type in /canceleliminate"""
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
        fullText = f"You are still immune for {remainingTime} seconds!\n\nYou may not be eliminated or eliminate!"
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
        bot.send_message(chat_id=userTracker[username]["chat_id"],
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

<b>Ask the victim to enter /dying</b> on their phone first! After which, you may type <b>/eliminate</b> again."""
        bot.send_message(chat_id=userTracker[username]["chat_id"],
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

{killerData[playerDataKeys.fullname]} (@{killerData[playerDataKeys.username]}) has <b>successfully eliminated</b> {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) by sash/stick!

Points added to faction bank: <b>{pointsToAdd}pts</b>
Current faction bank balance: <b>{killerFactionData[factionDataKeys.bank]}pts</b>

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is now <b>immune from eliminations</b> for the next {immuneSecondsUponDeath}s."""
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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>eliminated</b>! Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is now <b>immune from eliminations</b> for the next {immuneSecondsUponDeath}s."""
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

{killerFullname} (@{killerUsername}) tried to <b>wrongly eliminate</b> their faction mate, {victimFullname} (@{victimUsername}) by sash/stick!

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

{killerFullname} (@{killerUsername}) has <b>wrongly eliminated</b> {victimFullname} (@{victimUsername})!

Thus, <b>{wrongKillPenalty}pts</b> have been transferred from your faction bank to the victim's faction bank.
Current faction bank balance: <b>{killerBankBalance}pts</b>

Don't noob and anyhow eliminate can?"""
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

{victimFullname} (@{victimUsername}) has been <b>wrongly eliminated</b> by {killerFullname} (@{killerUsername})!

Thus, <b>{wrongKillPenalty}pts</b> have been transferred from the eliminater's faction bank to your faction bank.
Current faction bank balance: <b>{victimBankBalance}pts</b>

<b>Note:</b> The victim, {victimFullname} (@{victimUsername}), is NOT given immunity from eliminations."""
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


def visitInfoCentreCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    safe = checkSafetyBreaches(update, context)
    if not safe:
        return
    username = update.message.chat.username
    visited = visitedInfoCentre(update, context, username)
    if visited:
        return

    fullText = f"""/visitInfoCentre should only be entered <b>once you are going to engage with the game master at the information centre</b>

You may only visit the information centre <b>once per round</b>.

Are you sure you are visiting the information centre?"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         yesNoList, OptionIDEnum.visitInfoCentre),
                     parse_mode='HTML')


def handleVisitInfoCentre(update, context, yesNo):
    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
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

    fullText = f"""<b>You (@{username}) have registered yourself at the Info Centre</b>

Faction Name (ID): {factionsMap[str(playerFaction)]} ({playerFaction})

Show this pass to the game master to proceed with the station activities."""
    bot.send_photo(chat_id=chat_id,
                         photo=open("./images/green-pass.jpg", 'rb'))
    bot.edit_message_text(chat_id=chat_id,
                          text=fullText,
                          message_id=message_id,
                          parse_mode='HTML')


def visitedInfoCentre(update, context, username):
    userDb = userTracker[username]["db"]
    visitedInfoCentre = userDb.getPlayerVisitSpyStation(
        username, currentGame.currentRound)

    if visitedInfoCentre:
        fullText = f"""You have visited the information centre in this round!\n\n{dontWasteMyTimeText}"""
        bot.send_message(chat_id=update.message.chat.id,
                         text=fullText,
                         parse_mode='HTML')
        return True
    return False


# ========================Spy Master Commands==================================


def easyPredatorCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
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
                         factionsMap.keys(), OptionIDEnum.easyPredator),
                     parse_mode='HTML')


def handleEasyPredator(update, context, faction):
    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username, callback=True)
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


def easyPreyCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for <b>{easyPreyNumToSelect} people from the prey faction</b> of the requested faction, who <b>do not</b> possess the most number of points.

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.easyPrey),
                     parse_mode='HTML')


def handleEasyPrey(update, context, faction):
    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username, callback=True)
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

    numPreyLeft = len(sortedArr) - easyPreyTopCut
    if numPreyLeft <= 0:
        print("ERROR: TOO LITTLE PREY LEFT")
        return

    if numPreyLeft > easyPreyNumToSelect:
        numPreyToSelect = easyPreyNumToSelect
    else:
        numPreyToSelect = numPreyLeft

    # RAndom num avoids top ppl specified by tier1bTopCut
    # TODO: If num left < tier1bTopCut, this results in a loop
    randomNumArray = []
    for i in range(numPreyToSelect):
        random_num = random.randint(easyPreyTopCut, numPreyToSelect)
        while random_num in randomNumArray:
            random_num = random.randint(easyPreyTopCut, numPreyToSelect)
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


def mediumPredatorCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
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
                         factionsMap.keys(), OptionIDEnum.mediumPredator),
                     parse_mode='HTML')


def handleMediumPredator(update, context, faction):
    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username, callback=True)
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


def mediumPreyCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for <b>{mediumPreyNumToSelect} people from the prey faction</b> of the requested faction, who <b>do not</b> possess the most number of points.

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.mediumPrey),
                     parse_mode='HTML')


def handleMediumPrey(update, context, faction):
    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username, callback=True)
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

    numPreyLeft = len(sortedArr) - mediumPreyTopCut
    if numPreyLeft <= 0:
        print("ERROR: TOO LITTLE PREY LEFT ")
        return

    if numPreyLeft > mediumPreyNumToSelect:
        numPreyToSelect = mediumPreyNumToSelect
    else:
        numPreyToSelect = numPreyLeft

    # RAndom num avoids top ppl specified by tier2bTopCut
    # TODO: If num left < tier1bTopCut, this results in a loop
    randomNumArray = []
    for i in range(numPreyToSelect):
        random_num = random.randint(mediumPreyTopCut, numPreyToSelect)
        while random_num in randomNumArray:
            random_num = random.randint(mediumPreyTopCut, numPreyToSelect)
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


def hardPredatorCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for:
1) <b>The predator faction</b> of the requested faction AND
2) The player from the predator faction with the <b>most eliminations</b>

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.hardPredator),
                     parse_mode='HTML')


def handleHardPredator(update, context, faction):
    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username, callback=True)
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

The player in the predator faction with most eliminations is @{predatorMostKillsTuple[0]}, with {predatorMostKillsTuple[1][0]} eliminations.

~ Shan Royale 2022 Team"""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                          text=gameMasterText,
                          message_id=update.callback_query.message.message_id,
                          parse_mode='HTML')


def hardPreyCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""You are querying for <b>{hardPreyNumToSelect} people from the prey faction</b> of the requested faction, who possess the <b>most number of points</b>.

Please state the <b>ID of the faction</b> you are querying for.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.hardPrey),
                     parse_mode='HTML')


def handleHardPrey(update, context, faction):
    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username, callback=True)
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

    numPreyToSelect = hardPreyNumToSelect
    if len(sortedArr) <= hardPreyNumToSelect:
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
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return
    canGive = canGiveStick(update, context)
    if not canGive:
        return

    setState(username, StateEnum.giveStick)

    fullText = f"""/giveStick should only be entered when the player has <b>completed their required task at the information centre.</b>

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
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
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
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return
    canGive = canGiveStick(update, context)
    if not canGive:
        return

    fullText = f"""Sticks left for:
Round 1 - {maxStickPerRound - currentGame.stickRound1}
Round 2 - {maxStickPerRound - currentGame.stickRound2}"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     parse_mode='HTML')


def smiteCmd(update, context):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    fullText = f"""/smite should only be entered when a player has <b>turned in the smite notes</b> at the information centre.

If you wish to <b>proceed</b>, click the <b>tier of smite</b>, as requested by the player.

If you wish to <b>cancel</b>, click cancel"""
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         smiteTiersArr, OptionIDEnum.smiteAskTier),
                     parse_mode='HTML')

    return


def smiteAskName(update, context, tier):
    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
        return
    username = update.callback_query.message.chat.username
    gameMaster = checkGameMaster(update, context, username, callback=True)
    if not gameMaster:
        return

    if tier == "Cancel":
        bot.send_message(chat_id=update.callback_query.message.chat.id,
                     text=f"Smite has been cancelled\n\n{dontWasteMyTimeText}",
                     parse_mode='HTML')
        return

    setState(username, StateEnum.smite)
    userTracker[username]["smite_tier"] = tier

    fullText = f"""Smite Tier Chosen: <b>{tier}</b>
    
Type in the <b>telegram handle of the victim</b>, as requested by the player.

You must:
1) type in their handle <b>exactly as is</b> (with caps, special characters etc.)
2) <b>not put "@"</b> in front of their handle (eg. type in praveeeenk instead of @praveeeenk)

If you wish to <b>cancel</b>, type in /cancelsmite"""
    bot.edit_message_text(chat_id=update.callback_query.message.chat.id,
                     message_id=update.callback_query.message.message_id,
                     text=fullText,
                     parse_mode='HTML')


def smiteAskFaction(update, context, victimUsername):
    eliminationPhase = checkEliminationPhase(update, context)
    if not eliminationPhase:
        return
    username = update.message.chat.username
    gameMaster = checkGameMaster(update, context, username)
    if not gameMaster:
        return

    if victimUsername == "/cancelsmite":
        setState(username, None)
        fullText = f"Smite has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    valid = validUsername(update, context, victimUsername)
    if not valid:
        return

    # Store victimUsername
    userTracker[username]["smite_target"] = victimUsername

    fullText = f"""Victim Chosen: <b>{victimUsername}</b>
    
Please state the <b>ID of the faction</b> of the player requesting the smite.

<b>Faction Legend:</b>"""
    for id, name in factionsMap.items():
        fullText += f"\nID {id}: {name}"
    bot.send_message(chat_id=update.message.chat.id,
                     text=fullText,
                     reply_markup=makeInlineKeyboard(
                         factionsMap.keys(), OptionIDEnum.smiteAskFaction),
                     parse_mode='HTML')


def handleSmite(update, context, killerFaction):
    username = update.callback_query.message.chat.username
    victimUsername = userTracker[username]["smite_target"]
    tier = userTracker[username]["smite_tier"]
    if victimUsername == "":
        print(f"Victim Username is empty string! Request by {username}")
        return

    if tier == "":
        print(f"Tier is empty string! Request by {username}")
        return

    eliminationPhase = checkEliminationPhase(update, context, callback=True)
    if not eliminationPhase:
        setState(username, None)
        return
    safe = checkSafetyBreaches(update, context, callback=True)
    if not safe:
        setState(username, None)
        return

    if victimUsername == "/cancelsmite":
        setState(username, None)
        fullText = f"Smite has been cancelled\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id=userTracker[username]["chat_id"],
                         text=fullText,
                         parse_mode='HTML')
        return

    if tier == "Green":
        smiteGreenKill(update, context, killerFaction, victimUsername)
    elif tier == "Orange":
        smiteOrangeKill(update, context, killerFaction, victimUsername)
    elif tier == "Pink":
        smitePinkKill(update, context, killerFaction, victimUsername)

    userTracker[username]["smite_target"] = ""
    userTracker[username]["smite_tier"] = ""
    setState(username, None)


# Smite only Prey faction
def smiteOrangeKill(update, context, killerFaction, victimUsername):
    username = update.callback_query.message.chat.username
    userDb = userTracker[username]["db"]
    victimData = userDb.getPlayerDataJSON(
        victimUsername, currentGame.currentRound)

    victimFaction = victimData[playerDataKeys.faction]
    killerFactionData = userDb.getFactionDataJSON(killerFaction)

    isPrey = checkVictimInPreyFactionFromFaction(username, killerFaction, victimUsername)
    if not isPrey:
        # Blast message to killer's faction
        killerFactionText = f"""<b>{factionsMap[str(killerFaction)]} Faction Update</b>

Someone from your faction tried to use a smite note, but to no avail! The note has mysteriously disappeared into thin air...

:O

~ Shan Royale 2022 Team"""
        killerFactionMembers = userDb.getFactionMemberUsernames(
            killerFaction, currentGame.currentRound)
        for killerUsername in killerFactionMembers:
            if killerUsername not in userTracker.keys():
                continue
            chat_id = userTracker[username]["chat_id"]
            bot.send_message(chat_id=chat_id,
                            text=killerFactionText,
                            parse_mode='HTML')
        return

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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>smited</b> by one of your faction members!!

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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>smited</b> by {factionsMap[str(killerFaction)]} Faction!

Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is <b>NOT immune from subsequent eliminations</b>."""
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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>smited</b> by {factionsMap[str(killerFaction)]} Faction!

Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is <b>NOT immune from subsequent eliminations</b>."""
    chat_id = userTracker[username]["chat_id"]
    bot.send_message(chat_id=chat_id,
                        text=GMtext,
                        parse_mode='HTML')
    
    


# Smite only Predator faction
def smiteGreenKill(update, context, killerFaction, victimUsername):
    username = update.callback_query.message.chat.username
    userDb = userTracker[username]["db"]
    victimData = userDb.getPlayerDataJSON(
        victimUsername, currentGame.currentRound)

    victimFaction = victimData[playerDataKeys.faction]
    killerFactionData = userDb.getFactionDataJSON(killerFaction)

    isPredator = checkVictimInPredatorFactionFromFaction(username, killerFaction, victimUsername)
    if not isPredator:
        # Blast message to killer's faction
        killerFactionText = f"""<b>{factionsMap[str(killerFaction)]} Faction Update</b>

Someone from your faction tried to use a smite note, but to no avail! The note has mysteriously disappeared into thin air...

:O

~ Shan Royale 2022 Team"""
        killerFactionMembers = userDb.getFactionMemberUsernames(
            killerFaction, currentGame.currentRound)
        for killerUsername in killerFactionMembers:
            if killerUsername not in userTracker.keys():
                continue
            chat_id = userTracker[username]["chat_id"]
            bot.send_message(chat_id=chat_id,
                            text=killerFactionText,
                            parse_mode='HTML')
        return

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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>smited</b> by one of your faction members!!

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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>smited</b> by {factionsMap[str(killerFaction)]} Faction!

Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is <b>NOT immune from subsequent eliminations</b>."""
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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>smited</b> by {factionsMap[str(killerFaction)]} Faction!

Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is <b>NOT immune from subsequent eliminations</b>."""
    chat_id = userTracker[username]["chat_id"]
    bot.send_message(chat_id=chat_id,
                        text=GMtext,
                        parse_mode='HTML')


# Smite EVERYBODY
def smitePinkKill(update, context, killerFaction, victimUsername):
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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>smited</b> by one of your faction members!!

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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>smited</b> by {factionsMap[str(killerFaction)]} Faction!

Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is <b>NOT immune from subsequent eliminations</b>."""
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

{victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}) has been <b>smited</b> by {factionsMap[str(killerFaction)]} Faction!

Their points have been <b>reset to {minPoints}</b>.

<b>Note:</b> The victim, {victimData[playerDataKeys.fullname]} (@{victimData[playerDataKeys.username]}), is <b>NOT immune from subsequent eliminations</b>."""
    chat_id = userTracker[username]["chat_id"]
    bot.send_message(chat_id=chat_id,
                        text=GMtext,
                        parse_mode='HTML')


def checkVictimInPredatorFactionFromFaction(username, killerFaction, victimUsername):
    userDb = userTracker[username]["db"]
    victimFaction = userDb.getPlayerFaction(
        victimUsername, currentGame.currentRound)
    killerPredatorFaction = userDb.getPredatorFaction(killerFaction, currentGame.currentRound)
    if int(killerPredatorFaction) == int(victimFaction):
        return True
    return False


def checkVictimInPreyFactionFromFaction(username, killerFaction, victimUsername):
    userDb = userTracker[username]["db"]
    killerTargetFaction = userDb.getTargetFactionFromFaction(killerFaction, currentGame.currentRound)
    victimFaction = userDb.getPlayerFaction(
        victimUsername, currentGame.currentRound)
    if int(killerTargetFaction) == int(victimFaction):
        return True
    return False


# ===================Message and Callback Handlers==============================


def mainMessageHandler(update, context):
    username = update.message.chat.username
    text = update.message.text
    currentState = userTracker[username]["state"]
    if currentState == StateEnum.setPoints:
        handleSetPoints(update, context, text)
        return
    elif currentState == StateEnum.eliminate:
        handleKill(update, context, text)
        return
    elif currentState == StateEnum.giveStick:
        handleGiveStick(update, context, text)
        return
    elif currentState == StateEnum.smite:
        smiteAskFaction(update, context, text)
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
    if optionID == str(OptionIDEnum.visitInfoCentre):
        handleVisitInfoCentre(update, context, value)
        return
    if optionID == str(OptionIDEnum.easyPredator):
        handleEasyPredator(update, context, value)
        return
    if optionID == str(OptionIDEnum.easyPrey):
        handleEasyPrey(update, context, value)
        return
    if optionID == str(OptionIDEnum.mediumPredator):
        handleMediumPredator(update, context, value)
        return
    if optionID == str(OptionIDEnum.mediumPrey):
        handleMediumPrey(update, context, value)
        return
    if optionID == str(OptionIDEnum.hardPredator):
        handleHardPredator(update, context, value)
        return
    if optionID == str(OptionIDEnum.hardPrey):
        handleHardPrey(update, context, value)
        return
    if optionID == str(OptionIDEnum.smiteAskFaction):
        handleSmite(update, context, value)
        return
    if optionID == str(OptionIDEnum.smiteAskTier):
        smiteAskName(update, context, value)
        return
    if optionID == str(OptionIDEnum.adminAddPoints):
        askAdminAddPoints(update, context, value)
        return
    if optionID == str(OptionIDEnum.adminBroadcast):
        pumpAdminBroadcast(update, context, value)
        return
    if optionID == str(OptionIDEnum.adminExit):
        handleAdminExit(update, context, value)
        return
    else:
        print(
            f'ERROR IN CALLBACKHANDLER: No such optionID defined ({optionID})\nValue: {value}')
        return

# =========================Game Phase Checkers=========================

def checkSetPointsPhase(update, context, callback=False):
    if callback:
        chat_id = update.callback_query.message.chat.id
    else:
        chat_id = update.message.chat.id
    if (not currentGame.play) or currentGame.killEnabled:
        fullText = f"Set points phase has not started yet!\n\n{dontWasteMyTimeText}"
        bot.send_message(chat_id= update.message.chat.id,
                         text = fullText,
                         parse_mode = 'HTML')
        return False
    return True


def checkEliminationPhase(update, context, callback=False):
    if callback:
        chat_id = update.callback_query.message.chat.id
    else:
        chat_id = update.message.chat.id
    if (not currentGame.play) or (not currentGame.killEnabled):
        fullText = f"Elimination phase has not started yet!\n\n{dontWasteMyTimeText}"
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

def checkAdmin(update, context, username, callback=False):
    if username in admins:
        return True

    if callback:
        chat_id = update.callback_query.message.chat.id
    else:
        chat_id = update.message.chat.id

    fullText = f"You are not admin!\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id= update.message.chat.id,
                     text= fullText,
                     parse_mode= 'HTML')
    return False


def checkGameMaster(update, context, username, callback=False):
    if callback:
        chat_id = update.callback_query.message.chat.id
    else:
        chat_id = update.message.chat.id
    if username in gameMasters or username in admins:
        return True
        

    fullText = f"You are not GameMaster!\n\n{dontWasteMyTimeText}"
    bot.send_message(chat_id= update.message.chat.id,
                     text= fullText,
                     parse_mode= 'HTML')
    return False


def checkSafety(update, context, username, callback=False):
    if username in safetyOfficers or username in gameMasters or username in admins:
        return True

    if callback:
        chat_id = update.callback_query.message.chat.id
    else:
        chat_id = update.message.chat.id
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

def blastImageToAll(path):
    for user in userTracker.values():
        bot.send_photo(chat_id= user["chat_id"],
                         photo=open(path, 'rb'))

# ===================Main Method============================

def main():

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
    dp.add_handler(CommandHandler("adminExit", adminExit))
    # dp.add_handler(CommandHandler("adminpause", adminPause))
    # dp.add_handler(CommandHandler("adminresume", adminResume))

    # Player commands - general
    dp.add_handler(CommandHandler("start", startCmd))
    dp.add_handler(CommandHandler("help", helpCmd))
    dp.add_handler(CommandHandler("faction", factionCmd))
    dp.add_handler(CommandHandler("listbanks", listBanksCmd))

    # Player commands - set points phase
    dp.add_handler(CommandHandler("setpoints", setPointsCmd))
    dp.add_handler(CommandHandler("listpoints", listPointsCmd))

    # Player commands - elimination phase
    dp.add_handler(CommandHandler("dying", dyingCmd))
    dp.add_handler(CommandHandler("eliminate", killCmd))
    dp.add_handler(CommandHandler("stick", stickCmd))

    # Player commands - info centre (aka spystation)
    dp.add_handler(CommandHandler("visitInfoCentre", visitInfoCentreCmd))

    # Game Master commands - info centre (aka spystation)
    dp.add_handler(CommandHandler("easyPredator", easyPredatorCmd))
    dp.add_handler(CommandHandler("easyPrey", easyPreyCmd))
    dp.add_handler(CommandHandler("mediumPredator", mediumPredatorCmd))
    dp.add_handler(CommandHandler("mediumPrey", mediumPreyCmd))
    dp.add_handler(CommandHandler("hardPredator", hardPredatorCmd))
    dp.add_handler(CommandHandler("hardPrey", hardPreyCmd))
    dp.add_handler(CommandHandler("givestick", giveStickCmd))
    dp.add_handler(CommandHandler("checkstick", checkStickCmd))
    dp.add_handler(CommandHandler("smite", smiteCmd))

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

    
    # Save Game State upon exit
    atexit.register(saveGameState)

    # Start the Bot
    # updater.start_webhook(listen="0.0.0.0",
    #                   port=int(PORT),
    #                   url_path=str(API_KEY),
    #                   webhook_url='https://radiant-inlet-41935.herokuapp.com/' + str(API_KEY))

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.start_polling()

    # Save Excel sheet every 90s
    timeout = 60
    l = task.LoopingCall(saveGameState)
    l.start(timeout)
    reactor.run()


if __name__ == '__main__':
    main()

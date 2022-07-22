from game import Game
from dbhelper import DBHelper, playerDataKeys, factionDataKeys
import time
import json
import pandas

db = DBHelper("shan-royale.sqlite")

def rightKill(killerUsername, victimUsername):
    killerData = db.getPlayerDataJSON(killerUsername, 1)
    victimData = db.getPlayerDataJSON(victimUsername, 1)
    killerFactionData = db.getFactionDataJSON(killerData[playerDataKeys.faction])
    
    # Update faction data
    pointsToAdd = victimData[playerDataKeys.points]
    killerFactionData[factionDataKeys.bank] += pointsToAdd
    print(killerFactionData)
    db.replaceFactionDataFromJSON(killerFactionData)

    # Update victim data
    victimData[playerDataKeys.immunityExpiry] = time.time() + 90
    victimData[playerDataKeys.points] = 5
    victimData[playerDataKeys.dying] = 0
    victimData[playerDataKeys.deathCount] += 1
    print(victimData)
    db.replacePlayerDataFromJSON(victimData, 1)

    # Update killer data
    killerData[playerDataKeys.killCount] += 1
    print(killerData)
    db.replacePlayerDataFromJSON(killerData, 1)

def main():
    # Excel to Database
    excelFilePath = "./excel/shanRoyale2022Data1.xlsx"
    playerDataRound1JSONArr = json.loads(pandas.read_excel(excelFilePath, sheet_name="playerDataRound1").to_json(orient='records'))
    playerDataRound2JSONArr = json.loads(pandas.read_excel(excelFilePath, sheet_name="playerDataRound2").to_json(orient='records'))
    factionDataJSONArr = json.loads(pandas.read_excel(excelFilePath, sheet_name="factionData").to_json(orient='records'))
    db.playerDataJSONArrToDB(playerDataRound1JSONArr, 1)
    db.playerDataJSONArrToDB(playerDataRound2JSONArr, 2)
    db.factionDataJSONArrToDB(factionDataJSONArr)
    rightKill("praveeeenk", "vigonometry")
    return

if __name__ == '__main__':
    main()
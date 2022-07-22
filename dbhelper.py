from operator import ne
import sqlite3

class playerDataKeys:
    username = "username"
    fullname = "fullname"
    faction = "faction"
    dying = "dying"
    points = "points"
    deathCount = "deathCount"
    killCount = "killCount"
    visitSpyStation = "visitSpyStation"
    stickExpiry = "stickExpiry"
    immunityExpiry = "immunityExpiry"
    safetyBreaches = "safetyBreaches"

class factionDataKeys:
    faction = "faction"
    bank = "bank"
    enemyFactionRound1 = "enemyFactionRound1"
    enemyFactionRound2 = "enemyFactionRound2"
    pointsAssigned = "pointsAssigned"

class DBKeysMap:

    playerDataKeys = {
        "0": playerDataKeys.username,
        "1": playerDataKeys.fullname,
        "2": playerDataKeys.faction,
        "3": playerDataKeys.dying,
        "4": playerDataKeys.points,
        "5": playerDataKeys.deathCount,
        "6": playerDataKeys.killCount,
        "7": playerDataKeys.visitSpyStation,
        "8": playerDataKeys.stickExpiry,
        "9": playerDataKeys.immunityExpiry,
        "10": playerDataKeys.safetyBreaches
    }

    factionDataKeys = {
        "0": factionDataKeys.faction,
        "1": factionDataKeys.bank,
        "2": factionDataKeys.enemyFactionRound1,
        "3": factionDataKeys.enemyFactionRound2,
        "4": factionDataKeys.pointsAssigned
    }

class DBHelper:
    
    def __init__(self, dbname="shan-royale.sqlite"):
        self.dbname = dbname
        self.conn = sqlite3.connect(dbname)
        self.playerTable = "playerDataRound"
        self.factionTable = "factionData"
        self.gameTable = "gameData"
        self.setup()

    
    def setup(self):
        playerRound1DataStmt = f"""CREATE TABLE IF NOT EXISTS {self.playerTable}1 ( 
            username TEXT PRIMARY KEY,
            fullname TEXT,
            faction INTEGER DEFAULT 0,
            dying BOOL DEFAULT 0,
            points INTEGER DEFAULT 0,
            deathCount INTEGER DEFAULT 0,
            killCount INTEGER DEFAULT 0,
            visitSpyStation BOOL DEFAULT 0,
            stickExpiry BIGINT DEFAULT 0,
            immunityExpiry BIGINT DEFAULT 0,
            safetyBreaches INTEGER DEFAULT 0
        )"""
        playerRound2DataStmt = f"""CREATE TABLE IF NOT EXISTS {self.playerTable}2 ( 
            username TEXT PRIMARY KEY,
            fullname TEXT,
            faction INTEGER DEFAULT 0,
            dying BOOL DEFAULT 0,
            points INTEGER DEFAULT 0,
            deathCount INTEGER DEFAULT 0,
            killCount INTEGER DEFAULT 0,
            visitSpyStation BOOL DEFAULT 0,
            stickExpiry TIMESTAMP,
            immunityExpiry TIMESTAMP,
            safetyBreaches INTEGER DEFAULT 0
        )"""
        factionDataStmt = f"""CREATE TABLE IF NOT EXISTS {self.factionTable} ( 
            faction INTEGER DEFAULT 0 PRIMARY KEY,
            bank INTEGER DEFAULT 0,
            enemyFactionRound1 INTEGER DEFAULT 0,
            enemyFactionRound2 INTEGER DEFAULT 0,
            pointsAssigned INTEGER DEFAULT 0
        )"""
        # gameDataStmt = """CREATE TABLE IF NOT EXISTS gameData ( 
        #     id INTEGER DEFAULT 0 PRIMARY KEY,
        #     currentRound INTEGER DEFAULT 0,
        #     play BOOL DEFAULT 0,
        #     killEnabled BOOL DEFAULT 0,
        #     stickRound1 INTEGER DEFAULT 0,
        #     stickRound2 INTEGER DEFAULT 0
        # )"""
        self.conn.execute(playerRound1DataStmt)
        self.conn.execute(playerRound2DataStmt)
        self.conn.execute(factionDataStmt)
        # self.conn.execute(gameDataStmt)
        self.conn.commit()

    # TODO: Check if all updates and inserts have COMMIT
    #===========================All Data Queries=====================================
    # Player Data
    def replacePlayerDataFromJSON(self, playerDataJSON, round_num):
        username = playerDataJSON["username"]
        fullname = playerDataJSON["fullname"]
        faction = playerDataJSON["faction"]
        dying = playerDataJSON["dying"]
        points = playerDataJSON["points"]
        deathCount = playerDataJSON["deathCount"]
        killCount = playerDataJSON["killCount"]
        visitSpyStation = playerDataJSON["visitSpyStation"]
        stickExpiry = playerDataJSON["stickExpiry"]
        immunityExpiry = playerDataJSON["immunityExpiry"]
        safetyBreaches = playerDataJSON["safetyBreaches"]
        stmt = f"""REPLACE INTO {self.playerTable}{round_num} (username, fullname, faction, dying, points, deathCount, killCount, visitSpyStation, stickExpiry, immunityExpiry, safetyBreaches)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        args = (username, fullname, faction, dying, points, deathCount, killCount, visitSpyStation, stickExpiry, immunityExpiry, safetyBreaches, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    def playerDataJSONArrToDB(self, arr, round_num):
        for playerDataJSON in arr:
            username = playerDataJSON["username"]
            fullname = playerDataJSON["fullname"]
            faction = playerDataJSON["faction"]
            dying = playerDataJSON["dying"]
            points = playerDataJSON["points"]
            deathCount = playerDataJSON["deathCount"]
            killCount = playerDataJSON["killCount"]
            visitSpyStation = playerDataJSON["visitSpyStation"]
            stickExpiry = playerDataJSON["stickExpiry"]
            immunityExpiry = playerDataJSON["immunityExpiry"]
            safetyBreaches = playerDataJSON["safetyBreaches"]
            stmt = f"""REPLACE INTO {self.playerTable}{round_num} (username, fullname, faction, dying, points, deathCount, killCount, visitSpyStation, stickExpiry, immunityExpiry, safetyBreaches)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            args = (username, fullname, faction, dying, points, deathCount, killCount, visitSpyStation, stickExpiry, immunityExpiry, safetyBreaches, )
            self.conn.execute(stmt, args)
        self.conn.commit()
    
    def playerDataDBtoJSON(self, dataList):
        dataJSON = {}
        for i in range(len(dataList)):
            dataJSON[DBKeysMap.playerDataKeys[str(i)]] = dataList[i]
        return dataJSON

    def getPlayerDataJSON(self, username, round_num):
        stmt = f"SELECT * FROM {self.playerTable}{round_num} WHERE username = (?)"
        args = (username,)
        for dataTuple in self.conn.execute(stmt, args):
            return self.playerDataDBtoJSON(list(dataTuple))

    # Faction Data
    def replaceFactionDataFromJSON(self, factionDataJSON):
        faction = factionDataJSON["faction"]
        bank = factionDataJSON["bank"]
        enemyFactionRound1 = factionDataJSON["enemyFactionRound1"]
        enemyFactionRound2 = factionDataJSON["enemyFactionRound2"]
        pointsAssigned = factionDataJSON["pointsAssigned"]
        stmt = f"""REPLACE INTO {self.factionTable} (faction, bank, enemyFactionRound1, enemyFactionRound2, pointsAssigned)
            VALUES (?, ?, ?, ?, ?)"""
        args = (faction, bank, enemyFactionRound1, enemyFactionRound2, pointsAssigned)
        self.conn.execute(stmt, args)
        self.conn.commit()

    def factionDataJSONArrToDB(self, arr):
        for factionDataJSON in arr:
            faction = factionDataJSON["faction"]
            bank = factionDataJSON["bank"]
            enemyFactionRound1 = factionDataJSON["enemyFactionRound1"]
            enemyFactionRound2 = factionDataJSON["enemyFactionRound2"]
            pointsAssigned = factionDataJSON["pointsAssigned"]
            stmt = f"""REPLACE INTO {self.factionTable} (faction, bank, enemyFactionRound1, enemyFactionRound2, pointsAssigned)
                VALUES (?, ?, ?, ?, ?)"""
            args = (faction, bank, enemyFactionRound1, enemyFactionRound2, pointsAssigned)
            self.conn.execute(stmt, args)
        self.conn.commit()

    def factionDataDBtoJSON(self, dataList):
        dataJSON = {}
        for i in range(len(dataList)):
            dataJSON[DBKeysMap.factionDataKeys[str(i)]] = dataList[i]
        return dataJSON

    def getFactionDataJSON(self, faction):
        stmt = f"SELECT * FROM {self.factionTable} WHERE faction = (?)"
        args = (faction,)
        for dataTuple in self.conn.execute(stmt, args):
            return self.factionDataDBtoJSON(list(dataTuple))


    # ==============================Username Queries===========================
    # (Returns True if user exists)
    def checkUsernameInDB(self, username):
        stmtRound1 = f"""SELECT * FROM {self.playerTable}1 WHERE username = (?)"""
        stmtRound2 = f"""SELECT * FROM {self.playerTable}2 WHERE username = (?)"""
        args = (username, )
        queryReturnRound1 = [x[0] for x in self.conn.execute(stmtRound1, args)]
        queryReturnRound2 = [x[0] for x in self.conn.execute(stmtRound2, args)]

        if len(queryReturnRound1) == 0 or len(queryReturnRound2) == 0:
            print("USERNAME NOT IN DATABASE: " + username)
            return False
        return True

    def getAllUsernames(self, round_num):
        stmt = f"""SELECT username FROM {self.playerTable}{round_num}"""
        return [x[0] for x in self.conn.execute(stmt)]

    # ==============================Fullname Queries===========================
    def getFullname(self, username, round_num):
        stmt = f"SELECT {playerDataKeys.fullname} FROM {self.playerTable}{round_num} WHERE username = (?)"
        args = (username,)
        for x in self.conn.execute(stmt, args):
            return x[0]

    # ==============================Faction Queries===========================
    def getTargetFaction(self, username, round_num):
        playerFaction = self.getPlayerFaction(username, round_num)
        return self.getTargetFactionFromFaction(playerFaction, round_num)

    def getTargetFactionFromFaction(self, faction, round_num):
        stmt = f"SELECT enemyFactionRound{round_num} FROM {self.factionTable} WHERE faction = (?)"
        args = (faction, )
        for x in self.conn.execute(stmt, args):
            return x[0]

    def getPlayerFaction(self, username, round_num):
        stmt = f"SELECT faction FROM {self.playerTable}{round_num} WHERE username = (?)"
        args = (username, )
        for x in self.conn.execute(stmt, args):
            return x[0]

    def getFactionMemberUsernames(self, faction, round_num):
        stmt = f"SELECT username FROM {self.playerTable}{round_num} WHERE faction = (?)"
        args = (faction, )
        factionMembers = []
        for x in self.conn.execute(stmt, args):
            factionMembers.append(x[0])
        return factionMembers

    def getBank(self, faction):
        stmt = f"SELECT bank FROM {self.factionTable} WHERE faction = (?)"
        args = (faction, )
        for x in self.conn.execute(stmt, args):
            return x[0]

    def setBank(self, balance, faction):
        stmt = f"UPDATE {self.factionTable} SET bank = (?) WHERE faction = (?)"
        args = (balance, faction, )
        for x in self.conn.execute(stmt, args):
            return x[0]

    # =============================Points queries=================================
    def getFactionMemberPoints(self, faction, round_num):
        factionMembers = self.getFactionMemberUsernames(faction, round_num)
        factionMemberPointsMap = {}
        for username in factionMembers:
            points = self.getRoundPoints(username, round_num)
            factionMemberPointsMap[username] = points
        return factionMemberPointsMap

    def getFactionPoints(self, faction, round_num):
        factionMemberPointsMap = self.getFactionMemberPoints(faction, round_num)
        factionPoints = 0
        for points in factionMemberPointsMap.values():
            factionPoints += points
        return factionPoints
    
    def getRoundPoints(self, username, round_num):
        if int(round_num) !=1 and int(round_num) != 2:
            print(f"wrong num of rounds indiciated: {round_num}")
            return
        stmt = f"""SELECT points FROM {self.playerTable}{round_num} WHERE username = (?)"""
        args = (username, )
        for x in self.conn.execute(stmt, args):
            return x[0]
    
    def updateRoundPoints(self, username, points, round_num):
        if int(round_num) !=1 and int(round_num) != 2:
            print(f"wrong num of rounds indiciated: {round_num}")
            return
        stmt = f"""UPDATE {self.playerTable}{round_num} SET points = (?) WHERE username = (?)"""
        args = (points, username, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    #=================================KD Queries==================================================
    def getFactionMemberKD(self, faction, round_num):
        factionMembers = self.getFactionMemberUsernames(faction, round_num)
        factionMemberKDMap = {}
        for username in factionMembers:
            kills = self.getRoundKillCount(username, round_num)
            deaths = self.getRoundDeathCount(username, round_num)
            factionMemberKDMap[username] = [kills, deaths]
        return factionMemberKDMap
    
    def getRoundKillCount(self, username, round_num):
        if int(round_num) !=1 and int(round_num) != 2:
            print(f"wrong num of rounds indiciated: {round_num}")
            return
        stmt = f"""SELECT killCount FROM {self.playerTable}{round_num} WHERE username = (?)"""
        args = (username, )
        for x in self.conn.execute(stmt, args):
            return x[0]

    def getRoundDeathCount(self, username, round_num):
        if int(round_num) !=1 and int(round_num) != 2:
            print(f"wrong num of rounds indiciated: {round_num}")
            return
        stmt = f"""SELECT deathCount FROM {self.playerTable}{round_num} WHERE username = (?)"""
        args = (username, )
        for x in self.conn.execute(stmt, args):
            return x[0]

    # ===============================Safety Queries=================================================
    def getPlayerSafetyBreaches(self, username, round_num):
        stmt = f"SELECT safetyBreaches FROM {self.playerTable}{round_num} WHERE username = (?)"
        args = (username,)
        for x in self.conn.execute(stmt, args):
            return x[0]

    #==============================Expiry Queries===============================================
    def getImmunityExpiry(self, username, round_num):
        stmt = f"SELECT immunityExpiry FROM {self.playerTable}{round_num} WHERE username = (?)"
        args = (username,)
        for x in self.conn.execute(stmt, args):
            return x[0]

    def getStickExpiry(self, username, round_num):
        stmt = f"SELECT stickExpiry FROM {self.playerTable}{round_num} WHERE username = (?)"
        args = (username,)
        for x in self.conn.execute(stmt, args):
            return x[0]

    def setStickExpiry(self, username, round_num, stickExpiry):
        stmt = f"""UPDATE {self.playerTable}{round_num} SET stickExpiry = (?) WHERE username = (?)"""
        args = (stickExpiry, username, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    def getPlayerVisitSpyStation(self, username, round_num):
        stmt = f"SELECT visitSpyStation FROM {self.playerTable}{round_num} WHERE username = (?)"
        args = (username,)
        for x in self.conn.execute(stmt, args):
            return x[0]

    def setPlayerVisitSpyStation(self, username, round_num, visited):
        stmt = f"""UPDATE {self.playerTable}{round_num} SET visitSpyStation = (?) WHERE username = (?)"""
        args = (visited, username, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    #=============================Dying Queries=============================================
    def setPlayerDying(self, username, round_num, dying):
        stmt = f"""UPDATE {self.playerTable}{round_num} SET dying = (?) WHERE username = (?)"""
        args = (dying, username, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    def getPlayerDying(self, username, round_num):
        stmt = f"""SELECT dying FROM {self.playerTable}{round_num} WHERE username = (?)"""
        args = (username, )
        for x in self.conn.execute(stmt, args):
            return x[0]

    # Purge data queries

    def purgeplayerData(self):
        playerRound1Datastmt = "DELETE FROM playerRound1Data"
        playerRound2Datastmt = "DELETE FROM playerRound2Data"
        self.conn.execute(playerRound1Datastmt)
        self.conn.execute(playerRound2Datastmt)
        self.conn.commit()

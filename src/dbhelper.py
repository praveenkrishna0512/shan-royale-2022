from operator import ne
import sqlite3

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

    # ===================Excel to DB methods====================================
    # TODO CHECK THAT DO NOT CALL THIS AFTER GAME BEGINS
    def processPlayerDataJSONArr(self, arr, round_num):
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
    # TODO CHECK THAT DO NOT CALL THIS AFTER GAME BEGINS
    def processFactionDataJSONArr(self, arr):
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

    # ==============================Faction Queries===========================
    def getTargetFaction(self, username, round_num):
        playerFaction = self.getPlayerFaction(username, round_num)
        stmt = f"SELECT enemyFactionRound{round_num} FROM {self.factionTable} WHERE faction = (?)"
        args = (playerFaction, )
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
    # TODO: HERE NOW
    def getFactionMemberKD(self, faction, round_num):
        factionMembers = self.getFactionMemberUsernames(faction, round_num)
        factionMemberKDMap = {}
        for username in factionMembers:
            points = self.getRoundPoints(username, round_num)
            factionMemberKDMap[username] = points
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
        data = []
        for x in self.conn.execute(stmt, args):
            return x[0]

    # Get One User Data

    def getPlayerData(self, username, round_num):
        stmt = f"SELECT * FROM {self.playerTable}{round_num} WHERE username = (?)"
        args = (username,)
        data = []
        for x in self.conn.execute(stmt, args):
            for i in range(0, len(x)):
                data.append(x[i])
        return data

    # Purge data queries

    def purgeplayerData(self):
        playerRound1Datastmt = "DELETE FROM playerRound1Data"
        playerRound2Datastmt = "DELETE FROM playerRound2Data"
        self.conn.execute(playerRound1Datastmt)
        self.conn.execute(playerRound2Datastmt)
        self.conn.commit()

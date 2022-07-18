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


    # Username Queries (Returns True if user exists)
    def handleUsername(self, username, round_num):
        stmt = f"""SELECT * FROM {self.playerTable}{round_num} WHERE username = (?)"""
        args = (username, )
        queryReturn = [x[0] for x in self.conn.execute(stmt, args)]
        if len(queryReturn) == 0:
            print("Adding new username: " + username)
            self.__addUsername(username, round_num)
            return False
        return True

    def __addUsername(self, username, round_num):
        stmt = f"INSERT INTO {self.playerTable}{round_num} (username) VALUES (?)"
        args = (username, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    def getAllUsernames(self, round_num):
        stmt = f"""SELECT username FROM {self.playerTable}{round_num}"""
        return [x[0] for x in self.conn.execute(stmt)]

    # Points queries
    def updateRoundPoints(self, username, points, round_num):
        if round_num !=1 and round_num !=2:
            print(f"wrong num of rounds indiciated: {round_num}")
            return
        stmt = f"""UPDATE {self.playerTable}{round_num} SET points = (?) WHERE username = (?)"""
        args = (points, username, )
        self.conn.execute(stmt, args)
        self.conn.commit()

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

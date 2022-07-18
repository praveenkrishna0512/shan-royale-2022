from operator import ne
import sqlite3

class DBHelper:
    
    def __init__(self, dbname="shan-royale.sqlite"):
        # TODO CHANGE TO 0 and make set_round function
        self.curr_round = 1
        # TODO CHANGE TO "" and update it in set_round function
        self.currentPlayerTable = "playerRound1Data"
        self.dbname = dbname
        self.conn = sqlite3.connect(dbname)
        self.setup()

    
    def setup(self):
        playerRound1DataStmt = """CREATE TABLE IF NOT EXISTS playerRound1Data ( 
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
        playerRound2DataStmt = """CREATE TABLE IF NOT EXISTS playerRound2Data ( 
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
        factionDataStmt = """CREATE TABLE IF NOT EXISTS factionData ( 
            faction INTEGER DEFAULT 0 PRIMARY KEY,
            bank INTEGER DEFAULT 0,
            enemyFactionRound1 INTEGER DEFAULT 0,
            enemyFactionRound2 INTEGER DEFAULT 0,
            pointsAssigned INTEGER DEFAULT 0
        )"""
        gameDataStmt = """CREATE TABLE IF NOT EXISTS gameData ( 
            id INTEGER DEFAULT 0 PRIMARY KEY,
            currentRound INTEGER DEFAULT 0,
            play BOOL DEFAULT 0,
            killEnabled BOOL DEFAULT 0,
            stickRound1 INTEGER DEFAULT 0,
            stickRound2 INTEGER DEFAULT 0
        )"""
        self.conn.execute(playerRound1DataStmt)
        self.conn.execute(playerRound2DataStmt)
        self.conn.execute(factionDataStmt)
        self.conn.execute(gameDataStmt)
        self.conn.commit()

    # Username Queries (Returns True if user exists)
    def handleUsername(self, username):
        stmt = f"""SELECT * FROM {self.currentPlayerTable} WHERE username = (?)"""
        args = (username, )
        queryReturn = [x[0] for x in self.conn.execute(stmt, args)]
        if len(queryReturn) == 0:
            print("Adding new username: " + username)
            self.__addUsername(username)
            return False
        return True

    def __addUsername(self, username):
        stmt = f"INSERT INTO {self.currentPlayerTable} (username) VALUES (?)"
        args = (username, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    def getAllUsernames(self):
        stmt = f"""SELECT username FROM {self.currentPlayerTable}"""
        return [x[0] for x in self.conn.execute(stmt)]

    # Points queries
    def updateRoundPoints(self, username, points, round_no):
        if round_no !=1 and round_no !=2:
            print(f"wrong num of rounds indiciated: {round_no}")
            return
        stmt = f"""UPDATE {self.currentPlayerTable} SET pointsRound{round_no} = (?) WHERE username = (?)"""
        args = (points, username, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    # Get One User Data

    def getPlayerData(self, username):
        stmt = f"SELECT * FROM {self.currentPlayerTable} WHERE username = (?)"
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

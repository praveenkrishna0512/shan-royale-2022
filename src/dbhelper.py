from operator import ne
import sqlite3
dayList = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
noSessionString = "No Session"
thisWeekString = "This Week"
nextWeekString = "Next Week"

class DBHelper:
    
    def __init__(self, dbname="shan-royale.sqlite"):
        self.dbname = dbname
        self.conn = sqlite3.connect(dbname)

    # Timeslot Availability is captured in 16 bits for each day
    # First 8 bits represent this week, Last 8 bits represent next week
    # 0 means not available, 1 means available
    # The 8 bits represent these timeslots in this order: 7am, 9am, 11am, 1pm, 3pm, 5pm, 7pm, 9pm
    def setup(self):
        playerDataStmt = """CREATE TABLE IF NOT EXISTS playerData ( 
            username TEXT PRIMARY KEY,
            faction INTEGER DEFAULT 0,
            pointsRound1 INTEGER DEFAULT 0,
            pointsRound2 INTEGER DEFAULT 0,
            pointsRound3 INTEGER DEFAULT 0,
            deathCount INTEGER DEFAULT 0,
            killCount INTEGER DEFAULT 0
        )"""
        factionDataStmt = """CREATE TABLE IF NOT EXISTS factionData ( 
            faction INTEGER DEFAULT 0 PRIMARY KEY,
            bank INTEGER DEFAULT 0,
            enemyFaction INTEGER DEFAULT 0,
            pointsAssigned INTEGER DEFAULT 0
        )"""
        self.conn.execute(playerDataStmt)
        self.conn.execute(factionDataStmt)
        self.conn.commit()

    # Username Queries

    def handleUsername(self, username):
        stmt = """SELECT * FROM userData WHERE username = (?)"""
        args = (username, )
        queryReturn = [x[0] for x in self.conn.execute(stmt, args)]
        if len(queryReturn) == 0:
            self.__addUsername(username)

    def __addUsername(self, username):
        stmt = "INSERT INTO userData (username) VALUES (?)"
        args = (username, )
        self.conn.execute(stmt, args)
        self.conn.commit()

    def getAllUsernames(self):
        stmt = """SELECT username FROM userData"""
        return [x[0] for x in self.conn.execute(stmt)]

    # Session queries

    def setSession(self, username, state):
        # STATES (encoding - value passed in)
        # 0 - not amending, 1 - this week, 2 - next week
        inSession = self.determineSession(state)
        stmt2 = """UPDATE userData SET inSession = (?) WHERE username = (?)"""
        args2 = (inSession, username, )
        self.conn.execute(stmt2, args2)
        self.conn.commit()

    def determineSession(self, state):
        if state == noSessionString:
            return 0
        if state == thisWeekString:
            return 1
        if state == nextWeekString:
            return 2
        else:
            print("ERROR in determineSession: Bad Week State Input")

    def getSession(self, username):
        currSession = self.getSessionHelper(username)
        if currSession != thisWeekString and currSession != nextWeekString:
            print("ERROR in getSession: Wrong Session Input!")
            return
        return currSession

    def getSessionHelper(self, username):
        stmt = """SELECT inSession FROM userData WHERE username = (?)"""
        args = (username, )
        state = -1
        for x in self.conn.execute(stmt, args):
            state = x[0]
        if state == 0:
            return noSessionString
        if state == 1:
            return thisWeekString
        if state == 2:
            return nextWeekString

    # Get All User Data

    def getAllUserData(self, username):
        stmt = "SELECT * FROM userData WHERE username = (?)"
        args = (username, )
        return self.conn.execute(stmt, args)

    # Purge data queries

    def purgeUserData(self):
        stmt = "DELETE FROM userData"
        self.conn.execute(stmt)
        self.conn.commit()

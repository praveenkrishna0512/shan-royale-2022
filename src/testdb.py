from game import Game
from dbhelper import DBHelper

db = DBHelper("shan-royale.sqlite")

def main():
    db.handleUsername("praveeeenk")
    print(db.getPlayerData("praveeeenk"))
    return

if __name__ == '__main__':
    main()
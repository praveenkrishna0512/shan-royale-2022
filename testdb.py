from game import Game
from dbhelper import DBHelper

db = DBHelper("shan-royale.sqlite")

def main():
    print(db.getPlayerDataJSON("praveeeenk", 1))
    return

if __name__ == '__main__':
    main()
from game import Game
from dbhelper import DBHelper

db = DBHelper("shan-royale.sqlite")

def main():
    print(db.getFactionPoints(1, 2))
    return

if __name__ == '__main__':
    main()
from dbhelper import DBHelper

db = DBHelper("shan-royale.sqlite")

def main():
    db.addUsername("@praveeeenk")
    db.handleUsername("@praveeeenk")
    print(db.getAllUsernames())

if __name__ == '__main__':
    main()
from game import Game

def adminBeginGame(round_no):
    newGame = Game(round_no, play=True)
    return newGame

def adminEndSetPoints(game):
    print(game)
    game.killEnabled = True
    return game
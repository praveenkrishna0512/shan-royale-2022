from game import Game

def beginRound(round_no):
    newGame = Game(round_no, play=True)
    return newGame

def endSetPoints(game):
    game.killEnabled = True
    return game

def endRound(game):
    game.play = False
    game.killEnabled = False
    return game
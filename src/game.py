class Game:
    def __init__(self, currentRound, play=False, killEnabled=False, stickRound1=0, stickRound2=0):
        self.currentRound = currentRound
        self.play = play
        self.killEnabled = killEnabled
        self.stickRound1 = stickRound1
        self.stickRound2 = stickRound2
    
    def toString(self):
        print(f"""Game Info:
Current Round: {self.currentRound}
Play: {self.play}
killEnabled: {self.killEnabled}
stickRound1: {self.stickRound1}
stickRound2: {self.stickRound2}""")
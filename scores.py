import requests

class HighScoresFetch:
	def __init__(self, name, source='http://bomberman-aulas.ws.atnog.av.it.pt/highscores/'):
		self.name = name
		self.url = source+name
		self.data = requests.get(self.url).json()

	def get_best_entry(self, type="max", key='score'):
		return max([d for d in self.data], key=lambda x:x[key]) if type == "max" else min([d for d in self.data], key=lambda x:x[key])
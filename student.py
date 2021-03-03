import asyncio
import getpass
import json
import os
import random
import websockets
from threading import Thread
from mapa import Map
from tree_search import *
import mapa
from sokoban_domain import SokobanDomain
from consts import Tiles, TILES
import uteis

class Client:
    def __init__(self, addr, name):
        self.server_address=addr
        self.agent_name=name
        self.plan = None

    async def agent_loop(self, server_address, agent_name):
        async with websockets.connect(f"ws://{server_address}/player") as websocket:
            # Receive information about static game properties
            await websocket.send(json.dumps({"cmd": "join", "name": agent_name}))

            while True:
                try:
                    update = json.loads(
                        await websocket.recv()
                    )  # receive game update, this must be called timely or your game will get out of sync with the server
                    
                    if "map" in update:
                        # we got a new level
                        game_properties = update
                        print("Novo nível: ", update["map"])
                        mythread = Thread(target=self.sokobanSolver, args=(update["map"],))
                        mythread.start()

                    else:
                        # we got a current map state update
                        state = update

                    if self.plan==[] or self.plan==None:
                        key=''
                    else:
                        key = self.plan[0]
                        self.plan = self.plan[1:]    
                    await websocket.send(
                        json.dumps({"cmd": "key", "key": key})
                    )
                    
                except websockets.exceptions.ConnectionClosedOK:
                    print("Server has cleanly disconnected us")
                    return
    def sokobanSolver(self, filename):
        mapa = Map(filename)
        initial = [mapa.keeper, mapa.boxes]
        goal = [None, mapa.filter_tiles([Tiles.MAN_ON_GOAL, Tiles.BOX_ON_GOAL, Tiles.GOAL])]
        t = SearchTree(SearchProblem(SokobanDomain(filename), initial, goal), "greedy")

        t.search()
        self.plan = [idx for path in [idx[1] for idx in t.plan] for idx in path]
        return t

# DO NOT CHANGE THE LINES BELLOW
# You can change the default values using the command line, example:
# $ NAME='arrumador' python3 client.py
if __name__=="__main__":
    #"""
    c=Client("localhost:8001", "ogrande")
    loop = asyncio.get_event_loop()
    SERVER = os.environ.get("SERVER", "localhost")
    PORT = os.environ.get("PORT", "8001")
    NAME = os.environ.get("NAME", getpass.getuser())
    loop.run_until_complete(c.agent_loop(f"{SERVER}:{PORT}", NAME))
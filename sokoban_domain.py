from tree_search import SearchDomain, SearchProblem, SearchTree

from mapa import Map
from consts import Tiles, TILES
import copy

def directions():
    return list("wasd")

def inside_range(pos, size):
    return pos[0] in range(size[0]) and pos[1] in range(size[1])

#retorna a nova posição a partir de certa ação
def new_pos(pos, action):
    cx, cy = pos
    if   action == "w":
        return cx, cy - 1
    elif action == "a":
        return cx - 1, cy
    elif action == "s":
        return cx, cy + 1
    elif action == "d":
        return cx + 1, cy

#retorna a posição anterior a certa ação
def prior_pos(pos, action):
    cx, cy = pos
    if   action == "w":
        return cx, cy + 1
    elif action == "a":
        return cx + 1, cy
    elif action == "s":
        return cx, cy - 1
    elif action == "d":
        return cx - 1, cy

def manhattan_distance(pos1, pos2):
    return abs(pos1[0] - pos2[0]) + abs(pos1[1] - pos2[1])

class SokobanDomain(SearchDomain):
    def __init__(self, filename):
        self.count = 0

        self.level = filename
        mapa = Map(filename)

        for box in mapa.boxes:
            mapa.clear_tile(box)
        mapa.clear_tile(mapa.keeper)

        self.walls = mapa.filter_tiles([Tiles.WALL])
        self.goals = mapa.empty_goals
        self.floor = mapa.filter_tiles([Tiles.FLOOR])
        self.size  = mapa.size
       
        self.distanceToGoal = dict()
        for goal in self.goals:
            tmp = dict()
            self.distanceToGoal[goal] = tmp
            for pos in (self.floor + self.goals):
                tmp[pos] = float('inf')

        queue = []
        for goal in self.goals:
            self.distanceToGoal[goal][goal] = 0
            queue[:0] = (goal),
            while queue != []:
                pos = queue.pop()
                for dir in directions():
                    boxpos = new_pos(pos, dir)
                    playerpos = new_pos(boxpos, dir)
                    if(not mapa.is_blocked(boxpos) and not mapa.is_blocked(playerpos)):
                        goaldict = self.distanceToGoal[goal]
                        if goaldict[boxpos] == float('inf'):
                            goaldict[boxpos] = goaldict[pos] + 1
                            queue[:0] = (boxpos),

        self.simpledeadlocks = []
        positions = dict()
        for pos in self.floor:
            positions[pos] = True
        for goal in self.distanceToGoal:
            dicio = self.distanceToGoal[goal]
            for pos in dicio:
                if dicio[pos] != float('inf'):
                    positions[pos] = False

        for pos in positions:
            if positions[pos]:
                self.simpledeadlocks.append(pos)

        reachablegoals = dict()
        self.areas = dict()

        for pos in self.floor:
            if pos not in self.simpledeadlocks:
                reachablegoals[pos] = []
        
        for pos in reachablegoals:
            for goal in self.goals:
                if self.distanceToGoal[goal][pos] != float('inf'):
                    (reachablegoals[pos]).append(goal)
            goals = frozenset(reachablegoals[pos])
            reachablegoals[pos] = goals
            if goals not in self.areas:
                self.areas[goals] =  [pos]
            else:
                self.areas[goals] += [pos]

        self.visitedkeepers = {}

    def is_movable(self, boxes, walls, box, direction):
        '''
        @param boxes, the boxes that define a state, including the box that will move
        @param walls, the walls of a specified state
        @param box, the box that will move
        @param direction, the direction in which the box will move
        Function who analyses if a box is movable in a certain direction
        The function returns True if it can be moved, False otherwise
        '''
        obstacles  = self.get_other_boxes(boxes, box) + walls
        newbox = new_pos(box, direction)
        return inside_range(newbox, self.size) and (newbox not in obstacles + self.simpledeadlocks) and (prior_pos(box, direction) not in obstacles)

    def keeper_plan(self, boxes, initial, goal):
        '''
        @param boxes, the boxes that define a state
        @param initial, the keeper initial position
        @param goal, the keeper goal position
        Function that analyses if keeper can reach a certain position in a certain state
        return the keeper plan(the movements he does to reach the goal),
        which also means the goal is reachable from that certain state, or None otherwise
        '''
        domain  = KeeperDomain(boxes + self.walls, self.size)
        problem = SearchProblem(domain, initial, goal)
        tree    = SearchTree(problem, "greedy")
        if tree.search():
            return tree.plan
        return None

    def freeze_deadlock_detection(self, boxes, walls, box):
        '''
        @param boxes, the other boxes in the state removed the box
        @param walls, the considered walls in a certain context
        @param box, the box being analysed if generates a freeze deadlock
        Function that anlyses if a certain box can create a deadlock
        return True if it can, False otherwise
        '''
        if len([dir for dir in directions() if self.is_movable(boxes, walls, box, dir)]) == 0:
            countbox      = 0
            countdeadlock = 0
            for dir in directions():
                newbox = new_pos(box, dir)
                if(newbox in boxes):
                    countbox += 1
                    newboxes = self.get_other_boxes(boxes, box)
                    newwalls = walls + [box]
                    if self.freeze_deadlock_detection(newboxes, newwalls, newbox):
                        countdeadlock += 1
            if(countbox == countdeadlock):
                return True
        return False

    def areadeadlock_detection(self, boxes):
        for area in self.areas:
            if sum([1 for box in boxes if box in self.areas[area]]) > len(self.areas[area]):
                return True
        return False
                                
    def deadlock_detection(self, boxes, box, direction):
        '''
        @param boxes, the boxes that define a state, including the box that will move
        @param box, the box that will move
        @param direction, the direction the box will move
        Function that anlyses if a new state originated from a certain one
        can generate a deadlock
        returns True if the newstate is a deadlock, False otherwise
        '''
        newboxes = self.get_newboxes(boxes, box, direction)
        if self.areadeadlock_detection(newboxes):
            return True

        newbox = new_pos(box, direction)
        if not newbox in self.goals:
            if self.freeze_deadlock_detection(newboxes, self.walls, newbox):
                return True
        return False

    def visitable(self, state):
        '''
        @param state: the search state
        Analyses if the current state can be reached from a previous visited state, 
        which makes this state expansion irrelevant.
        returns True if it can be visited from a previous visited state, False otherwise
        '''
        key = frozenset(state[1])
        if key in self.visitedkeepers:
            for visitedplayer in self.visitedkeepers[key]:
                plan = self.keeper_plan(state[1], state[0], visitedplayer)
                if not plan is None:
                    return True
        return False

    def allowed(self, state, box, dir):
        if not self.is_movable(state[1], self.walls, box, dir):
            return False
        if self.deadlock_detection(state[1], box, dir):
            return False
        return True

    def get_newboxes(self, boxes, box, direction):
        return self.get_other_boxes(boxes, box) + [new_pos(box, direction)]

    def get_other_boxes(self, boxes, box):
        other_boxes = copy.deepcopy(boxes)
        other_boxes.remove(box)
        return other_boxes

    def sorting(self,boxes):
        '''
        @param boxes. the boxes that define a certain state
        returns the sorted list of the boxes
        '''
        return sorted(boxes, key=lambda pos: (pos[0], pos[1]))

    def greedy_distance(self, boxes, infinite=100000000):
        edges = sorted([((goal, box), self.distanceToGoal[goal][box]) for box in boxes for goal in self.goals], key=lambda p: p[1])
        for idx in range(len(edges)):
            edge = edges[idx]
            if edge[1] == float('inf'):
                edges[idx] = (edge[0], infinite)
    
        matches = []
        matchedBoxes = set()
        matchedGoals = set()
        for tmp in edges:
            goal = tmp[0][0]
            box = tmp[0][1]
            if(not (goal in matchedGoals) and not(box in matchedBoxes)):
                matches += [tmp]
                matchedBoxes.add(box)
                matchedGoals.add(goal)

        for box in boxes:
            if box not in matchedBoxes:
                closestgoal = None
                for goal in [goal for goal in self.goals if goal not in matchedGoals]:
                    if (box in self.distanceToGoal[goal]) and (closestgoal is None or self.distanceToGoal[goal][box] < self.distanceToGoal[closestgoal][box]):
                        closestgoal = goal
                matches += [((closestgoal, box), self.distanceToGoal[closestgoal][box])]
                matchedBoxes.add(box)
                matchedGoals.add(closestgoal)

        soma = sum([idx[1] for idx in matches])
        if soma == float('inf'):
            soma = 0
        return soma


    def actions(self,state):

        if self.visitable(state):
            return -1

        if frozenset(state[1]) in self.visitedkeepers:
            self.visitedkeepers[frozenset(state[1])].append(state[0])
        else:
            self.visitedkeepers[frozenset(state[1])] = [state[0]]

        actlist = []
        for box in state[1]:
            for direction in [dir for dir in directions() if self.allowed(state, box, dir)]:
                plan = self.keeper_plan(state[1], state[0], prior_pos(box, direction))
                if not plan is None:
                    actlist += [(box, plan + [direction])]
        return actlist

    def result(self, state, action):
        box, path = action
        return [box, self.get_newboxes(state[1], box, path[-1])]

    def cost(self, state, action):
        return len(action[1])

    def heuristic(self, state, goal):
        return self.greedy_distance(state[1])

    def equivalent(self,state1,state2):
        return (self.sorting(state1[1])==self.sorting(state2[1])) and state1[0] == state2[0]

    def satisfies(self, state, goal):
        return (self.sorting(state[1])==self.sorting(goal[1]))

    def hash(self, state):
        return (str([state[0]]+self.sorting(state[1])))

class KeeperDomain(SearchDomain):
    def __init__(self, obstacles, size):
        '''
        @param obstacles: positions in the map in which you can not set the keeper because
        it has either a wall or a box from a specific state.
        @param size: tuple (x,y) with the vertical and horizontal size of the map
        '''
        self.size = size
        self.obstacles = obstacles

    def is_movable(self, pos, direction):
        '''
        @param pos: the current keeper position
        @param direction: the direction in which the keeper will move
        checks if keeper can move in the specified direction
        return True if it is possible, False otherwise
        '''
        newpos = new_pos(pos, direction)
        return inside_range(newpos, self.size) and newpos not in self.obstacles

    def actions(self,state):
        return [dir for dir in directions() if self.is_movable(state, dir)]

    def result(self,state,action):
        return new_pos(state, action)
        
    def cost(self, state, action):
        return 1

    def heuristic(self, state, goal):
        return manhattan_distance(state, goal)

    def equivalent(self,state1,state2):
        return state1==state2

    def satisfies(self, state, goal):
        return self.equivalent(state, goal)

    def hash(self, state):
        return str(state)
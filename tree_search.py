
# Module: tree_search
# 
# This module provides a set o classes for automated
# problem solving through tree search:
#    SearchDomain  - problem domains
#    SearchProblem - concrete problems to be solved
#    SearchNode    - search tree nodes
#    SearchTree    - search tree with the necessary methods for searhing
#
#  (c) Luis Seabra Lopes
#  Introducao a Inteligencia Artificial, 2012-2019,
#  Inteligência Artificial, 2014-2019

from abc import ABC, abstractmethod
import heapq

# Dominios de pesquisa
# Permitem calcular
# as accoes possiveis em cada estado, etc
class SearchDomain(ABC):

    # construtor
    @abstractmethod
    def __init__(self):
        pass

    # lista de accoes possiveis num estado
    @abstractmethod
    def actions(self, state):
        pass

    # resultado de uma accao num estado, ou seja, o estado seguinte
    @abstractmethod
    def result(self, state, action):
        pass

    # custo de uma accao num estado
    @abstractmethod
    def cost(self, state, action):
        pass

    # custo estimado de chegar de um estado a outro
    @abstractmethod
    def heuristic(self, state, goal):
        pass

    #see if two states are equivalent
    @abstractmethod
    def equivalent(self, state1, state2):
        pass

    # test if the given "goal" is satisfied in "state"
    @abstractmethod
    def satisfies(self, state, goal):
        pass

    #creates a hash value to the state
    @abstractmethod
    def hash(self, state):
        pass


# Problemas concretos a resolver
# dentro de um determinado dominio
class SearchProblem:
    def __init__(self, domain, initial, goal):
        self.domain = domain
        self.initial = initial
        self.goal = goal
        
    def goal_test(self, state):
        return self.domain.satisfies(state,self.goal)

    def goal_box(self, box):
        return self.domain.satisfies_box(box, self.goal)

# Nos de uma arvore de pesquisa
class SearchNode:
    def __init__(self,state,parent, depth, cost, heuristic=0, action=None): 
        self.state     = state
        self.parent    = parent
        self.depth     = depth
        self.cost      = cost
        self.heuristic = heuristic
        self.action    = action
        self.children  = None
    
    def in_parent(self, state, equals):
        if self.parent == None:
            return False
        return equals(state, self.parent.state) or self.parent.in_parent(state, equals)

    def __str__(self):
        return f"no({str(self.state)},{str(self.parent)}, {str(self.action)})"
    def __repr__(self):
        return str(self)

# Arvores de pesquisa
class SearchTree:

    # construtor
    def __init__(self,problem, strategy='breadth'): 
        self.problem          = problem
        self.root             = SearchNode(problem.initial, None, 0, 0, self.problem.domain.heuristic(
                                self.problem.initial, self.problem.goal))
        self.open_nodes       = [(0,0,self.root)]
        heapq.heapify(self.open_nodes)
        self.strategy         = strategy
        self.solution         = None

        self.visited_nodes = set()


    @property
    def visited_ones(self):
        return len(self.visited_nodes)

    @property
    def length(self):
        if self.solution:
            return self.solution.depth
        return None

    @property
    def path(self):
        if self.solution:
            return self.get_path(self.solution)
        return None

    @property
    def cost(self):
        if self.solution:
            return self.solution.cost
        return None

    @property
    def plan(self):
        if self.solution:
            return self.get_plan(self.solution)
        return None

    # obter o caminho (sequencia de estados) da raiz ate um no
    def get_path(self,node):
        if node.parent == None:
            return [node.state]
        return self.get_path(node.parent) + [node.state]

    def get_plan(self,node):
        if node.parent == None:
            return []
        return self.get_plan(node.parent) + [node.action]

    def visited(self, state):
        return self.problem.domain.hash(state) in self.visited_nodes

    def instantiate_state(self, node, action):
        newstate = self.problem.domain.result(node.state,action)
        newnode  = SearchNode(newstate,node, node.depth+1, node.cost+self.problem.domain.cost(node.state, action), self.problem.domain.heuristic(newstate,self.problem.goal), action)
        return newstate, newnode

    # procurar a solucao
    def search(self):
        node_counter = 0
        while self.open_nodes != []:
            node = heapq.heappop(self.open_nodes)[2]

            if self.visited(node.state):
                continue

            self.visited_nodes.add(self.problem.domain.hash(node.state))

            if self.problem.goal_test(node.state):
                self.solution = node
                return self.path

            node.children = []

            actions = self.problem.domain.actions(node.state)
            if actions == -1:
                self.visited_nodes.add(self.problem.domain.hash(node.state))
                continue

            for action in actions:
                newstate, newnode = self.instantiate_state(node, action)
                if not node.in_parent(newstate, self.problem.domain.equivalent) and (not self.visited(newstate)):
                    node.children.append(newnode)
                    value = 0
                    if self.strategy == 'breadth':
                        value = node_counter
                    elif self.strategy == 'uniform':
                        value = newnode.cost
                    elif self.strategy == 'greedy':
                        value = newnode.heuristic
                    elif self.strategy == 'a*':
                        value = newnode.heuristic + newnode.cost
                    heapq.heappush(self.open_nodes,(value,node_counter,newnode))
                    node_counter += 1
        return None

    def show(self,node=None,indent=''):
        if node==None:
            self.show(self.root)
            print('-----------------------------------------------------------------------')
        else:
            if(self.problem.domain.equivalent(node.state, self.root.state)):
                print(indent+str(node.state))
            else:
                print(indent+str(node.action))
            if node.children==None:
                return
            for n in node.children:
                self.show(n,indent+'--')

#!/usr/bin/env python3

"""
k-induction
"""

from pn import PetriNet
from eq import System
from formula import Formula

import sys
from subprocess import PIPE, Popen
from threading import Thread, Event

stop_it = Event()


class KInduction:
    """
    K-induction method
    """
    def __init__(self, pn, pn_reduced, eq, formula):
        self.pn = pn
        self.pn_reduced = pn_reduced
        self.eq = eq
        self.formula = formula
        self.solver = Popen(["z3", "-in"], stdin = PIPE, stdout=PIPE)

    def smtlib_ordered(self, k):
        text = ""

        text += "; Declaration of the places from the original Petri Net\n"
        text += self.pn.smtlib_declare_places()

        text += "; Formula to check the satisfiability\n"
        text += self.formula.smtlib()

        text += "; Reduction Equations"
        text += self.eq.smtlib_only_non_reduced_places()

        text += "; Declaration of the places from the reduced Petri Net (order: {})\n".format(0)
        text += self.pn_reduced.smtlib_declare_places_ordered(0)

        text += "; Inital Marking of the reduced Petri Net\n"
        text += self.pn_reduced.smtlib_set_marking_ordered(0)

        for i in range(k):
            text += "; Declaration of the places from the reduced Petri Net (order: {})\n".format(1)
            text += self.pn_reduced.smtlib_declare_places_ordered(i + 1)

            text += "; Transition Relation: {} -> {}\n".format(i, i + 1)
            text += self.pn_reduced.smtlib_transitions_ordered(i)

        text += "; Reduction Equations\n"
        text += self.eq.smtlib_ordered(k)

        text += "(check-sat)\n(get-model)\n"

        return text

    def solve(self):
        print("K-Induction running:")
        k = 0 
        self.solver.stdin.write(bytes(self.pn.smtlib_declare_places(), 'utf-8'))
        self.solver.stdin.write(bytes(self.formula.smtlib(), 'utf-8'))
        self.solver.stdin.write(bytes(self.eq.smtlib_only_non_reduced_places(), 'utf-8'))
        self.solver.stdin.write(bytes(self.pn_reduced.smtlib_declare_places_ordered(0), 'utf-8'))
        self.solver.stdin.write(bytes(self.pn_reduced.smtlib_set_marking_ordered(0), 'utf-8'))
        self.solver.stdin.write(bytes("(push)\n", 'utf-8'))
        self.solver.stdin.write(bytes(self.eq.smtlib_ordered(k), 'utf-8'))
        
        while k < 100 and not self.formula.check_sat(self.solver) and not stop_it.is_set():
            print("k =", k)
            self.solver.stdin.write(bytes("(pop)\n", 'utf-8'))
            self.solver.stdin.write(bytes(self.pn_reduced.smtlib_declare_places_ordered(k + 1), 'utf-8'))
            self.solver.stdin.write(bytes(self.pn_reduced.smtlib_transitions_ordered(k), 'utf-8'))
            self.solver.stdin.write(bytes("(push)\n", 'utf-8'))
            self.solver.stdin.write(bytes(self.eq.smtlib_ordered(k + 1), 'utf-8'))
            k += 1
        
        if k < 100 and not stop_it.is_set():
            self.formula.get_model(self.solver)
        else:
            print("Method stopped!")


if __name__ == '__main__':
    
    if len(sys.argv) < 2:
        exit("File missing: ./k_induction.py <path_to_initial_petri_net> [<path_to_reduce_net>]")

    pn = PetriNet(sys.argv[1])
    
    if len(sys.argv) == 3:
        pn_reduced = PetriNet(sys.argv[2])
        system = System(sys.argv[2], pn.places.keys(), pn_reduced.places.keys())
    else:
        pn_reduced = PetriNet(sys.argv[1])
        system = System(sys.argv[1], pn.places.keys(), pn_reduced.places.keys())
    
    formula = Formula(pn)
    
    k_induction = KInduction(pn, pn_reduced, system, formula)

    print("Input into the SMT Solver")
    print("-------------------------")
    print(k_induction.smtlib_ordered(1))

    print("Result computed using z3")
    print("------------------------")
    proc = Thread(target= k_induction.solve)
    proc.start()
    proc.join(timeout = 600)
    stop_it.set()

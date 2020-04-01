#!/usr/bin/env python3

"""
Z3 interface

Using SMT-LIB v2 format
Standard: http://smtlib.cs.uiowa.edu/papers/smt-lib-reference-v2.6-r2017-07-18.pdf

Dependency: https://github.com/Z3Prover/z3

This module can easily be hacked to replace Z3
by an other SMT solver supporting the SMT-LIB format.
"""
from formula import Clause, Inequality

from subprocess import PIPE, Popen

class Solver:
    """
    Solver defined by:
    - a Z3 process
    """
    def __init__(self):
        """Execute z3 in a new process."""
        self.solver = Popen(["z3", "-in"], stdin = PIPE, stdout = PIPE)

    def write(self, text):
        """Write instructions into the standard input of z3."""
        self.solver.stdin.write(bytes(text, 'utf-8'))
        self.solver.stdin.flush()

    def reset(self):
        """Reset z3."""
        self.write("(reset)\n")

    def exit(self):
        """"Exit z3."""
        self.write("(exit)\n")

    def push(self):
        """
        Push.
        Creates a new scope by saving the current stack size
        """
        self.write("(push)\n")

    def pop(self):
        """
        Pop.
        Removes any assertion or declaration performed between it and the matching push.
        """
        self.write("(pop)\n")

    def check_sat(self):
        """Check the satisfiability of the current stack of z3."""
        self.write("(check-sat)\n")
        return self.solver.stdout.readline().decode('utf-8').strip() == 'sat'

    def get_model(self, pn, order = None):
        """Get a model from the current SAT stack and return it as conjunctive clause."""
        self.write("(get-model)\n")
        model = []
        # Read the model
        self.solver.stdout.readline()
        # Parse the model
        while True:
            place_content = self.solver.stdout.readline().decode('utf-8').strip().split(' ')
            if len(place_content) < 2 or self.solver.poll() is not None:
                break
            place_marking =  self.solver.stdout.readline().decode('utf-8').strip().replace(' ', '').replace(')', '')
            place = ""
            if order is None:
                place = place_content[1]
            else:
                place_content = place_content[1].split('@')
                if int(place_content[1]) == order:
                    place = place_content[0]
            if place_marking and place in pn.places:
                model.append(Inequality(pn.places[place], place_marking, '='))
        return Clause(model, 'and')

    def display_model(self, pn):
        """Display the obtained model."""
        model = ''
        for eq in self.get_model(pn).inequalities:
            if int(eq.right_member) > 0:
                model += ' ' + eq.left_member.id
        if model == '':
            model = " empty marking"
        print("Model:", model, sep='')


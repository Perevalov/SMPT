#!/usr/bin/env python3

"""
K-Induction

Based on:
Mary Sheeran, Satnam Singh, and Gunnar Stälmarck.
Checking safety properties using induction and a SAT-solver. 
FMCAD 2000

Adapted for Petri nets

This file is part of SMPT.

SMPT is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

SMPT is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with SMPT. If not, see <https://www.gnu.org/licenses/>.
"""

__author__ = "Nicolas AMAT, LAAS-CNRS"
__contact__ = "namat@laas.fr"
__license__ = "GPLv3"
__version__ = "2.0.0"

import logging as log
import sys
from multiprocessing import Process, Queue

from formula import Formula
from ptnet import PetriNet
from solver import Solver
from system import System
from utils import STOP, send_signal


class KInduction:
    """
    K-Induction method.
    """

    def __init__(self, ptnet, formula, ptnet_reduced=None, system=None, show_model=False, debug=False, induction_queue=None, sequential=False):
        """ Initializer.
        """
        # Initial Petri net
        self.ptnet = ptnet

        # Reduced Petri net
        self.ptnet_reduced = ptnet_reduced

        # System of linear equations
        self.system = system

        # Formula to study
        self.formula = formula

        # Show model option
        self.show_model = show_model

        # SMT solver
        self.solver = Solver(debug)

        # Queue shared with BMC
        self.induction_queue = induction_queue

        # Additional solver if sequential enabled
        self.bmc_solver = Solver(debug)

    def smtlib(self, k):
        """ SMT-LIB format for debugging.
        """
        if self.ptnet_reduced is None:
            smt_input = self.smtlib_without_reduction(k)
        else:
            smt_input = self.smtlib_with_reduction(k)

        smt_input += "(check-sat)\n"

        return smt_input

    def smtlib_without_reduction(self, k):
        """ SMT-LIB format for debugging.
            Case without reduction.
        """
        smt_input = ""

        smt_input += "; Declaration of the places from the Petri net (iteration: {})\n".format(0)
        smt_input += self.ptnet.smtlib_declare_places(0)

        for i in range(k):
            smt_input += "; Assert states safes (iteration:{})\n".format(i)
            smt_input += self.formula.P.smtlib(i, assertion=True)
            
            smt_input += "; Declaration of the places from the Petri net (iteration: {})\n".format(1)
            smt_input += self.ptnet.smtlib_declare_places(i + 1)

            smt_input += "; Transition relation: {} -> {}\n".format(i, i + 1)
            smt_input += self.ptnet.smtlib_transition_relation(i, eq=False)

        smt_input += "; Formula to check the satisfiability\n"
        smt_input += self.formula.R.smtlib(k + 1, assertion=True)

        return smt_input

    def smtlib_with_reduction(self, k):
        """ SMT-LIB format for debugging.
            Case with reduction.
        """
        # smt_input = ""

        # smt_input += "; Declaration of the places from the initial Petri net\n"
        # smt_input += self.ptnet.smtlib_declare_places(0)

        # smt_input += "; Declaration of the additional variables\n"
        # smt_input += self.system.smtlib_declare_additional_variables()

        # smt_input += "; Reduction equations (not involving places from the reduced Petri net)"
        # smt_input += self.system.smtlib_equations_without_places_from_reduced_net()

        # smt_input += "; Declaration of the places from the reduced Petri net (iteration: {})\n".format(0)
        # smt_input += self.ptnet_reduced.smtlib_declare_places(0)

        # smt_input += "; Initial marking of the reduced Petri net\n"
        # smt_input += self.ptnet_reduced.smtlib_initial_marking(0)

        # for i in range(k):
        #     smt_input += "; Declaration of the places from the reduced Petri net (iteration: {})\n".format(1)
        #     smt_input += self.ptnet_reduced.smtlib_declare_places(i + 1)

        #     smt_input += "; Transition relation: {} -> {}\n".format(i, i + 1)
        #     smt_input += self.ptnet_reduced.smtlib_transition_relation(i)

        # smt_input += "; Reduction equations\n"
        # smt_input += self.system.smtlib_equations_with_places_from_reduced_net(k)

        # smt_input += "; Link initial and reduced Petri nets\n"
        # smt_input += self.system.smtlib_link_nets(k)

        # return smt_input
        return ""

    def prove(self, result, concurrent_pids):
        """ Prover.
        """
        log.info("[K-INDUCTION] RUNNING")

        if self.ptnet_reduced is None:
            iteration = self.prove_without_reduction()
        else:
            iteration = self.prove_with_reduction()

        if self.induction_queue is not None:
            self.induction_queue.put(iteration)

        # Kill the solver
        self.solver.kill()

        # Quit if the solver has aborted
        if self.solver.aborted:
            return

        # Put the result in the queue
        result.put([False, None])

        # Terminate concurrent methods
        if not concurrent_pids.empty():
            send_signal(concurrent_pids.get(), STOP)

    def prove_without_reduction(self):
        """ Prover for non-reduced Petri Net.
        """
        log.info("[K-INDUCTION] > Initialization")

        log.info("[K-INDUCTION] \t>> Declaration of the places from the Petri net (iteration: 0)")
        self.solver.write(self.ptnet.smtlib_declare_places(0))

        log.info("[K-INDUCTION] \t>> Assert safe states (iteration: 0)")
        self.solver.write(self.formula.P.smtlib(0, assertion=True))

        log.info("[K-INDUCTION] \t>> Declaration of the places from the Petri net (iteration: 1)")
        self.solver.write(self.ptnet.smtlib_declare_places(1))

        log.info("[K-INDUCTION] \t>> Transition relation: {} -> {}".format(0, 1))
        self.solver.write(self.ptnet.smtlib_transition_relation(0, eq=False))

        log.info("[K-INDUCTION] \t>> Push")
        self.solver.push()

        log.info("[K-INDUCTION] \t>> Formula to check the satisfiability (iteration: 1)")
        self.solver.write(self.formula.R.smtlib(1, assertion=True))

        k = 1
        while self.solver.check_sat():

            log.info("[K-INDUCTION] > k = {}".format(k))

            log.info("[K-INDUCTION] \t>> Pop")
            self.solver.pop()

            log.info("[K-INDUCTION] \t>> Declaration of the places from the Petri net (iteration: {})".format(k + 1))
            self.solver.write(self.ptnet.smtlib_declare_places(k + 1))

            log.info("[K-INDUCTION] \t>> Assert states safe (iteration: {})".format(k))
            self.solver.write(self.formula.P.smtlib(k, assertion=True))

            log.info("[K-INDUCTION] \t>> Transition relation: {} -> {}".format(k, k + 1))
            self.solver.write(self.ptnet.smtlib_transition_relation(k, eq=False))

            log.info("[K-INDUCTION] \t>> Push")
            self.solver.push()

            log.info("[K-INDUCTION] \t>> Formula to check the satisfiability (iteration: {})".format(k + 1))
            self.solver.write(self.formula.R.smtlib(k + 1, assertion=True))

            k += 1

        return k

    def prove_with_reduction(self):
        """ Prover for reduced Petri Net.
        """
        # log.info("[K-INDUCTION] > Initialization")
        # log.info("[K-INDUCTION] \t>> Declaration of the places from the initial Petri net")
        # self.solver.write(self.ptnet.smtlib_declare_places())
        # log.info("[K-INDUCTION] \t>> Declaration of the additional variables")
        # self.solver.write(self.system.smtlib_declare_additional_variables())
        # log.info("[K-INDUCTION] \t>> Formula to check the satisfiability")
        # self.solver.write(self.formula.R.smtlib(assertion=True))
        # log.info("[K-INDUCTION] \t>> Reduction equations (not involving places from the reduced Petri net)")
        # self.solver.write(self.system.smtlib_equations_without_places_from_reduced_net())
        # log.info("[K-INDUCTION] \t>> Declaration of the places from the reduced Petri net (iteration: 0)")
        # self.solver.write(self.ptnet_reduced.smtlib_declare_places(0))
        # log.info("[K-INDUCTION] \t>> Initial marking of the reduced Petri net")
        # self.solver.write(self.ptnet_reduced.smtlib_initial_marking(0))
        # log.info("[K-INDUCTION] \t>> Push")
        # self.solver.push()
        # log.info("[K-INDUCTION] \t>> Reduction equations")
        # self.solver.write(self.system.smtlib_equations_with_places_from_reduced_net(0))
        # log.info("[K-INDUCTION] \t>> Link initial and reduced Petri nets")
        # self.solver.write(self.system.smtlib_link_nets(0))

        # if not self.ptnet_reduced.places and not self.solver.check_sat():
        #     return -1

        # k = 0
        # while not self.solver.check_sat():
        #     log.info("[K-INDUCTION] > k = {}".format(k))
        #     log.info("[K-INDUCTION] \t>> Pop")
        #     self.solver.pop()
        #     log.info("[K-INDUCTION] \t>> Declaration of the places from the reduced Petri net (iteration: {})".format(k + 1))
        #     self.solver.write(self.ptnet_reduced.smtlib_declare_places(k + 1))
        #     log.info("[K-INDUCTION] \t>> Transition relation: {} -> {}".format(k, k + 1))
        #     self.solver.write(self.ptnet_reduced.smtlib_transition_relation(k))
        #     log.info("[K-INDUCTION] \t>> Push")
        #     self.solver.push()
        #     log.info("[K-INDUCTION] \t>> Reduction equations")
        #     self.solver.write(self.system.smtlib_equations_with_places_from_reduced_net(k + 1))
        #     log.info("[K-INDUCTION] \t>> Link initial and reduced Petri nets")
        #     self.solver.write(self.system.smtlib_link_nets(k + 1))
        #     k += 1

        # return None
        return None

if __name__ == '__main__':

    if len(sys.argv) < 2:
        sys.exit("Argument missing: ./bmc.py <path_to_Petri_net> [<path_to_reduced_Petri_net>]")

    log.basicConfig(format="%(message)s", level=log.DEBUG)

    ptnet = PetriNet(sys.argv[1])

    formula = Formula(ptnet)
    formula.generate_deadlock()

    if len(sys.argv) == 3:
        ptnet_reduced = PetriNet(sys.argv[2])
        system = System(sys.argv[2], ptnet.places.keys(), ptnet_reduced.places.keys())
    else:
        ptnet_reduced = None
        system = None

    k_induction = KInduction(ptnet, formula, ptnet_reduced=ptnet_reduced, system=system, show_model=True)

    print("> Generated SMT-LIB")
    print("-------------------")
    print(k_induction.smtlib(1))

    print("> Result computed using z3")
    print("--------------------------")
    result, concurrent_pids = Queue(), Queue()
    proc = Process(target=k_induction.prove, args=(result, concurrent_pids,))
    proc.start()
    proc.join(timeout=60)
    if not result.empty():
        sat, _ = result.get()
        print(formula.result(sat))

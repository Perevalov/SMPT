"""
CP: Constraint Programming Method

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

from __future__ import annotations

__author__ = "Nicolas AMAT, LAAS-CNRS"
__contact__ = "namat@laas.fr"
__license__ = "GPLv3"
__version__ = "4.0.0"

import logging as log
from multiprocessing import Queue

from smpt.checkers.abstractchecker import AbstractChecker
from smpt.exec.utils import STOP, send_signal_pids
from smpt.interfaces.minizinc import MiniZinc
from smpt.interfaces.solver import Solver
from smpt.interfaces.z3 import Z3
from smpt.ptio.formula import Formula
from smpt.ptio.ptnet import Marking, PetriNet
from smpt.ptio.system import System
from smpt.ptio.verdict import Verdict


class CP(AbstractChecker):
    """ Constraint Programming method.

    Attributes
    ----------
    ptnet : PetriNet
        Initial Petri net.
    system : System, optional
        System of reduction equations.
    formula : Formula
        Reachability formula.
    show_model : bool
        Show model flag.
    minizinc : bool
        MiniZinc flag.
    solver : Solver
        Solver (Z3 or MiniZinc).
    """

    def __init__(self, ptnet: PetriNet, formula: Formula, system: System, show_model: bool = False, debug: bool = False, minizinc: bool = False, solver_pids: Queue[int] = None) -> None:
        """ Initializer.

        Parameters
        ----------
        ptnet : PetriNet
            Initial Petri net.
        formula : Formula
            Reachability formula.
        system : System, optional
            System of reduction equations.
        show_model : bool, optional
            Show model flag.
        debug : bool, optional
            Debugging flag.
        minizinc : bool, optional
            MiniZinc flag.
        solver_pids : Queue of int, optional
            Queue to share the current PID.
        """
        # Initial Petri net
        self.ptnet: PetriNet = ptnet

        # System of linear equations
        self.system: System = system

        # Formula to study
        self.formula: Formula = formula

        # Show model option
        self.show_model: bool = show_model

        # MiniZinc option
        self.minizinc: bool = minizinc

        # Solver
        if minizinc:
            self.solver: Solver = MiniZinc(
                debug=debug, solver_pids=solver_pids)
        else:
            self.solver = Z3(debug=debug, solver_pids=solver_pids)

    def prove(self, results: Queue[tuple[Verdict, Marking]], concurrent_pids: Queue[list[int]]) -> None:
        """ Prover.

        Parameters
        ----------
        result : Queue of tuple of Verdict, Marking
            Queue to exchange the verdict.
        concurrent_pids : Queue of int
            Queue to get the PIDs of the concurrent methods.
        """
        model = None

        if self.minizinc:
            sat = self.prove_minizinc()
        else:
            sat = self.prove_smt()

        if sat and self.show_model:
            model = self.solver.get_marking(self.ptnet)

        if sat:
            verdict = Verdict.CEX
        else:
            verdict = Verdict.INV

        # Kill the solver
        self.solver.kill()

        # Quit if the solver has aborted
        if self.solver.aborted:
            return

        # Put the result in the queue
        results.put((verdict, model))

        # Terminate concurrent methods
        if not concurrent_pids.empty():
            send_signal_pids(concurrent_pids.get(), STOP)

    def prove_minizinc(self) -> bool:
        """ Solve constraints using MiniZinc.

        Returns
        -------
        bool
            Satisfiability of the formula.
        """
        log.info("[CP] \t>> Declaration of the places from the initial Petri net")
        self.solver.write(self.ptnet.minizinc_declare_places())

        log.info(
            "[CP] \t>> Declaration of the additional variables and assertion of the reduction equations")
        self.solver.write(self.system.minizinc())

        log.info("[CP] \t>> Formula to check the satisfiability")
        self.solver.write(self.formula.R.minizinc(assertion=True))

        return self.solver.check_sat()

    def prove_smt(self) -> bool:
        """ Solve constraints using SMT.

        Returns
        -------
        bool
            Satisfiability of the formula.
        """
        log.info("[CP] \t>> Declaration of the places from the initial Petri net")
        self.solver.write(self.ptnet.smtlib_declare_places())

        log.info(
            "[CP] \t>> Declaration of the additional variables and assertion of the reduction equations")
        self.solver.write(self.system.smtlib())

        log.info("[CP] \t>> Formula to check the satisfiability")
        self.solver.write(self.formula.R.smtlib(assertion=True))

        return self.solver.check_sat()

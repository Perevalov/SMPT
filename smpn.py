#!/usr/bin/env python3

"""
Satisfiability Modulo Petri Net
"""

from pn import PetriNet
from formula import Properties
from eq import System
from enumerativemarking import EnumerativeMarking
from kinduction import KInduction

import argparse
import os
import subprocess
from threading import Thread, Event

stop_it = Event()


def enumerative_marking(pn, pn_reduced, eq, formula, path_markings):
    """
    Enumerative method caller
    """
    markings = EnumerativeMarking(path_markings, pn_reduced)

    smtlib = "; Variable Definitions\n" \
        + pn.smtlib_declare_places()    \
        + "; Reduction Equations\n"     \
        + eq.smtlib()                   \
        + "; Property Formula\n"        \
        + formula.smtlib()              \
        + "; Reduced Net Markings\n"    \
        + markings.smtlib()                \
        + "(check-sat)\n(get-model)\n"

    print("Input into the SMT Solver")
    print("-------------------------")
    print(smtlib)

    smt_filename = "a.smt"
    smt_file = open(smt_filename, 'w')
    smt_file.write(smtlib)
    smt_file.close()
    proc = subprocess.Popen(['z3', '-smt2', smt_filename], stdout=subprocess.PIPE)

    print("Result computed using z3")
    print("------------------------")
    formula.result(proc)

    proc.poll()
    os.remove(smt_filename)


def k_induction(pn, pn_reduced, eq, formula):
    """
    K-induction method caller
    """
    k_induction = KInduction(pn, pn_reduced, eq, formula)

    # Run solver with timeout
    proc = Thread(target= k_induction.solve)
    proc.start()
    proc.join(timeout = 5)
    stop_it.set()

def main():
    """
    Main Function
    """
    parser = argparse.ArgumentParser(description='Satisfiability Modulo Petri Net')
    
    parser.add_argument('--version', action='version',
                        version='%(prog)s 1.0')
    
    parser.add_argument('path_pn',
                        metavar='pn',
                        type=str,
                        help='path to Petri Net (.net format)')

    parser.add_argument('path_props',
                        metavar='properties',
                        type=str,
                        help='path to Properties (.xml format)')

    parser.add_argument('--reduced',
                        action='store',
                        dest='path_pn_reduced',
                        type=str,
                        help='Path to reduced Petri Net (.net format)')

    parser.add_argument('--enumerative',
                        action='store',
                        dest='path_markings',
                        type=str,
                        help='Path to markings  (.aut format)')

    results = parser.parse_args()

    pn = PetriNet(results.path_pn)
    
    if results.path_pn_reduced is not None:
        pn_reduced = PetriNet(results.path_pn_reduced)
        eq = System(results.path_pn_reduced, pn.places.keys(), pn_reduced.places.keys())
    else:
        pn_reduced = PetriNet(results.path_pn)
        eq = System(results.path_pn, pn.places.keys(), pn_reduced.places.keys())

    props = Properties(pn, results.path_props)

    for formula_id, formula in props.formulas.items():
        print("---{}---".format(formula_id))
        if results.path_markings is not None:
            enumerative_marking(pn, pn_reduced, eq, formula, results.path_markings)
        else:
            k_induction(pn, pn_reduced, eq, formula)
    exit(0)


if __name__ == '__main__':
    main()
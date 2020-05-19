#!/usr/bin/env python3

"""
Satisfiability Modulo Petri Net

LAAS-CNRS

Author: Nicolas AMAT
"""

from pn import PetriNet
from formula import Properties, Formula
from eq import System
from enumerative_marking import EnumerativeMarking
from k_induction import KInduction, stop_k_induction
from ic3 import IC3, stop_ic3
from concurrent_places import ConcurrentPlaces
from parallelizer import Parallelizer

import argparse
import logging as log
import os
import subprocess
import sys
import tempfile
from threading import Thread, Event


def about():
    """ About printer.
    """
    logo = "            _____                    _____                    _____                _____            \n" \
         + "           /\    \                  /\    \                  /\    \              /\    \           \n" \
         + "          /::\    \                /::\____\                /::\    \            /::\    \          \n" \
         + "         /::::\    \              /::::|   |               /::::\    \           \:::\    \         \n" \
         + "        /::::::\    \            /:::::|   |              /::::::\    \           \:::\    \        \n" \
         + "       /:::/\:::\    \          /::::::|   |             /:::/\:::\    \           \:::\    \       \n" \
         + "      /:::/__\:::\    \        /:::/|::|   |            /:::/__\:::\    \           \:::\    \      \n" \
         + "      \:::\   \:::\    \      /:::/ |::|   |           /::::\   \:::\    \          /::::\    \     \n" \
         + "    ___\:::\   \:::\    \    /:::/  |::|___|______    /::::::\   \:::\    \        /::::::\    \    \n" \
         + "   /\   \:::\   \:::\    \  /:::/   |::::::::\    \  /:::/\:::\   \:::\____\      /:::/\:::\    \   \n" \
         + "  /::\   \:::\   \:::\____\/:::/    |:::::::::\____\/:::/  \:::\   \:::|    |    /:::/  \:::\____\  \n" \
         + "  \:::\   \:::\   \::/    /\::/    / ~~~~~/:::/    /\::/    \:::\  /:::|____|   /:::/    \::/    /  \n" \
         + "   \:::\   \:::\   \/____/  \/____/      /:::/    /  \/_____/\:::\/:::/    /   /:::/    / \/____/   \n" \
         + "    \:::\   \:::\    \                  /:::/    /            \::::::/    /   /:::/    /            \n" \
         + "     \:::\   \:::\____\                /:::/    /              \::::/    /   /:::/    /             \n" \
         + "      \:::\  /:::/    /               /:::/    /                \::/____/    \::/    /              \n" \
         + "       \:::\/:::/    /               /:::/    /                  ~~           \/____/               \n" \
         + "        \::::::/    /               /:::/    /                                                      \n" \
         + "         \::::/    /               /:::/    /                                                       \n" \
         + "          \::/    /                \::/    /                                                        \n" \
         + "           \/____/                  \/____/                                                         \n"
    print(logo)
    print("\tSatisfiability Modulo PeTri Net")
    print("\t-------------------------------\n")
    print("LAAS-CNRS")
    print("Author: Nicolas AMAT")
    exit(0)

def enumerative_marking(path_markings, pn, formula, pn_reduced, eq, debug):
    """ Enumerative method caller
    """
    markings = EnumerativeMarking(path_markings, pn, formula, pn_reduced, eq, debug)
    markings.prove()

def k_induction(pn, formula, pn_reduced, eq, debug, timeout):
    """ K-induction method caller
    """
    k_induction = KInduction(pn, formula, pn_reduced, eq, debug)

    # Run analysis method with timeout
    proc = Thread(target=k_induction.prove)
    proc.start()
    proc.join(timeout)
    stop_k_induction.set()

def ic3(pn):
    """ IC3 method caller
    """
    ic3 = IC3(pn, formula, pn_reduced, eq, debug)

    # Run analysis method with timeout
    proc = Thread(target=ic3.prove)
    proc.start()
    proc.join(timeout)
    stop_ic3.set()

def main():
    """ Main Function
    """
    if len(sys.argv) == 2 and sys.argv[1] == '--about':
        about()

    parser = argparse.ArgumentParser(description='Satisfiability Modulo Petri Net')

    parser.add_argument('--version',
                        action='version',
                        version='%(prog)s 1.0')

    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help="increase output verbosity")

    parser.add_argument('--debug',
                        action='store_true',
                        help="display the SMT-LIB input/ouput")
    
    parser.add_argument('path_pn',
                        metavar='pn',
                        type=str,
                        help='path to Petri Net (.net format)')

    group_formula = parser.add_mutually_exclusive_group(required=True)

    group_formula.add_argument('--xml',
                        action='store',
                        dest='path_properties',
                        type=str,
                        help='use xml format for properties')

    group_formula.add_argument('--reachability',
                        action='store',
                        dest='reach_places',
                        type=str,
                        help='reachibility analysis (seperate places by commas)')

    group_formula.add_argument('--concurrent-places',
                        action='store_true',
                        help="concurrent places analysis")

    parser.add_argument('--compressed-matrix',
                        action='store_true',
                        help="concurrent places matrix compressed")

    parser.add_argument('--complete-matrix',
                        action='store_true',
                        help="run an analysis on the compleness of the matrix")

    group_reduce = parser.add_mutually_exclusive_group()
    
    group_reduce.add_argument('--auto-reduce',
                        action='store_true',
                        help="reduce automatically the Petri Net (using `reduce`)")

    group_reduce.add_argument('--reduced',
                        action='store',
                        dest='path_pn_reduced',
                        type=str,
                        help='path to reduced Petri Net (.net format)')

    group_enumerative = parser.add_mutually_exclusive_group()

    group_enumerative.add_argument('--auto-enumerative',
                        action='store_true',
                        help="enumerate automatically the states (using `tina`)")

    group_enumerative.add_argument('--enumerative',
                        action='store',
                        dest='path_markings',
                        type=str,
                        help='Path to markings  (.aut format)')

    parser.add_argument('--timeout',
                        action='store',
                        dest='timeout',
                        type=int,
                        default=60,
                        help='configure the timeout')                    

    results = parser.parse_args()

    if results.verbose:
        log.basicConfig(format="%(message)s", level=log.DEBUG)
    else:
        log.basicConfig(format="%(message)s")

    pn = PetriNet(results.path_pn)
    
    pn_reduced = None
    eq = None
    
    if results.auto_reduce:
        fp_pn_reduced = tempfile.NamedTemporaryFile(suffix='.net')
        subprocess.run(["reduce", "-rg,redundant,compact,convert,transitions", results.path_pn, fp_pn_reduced.name])
        results.path_pn_reduced = fp_pn_reduced.name

    if results.path_pn_reduced is not None:
        pn_reduced = PetriNet(results.path_pn_reduced)
        eq = System(results.path_pn_reduced, pn.places.keys(), pn_reduced.places.keys())
    
    if results.auto_enumerative:
        fp_markings = tempfile.NamedTemporaryFile(suffix='.aut')
        if results.path_pn_reduced is not None:
            path_pn = results.path_pn_reduced
        else:
            path_pn = results.path_pn
        subprocess.run(["tina", "-aut", "-sp", "1", path_pn, fp_markings.name])
        results.path_markings = fp_markings.name

    if results.path_properties is not None:
        props = Properties(pn, results.path_properties)
        for formula_id, formula in props.formulas.items():
            print("---{}---".format(formula_id))
            if results.path_markings is not None:
                enumerative_marking(results.path_markings, pn, formula, pn_reduced, eq, results.debug)
            else:
                k_induction(pn, formula, pn_reduced, eq, results.debug, results.timeout)

    if results.reach_places is not None:
        print("---Reachability: {}---".format(results.reach_places))
        places = results.reach_places.replace('#', '').replace('{', '').replace('}', '').split(',')
        marking = {}
        for pl in places:
            marking[pn.places[pl]] = 1
        formula = Formula(pn, 'reachability', marking=marking)
        parallelizer = Parallelizer(pn, formula, pn_reduced, eq, results.debug)
        model = parallelizer.run()
       
    if results.concurrent_places:
        concurrent_places = ConcurrentPlaces(pn, pn_reduced, eq, results.debug)
        concurrent_places.analyze(results.timeout, results.complete_matrix)
        concurrent_places.display(results.compressed_matrix)

    if results.auto_reduce:
        fp_pn_reduced.close()

    if results.auto_enumerative:
        fp_markings.close()


if __name__ == '__main__':
    main()
    exit(0)


"""
Reduction Equations Module

Equations provided by the `reduce` tool from the TINA toolbox.
TINA toolbox: http://projects.laas.fr/tina/

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

import re
import sys
from typing import Optional


class System:
    """ Reduction equations system.

    Attributes
    ----------
    places_initial : list of str
        A list of place identifiers from the initial Petri net.
    places_reduced : list of str
        A list of place identifiers from the reduced Petri net.
    additional_vars : list of Variable
        A list of additional variables (not places).
    equations : list of Equation
        A list of (in)equations.
    """

    def __init__(self, filename: str, places_initial: Optional[list[str]] = None, places_reduced: Optional[list[str]] = None) -> None:
        """ Initializer.

        Parameters
        ----------
        filename : str
            Path to reduction system (.net format).
        places_initial : list of str, optional
            A list of place identifiers from the initial Petri net.
        places_reduced : list of str, optional
            A list of place indentifiers from the reduced Petri net.
        """
        if places_initial is None:
            places_initial = []
        self.places_initial: list[str] = places_initial

        if places_reduced is None:
            places_reduced = []
        self.places_reduced: list[str] = places_reduced

        self.additional_vars: list[str] = []

        self.equations: list[Equation] = []

        self.parser(filename)

    def __str__(self) -> str:
        """ Equations to textual format.

            Returns
            -------
            str
                Debugging format.
        """
        return '\n'.join(map(str, self.equations))

    def smtlib(self, k: Optional[int] = None, k_initial: Optional[int] = None) -> str:
        """ Decalare the additional variables and assert the equations.

        Parameters
        ----------
        k : int, optional
            Order for the current net (reduced one).
        k_initial : int, optional
            Order for the initial net (used by PDR).

        Returns
        --------
        str
            SMT-LIB format.
        """
        if k is None:
            smt_input = ''.join(
                map(lambda var: "(declare-const {} Int)\n(assert (>= {} 0))\n".format(var, var), self.additional_vars))
        else:
            smt_input = ''.join(
                map(lambda var: "(declare-const {}@{} Int)\n(assert (>= {}@{} 0))\n".format(var, k, var, k), self.additional_vars))

        if k is None and k_initial is None:
            smt_input += '\n'.join(map(lambda eq: eq.smtlib(),
                                   self.equations)) + '\n'
        else:
            smt_input += '\n'.join(map(lambda eq: eq.smtlib_with_order(k, k_initial, self.places_reduced, [
                                   *self.places_initial] + self.additional_vars), self.equations)) + '\n'

        return smt_input

    def minizinc(self) -> str:
        """ Declare the additional variables and assert the equations.

        Returns
        -------
        str
            MiniZinc format.
        """
        minizinc_input = ""

        for var in self.additional_vars:
            if var not in self.places_reduced:
                minizinc_input += "var 0..MAX: {};\n".format(var)

        minizinc_input += ''.join(map(lambda eq: eq.minizinc(),
                                  self.equations))

        return minizinc_input

    def smtlib_declare_additional_variables(self, k_initial: Optional[int] = None) -> str:
        """ Declare the additional variables.

        Parameters
        ----------
        k_initial : int, optional
            Order for the initial net (used by PDR).
        
        Returns
        --------
        str
            SMT-LIB format.
        """
        smt_input = ""

        for var in self.additional_vars:
            if var not in self.places_reduced:
                var_name = var if k_initial is None else "{}@{}".format(
                    var, k_initial)
                smt_input += "(declare-const {} Int)\n(assert (>= {} 0))\n".format(
                    var_name, var_name)

        return smt_input

    def smtlib_equations_without_places_from_reduced_net(self, k_initial: Optional[int] = None) -> str:
        """ Assert equations not involving places in the reduced net.

        Parameters
        ----------
        k_initial : int, optional
            Order for the initial net (used by PDR).

        Returns
        --------
        str
            SMT-LIB format.
        """
        smt_input = ""

        for eq in self.equations:
            if not eq.contain_reduced:
                smt_input += eq.smtlib(k_initial,
                                       [*self.places_initial] + self.additional_vars) + '\n'

        return smt_input

    def smtlib_equations_with_places_from_reduced_net(self, k: int, k_initial: Optional[int] = None) -> str:
        """ Assert equations involving places in the reduced net.

        Parameters
        ----------
        k : int
            Order for the current net (reduced one).
        k_initial : int, optional
            Order for the initial net (used by PDR).

        Returns
        --------
        str
            SMT-LIB format.
        """
        smt_input = ""

        for eq in self.equations:
            if eq.contain_reduced:
                smt_input += eq.smtlib_with_order(k, k_initial, self.places_reduced,
                                                  [*self.places_initial] + self.additional_vars) + '\n'

        return smt_input

    def smtlib_link_nets(self, k: int, k_initial: Optional[int] = None) -> str:
        """ Assert equalities between places common to the initial and reduced nets.

        Parameters
        ----------
        k : int
            Order for the current net (reduced one).
        k_initial : int, optional
            Order for the initial net (used by PDR).

        Returns
        --------
        str
            SMT-LIB format.
        """
        smt_input = ""

        for pl in self.places_reduced:
            if pl in self.places_initial:
                if k_initial is None:
                    smt_input += "(assert (= {}@{} {}))\n".format(pl, k, pl)
                else:
                    smt_input += "(assert (= {}@{} {}@{}))\n".format(pl,
                                                                     k, pl, k_initial)

        return smt_input

    def parser(self, filename: str) -> None:
        """ System of reduction equations parser.
            
        Parameters
        ----------
        filename : str
            Path to reduction system (.net format).

        Raises
        ------
        FileNotFoundError
            Reduction system file not found.
        """
        try:
            with open(filename, 'r') as fp:
                content = re.search(r'generated equations\n(.*)?\n\n',
                                    fp.read().replace('#', '.').replace(',', '.'), re.DOTALL)  # '#' and ',' forbidden in SMT-LIB
                if content:
                    for line in re.split('\n+', content.group())[1:-1]:
                        if line.partition(' |- ')[0] not in ['. O', '. C']:
                            self.equations.append(
                                Equation(line, self))
            fp.close()
        except FileNotFoundError as e:
            sys.exit(e)


class Equation:
    """ Reduction equation.

    Attributes
    ----------
    left : list of Variable
        A left members (sum).
    right : list of Variable
        A right members (sum).
    operator : str
        An operator (=, <=, >=, <, >).
    contain_reduced : bool
        A boolean indicating whether the equation involves places from the reduced net.
    """

    def __init__(self, content: str, system: System) -> None:
        """ Initializer.

        Parameters
        ----------
        content : str
            Equation to parse.
        system : System
            Current system of reduction equations.
        """
        self.left: list[Variable] = []
        self.right: list[Variable] = []
        self.operator: str = ""

        self.contain_reduced: bool = False

        self.parse_equation(content, system)

    def __str__(self) -> str:
        """ Equation to .net format.

        Returns
        -------
        str
            Debugging format.
        """
        return ' + '.join(map(str, self.left)) + ' = ' + ' + '.join(map(str, self.right))

    def smtlib(self, k_initial: Optional[int] = None, additional_vars: Optional[list[str]] = None) -> str:
        """ Assert the Equation.

        Parameters
        ----------
        k_initial : int, optional
            Order for the initial net (used by PDR).
        additional_vars : list of str
            Identfifiers of additional variables.

        Returns
        -------
        str
            SMT-LIB format.
        """
        if additional_vars is None:
            additional_vars = []

        return "(assert ({}".format(self.operator) \
               + self.member_smtlib(self.left, k_initial, additional_vars) \
               + self.member_smtlib(self.right, k_initial, additional_vars) \
               + "))"

    def minizinc(self) -> str:
        """ Assert the Equation.

        Returns
        -------
            MiniZinc format.
        """
        return "constraint " \
               + self.member_minizinc(self.left) \
               + " {} ".format(self.operator) \
               + self.member_minizinc(self.right) \
               + ";\n"

    def member_smtlib(self, member: list[Variable], k_initial: Optional[int] = None, additional_vars: Optional[list[str]] = None) -> str:
        """ Helper to assert a member (left or right).

        Parameters
        ----------
        member : list of Variable
            One of the two members (left or right).
        k_initial : int, optional
            Order for the initial net (used by PDR).
        additional_vars : list of str, optional
             Identfifiers of additional variables.
            
        Returns
        -------
        str
            SMT-LIB format.
        """
        if additional_vars is None:
            additional_vars = []

        smt_input = ""

        for var in member:
            if k_initial is None or var.id not in additional_vars:
                smt_input += var.smtlib()
            else:
                smt_input += var.smtlib(k_initial)

        if len(member) > 1:
            smt_input = " (+{})".format(smt_input)

        return smt_input

    def member_minizinc(self, member: list[Variable]) -> str:
        """ Helper to assert a member (left or right).

        Parameters
        ----------
        member : list of Variable
            One of the two members (left or right).

        Returns
        -------
        str
            MiniZinc format.
        """
        return ' + '.join(map(lambda var: var.minizinc(), member))

    def smtlib_with_order(self, k: Optional[int], k_initial: Optional[int] = None, places_reduced: Optional[list[str]] = None, additional_vars: Optional[list[str]] = None) -> str:
        """ Assert equations with order.

        Parameters
        ----------
        k : int
            Order for the current net (reduced one).
        k_initial : int, optional
            Order for the initial net (used by PDR).
        places_reduced : list of str, optional
            Identifiers of the reduced places.
        additional_vars : list of str, optional
            Identfifiers of additional variables.
            
        Returns
        -------
        str
            SMT-LIB format.
        """
        if places_reduced is None:
            places_reduced = []

        if additional_vars is None:
            additional_vars = []

        return "(assert ({}".format(self.operator) \
               + self.member_smtlib_with_order(self.left, k, k_initial, places_reduced, additional_vars) \
               + self.member_smtlib_with_order(self.right, k, k_initial, places_reduced, additional_vars) \
               + "))"

    def member_smtlib_with_order(self, member, k: Optional[int], k_initial: Optional[int] = None, places_reduced: Optional[list[str]] = None, additional_vars: Optional[list[str]] = None) -> str:
        """ Helper to assert a member with order (left or right).

        Parameters
        ----------
        member : list of Variable
            One of the two members (left or right).
        k : int
            Order for the current net (reduced one).
        k_initial : int, optional
            Order for the initial net (used by PDR).
        places_reduced : list of str
            Identifiers of the reduced places.
        additional_vars : list of str
            Identfifiers of additional variables.
            
        Returns
        -------
        str
            SMTLIB format.
        """
        if places_reduced is None:
            places_reduced = []

        if additional_vars is None:
            additional_vars = []

        smt_input = ""
        for var in member:
            if var.id in places_reduced:
                smt_input += var.smtlib(k)
            elif k_initial is not None and var.id in additional_vars:
                smt_input += var.smtlib(k_initial)
            else:
                smt_input += var.smtlib()

        if len(member) > 1:
            smt_input = " (+{})".format(smt_input)

        return smt_input

    def parse_equation(self, content: str, system: System) -> None:
        """ Equation parser.

        Parameters
        ----------
        content : str
            Content to parse (.net format).
        system : System
            Current system of reduction equations. 
        """
        elements = re.split(r'\s+', content.partition(' |- ')[2])

        current, inversed = self.left, self.right
        minus = False

        for element in elements:

            if element in ['=', '<=', '>=', '<', '>']:
                self.operator = element
                current, inversed = inversed, current
                minus = False
                continue

            if element == '+':
                minus = False
                continue

            if element == '-':
                minus = True
                continue

            multiplier = None

            # `convert` specific case
            if '-1.' in element:
                element = element.replace('-1.', '')
                minus ^= True
                if minus:
                    current.append(Variable('0', multiplier))

            elif element.rfind('.') > element.rfind('}'):
                index = element.rfind('.')
                element, multiplier = element[:index], element[index+1:]

            variable = element.replace('{', '').replace('}', '')
            self.check_variable(variable, system)

            if not minus:
                current.append(Variable(variable, multiplier))
            else:
                inversed.append(Variable(variable, multiplier))

    def check_variable(self, element: str, system: System) -> None:
        """ Check if a given element is an additional variable and a place from the reduced net.

        Parameters
        ----------
        element : str
            Variable of integer constant.
        system : System
            Current system of reduction equations.
        """
        if not element.isnumeric():
            if element not in system.places_initial and element not in system.additional_vars:
                system.additional_vars.append(element)
            if element in system.places_reduced:
                self.contain_reduced = True


class Variable:
    """ Variable.

    Note
    ----
    May be constant value. 

    Attributes
    ----------
    id : str
        An identifier.
    multiplier : str, optional
        A multiplier (if there is one).
    """

    def __init__(self, id: str, multiplier: Optional[str] = None) -> None:
        """ Initializer.

        Parameters
        ----------
        id : str
            An identifier.
        multiplier : int, optional
            A multiplier.
        """
        self.id: str = id
        self.multiplier: Optional[str] = multiplier

    def __str__(self) -> str:
        """ Variable to textual format.

        Returns
        -------
        str
            Debugging format.
        """
        text = ""

        if self.multiplier is not None:
            text += "{}.".format(self.multiplier)

        return text + self.id

    def smtlib(self, k: Optional[int] = None) -> str:
        """ Assert the Variable and its multiplier if needed.

        Parameters
        ----------
        k : int, optional
            Order.

        Returns
        -------
        str
            SMT-LIB format.
        """
        smtlib_input = self.id

        if k is not None:
            smtlib_input += "@{}".format(k)

        if self.multiplier is not None:
            smtlib_input = "(* {} {})".format(self.multiplier, smtlib_input)

        return " {}".format(smtlib_input)

    def minizinc(self) -> str:
        """ Assert the Variable and its multiplier if needed.

        Returns
        -------
        str
            MiniZinc format.
        """
        minizinc_input = self.id

        if self.multiplier:
            minizinc_input = "({} * {})".format(self.multiplier,
                                                minizinc_input)

        return minizinc_input

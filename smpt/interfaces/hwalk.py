
"""
Hwalk Interface

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
__version__ = "5.0"

from os import environ
from subprocess import check_output


def hwalk(path_net, path_xml, select_queries = None, fireability = False, timeout = None) -> set[str]:
    """ Run hwalk.
    """
    environ["GOMEMLIMIT"] = "14GiB"

    answered: set[str] = set()

    process = ['hwalk', '-n', path_net, '--xml', path_xml, '-c', '500']

    if fireability:
        process.append('--fireability')
    else:
        process.append('--reachability')

    if select_queries is not None:
        process.append('--select-queries')
        process.append(','.join(map(str, select_queries)))

    hwalk = check_output(process, timeout=timeout).decode('utf-8')

    for line in hwalk.splitlines():

        if 'FORMULA' in line:
            print('\n{} TECHNIQUES COLORED_WALK'.format(line))
            answered.add(line.split(' ')[1])

    return answered

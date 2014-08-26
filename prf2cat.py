#!/usr/bin/env python2
#
# Copyright (c) 2006,2007 Matt Gerassimoff
#
# This file is part of g2ools.
#
# g2ools is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# g2ools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

import sys
from nord.g2.file import Prf2File
from nord.g2.pprint import printpatch

def printf(fmt, *a):
  return sys.stdout.write(fmt % a)

prog = sys.argv.pop(0)
while len(sys.argv):
  filename = sys.argv.pop(0)
  printf('"%s"\n', filename)
  prf2 = Prf2File(filename)
  perf = prf2.performance
  for i in range(4):
    printf('Patch %d: "%s"\n', i+1, perf.description.patches[i].name)
    printpatch(perf.patches[i])


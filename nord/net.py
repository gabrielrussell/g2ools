#
# net.py - maintain netlist from cable connections
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

class Net:
  def __init__(self, output, inputs):
    self.output = output
    self.inputs = inputs

# addnet - update the netlist adding source and dest
def addnet(netlist, source, dest):
  found = 0
  for net in netlist:
    if source == net.output or source in net.inputs or dest in net.inputs:
      found = 1
      if not dest in net.inputs: # just in case two connections are made
        net.inputs.append(dest)
      if source.direction:
        if net.output and not source is net.output:
          raise \
            'Two outputs connected to net: source=%s:%s net.source=%s:%s' % (
            source.module.name, source.type.name,
            net.output.module.name, net.output.type.name)
        net.output = source
      elif not source in net.inputs: # just in case two connections are made
        net.inputs.append(source)

  # add new net if one not found
  if found == 0:
    if source.direction:
      net = Net(source,[dest])
    else:
      net = Net(None,[dest,source])
    netlist.append(net)

  # update source and dest nets list
  if not source.net:
    source.net = net

  if not dest.net:
    dest.net = net

# delnode - update the netlist removing the node srcdest
def delnode(netlist, srcdest):
  pass
  # find net with both source and dest on it
  # remove dest from net

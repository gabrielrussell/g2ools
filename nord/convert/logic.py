#
# logic.py - Logic tab conversion objects
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
from nord.g2.modules import fromname as g2name
from convert import *

class ConvPosEdgeDly(Convert):
  maing2module = 'Delay'
  parammap = ['Time']
  inputmap = ['In']
  outputmap = ['Out']
  delaymode = 0

  def domodule(self):
    nmm,g2m = self.nmmodule, self.g2module
    nmmp,g2mp = nmm.params, g2m.params

    g2m.modes.DelayMode.value = self.delaymode

class ConvNegEdgeDly(ConvPosEdgeDly):
  delaymode = 1

class ConvPulse(Convert):
  maing2module = 'Pulse'
  parammap = ['Time']
  inputmap = ['In']
  outputmap = ['Out']

class ConvLogicDelay(ConvPosEdgeDly):
  delaymode = 2

class ConvLogicInv(Convert):
  maing2module = 'Invert'
  inputmap = ['In2']
  outputmap = ['Out2']

class ConvLogicProc(Convert):
  maing2module = 'Gate'
  inputmap = ['In2_1','In2_2']
  outputmap = ['Out2']

  def domodule(self):
    nmm,g2m = self.nmmodule, self.g2module
    nmmp,g2mp = nmm.params, g2m.params

    g2m.modes.GateMode1.value = [0,2,4][getv(nmmp.Mode)]

class ConvCompareLev(Convert):
  maing2module = 'CompLev'
  parammap = [['C','Level']]
  inputmap = ['In']
  outputmap = ['Out']

class ConvCompareAB(Convert):
  maing2module = 'CompSig'
  inputmap = ['A','B']
  outputmap = ['Out']

class ConvClkDiv(Convert):
  maing2module = 'ClkDiv'
  parammap = ['Divider']
  inputmap = ['Clk','Rst']
  outputmap = ['Out',None,None]

  def domodule(self):
    nmm,g2m = self.nmmodule, self.g2module
    nmmp,g2mp = nmm.params, g2m.params

    g2m.modes.DivMode.value = 1

class ConvClkDivFix(Convert):
  maing2module = 'ClkDiv'
  inputmap = ['Rst','Clk']
  outputmap = ['Out',None,None]

  def domodule(self):
    nmm,g2m = self.nmmodule,self.g2module
    nmmp,g2mp = nmm.params, g2m.params

    setv(g2mp.Divider,15)
    g2m.modes.DivMode.value = 1

    rst,midiclk = g2m.inputs.Rst, g2m.inputs.Clk
    vert = self.height
    for div in [11,7]:
      clk = self.g2area.addmodule(g2name['ClkDiv'],horiz=g2m.horiz,vert=vert)
      self.g2modules.append(clk)
      vert += clk.type.height
      clk.name = g2m.name
      clk.modes.DivMode.value = 1
      setv(clk.params.Divider,div)
      self.g2area.connect(rst,clk.inputs.Rst,g2cablecolors.yellow)
      self.g2area.connect(midiclk,clk.inputs.Clk,g2cablecolors.yellow)
      rst,midiclk = clk.inputs.Rst,clk.inputs.Clk
    self.height = vert
    self.outputs[1:] = [ mod.outputs.Out for mod in self.g2modules ]


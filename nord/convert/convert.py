#
# convert.py - main convert object
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
from nord.utils import *
from nord.g2.modules import fromname as g2name
from nord.g2.colors import g2cablecolors
from nord.nm1.colors import nm1conncolors
from nord.units import *
from nord.utils import toascii
from table import *

# updatevals - parameters set from constructor, this changes the times
#              based on the convertion tables in ./units.py.
def updatevals(g2mp,params,nm1tab,g2tab):
  for param in params:
    midival = getv(getattr(g2mp,param))
    newmidival = nm2g2val(midival,nm1tab,g2tab)
    setv(getattr(g2mp,param),newmidival)

class Convert:
  def __init__(self, nmarea, g2area, nmmodule, config):
    self.nmarea = nmarea
    self.g2area = g2area
    nmm = self.nmmodule = nmmodule
    self.config = config
    # use for cabling
    for output in nmmodule.outputs:
      output.conv = self 
    for input in nmmodule.inputs:
      input.conv = self 
    self.nmmodule.conv = self # to get back here when needed (cables)
    self.g2modules = []
    self.params = []
    self.outputs = []
    self.inputs = []

    g2m = self.g2module = g2area.addmodule(self.maing2module)
    g2m.name = toascii(nmm.name)
    self.horiz = g2m.horiz = nmm.horiz
    self.height = g2m.type.height

    if hasattr(self,'parammap'):
      for param in self.parammap:
        if type(param) == type(''):
          setv(getattr(g2m.params,param),getv(getattr(nmm.params,param)))
          self.params.append(getattr(g2m.params,param))
        elif type(param) == type([]):
          setv(getattr(g2m.params,param[0]),getv(getattr(nmm.params,param[1])))
          self.params.append(getattr(g2m.params,param[0]))
        else:
          self.params.append(param) # None: placeholder for other parameters

    if hasattr(self,'inputmap'):
      for input in self.inputmap:
        if input:
          input = getattr(g2m.inputs,input)
        self.inputs.append(input)
          
    if hasattr(self,'outputmap'):
      for output in self.outputmap:
        if output:
          output = getattr(g2m.outputs,output)
        self.outputs.append(output)

  def addmodule(self, shortnm, **kw):
    mod = self.g2area.addmodule(shortnm, **kw)
    mod.horiz = self.g2module.horiz
    mod.vert = self.height
    self.height += mod.type.height
    self.g2modules.append(mod)
    return mod
  
  def connect(self, source, dest):
    self.g2area.connect(source,dest,g2cablecolors.blue) # change color later

  # domodule - process module, setup paramaters, inputs, outputs
  def domodule(self):
    pass

  # precables - process modules after after all domodules() are done
  #             but before cabling starts
  def precables(self):
    pass

  # finailize - after all cables, colors, repositioning, uprate,
  #             knobs, morphs, midiccs, and current notes.
  def finalize(self):
    pass

  def domorphrange(self,paramindex,morphrange):
    return morphrange

  # reposition module based on nm1's separation from module above
  def reposition(self, convabove):
    nmm,g2m = self.nmmodule,self.g2module
    if not convabove:
      g2m.vert += nmm.vert
      for g2mod in self.g2modules:
        g2mod.vert += nmm.vert
      return

    nma,g2a = convabove.nmmodule,convabove.g2module
    sep = nmm.vert - nma.vert - nma.type.height
    vert = g2a.vert + convabove.height + sep
    g2m.vert += vert
    for g2mod in self.g2modules:
      g2mod.vert += vert

  # return True of no modules in column from rowstart to rowend
  def emptyspace(self, column, rowstart, rowend):
    pass
    
  # readjust horiz>=column for all modules in both g2area, nmarea
  def insertcolumn(self, column):
    for nmmod in nmarea.modules:
      if nmmod.horiz >= column:
        nmmod.horiz += 1
    for g2mod in g2area.modules:
      if g2mod.horiz >= column:
        g2mod.horiz += 1

def handlekbt(conv,input,kbt100,addalways=False):
  nmm,g2m = conv.nmmodule,conv.g2module
  nmmp,g2mp = nmm.params, g2m.params

  kbt = getv(nmmp.Kbt)
  if addalways:
    pass
  elif kbt == 0:
    setv(conv.kbt,kbt)
    return None
  elif kbt == 64:
    setv(conv.kbt,kbt100)
    return None

  if not g2m.area.keyboard:
    g2m.area.keyboard = conv.addmodule('Keyboard')
  keyboard = g2m.area.keyboard

  setv(conv.kbt,0)
  mix21b = conv.addmodule('Mix2-1B',name='Kbt')
  conv.connect(keyboard.outputs.Note,mix21b.inputs.In1)
  conv.connect(mix21b.inputs.In1,mix21b.inputs.In2)
  conv.connect(mix21b.outputs.Out,input)
  setv(mix21b.params.ExpLin,1) # Lin
  setv(mix21b.params.Lev1,kbttable[kbt][0])
  setv(mix21b.params.Lev2,kbttable[kbt][1])
  return input
  
def handleoscmasterslv(conv,mst,left,bp,right,lev1,lev2,sub48=False):
  nmm, g2m = conv.nmmodule, conv.g2module

  conv.nonslaves = []
  conv.slaves = []
  slv = nmm.outputs.Slv
  if mst.type.shortnm != 'OscMaster' or len(slv.cables) == 0:
    return None

  out = mst.outputs.Out
  conv.slvoutput = out

  for input in slv.net.inputs:
    if input.rate != nm1conncolors.slave:
      conv.nonslaves.append(input)
    else:
      conv.slaves.append(input)

  if len(conv.nonslaves) == 0:
    return mst.outputs.Out

  if sub48:
    sub48 = conv.addmodule('LevAdd',name='-48')
    setv(sub48.params.Level,16)
    conv.connect(out,sub48.inputs.In)
    out = sub48.outputs.Out
    
  # Grey to Blue handling
  levscaler = conv.addmodule('LevScaler',name='GreyIn')
  setv(levscaler.params.Kbt,0)
  setv(levscaler.params.L,16)
  setv(levscaler.params.BP,127)
  setv(levscaler.params.R,112)
  levscaler2 = conv.addmodule('LevScaler',name='GreyIn')
  setv(levscaler2.params.Kbt,0)
  setv(levscaler2.params.L,left)
  setv(levscaler2.params.BP,bp)
  setv(levscaler2.params.R,right)
  mix21b = conv.addmodule('Mix2-1B')
  setv(mix21b.params.Lev1,lev1)
  setv(mix21b.params.Lev2,lev2)
  greyout = conv.addmodule('LevAmp',name='GreyOut')
  setv(greyout.params.Gain,127)
  conv.connect(out,levscaler.inputs.Note)
  conv.connect(levscaler.inputs.Note,levscaler2.inputs.Note)
  conv.connect(levscaler.outputs.Level,mix21b.inputs.In1)
  conv.connect(levscaler.outputs.Level,levscaler2.inputs.In)
  conv.connect(levscaler2.outputs.Out,mix21b.inputs.In2)
  conv.connect(mix21b.outputs.Out,greyout.inputs.In)

  return greyout.outputs.Out

def doslvcables(conv):
  if not hasattr(conv,'slvoutput'):
    return
  for input in conv.slaves:
    conv.nmmodule.area.removeconnector(input)
    conv.connect(conv.slvoutput,input.module.conv.inputs[input.index])


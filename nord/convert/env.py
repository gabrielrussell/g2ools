#
# env.py - Env tab conversion objects
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
from nord import printf
from nord.utils import setv, getv
from nord.units import nm1adsrtime, g2adsrtime, adsrtime_map
from nord.convert import Convert
from nord.convert.convert import updatevals

def handleretrig(conv):
  gatein, retrig = conv.g2module.inputs.Gate, None
  if len(conv.nmmodule.inputs.Retrig.cables):
    flipflop = conv.add_module('FlipFlop')
    gate = conv.add_module('Gate')
    gate.modes.GateMode2.value = 1
    conv.connect(flipflop.outputs.Q, flipflop.inputs.Rst)
    conv.connect(flipflop.outputs.NotQ, gate.inputs.In1_1)
    conv.connect(gate.outputs.Out1, conv.g2module.inputs.Gate)
    conv.connect(gate.inputs.In2_1, gate.inputs.In2_2)
    conv.connect(gate.outputs.Out2, flipflop.inputs.In)
    gatein = gate.inputs.In1_2
    retrig = flipflop.inputs.Clk
  return gatein, retrig

def handlegate(conv, name='Gate'):
  gate = getattr(conv.nmmodule.inputs, name)
  # if gate source Keyboard, disconnect and set KB
  if not gate or not gate.net or not gate.net.output:
    return
  if gate.net.output.module.type.shortnm == 'Keyboard':
    conv.nmmodule.area.removeconnector(gate)
    setv(conv.g2module.params.KB, 1)

class ConvADSR_Env(Convert):
  maing2module = 'EnvADSR'
  parammap = [['Shape', 'AttackShape'],
      'Attack', 'Decay', 'Sustain', 'Release', None ]
  inputmap = ['In', 'Gate', '', 'AM']
  outputmap = ['Env', 'Out']
              
  def domodule(self):
    nmm, g2m = self.nmmodule, self.g2module
    nmmp, g2mp = nmm.params, g2m.params
    handlegate(self)

    # handle special parameters
    updatevals(g2mp, ['Attack', 'Decay', 'Release'], adsrtime_map)
    setv(g2mp.OutputType, [0, 3][getv(nmmp.Invert)])
    self.inputs[1:3] = handleretrig(self)

class ConvAD_Env(Convert):
  maing2module = 'EnvADR'
  parammap = ['Attack', ['Release', 'Decay'], ['TG', 'Gate']]
  inputmap = ['Gate', 'In', 'AM']
  outputmap = ['Env', 'Out']

  def __init__(self, nmarea, g2area, nmmodule, options):
    if options.adsrforad:
      self.maing2module = 'EnvADSR'
      self.parammap[-1][0] = 'NR'
    super(ConvAD_Env, self).__init__(nmarea, g2area, nmmodule, options)

  def domodule(self):
    nmm, g2m = self.nmmodule, self.g2module
    nmmp, g2mp = nmm.params, g2m.params
    handlegate(self, 'Trigger')

    # handle special parameters
    updatevals(g2mp, ['Attack', 'Release'], adsrtime_map)
    if self.options.adsrforad:
      printf('%s\n', g2m.type.shortnm)
      setv(g2mp.Sustain, 0)
      setv(g2mp.Decay, getv(g2mp.Release))

class ConvMod_Env(Convert):
  maing2module = 'ModADSR'
  parammap = ['Attack', 'Decay', 'Sustain', 'Release',
              'AttackMod', 'DecayMod', 'SustainMod', 'ReleaseMod', None]
  inputmap = ['Gate', '', 'AttackMod', 'DecayMod', 'SustainMod', 'ReleaseMod',
              'In', 'AM']
  outputmap = ['Env', 'Out']

  def domodule(self):
    nmm, g2m = self.nmmodule, self.g2module
    nmmp, g2mp = nmm.params, g2m.params
    handlegate(self)

    # handle special parameters
    updatevals(g2mp, ['Attack', 'Decay', 'Release'], adsrtime_map)
    if len(nmm.inputs.AttackMod.cables):
      levconv = self.add_module('LevConv', name='Attack')
      setv(levconv.params.InputType, 0)  # Bip
      setv(levconv.params.OutputType, 5) # BipInv
      self.connect(levconv.outputs.Out, g2m.inputs.AttackMod)
      self.inputs[2] = levconv.inputs.In
    if len(nmm.inputs.DecayMod.cables):
      levconv = self.add_module('LevConv', name='Decay')
      setv(levconv.params.InputType, 0)  # Bip
      setv(levconv.params.OutputType, 5) # BipInv
      self.connect(levconv.outputs.Out, g2m.inputs.DecayMod)
      self.inputs[3] = levconv.inputs.In
    if len(nmm.inputs.ReleaseMod.cables):
      levconv = self.add_module('LevConv', name='Release')
      setv(levconv.params.InputType, 0)  # Bip
      setv(levconv.params.OutputType, 5) # BipInv
      self.connect(levconv.outputs.Out, g2m.inputs.ReleaseMod)
      self.inputs[5] = levconv.inputs.In
    setv(g2mp.OutputType, [0, 3][getv(nmmp.Invert)])
    self.inputs[:2] = handleretrig(self)

class ConvAHD_Env(Convert):
  maing2module = 'ModAHD'
  parammap = ['Attack', 'Hold', 'Decay', 'AttackMod', 'HoldMod', 'DecayMod']
  inputmap = ['Trig', 'AttackMod', 'HoldMod', 'DecayMod', 'In', 'AM']
  outputmap = ['Env', 'Out']

  def domodule(self):
    nmm, g2m = self.nmmodule, self.g2module
    nmmp, g2mp = nmm.params, g2m.params
    handlegate(self, 'Trig')

    # handle special parameters
    updatevals(g2mp, ['Attack', 'Hold', 'Decay'], adsrtime_map)
    if len(nmm.inputs.AttackMod.cables):
      levconv = self.add_module('LevConv', name='Attack')
      setv(levconv.params.InputType, 0)  # Bip
      setv(levconv.params.OutputType, 5) # BipInv
      self.connect(levconv.outputs.Out, g2m.inputs.AttackMod)
      self.inputs[1] = levconv.inputs.In
    if len(nmm.inputs.DecayMod.cables):
      levconv = self.add_module('LevConv', name='Decay')
      setv(levconv.params.InputType, 0)  # Bip
      setv(levconv.params.OutputType, 5) # BipInv
      self.connect(levconv.outputs.Out, g2m.inputs.DecayMod)
      self.inputs[3] = levconv.inputs.In

class ConvMulti_Env(Convert):
  maing2module = 'EnvMulti'
  parammap = ['Level1', 'Level2', 'Level3', 'Level4',
              'Time1', 'Time2', 'Time3', 'Time4', None,
              ['SustainMode', 'Sustain'], ['Shape', 'Curve']]
  inputmap = ['Gate', 'In', 'AM']
  outputmap = ['Env', 'Out']

  def closesttime(self, time):
    timeval = 0
    timemin = abs(g2adsrtime[0]-time)
    for i, adsrtime in enumerate(g2adsrtime):
      if abs(adsrtime-time) < timemin:
        timemin = abs(adsrtime-time)
        timeval = i
    return timeval

  def domodule(self):
    nmm, g2m = self.nmmodule, self.g2module
    nmmp, g2mp = nmm.params, g2m.params
    handlegate(self)

    setv(g2mp.SustainMode, [3, 0, 1, 2, 3][getv(nmmp.Sustain)])
    setv(g2mp.Shape, [3, 2, 1][getv(nmmp.Curve)])
    # handle special parameters
    updatevals(g2mp, ['Time%d' % i for i in xrange(1, 5)]+['NR'], adsrtime_map)
    # if L4 is sustain, deal with it.
    sustain = getv(nmmp.Sustain)
    if sustain == 4:
      adsr = self.add_module('EnvADSR')
      setv(adsr.params.Shape, [3, 2, 1][getv(nmmp.Curve)])
      setv(adsr.params.KB, getv(g2mp.KB))
      setv(adsr.params.Attack, 0)
      setv(adsr.params.Decay, 0)
      setv(adsr.params.Sustain, 127)
      setv(adsr.params.Release, getv(nmmp.Time5))
      updatevals(adsr.params, ['Release'], adsrtime_map)
      self.connect(g2m.inputs.Gate, adsr.inputs.Gate)
      self.connect(adsr.outputs.Env, g2m.inputs.AM)
      self.inputs[2] = adsr.inputs.AM
      return
    elif sustain == 3 and getv(nmmp.Time5) <= 16: # 16=5.3ms
      pass
    time = nm1adsrtime[getv(nmmp.Time4)]+nm1adsrtime[getv(nmmp.Time5)]
    setv(g2mp.Time4, self.closesttime(time))
    setv(g2mp.Level4, 0)

class ConvEnvFollower(Convert):
  maing2module = 'EnvFollow'
  parammap = ['Attack', 'Release']
  inputmap = ['In']
  outputmap = ['Out']


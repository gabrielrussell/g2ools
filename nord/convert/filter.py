#
# filter.py - Filter tab conversion objects
#
from nord.g2.modules import fromname as g2name
from convert import *

class ConvFilterA(Convert):
  maing2module = 'FltLP'
  parammap = ['Freq']
  inputmap = ['In']
  outputmap = ['Out']

class ConvFilterB(Convert):
  maing2module = 'FltHP'
  parammap = ['Freq']
  inputmap = ['In']
  outputmap = ['Out']

class ConvFilterC(Convert):
  maing2module = 'FltMulti'
  parammap = ['Freq',['Res','Resonance'],['GC','GainControl']]
  inputmap = ['In']
  outputmap = ['LP','BP','HP']

class ConvFilterD(Convert):
  maing2module = 'FltMulti'
  parammap = ['Freq',['PitchMod','FreqMod']]
  inputmap = ['PitchVar','In']
  outputmap = ['LP','BP','HP']

  def domodule(self):
    nmm,g2m = self.nmmodule, self.g2module
    nmmp,g2mp = nmm.params, g2m.params

# copied from convert.py for osc.py (maybe it can be unified?)
def fltdualpitchmod(nmm,g2m,conv):
  p1 = p2 = None
  if len(nmm.inputs.FreqMod1.cables) and len(nmm.inputs.FreqMod2.cables):
    g2area = conv.g2area
    g2mm = g2area.addmodule(g2name['Mix2-1B'])
    g2mm.name = 'FreqMod'
    conv.g2modules.append(g2mm)
    g2mm.horiz = g2m.horiz
    g2mm.vert = g2m.type.height
    conv.height = g2mm.vert + g2mm.type.height
    color=g2cablecolors.red
    g2area.connect(g2mm.outputs.Out,g2m.inputs.PitchVar,color)
    p1,p2 = g2mm.inputs.In1,g2mm.inputs.In2
    setv(g2m.params.PitchMod,127)
    cpv(g2mm.params.Lev1,nmm.params.FreqMod1)
    cpv(g2mm.params.Lev2,nmm.params.FreqMod2)
  elif len(nmm.inputs.FreqMod1.cables):
    p1 = g2m.inputs.PitchVar
    cpv(g2m.params.PitchMod,nmm.params.FreqMod1)
  elif len(nmm.inputs.FreqMod2.cables):
    p2 = g2m.inputs.PitchVar
    cpv(g2m.params.PitchMod,nmm.params.FreqMod2)

  return p1, p2

class ConvFilterE(Convert):
  maing2module = 'FltNord'
  parammap = ['FilterType','Slope','Freq',
              ['Res','Resonance'],['PitchMod','FreqMod1'],
              ['GC','GainControl'],['ResMod','ResonanceMod']]
  inputmap = ['PitchVar','Res','In',None]
  outputmap = ['Out']

  def domodule(self):
    nmm,g2m = self.nmmodule, self.g2module
    nmmp,g2mp = nmm.params, g2m.params

    # deal with KBT later

    # handle special inputs
    p1,p2 = fltdualpitchmod(nmm,g2m,self)
    self.inputs[0] = p1
    self.inputs[3] = p2

class ConvFilterF(Convert):
  maing2module = 'FltClassic'
  parammap = ['Freq','Slope',['Res','Resonance'],
              ['PitchMod','FreqMod1']]
  inputmap = ['PitchVar',None,'In',None]
  outputmap = ['Out']

  def domodule(self):
    nmm,g2m = self.nmmodule, self.g2module
    nmmp,g2mp = nmm.params, g2m.params

    # deal with KBT later

    # handle special inputs
    p1,p2 = fltdualpitchmod(nmm,g2m,self)
    self.inputs[0:2] = p1,p2

class ConvVocalFilter(Convert):
  maing2module = 'FltVoice'
  parammap = ['Vowel1','Vowel2','Vowel3','Level','Vowel', 'VowelMod',
              'Freq','FreqMod', ['Res','Resonance']]
  inputmap = ['In','VowelMod','FreqMod']
  outputmap = ['Out']

class ConvVocoder(Convert):
  maing2module = 'Vocoder'
  parammap = ['Band%d' % i for i in range(1,17)]+['Emphasis','Monitor']
  inputmap = ['Ctrl','In']
  outputmap = ['Out']

class ConvEqMid(Convert):
  maing2module = 'EqPeak'
  parammap = ['Freq','Gain','BandWidth','Level']
  inputmap = ['In']
  outputmap = ['Out']

  def domodule(self):
    nmm,g2m = self.nmmodule, self.g2module
    nmmp,g2mp = nmm.params, g2m.params
    
    setv(g2mp.Active,1-getv(nmmp.Mute))


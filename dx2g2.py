#!/usr/bin/env python2

import logging
import os, sys, traceback
from optparse import OptionParser, make_option
from array import array
sys.path.append('.')
from nord import units
from nord.g2.file import Pch2File, crc
from nord.g2.colors import g2modulecolors
from nord.convert.version import version as g2oolsversion
from nord.convert.dx7 import dxtable

class DX7Converter: 
  def __init__(self):
    self.pch2 = Pch2File('dx7.pch2')
    self.dxrouter = self.module_by_name('DXRouter1')
    self.operators = [self.module_by_name('Operator%d'%i) for i in range(1, 7)]
    self.lfo = self.module_by_name('LFO')
    self.lfosync = self.module_by_name('LFO Sync')
    self.lfodelay = self.module_by_name('LFO Delay')
    self.lfopitchmod = self.module_by_name('LFO PM')
    self.lfoselect = self.module_by_name('LFO Select')
    self.lfoam = self.module_by_name('LFO AM')
    self.pitcheg = self.module_by_name('PitchEG')
    self.pmodsens = self.module_by_name('PmodSens')
    self.pmodadj = self.module_by_name('PmodAdj')
    self.transpose = self.module_by_name('Transpose')

  def module_by_name(self, name):
    for module in self.pch2.patch.voice.modules:
      if module.name == name:
        return module
    return None

class Operator:
  pass

class LFO:
  pass

class PitchEG:
  pass

class DX7Patch:
  def __init__(self):
    self.operators = [ Operator() for i in range(6) ]

def parsedx7(data):
  x = array('B', data)
  acrc = crc(data[:-10])
  patch = DX7Patch()
  for i in range(6):
    op = patch.operators[5-i]
    op.R1, op.R2, op.R3, op.R4 = x[:4]; x = x[4:]
    op.L1, op.L2, op.L3, op.L4 = x[:4]; x = x[4:]
    op.BrPoint, op.LDepth, op.RDepth = x[:3]; x = x[3:]
    c = x.pop(0); op.RDepthMode, op.LDepthMode = (c>>2), c&3
    c = x.pop(0); op.FreqDetune, op.RateScale = c>>4, c&7
    c = x.pop(0); op.Vel, op.AMod = c>>2, c&3
    op.OutLevel = x.pop(0)
    c = x.pop(0); op.FreqCoarse, op.RatioFixed = c>>1, c&1
    op.FreqFine = x.pop(0)
  pitcheg = patch.pitcheg = PitchEG()
  pitcheg.R1, pitcheg.R2, pitcheg.R3, pitcheg.R4 = x[:4]; x = x[4:]
  pitcheg.L1, pitcheg.L2, pitcheg.L3, pitcheg.L4 = x[:4]; x = x[4:]
  patch.Algorithm = x.pop(0)
  c = x.pop(0); patch.OscKeySync, patch.Feedback = c>>3, c&7
  lfo = patch.lfo = LFO()
  lfo.Rate, lfo.Delay, lfo.PitchMod, lfo.AmMod = x[:4]; x = x[4:]
  c = x.pop(0); lfo.PitchModSens, lfo.Waveform, lfo.Sync = c>>4, (c>>1)&0x7, c&1
  patch.Transpose = x.pop(0)
  if acrc in dxtable.factorycrcs:
    # show factory names in different color
    patch.Color = g2modulecolors.red3
  else:
    patch.Color = g2modulecolors.grey
  patch.Name = x.tostring()
  return patch
  
def convert(filename, options):
  f = open(filename, 'rb')
  data = f.read()
  voice1 = '\xf0\x43\x00\x00\x01\x1b'
  voice32 = '\xf0\x43\x00\x09\x20\x00'
  patches = []
  while data:
    syx = data.find('\xf0')
    if syx < 0:
      break
    esx = data.find('\xf7', syx)
    if data[syx:syx+len(voice1)] == voice1:
      logging.info('%s 1 voice' % filename)
    elif data[syx:syx+len(voice32)] == voice32:
      logging.info('%s 32 voices' % filename)
      v32data = data[syx+len(voice32):esx]
      for i in range(len(v32data)/128):
        patch = parsedx7(v32data[i*128:i*128+128])
        patch.number = i+1
        patches.append(patch)
    data = data[esx+1:]
  outname = filename[:-4]
  groups = [ patches[i:i+8] for i in range(0, len(patches), 8)]
  bank = 1
  opparamnms = [
    'R1', 'L1', 'R2', 'L2', 'R3', 'L3', 'R4', 'L4',
    'BrPoint', 'LDepth', 'RDepth', 'LDepthMode', 'RDepthMode',
    'FreqDetune', 'RateScale', 'Vel', 'AMod',
    'OutLevel', 'FreqCoarse', 'RatioFixed', 'FreqFine',
  ]
  def scale100to127(dxval):
    return int(0.5+127*dxval/99.)

  def g2time(dxrate, l1, l2):
    dl = abs(dxtable.pitcheglevs[l2]-dxtable.pitcheglevs[l1])/3.75
    dxtime = dxtable.pitchegrates[99-dxrate] * dl
    mintime = abs(units.g2adsrtime[0]-dxtime)
    minval = 0
    for i in range(1, len(units.g2adsrtime)):
      if abs(units.g2adsrtime[i]-dxtime) < mintime:
        mintime = abs(units.g2adsrtime[i]-dxtime)
        minval = i
    return minval

  def g2pitch(dxlevel):
    return int(dxlevel*1.28)

  for group in groups:
    dxconv = DX7Converter()
    for i in range(len(group)):
      dxpatch = group[i]
      nm = '%2d. %s' % (i+1, dxpatch.Name)
      logging.info(nm)
      dxconv.pch2.patch.voice.add_module('Name', name=nm,
          horiz=0, vert=i, color=dxpatch.Color)
      # set DXRouter stuff
      dxconv.dxrouter.params.Algorithm.variations[i] = dxpatch.Algorithm
      dxconv.dxrouter.params.Feedback.variations[i] = dxpatch.Feedback
      # set all Operator's parameters
      for op in range(len(dxpatch.operators)):
        dxop = dxpatch.operators[op]
        g2op = dxconv.operators[op]
        for paramnm in opparamnms:
          g2param = getattr(g2op.params, paramnm)
          dxparam = getattr(dxop, paramnm)
          #printf(' %s %s\n', paramnm, dxparam, )
          g2param.variations[i] = dxparam
        g2op.params.AMod.variations[i] = dxtable.amodsens[dxop.AMod][1]
        g2op.params.Kbt.variations[i] = 1 - dxop.RatioFixed

      # set LFO parameters
      lfop = dxconv.lfo.params
      # 0:TR, 1:SD, 2:SU, 3:SQ, 4:SI, 5:SH
      wave = dxpatch.lfo.Waveform
      lfop.Waveform.variations[i] = [1, 2, 2, 3, 0, 4][wave]
      if wave == 0: # TR
        lfop.Phase.variations[i] = 98 # 276
        lfop.OutputType = 1 # PosInv
        dxconv.lfoselect.params.Sel.variations[i] = 0
      elif wave == 1: # SD
        lfop.Phase.variations[i] = 0
        lfop.OutputType = 0 # Pos
        dxconv.lfoselect.params.Sel.variations[i] = 0
      elif wave == 2: # SU
        lfop.Phase.variations[i] = 0
        lfop.OutputType = 1 # PosInv
        dxconv.lfoselect.params.Sel.variations[i] = 0
      elif wave == 3: # SQ
        lfop.Phase.variations[i] = 0
        lfop.OutputType = 1 # PosInv
        dxconv.lfoselect.params.Sel.variations[i] = 0
      elif wave == 4: # SI
        lfop.Phase.variations[i] = 0
        lfop.OutputType = 1 # PosInv
        dxconv.lfoselect.params.Sel.variations[i] = 0
      elif wave == 5: # SH
        lfop.Phase.variations[i] = 0
        lfop.OutputType = 1 # PosInv
        dxconv.lfoselect.params.Sel.variations[i] = 1

      rate = min(dxpatch.lfo.Rate, len(dxtable.lfo)-1)
      lfop.Rate.variations[i] = dxtable.lfo[rate][1]
      lfop.Range.variations[i] = dxtable.lfo[rate][0]
      lfop.RateMod.variations[i] = dxtable.lfo[rate][2]
      dxconv.lfodelay.params.Attack.variations[i] = \
          dxtable.lfo[dxpatch.lfo.Delay][3]
      lfop.PolyMono.variations[i] = dxpatch.lfo.Sync
      dxconv.lfopitchmod.params.Lev1.variations[i] = \
           scale100to127(dxpatch.lfo.PitchMod)
      dxconv.lfoam.params.Lev1.variations[i] = scale100to127(dxpatch.lfo.AmMod)
      dxconv.pmodsens.params.Gain.variations[i] = \
          dxtable.pmodsens[dxpatch.lfo.PitchModSens][1]
      dxconv.pmodadj.params.Lev1.variations[i] = \
          dxtable.pmodsens[dxpatch.lfo.PitchModSens][2]
      dxconv.pmodadj.params.Lev2.variations[i] = \
          dxtable.pmodsens[dxpatch.lfo.PitchModSens][3]
      # set PitchEG parameters
      pitchegp = dxconv.pitcheg.params
      pitcheg = dxpatch.pitcheg
      pitchegp.Time1.variations[i] = g2time(pitcheg.R1, pitcheg.L4, pitcheg.L1)
      pitchegp.Level1.variations[i] = g2pitch(pitcheg.L1)
      pitchegp.Time2.variations[i] = g2time(pitcheg.R2, pitcheg.L1, pitcheg.L2)
      pitchegp.Level2.variations[i] = g2pitch(pitcheg.L2)
      pitchegp.Time3.variations[i] = g2time(pitcheg.R3, pitcheg.L2, pitcheg.L3)
      pitchegp.Level3.variations[i] = g2pitch(pitcheg.L3)
      pitchegp.Time4.variations[i] = g2time(pitcheg.R4, pitcheg.L3, pitcheg.L4)
      pitchegp.Level4.variations[i] = g2pitch(pitcheg.L4)
      # set Transpose
      dxconv.transpose.params.Lev.variations[i] = dxpatch.Transpose + 40
      # sync
      morph = dxconv.pch2.patch.settings.morphs[7]
      if dxpatch.OscKeySync:
        morph.dial.variations[i] = 127
      else:
        morph.dial.variations[i] = 0
    #
    def addnamebars(pch2, lines, horiz, vert):
      for line in lines:
        m = pch2.patch.voice.add_module('Name', name=line)
        m.horiz = horiz
        m.vert = vert
        vert += 1
      return vert

    lines = ['Converted by',
           'g2ools-%s' % g2oolsversion,
           'by',
           'Matt Gerassimoff',
           'model by',
           'Sven Roehrig']
    vert = 0
    for module in dxconv.pch2.patch.voice.modules:
      if module.horiz != 0:
        continue
      v = module.vert + module.type.height
      #printf('%s %d %d %d\n', module.name, module.vert, module.type.height, v)
      if v > vert:
        vert = v
    vert = addnamebars(dxconv.pch2, lines, 0, vert+1)
    vert = addnamebars(dxconv.pch2, ['All rights', 'reserved'], 0, vert+1)


    dxconv.pch2.write(outname+'b%d.pch2' % bank)
    bank += 1

dx2g2_options = [
  make_option('-d', '--debug', action='store_true',
      dest='debug', default=False,
      help='Allow exceptions to terminate application'),
  make_option('-r', '--recursive', action='store_true',
      dest='recursive', default=False,
      help='On dir arguments, convert all .pch files'),
  make_option('-v', '--verbose', action='store',
      dest='verbosity', default='3', choices=map(str, range(5)),
      help='Set converter verbosity level 0-4'),
]

def main(argv):
  from glob import glob
  global dx2g2_options

  parser = OptionParser("usage: %prog [options] arg", option_list=dx2g2_options)
  (options, args) = parser.parse_args(argv)
  args.pop(0)
  verbosity = [
      logging.ERROR,
      logging.WARNING,
      logging.CRITICAL,
      logging.INFO,
      logging.DEBUG,
  ][int(options.verbosity)]

  log = logging.getLogger('')
  log.setLevel(verbosity)

  def doconvert(filename, options):
    # general algorithm for converter:
    if options.debug:
      convert(filename, options) # allow exception thru if debugging
    else:
      try:
        convert(filename, options)
      except KeyboardInterrupt:
        sys.exit(1)
      except Exception:
        logging.error(traceback.format_exc())
        return '%s\n%s' % (filename, traceback.format_exc())
    return ''

  failedpatches = []
  while len(args):
    patchlist = glob(args.pop(0))
    for filename in patchlist:
      if os.path.isdir(filename) and options.recursive:
        for root, dirs, files in os.walk(filename):
          for f in files:
            filename = os.path.join(root, f)
            if filename[-4:].lower() == '.syx':
              logging.critical('"%s"' % filename)
              testname = filename
              if filename[-4:].lower() != '.syx':
                testname = filename+'.syx'
              failed = doconvert(filename, options)
              if failed:
                failedpatches.append(failed)
              logging.info('-' * 20)
      else:
        logging.critical('"%s"' % filename)
        failed = doconvert(filename, options)
        if failed:
          failedpatches.append(failed)
        logging.info('-' * 20)

  if len(failedpatches):
    f = open('failedpatches.txt', 'w')
    s = 'Failed patches: \n %s\n' % '\n '.join(failedpatches)
    f.write(s)
    logging.warning(s)

if __name__ == '__main__':
  logging.basicConfig(format='%(message)s')
  main(sys.argv)


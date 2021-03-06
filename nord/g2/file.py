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

import string, sys
from struct import pack, unpack

import nord.g2.modules
from nord import printf
from nord.module import Module
from nord.file import hexdump, binhexdump
from nord.file import Patch, Performance, Note, Cable, Knob, Ctrl, MorphMap
from nord.g2 import modules
from nord.g2.crc import crc
from nord.g2.bits import setbits, getbits, BitStream

section_debug = 0 # outputs section debug 
title_section = 0 # replace end of section with section title

NVARIATIONS = 9 # 1-8, init
NMORPHS = 8     # 8 morphs
NKNOBS = 120    # 120 knob settings
NMORPHMAPS = 25 # max morphmaps per variation

FX, VOICE, SETTINGS = 0, 1, 2

class G2Error(Exception):
  '''G2Error - exception for throwing an unrecoverable error.'''
  def __init__(self, value):
    Exception.__init__(self)
    self.value = value
  def __str__(self):
    return repr(self.value)

def read_string(bitstream, l, pad=False):
  read_str = bitstream.read_str
  if pad == True:
    return read_str(l).strip('\0')
  else:
    s = bytearray(l)
    for i in xrange(l):
      s[i] = read_str(1)
      if s[i] == 0:
        return str(s[:i])
    return str(s[:l])

def format_string(s, l, pad=False):
  if len(s) < l:
    s = s + '\0'
  if pad == True:
    s = s.ljust(l, '\0')
  return s[:l] # in case the string is longer

def write_string(bitstream, s, l, pad=False):
  bitstream.write_str(format_string(s, l, pad))

def get_patch_area(patch, area):
  return [patch.fx, patch.voice][area]

class Section(object):
  '''Section abstract class that represents a section of .pch2 file.
  all sections objects have parse() and format() methods.
'''
  default = [0] * (2 << 10) # max 64k section size
  def __init__(self, **kw):
    self.__dict__ = kw
    self.data = bytearray(64<<10)

class SectionManager(object):
  def add(self, class_):
    self.__dict__[class_.type] = class_

  def get(self, type, default=None):
    return self.__dict__.get(type, default)

section_manager = SectionManager()

class Description(object):
  '''Description class for patch/performance description.'''
  pass

class PatchDescription(Section):
  '''PatchDescription Section subclass'''
  type = 0x21
  description_attrs = [
    ['reserved', 5], ['voices', 5], ['height', 14], ['unk2', 3],
    ['red', 1], ['blue', 1], ['yellow', 1], ['orange', 1],
    ['green', 1], ['purple', 1], ['white', 1],
    ['monopoly', 2], ['variation', 8], ['category', 8],
  ]
  def parse_description(self, description, bitstream):
    for name, nbits in self.description_attrs:
      setattr(description, name, bitstream.read_bits(nbits))

  def format_description(self, description, bitstream):
    for name, nbits in self.description_attrs:
      bitstream.write_bits(nbits, getattr(description, name))
    bitstream.write_bits(8, 0)

  def parse(self, patch, data):
    description = patch.description = Description()  # G2Patch
    bitstream = BitStream(data, 7*8)
    self.parse_description(patch.description, bitstream)

  def format(self, patch, data):
    bitstream = BitStream(data, 7*8)
    self.format_description(patch.description, bitstream)
    return bitstream.tell_bit()
section_manager.add(PatchDescription)

class ModuleList(Section):
  '''ModuleList Section subclass'''
  type = 0x4a

  # NOTE: module.leds seems to be related to a group of modules. i cannot
  #       see the relationship but I have got a list of modules
  #       that require this to be set.  This will probably be handled
  #       without this property but added to the module types that
  #       set it.
  # make sure leds bit is set for specific modules
  # - some earlier generated .pch2 files where different
  #   these were emperically determined.
  # NOTE2: these should be in nord/g2/modules.py
  ledtypes = [
    3, 4, 17, 38, 42, 48, 50, 57, 59, 60, 68, 69,
    71, 75, 76, 81, 82, 83, 85,
    105, 108, 112, 115, 141, 142, 143, 147, 148, 149, 150,
    156, 157, 170, 171, 178, 188, 189, 198, 199, 208,
  ]
  def fixleds(self, module):
    module.leds = 0
    #if module.type.id in ModuleList.ledtypes:
    #  module.leds = 1
    #else:
    #  module.leds = 0

  module_params = [
    ['index', 8 ], ['horiz', 7], ['vert', 7], ['color', 8],
    ['uprate', 1 ], ['leds', 1], ['reserved', 6],
  ]
  def parse_area(self, area, bitstream):
    read_bits = bitstream.read_bits
    nmodules  = read_bits(8)
    area.modules = [ None ] * nmodules
    for i in xrange(nmodules):
      id = read_bits(8)
      module = Module(modules.fromid(id), area)
      area.modules[i] = module

      for attr, nbits in self.module_params:
        setattr(module, attr, read_bits(nbits))
      nmodes = read_bits(4)
      self.fixleds(module)

      # mode data for module (if there is any)
      for mode in module.modes:
        mode.value = read_bits(6)

      # add missing mode data. some .pch2 versions didn't contain
      #   all the modes in version 23 BUILD 266
      module_type = module.type
      if len(module.modes) < len(module_type.modes):
        for mode in xrange(len(module.modes), len(module_type.modes)):
          module.modes[mode].value = module_type.modes[mode].type.default

  def format_area(self, area, bitstream):
    write_bits = bitstream.write_bits
    write_bits(2, self.area)
    write_bits(8, len(area.modules))

    for module in area.modules:
      write_bits(8, module.type.id)
      module.reserved = 0 # just in case is wasn't set
      for attr, nbits in self.module_params:
        bitstream.write_bits(nbits, getattr(module, attr))
      self.fixleds(module)

      write_bits(4, len(module.modes))
      for mode in module.modes:
        write_bits(6, mode.value)

  def parse(self, patch, data):
    bitstream = BitStream(data)
    self.area = bitstream.read_bits(2)
    area      = get_patch_area(patch, self.area)
    self.parse_area(area, bitstream)

  def format(self, patch, data):
    bitstream = BitStream(data)
    area      = get_patch_area(patch, self.area)
    self.format_area(area, bitstream)
    return bitstream.tell_bit()
section_manager.add(ModuleList)

class CurrentNote(Section):
  '''CurrentNote Section subclass'''
  type = 0x69
  def parse(self, patch, data):
    bitstream = BitStream(data)
    lastnote  = patch.lastnote = Note()  # G2Patch
    values    = bitstream.read_bitsa([7] * 3)
    lastnote.note, lastnote.attack, lastnote.release = values
    nnotes    = bitstream.read_bits(5) + 1
    notes     = patch.notes = [ Note() for i in xrange(nnotes) ]  # G2Patch
    for note in notes:
      note.note, note.attack, note.release = bitstream.read_bitsa([7, 7, 7]) 

  def format(self, patch, data):
    bitstream = BitStream(data)
    if len(patch.notes):
      lastnote = patch.lastnote
      if not lastnote:
        values = [ 64, 0, 0 ]
      else:
        values = [ lastnote.note, lastnote.attack, lastnote.release ]
      bitstream.write_bitsa([7, 7, 7], values)
      bitstream.write_bits(5, len(patch.notes)-1)
      for note in patch.notes:
        bitstream.write_bitsa([7, 7, 7], [note.note, note.attack, note.release])
    else:
      bitstream.write_bits(24, 0x800000)
      bitstream.write_bits(24, 0x200000)
    return bitstream.tell_bit()

def invalid_cable(smodule, sconn, direction, dmodule, dconn):
  '''invalid_cable(area, smodule, sconn, direction, dmodule, dconn) -> bool
 if connection valid return 0, otherwise error.
'''
  if direction == 1:                  # verify from
    if sconn >= len(smodule.outputs): # out -> in
      return 1
  elif sconn >= len(smodule.inputs):  # in -> in
    return 2
  if dconn >= len(dmodule.inputs):    # verify to
    return 3

  return 0 # if we got here, everything's cool.
section_manager.add(CurrentNote)

class CableList(Section):
  '''CableList Section subclass'''
  type = 0x52
  def parse_area(self, area, bitstream):
    _, ncables = bitstream.read_bitsa([6, 16])
    area.cables = [ None ] * ncables
    for i in xrange(ncables):
      cable       = Cable(area)
      cable.color, source, src_conn, direction, dest, dest_conn = \
          bitstream.read_bitsa([3, 8, 6, 1, 8, 6])

      src_module  = area.find_module(source)
      dest_module = area.find_module(dest)

      if invalid_cable(src_module, src_conn, direction, dest_module, dest_conn):
        printf('Invalid cable %d: "%s"(%d,%d) -%d-> "%s"(%d,%d)\n',
            i, src_module.type.shortnm, src_module.index, src_conn, direction,
            dest_module.type.shortnm, dest_module.index, dest_conn)
        continue

      if direction == 1:
        cable.source = src_module.outputs[src_conn]
      else:
        cable.source = src_module.inputs[src_conn]
      cable.dest = dest_module.inputs[dest_conn]

      area.cables[i] = cable
      cable.source.cables.append(cable)
      cable.dest.cables.append(cable)

      area.netlist.add(cable.source, cable.dest)

  def format_area(self, area, bitstream):
    bitstream.write_bitsa([2, 6, 16], [area.index, 0, len(area.cables)])
    for cable in area.cables:
      bitstream.write_bitsa([3, 8, 6, 1, 8, 6],
        [ cable.color, cable.source.module.index, cable.source.index,
          cable.source.direction, cable.dest.module.index, cable.dest.index])

  def parse(self, patch, data):
    bitstream = BitStream(data)
    self.area = bitstream.read_bits(2)
    area = get_patch_area(patch, self.area)
    self.parse_area(area, bitstream)

  def format(self, patch, data):
    bitstream = BitStream(data)
    area = get_patch_area(patch, self.area)
    self.format_area(area, bitstream)
    return bitstream.tell_bit()
section_manager.add(CableList)

class SettingsArea(object):
  def __init__(self):
    self.index  = SETTINGS
    self.name   = 'settings'

class ParameterModule(object):
  def __init__(self, area, index):
    self.area   = area
    self.index  = index

class Parameter(object):
  '''Parameter class for module parameters/settings.'''
  def __init__(self, area, mod_index, index, default=0, name='', module=None):
    self.area       = area
    self.index      = index
    self.variations = [default]*NVARIATIONS
    self.name       = name
    self.module     = ParameterModule(area, mod_index)
    self.knob       = None
    self.mmap       = None
    self.ctrl       = None

class Morph(object):
  '''Morph class for morph settings.'''
  def __init__(self, area, index):
    self.name  = 'morph%d' % (index+1)
    self.maps  = [[] for variation in xrange(NVARIATIONS) ]
    self.index = index
    self.area  = area

    # morph "module" has 2 parameters dial and mode
    self.dial = Parameter(area, 1, index, 0, name='dial')
    self.mode = Parameter(area, 1, index+NMORPHS, 1, name='mode')

class Settings(object):
  '''Settings class for patch settings.'''
  groups = [
    [ 'patchvol', 'activemuted' ],
    [ 'glide', 'glidetime' ],
    [ 'bend', 'semi' ],
    [ 'vibrato', 'cents', 'rate' ],
    [ 'arpeggiator', 'arptime', 'arptype', 'octaves' ],
    [ 'octaveshift', 'sustain' ],
  ]

  def __init__(self):
    self.area = SettingsArea()
    for i, group in enumerate(self.groups, 2):
      for j, name in enumerate(group):
        setattr(self, name, Parameter(self.area, i, j, name=name))
    self.morphs = [ Morph(self.area, morph+1) for morph in xrange(NMORPHS) ]
    self.morphmaps = [ [] for variation in xrange(NVARIATIONS) ]

class Parameters(Section):
  '''Parameters Section subclass'''
  type = 0x4d
  def parse_settings(self, settings, bitstream):
    read_bits = bitstream.read_bits
    read_bitsa = bitstream.read_bitsa

    nsections, nvariations, section, nentries = read_bitsa([8, 8, 8, 7])
    # nentries: 16 parameters per variation: 8 dials, 8 modes 
    for i in xrange(nvariations): # usually 9
      variation = read_bits(8)
      for morph in settings.morphs:
        dial = read_bits(7)
        if variation < NVARIATIONS:
          morph.dial.variations[variation] = dial

      for morph in settings.morphs:
        mode = read_bits(7)
        if variation < NVARIATIONS:
          morph.mode.variations[variation] = mode

    for group in settings.groups:
      section, nentries = read_bitsa([8, 7])
      for i in xrange(nvariations):
        variation = read_bits(8)
        for entry in xrange(nentries):
          value = read_bits(7)
          if variation < NVARIATIONS:
            getattr(settings, group[entry]).variations[variation] = value

  def format_settings(self, settings, bitstream):
    write_bits = bitstream.write_bits
    write_bitsa = bitstream.write_bitsa

    #                                           1 for morph--.  .-- 16/var
    write_bitsa([2, 8, 8, 8, 7], [SETTINGS, 7, NVARIATIONS, 1, 16])

    for variation in xrange(NVARIATIONS): # morph groups
      write_bits(8, variation)
      for morph in settings.morphs:
        write_bits(7, morph.dial.variations[variation])
      for morph in settings.morphs:
        write_bits(7, morph.mode.variations[variation])

    section = 2 # starts at 2 (above: morph is section 1)
    for group in settings.groups:
      nentries = len(group)
      write_bitsa([8, 7], [section, nentries])
      for variation in xrange(NVARIATIONS):
        write_bits(8, variation)
        for entry in xrange(nentries):
          value = getattr(settings, group[entry]).variations[variation]
          write_bits(7, value)
      section += 1

    return bitstream.tell_bit()

  def parse_area(self, area, bitstream):
    read_bits = bitstream.read_bits

    nmodules, nvariations = bitstream.read_bitsa([8, 8])
    for i in xrange(nmodules):
      index, nparams = bitstream.read_bitsa([8, 7])
      module = area.find_module(index)
      params = module.params
      for i in xrange(nvariations):
        variation = read_bits(8)
        for param in xrange(nparams):
          value = read_bits(7)
          if param < len(params) and variation < NVARIATIONS:
            params[param].variations[variation] = value

  def format_area(self, area, bitstream):
    modules = []
    for module in area.modules:
      try:
        if not len(module.params):
          continue
        modules.append(module)
      except:
        pass
    modules.sort(lambda a, b: cmp(a.index, b.index))

    write_bits = bitstream.write_bits

    mlen = len(modules)
    bitstream.write_bitsa([2, 8], [area.index, mlen])
    if mlen == 0:
      write_bits(8, 0)
      return bitstream.tell_bit()

    write_bits(8, NVARIATIONS)
    for module in modules:
      write_bits(8, module.index)

      params = module.params
      write_bits(7, len(params))
      for variation in xrange(NVARIATIONS):
        write_bits(8, variation)
        for param in params:
          write_bits(7, param.variations[variation])

  def parse(self, patch, data):
    bitstream = BitStream(data)
    self.area = bitstream.read_bits(2)
    if self.area == SETTINGS:
      patch.settings = Settings()  # G2Patch
      self.parse_settings(patch.settings, bitstream)
    else:
      area = get_patch_area(patch, self.area)
      self.parse_area(area, bitstream)

  def format(self, patch, data):
    bitstream = BitStream(data)
    if self.area == SETTINGS:
      self.format_settings(patch.settings, bitstream)
    else:
      area = get_patch_area(patch, self.area)
      self.format_area(area, bitstream)
    return bitstream.tell_bit()
section_manager.add(Parameters)

def get_settings_param(patch, index, param):
  if index < 2:
    morph = patch.settings.morphs[param & 7]
    if param < 8:
      return morph.dial
    else:
      return morph.mode
  else:
    group = patch.settings.groups[index - 2]
    return getattr(patch.settings, group[param])

class MorphParameters(Section):
  '''MorphParameters Section subclass'''
  type = 0x65
  def parse(self, patch, data):
    bitstream = BitStream(data)
    read_bits = bitstream.read_bits

    nvariations, nmorphs, _, _ = bitstream.read_bitsa([8, 4, 10, 10])

    # variations seem to be 9 bytes with first nibble variation # from 0 ~ 8
    # number of morph parameters starts at byte 7-bit 0 for 5-bits
    morphs = patch.settings.morphs
    morphmaps = patch.settings.morphmaps

    for i in xrange(nvariations):
      variation = read_bits(4)
      bitstream.seek_bit(4 + (6*8) + 4, 1) # zeros

      nmorphs = read_bits(8)
      for j in xrange(nmorphs):
        morph_map       = MorphMap()
        area, index, param, morph = bitstream.read_bitsa([2, 8, 7, 4])
        morph_map.range = read_bits(8, 1)

        module = get_patch_area(patch, area).find_module(index)
        morph_map.param     = module.params[param]
        morph_map.variation = variation
        morph_map.morph     = morphs[morph-1]
        morph_map.morph.maps[variation].append(morph_map)
        morphmaps[variation].append(morph_map)

      reserved = read_bits(4) # always 0

  def format(self, patch, data):
    bitstream = BitStream(data)
    write_bits = bitstream.write_bits

    bitstream.write_bitsa([8, 4, 10, 10], [ NVARIATIONS, NMORPHS, 0, 0])

    # variations seem to be 9 bytes with first nibble variation # from 0 ~ 8
    # number of morph parameters starts at byte 7-bit 0 for 5-bits
    morphs = patch.settings.morphs

    for variation in xrange(NVARIATIONS):
      write_bits(4, variation)
      bitstream.seek_bit(4 + (6 * 8) + 4, 1)

      # collect all morph_maps of this variation into 1 array
      morph_maps = []
      for morph in morphs:
        morph_maps.extend(morph.maps[variation])
      def mod_param_index_cmp(a, b):
        return cmp(a.param.module.index, b.param.module.index)
      morph_maps.sort(mod_param_index_cmp)

      write_bits(8, len(morph_maps))
      for morph_map in morph_maps:
        values = [
            morph_map.param.module.area.index, morph_map.param.module.index,
            morph_map.param.index, morph_map.morph.index, morph_map.range,
        ] # range is signed
        bitstream.write_bitsa([2, 8, 7, 4, 8], values)
      write_bits(4, 0) # always 0

    bitstream.seek_bit(-4, 1) # remove last 4-bits
    return bitstream.tell_bit()
section_manager.add(MorphParameters)

class KnobAssignments(Section):
  '''KnobAssignments Section subclass'''
  type = 0x62
  def parse(self, patch, data):
    bitstream = BitStream(data)
    nknobs = bitstream.read_bits(16)
    patch.knobs = [ Knob() for i in xrange(nknobs)] # G2Patch / G2Performance
    for knob in patch.knobs:
      knob.assigned = bitstream.read_bits(1)
      if not knob.assigned:
        continue
      area, index, knob.isled, param = bitstream.read_bitsa([2, 8, 2, 7])
      if type(patch) == Performance:
        knob.slot = bitstream.read_bits(2)
        perf = patch
        patch = perf.slots[knob.slot].patch
      else:
        knob.slot = 0

      if area == SETTINGS:
        knob.param = get_settings_param(patch, index, param)
      else:
        module = get_patch_area(patch, area).find_module(index)
        if module:
          knob.param = module.params[param]
        else:
          knob.assigned = 0
          continue
      knob.param.knob = knob

  def format(self, patch, data):
    bitstream = BitStream(data)
    bitstream.write_bits(16, NKNOBS)
    for knob in patch.knobs:
      bitstream.write_bits(1, knob.assigned)
      if not knob.assigned:
        continue
      module = knob.param.module
      bitstream.write_bitsa([2, 8, 2, 7],
          [ module.area.index, module.index, knob.isled, knob.param.index ])
      if type(patch) == Performance:
        bitstream.write_bits(2, knob.slot)
    return bitstream.tell_bit()
section_manager.add(KnobAssignments)

class CtrlAssignments(Section):
  '''CtrlAssignments Section subclass'''
  type = 0x60
  def parse(self, patch, data):
    bitstream = BitStream(data)
    nctrls = bitstream.read_bits(7)
    patch.ctrls = [ Ctrl() for i in xrange(nctrls)]  # G2Patch? / G2Ctrl?
    for ctrl in patch.ctrls:
      ctrl.midicc, area, index, param = bitstream.read_bitsa([7, 2, 8, 7])
      if area == SETTINGS:
        ctrl.param = get_settings_param(patch, index, param)
      else:
        module = get_patch_area(patch, area).find_module(index)
        ctrl.param = module.params[param]
      ctrl.param.ctrl = ctrl

  def format(self, patch, data):
    bitstream = BitStream(data)
    bitstream.write_bits(7, len(patch.ctrls))
    for ctrl in patch.ctrls:
      param = ctrl.param
      bitstream.write_bitsa([7, 2, 8, 7], [ ctrl.midicc,
          param.module.area.index, param.module.index, param.index ])
    return bitstream.tell_bit()
section_manager.add(CtrlAssignments)

class Labels(Section):
  '''Labels Section subclass'''
  type = 0x5b
  def parse_morphs(self, morphs, bitstream):
    nentries, entry, length = bitstream.read_bitsa([8, 8, 8]) # 1, 1, 0x50
    for morph in morphs:
      index, morphlen, entry = bitstream.read_bytes(3)
      morph.label = read_string(bitstream, 7, pad=True)

  def format_morphs(self, morphs, bitstream):
    bitstream.write_bits(2, SETTINGS)
    bitstream.write_str('\1\1\x50')
    s = bytearray([1, 1, 0])
    for morph in morphs:
      s[2] = 8 + morph.index
      bitstream.write_str(str(s))
      write_string(bitstream, morph.label, 7, pad=True)
    return bitstream.tell_bit()

  def parse_module(self, module, bitstream):
    modlen = bitstream.read_bits(8)
    if module.type.id == 121: # SeqNote
      # extra editor parameters 
      # [0, 1, mag, 0, 1, octave]
      # mag: 0=3-octaves, 1=2-octaves, 2=1-octave
      # octave: 0-9 (c0-c9)
      module.editmodes = bitstream.read_bytes(modlen)
    else:
      while modlen > 0:
        stri, paramlen, parami = bitstream.read_bitsa([8, 8, 8]) 
        modlen -= 3
        param = module.params[parami]
        paramlen -= 1 # decrease because we got param index
        if paramlen:
          param.labels = [ read_string(bitstream, 7, pad=True)
              for i in xrange(paramlen / 7) ]
          modlen -= paramlen
        else:
          param.labels = ['']
        if section_debug:
          printf('%d %s %d %d %s\n', module.index, module.type.shortnm,
              paramlen, parami, param.labels)

  def parse_area(self, area, bitstream):
    read_bits = bitstream.read_bits
    nmodules = read_bits(8)
    for i in xrange(nmodules):
      index  = read_bits(8)
      module = area.find_module(index)
      self.parse_module(module, bitstream)

  def format_module(self, module, bitstream):
    s = ''
    if module.type.id == 121: # SeqNote
      s += str(bytearray(module.editmodes))
    else:
      # build up the labels and then write them
      for i, param in enumerate(module.params):
        if not hasattr(param, 'labels'):
          continue
        if section_debug:
          printf('%d %s %d %d %s\n', module.index, module.type.shortnm,
              7*len(param.labels), i, param.labels)
        labels = [format_string(lbl, 7, pad=True) for lbl in param.labels]
        ps = chr(i) + ''.join(labels)
        s += chr(1)+chr(len(ps))+ps

    bitstream.write_bitsa([8, 8], [module.index, len(s)])
    bitstream.write_str(s)

  def format_area(self, area, bitstream):
    # collect all modules with parameters that have labels
    modules = []
    for module in area.modules:
      if hasattr(module, 'params'):
        for param in module.params:
          if hasattr(param, 'labels'):
            modules.append(module)
            break
      elif hasattr(module, 'editmodes'):
        modules.append(module)

    bitstream.write_bitsa([2, 8], [area.index, len(modules)])
    for module in modules:
      self.format_module(module, bitstream)

    return bitstream.tell_bit()

  def parse(self, patch, data):
    bitstream = BitStream(data)
    self.area = bitstream.read_bits(2)
    if self.area == SETTINGS:
      self.parse_morphs(patch.settings.morphs, bitstream)
    else:
      area = get_patch_area(patch, self.area)
      self.parse_area(area, bitstream)

  def format(self, patch, data):
    bitstream = BitStream(data)
    if self.area == SETTINGS:
      return self.format_morphs(patch.settings.morphs, bitstream)
    else:
      area = get_patch_area(patch, self.area)
      return self.format_area(area, bitstream)
section_manager.add(Labels)

class ModuleNames(Section):
  '''ModuleNames Section subclass'''
  type = 0x5a
  def parse_area(self, area, bitstream):
    areai, nmodules = bitstream.read_bitsa([6, 8])
    for i in xrange(nmodules):
      module = area.find_module(bitstream.read_bits(8))
      module.name = read_string(bitstream, 16)

  def parse(self, patch, data):
    bitstream = BitStream(data)
    self.area = bitstream.read_bits(2)
    area = get_patch_area(patch, self.area)
    self.parse_area(area, bitstream)

  def format_area(self, area, bitstream):
    bitstream.write_bitsa([2, 6, 8], [area.index, self.area, len(area.modules)])
    for module in area.modules:
      bitstream.write_bits(8, module.index)
      write_string(bitstream, module.name, 16)

  def format(self, patch, data):
    bitstream = BitStream(data)
    area = get_patch_area(patch, self.area)
    self.format_area(area, bitstream)
    return bitstream.tell_bit()
section_manager.add(ModuleNames)

class TextPad(Section):
  '''TextPad Section subclass'''
  type = 0x6f
  def parse(self, patch, data):
    patch.textpad = data

  def format(self, patch, data):
    bitstream = BitStream(data)
    bitstream.write_str(patch.textpad)
    return bitstream.tell_bit()
section_manager.add(TextPad)

class PerformanceDescription(Section):
  '''PerformanceDescription Section subclass'''
  type = 0x11
  description_attrs = [
    ['unk1', 8],
    ['unk2', 4], ['focus', 2], [ 'unk3', 2 ],
    ['rangesel', 8], ['bpm', 8],
    ['split', 8], ['clock', 8], ['unk4', 8], ['unk5', 8],
  ]
  slot_attrs = [
    ['active', 8], ['keyboard', 8], ['hold', 8], ['bank', 8 ], [ 'patch', 8 ],
    ['keylow', 8], ['keyhigh', 8], ['unk3', 8], ['unk4', 8], ['unk5', 8],
  ]
  def parse(self, performance, data):
    description = performance.description = Description() # G2Performance
    bitstream = BitStream(data)
    read_bits = bitstream.read_bits

    for name, nbits in self.description_attrs:
      value = read_bits(nbits)
      setattr(description, name, value)

    for slot in performance.slots:
      slot.description = Description()
      slot.name = read_string(bitstream, 16)
      for name, nbits in self.slot_attrs:
        value = read_bits(nbits)
        setattr(slot.description, name, value)

  def format(self, performance, data):
    bitstream = BitStream(data)
    write_bits = bitstream.write_bits
    description = performance.description

    for name, nbits in self.description_attrs:
      write_bits(nbits, getattr(description, name))

    for slot in performance.slots:
      write_string(bitstream, slot.name, 16)
      for name, nbits in self.slot_attrs:
        write_bits(nbits, getattr(slot.description, name))

    return bitstream.tell_bit()
section_manager.add(PerformanceDescription)

class GlobalKnobAssignments(KnobAssignments):
  '''GlobalKnobAssignments Section subclasss'''
  type = 0x5f

class Pch2File(object):
  '''Pch2File(filename) - main reading/writing object for .pch2 files
   this may become generic G2 file for .pch2 and .prf2 files
   just by handling the performance sections (and perhaps others)
   and parsing all 4 patches within the .prf2 file.
'''
  patch_sections = [
    PatchDescription(),
    ModuleList(area=1),
    ModuleList(area=0),
    CurrentNote(),
    CableList(area=1),
    CableList(area=0),
    Parameters(area=2),
    Parameters(area=1),
    Parameters(area=0),
    MorphParameters(area=2),
    KnobAssignments(),
    CtrlAssignments(),
    Labels(area=2),
    Labels(area=1),
    Labels(area=0),
    ModuleNames(area=1),
    ModuleNames(area=0),
    TextPad(),
  ]
  standard_text_header = '''Version=Nord Modular G2 File Format 1\r
Type=%s\r
Version=%d\r
Info=BUILD %d\r
\0'''  # needs the null byte
  binary_version = 23
  build_version = 266

  def __init__(self, filename=None):
    self.type = 'Patch'
    self.binary_revision = 0
    self.patch = Patch(nord.g2.modules.fromname)
    if filename:
      self.read(filename)

  def parse_section(self, section, patch_or_perf, memview):
    type, l = unpack('>BH', memview[:3])
    l += 3
    if section_debug:
      nm = section.__class__.__name__
      printf('0x%02x %-25s len:0x%04x\n', type, nm, l)
      printf('%s\n', binhexdump(memview[:l].tobytes()))
    section.parse(patch_or_perf, memview[3:l])
    return memview[l:]

  def parse_patch(self, patch, memview):
    memview = self.parse_section(PatchDescription(), patch, memview)
    while len(memview) > 0:
      type = ord(memview[0])
      if type == PatchDescription.type: # prf2 concats patches
        break
      section_class = section_manager.get(type, None)
      if not section_class:
        break
      memview = self.parse_section(section_class(), patch, memview)
    return memview

  def parse(self, memview):
    return self.parse_patch(self.patch, memview)

  def parse_header(self, memview, filename):
    header2x = bytearray(memview[:2*len(self.standard_text_header)])
    null = header2x.find('\0')
    if null < 0:
      raise G2Error('Invalid G2File "%s" missing null terminator.' % filename)
    self.txthdr = str(header2x[:null])
    self.binhdr = header2x[null+1], header2x[null+2]
    if self.binhdr[0] != self.binary_version:
      printf('Warning: %s version %d\n', filename, self.binhdr[0])
      printf('         version %d supported. it may fail to load.\n',
          self.binary_version)
    return memview[null+1:]  # include binhdr for crc

  # read - this is where the rubber meets the road.  it start here....
  def read(self, filename):
    self.filename = filename
    self.data = bytearray(open(filename, 'rb').read())
    memview = self.parse_header(memoryview(self.data), filename)
    bytes = len(self.parse(memview[2:-2]))
    ecrc = unpack('>H', self.data[-2:])[0]
    acrc = crc(memview[:-2])
    if ecrc != acrc:
      printf('Bad CRC 0x%x 0x%x\n' % (ecrc, acrc))

  def format_section(self, section, patch_or_perf, memview):
    #print section.__class__.__name__
    bits = section.format(patch_or_perf, memview[3:]) # skip type, size 
    bytes = (bits + 7) >> 3
    # write type, size
    memview[:3] = pack('>BH', section.type, bytes)

    if section_debug:
      nm = section.__class__.__name__
      printf('0x%02x %-25s len:0x%04x\n', section.type, nm, bytes)
      tbl = string.maketrans(string.ascii_lowercase, ' '*26)
      nm = nm.translate(tbl).replace(' ', '')
      printf('%s\n', nm)
      #if title_section and len(nm) < len(f):
      #  f = nm+f[len(nm):]

    return memview[bytes + 3:]

  def format_patch(self, patch, memview):
    for section in Pch2File.patch_sections:
      memview = self.format_section(section, patch, memview)
    return memview

  def format(self, memview):
    return self.format_patch(self.patch, memview)

  def format_file(self):
    data = bytearray(64<<10)
    memview = memoryview(data)
    hdr = Pch2File.standard_text_header % (self.type,
        self.binary_version, self.build_version)
    memview[:len(hdr)] = hdr
    memview = memview[len(hdr):]
    #memview = self.format_header(memview)
    memview[0] = chr(self.binary_version)
    memview[1] = chr(self.binary_revision)
    fmemview = self.format(memview[2:])
    bytes = len(memview) - len(fmemview)
    data_crc = crc(memview[:bytes])
    memview[bytes:bytes+2] = pack('>H', crc(memview[:bytes]))
    bytes = len(data) - len(fmemview) + 2
    return data[:bytes]

  # write - this looks a lot easier then read ehhhh???
  def write(self, filename=None):
    out = open(filename, 'wb')
    out.write(str(self.format_file()))

class Prf2File(Pch2File):
  '''Prf2File(filename) -> load a nord modular g2 performance.'''
  def __init__(self, filename=None):
    self.type = 'Performance'
    self.binary_revision = 1
    self.performance = Performance(nord.g2.modules.fromname)
    self.performance_section = PerformanceDescription()
    self.globalknobs_section = GlobalKnobAssignments()
    if filename:
      self.read(filename)

  def parse(self, memview):
    performance = self.performance
    performance_section = self.performance_section
    globalknobs_section = self.globalknobs_section
    memview = self.parse_section(performance_section, performance, memview)
    for slot in performance.slots:
      memview = self.parse_patch(slot.patch, memview)
    memview = self.parse_section(globalknobs_section, performance, memview)
    return memview

  def format_performance(self, memview):
    performance = self.performance
    performace_section = self.performance_section
    globalknobs_section = self.globalknobs_section
    memview = self.format_section(performance_section, performance, memview)
    for slot in performance.slots:
      memview = self.format_patch(slot.patch, memview)
    memview = self.format_section(globalknobs_section, performance, memview)
    return memview

  def format(self, memview):
    return self.format_performace(memview)

if __name__ == '__main__':
  prog = sys.argv.pop(0)
  filename = sys.argv.pop(0)
  printf('"%s"\n', filename)
  pch2 = Pch2File(filename)
  #pch2.write(sys.argv.pop(0))


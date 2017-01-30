"""Code for assessing alignment accuracy"""
import re

from mitty.simulation.sequencing.writefastq import ri, load_qname_sidecar, parse_qname
# good to have these together. Code that uses score_alignment_error is very likely to use
# ri, load_qname_sidecar and parse_qname

cigar_parser = re.compile(r'(\d+)(\D)')


def score_alignment_error(r, ri, max_d=200, strict=False):
  """
  :param r: aligned read
  :param ri: readinfo for correct alignment
  :param strict: If True, soft clipped alignments or split alignments are marked incorrect
                 if False alignment to breakpoints gets full score
  :return:
  """
  d_err = max_d
  if strict or ri.cigar[0] == '>':
    # Both the strict case and the case where the read comes from inside a long insertion are scored
    # similarly
    d_err = max(min((r.pos + 1 - ri.pos if r.reference_name == ri.chrom else max_d), max_d), -max_d)
  else:  # Score read as correct if read is placed at any breakpoint correctly
    if r.reference_name == ri.chrom:
      correct_pos = ri.pos
      for cnt, op in cigar_parser.findall(ri.cigar):
        if op == '=' or op == 'M' or op == 'X':
          if abs(r.pos + 1 - correct_pos) < abs(d_err):
            d_err = r.pos + 1 - correct_pos
          correct_pos += int(cnt)
        elif op == 'D':
          correct_pos += int(cnt)

  return d_err


def tag_alignment(r, ri):
  """Given correct alignment set tags on the read indicating correct alignment

  :param r:
  :param ri:
  :return: mutates r
  """
  r.set_tags(
    [('Xd', score_alignment_error(r, ri), 'i'),
     ('XR', ri.chrom, 'Z'),
     ('XP', ri.pos, 'i'),
     ('XM', ri.cigar, 'Z')])
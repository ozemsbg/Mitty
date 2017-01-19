"""Needed a way to go through the evaluation VCF from VCF benchmarking and spit out the FP and FN
calls into separate VCFs and then extract reads from those regions into a BAM.

vcffilter can mark the FP and FNs but leaves all the other records in. Would need to chain with vcftools
and at this point things are complicated enough that it's easier to use Python for this.

This tools drops two VCFs, one for FN and one for FP. Each has an associated ROI BED file.

These BED files can be used with samtools view to generate BAMs that contain reads from just these variants
"""
import time

import pysam

import logging
logger = logging.getLogger(__name__)


def extract_fp_fn(fname_in, prefix_out):
  """

  :param fname_in:
  :param prefix_out:
  :return:
  """
  logger.debug('Starting filtering ...')
  t0 = time.time()

  mode = 'rb' if fname_in.endswith('bcf') else 'r'
  vcf_in = pysam.VariantFile(fname_in, mode)

  fp_vcf_out = pysam.VariantFile(prefix_out + '-fp.vcf', mode='w', header=vcf_in.header)
  fp_roi_bed = open(prefix_out + '-fp-roi.bed', 'w')
  fn_vcf_out = pysam.VariantFile(prefix_out + '-fn.vcf', mode='w', header=vcf_in.header)
  fn_roi_bed = open(prefix_out + '-fn-roi.bed', 'w')
  bam_in = pysam.AlignmentFile(fname_in[:-3] + 'bam', "rb")#caner
  fp_bam_out = pysam.AlignmentFile(prefix_out+'-fp.bam', "wb", template=bam_in) #caner
  fn_bam_out = pysam.AlignmentFile(prefix_out+'-fn.bam', "wb", template=bam_in) #caner

  n, fp_cnt, fn_cnt = -1, 0, 0
  #CANER - distribution of variant sizes
  fp_ins_size_in_curr_bin=0
  fp_del_size_in_curr_bin=0
  fn_ins_size_in_curr_bin=0
  fn_del_size_in_curr_bin=0
  fp_snp_size_in_curr_bin=0
  fn_snp_size_in_curr_bin=0
  fp_subst_size_in_curr_bin=0
  fn_subst_size_in_curr_bin=0

  for n, v in enumerate(vcf_in):
    s = v.samples['TRUTH']
    if s['BD'] == 'FN':
      fn_cnt += 1
      fn_vcf_out.write(v)
      save_roi(fn_roi_bed, v)
      #fp_bam_out.write(bam_in.fetch(v.chrom, v.start, v.stop))#caner
      ref=v.ref#caner
      alts=v.alts#caner
      for alt in alts:#caner
      	#caner -  process Distribution of variant sizes
      	pass

    s = v.samples['QUERY']
    if s['BD'] == 'FP':
      fp_cnt += 1
      fp_vcf_out.write(v)
      save_roi(fp_roi_bed, v)
      #fn_bam_out.write(bam_in.fetch(v.chrom, v.start, v.stop))#caner
      ref=v.ref#caner
      alts=v.alts#caner
      for alt in alts:#caner
      	pass#caner - Distribution of variant sizes
      
      

  bam_in.close()#caner
  fp_bam_out.close()#caner
  fn_bam_out.close()#caner
  logger.debug('Processed {} calls'.format(n + 1))
  logger.debug('Sample had {} FP, {} FN'.format(fp_cnt, fn_cnt))
  t1 = time.time()
  logger.debug('Took {} s'.format(t1 - t0))


def save_roi(fp, v):
  fp.write('{}\t{}\t{}\n'.format(v.chrom, v.start, v.stop))

extract_fp_fn("input.vcf","outcan")

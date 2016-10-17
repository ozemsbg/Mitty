"""Contains the logic for handling read model invocation, read creation and writing"""

__qname_format__ = '@read_serial|chrom|copy|strand|pos|rlen|cigar|vs1,vs2,...|strand|pos|rlen|cigar|vs1,vs2,...'
__qname_format_details__ = """
@read_serial|chrom|copy|strand|pos|rlen|cigar|vs1,vs2,...|strand|pos|rlen|cigar|vs1,vs2,...
    |          |     |    |     |    |    |        |         |                      |
 unique        |     |    |     | read    |        |         ---- repeated for ------
 number for    |     |    |     | len     |        |          other read in template
 template      |     |    |     |         |        |
               |     |    |     |     cigar    comma separated
      chrom read     |    |     |              list of sizes of
  was taken from     |    |     |              variants this read
       One based     |    |     |              covers
                     |    |     |
                     |    |     |
    copy of chrom read    |     |
 was taken from (0, 1)    |     |
                          |     |
         forward strand (0)     |
      or reverse strand (1)     |
                                |
                      pos of read
                        One based

The chrom and pos are one based to make comparing qname info in genome browser easier

For reads from inside a long insertion the CIGAR has the following format:

  '>p:nI'

where:

 '>' is the unique key that indicates a read inside a long insertion
 'p' is how many bases into the insertion branch the read starts
 'n' is simply the length of the read
"""
import time
from multiprocessing import Process, Queue
import queue

import pysam
import numpy as np

import mitty.lib.vcfio as vio
import mitty.simulation.rpc as rpc

import logging

logger = logging.getLogger(__name__)


SEED_MAX = (1 << 32) - 1  # Used for seeding rng
__process_stop_code__ = 'SETECASTRONOMY'
DNA_complement = str.maketrans('ATCGN', 'TAGCN')

# Will hold the mem-shared read only data
vcf_df = None


# The sequence of steps is to
# 1. Generate read templates based on BED file  -> save as global
# 2. Start up a bunch of workers and pass regions to them
# 3. Each worker creates the nodelist for the region and uses the relavant templates to create reads
# 4. Write out the reads as they are generated
#
# This code generates perfect reads. The reads can be piped (Tee-d) to an algorithm that implements
# corruption

# The following functions save data to global (Read only) variables so that we can use them with
# multi-processing


def process_multi_threaded(fasta_fname, vcf_fname, sample_name, bed_fname,
                           read_module, model_params,
                           fastq1_fname, fastq2_fname, threads=2, seed=7):
  """

  :param fasta_fname:
  :param vcf_fname:
  :param sample_name:
  :param bed_fname:
  :param read_model:
  :param threads:
  :param seed:
  :return:
  """

  read_model = read_module.read_model_params(**model_params)

  global vcf_df
  vcf_df = vio.load_variant_file(vcf_fname, sample_name, bed_fname)

  in_queue = Queue()
  out_queue = Queue()

  logger.debug('Loading up the work queue')
  for wd in get_data_for_workers(read_model, vcf_df, seed):
    in_queue.put(wd)

  logger.debug('Starting {} workers'.format(threads))
  workers = []
  for worker_id in range(threads):
    p = Process(target=read_generating_worker,
                args=(worker_id, fasta_fname, sample_name, read_module, read_model, in_queue, out_queue))
    p.start()
    workers.append(p)
    in_queue.put(__process_stop_code__)

  logger.debug('Writing data ...')
  t0 = time.time()
  cnt = 0
  with open(fastq1_fname, 'w') as fastq1, open(fastq2_fname, 'w') as fastq2:
    while 1:
      try:
        ln = out_queue.get(timeout=1)
        cnt += 1
        fastq1.write(ln[0])  # make this cleaner for SE files etc.
        fastq2.write(ln[1])
      except queue.Empty:
        if all(not p.is_alive() for p in workers):
          break
  t1 = time.time()
  logger.debug('... finished writing {} templates in {}s ({} t/s)'.format(cnt, t1 - t0, cnt/(t1 - t0)))

  for w in workers:
    w.join()
  logger.debug('All workers are done')


def get_data_for_workers(model, vcf, seed):
  """Given a vcf structure return an iterator that keeps returning us a region and copy to generate
  reads from until the desired coverage has been attained.

  :param model: Must contain a 'passes' field that determines how many times a region is passed to it
  :param vcf: ploidy aware variant structure as returned by vcfio. We only use the region and ploidy information
              to create and return a generator for regions. We generate as many regions as needed to achieve the
              given coverage, taking ploidy of the region into account
  :param seed: This is used to seed an RNG that generates rng seeds passed to all the workers
  :return: a generator that returns worker data as a dict
           {
             'region_idx': r_idx,  # Index into VCF structure
             'region_cpy': cpy,  # which copy of the region to use
             'rng_seed': s   # seed for the RNGs in the worker
           }

           access the variants as vcf_df[r_idx]['v'][cpy]
  """
  seed_rng = np.random.RandomState(seed)
  shuffle_seed = seed_rng.randint(SEED_MAX)
  region_list = [
    {'region_idx': idx, 'region_cpy': cpy, 'rng_seed': seed_rng.randint(SEED_MAX)}
    for idx, v in enumerate(vcf)
    for cpy in range(len(v['v']))
    for _ in range(model['passes'])
  ]
  logger.debug('{} passes will be made'.format(len(region_list)))
  np.random.RandomState(shuffle_seed).shuffle(region_list)

  for region in region_list:
    yield region


# def read_generating_worker(worker_id, fasta_fname, sample_name, read_module, read_model, in_queue, out_queue):
#   for ps, wd in enumerate(iter(in_queue.get, __process_stop_code__)):
#     out_queue.put([str(ps), str(wd)])


def read_generating_worker(worker_id, fasta_fname, sample_name, read_module, read_model, in_queue, out_queue):
  """This worker will be given a fasta_fname, and region information. It is to generate the node_list,
  the read locations and then, finally, the reads themselves. The reads - in FASTQ format - are returned
  to the parent thread for writing.

  :param worker_id: Just a serial that helps us number reads uniquely
  :param fasta_fname:
  :param sample_name:  (This is just passed to the read qname)
  :param model:
  :param region_idx:
  :param in_queue: will be sending work information as (region_idx, cpy)
  :param out_queue: We'll be sending strings representing each template in FASTQ format
  :return:
  """
  fasta = pysam.FastaFile(fasta_fname)
  for ps, wd in enumerate(iter(in_queue.get, __process_stop_code__)):
    r_idx, cpy, rng_seed = wd['region_idx'], wd['region_cpy'], wd['rng_seed']
    region = vcf_df[r_idx]['region']
    ref_seq = fasta.fetch(reference=region[0], start=region[1], end=region[2])
    # The structure needed to generate read sequences, pos and CIGAR strings
    node_list = rpc.create_node_list(ref_seq, ref_start_pos=region[1], vl=vcf_df[r_idx]['v'][cpy])
    r_info_l = read_module.generate_reads(read_model, region, rng_seed)

    qname_serial_stub = '{}:{}:{}'.format(sample_name, worker_id, ps)
    t0 = time.time()
    n = 0
    for n, template in enumerate(zip(
      *[zip(*([r_info[k] for k in ['strand', 'file_order', 'pos', 'len']] +
                rpc.get_begin_end_nodes(r_info['pos'], r_info['len'], node_list))) for r_info in r_info_l])):
      reads = [None] * len(template)
      for s, fo, p, l, ns, ne in template:
        pos, cigar, v_list, seq = rpc.generate_read(p, l, ns, ne, node_list)
        if s == 1:
          seq = seq.translate(DNA_complement)[::-1]
        reads[fo] = (s, pos, l, cigar, v_list, seq)

      out_queue.put(fastq_lines('{}:{}'.format(qname_serial_stub, n), region[0], cpy, reads))

    t1 = time.time()
    logger.debug('Wrote {} templates in {}s ({} t/s)'.format(n, t1 - t0, n/(t1 - t0)))


# @read_serial|chrom|copy|strand|pos|rlen|cigar|vs1,vs2,...|strand|pos|rlen|cigar|vs1,vs2,...
def fastq_lines(n, chrom, cpy, reads):
  qname = '@{}|{}|{}'.format(n, chrom, cpy)
  for r in reads:
    qname += '|{}|{}|{}|{}|{}'.format(r[0], r[1], r[2], r[3], str(r[4])[1:-1])

  return [
    qname + '\n' + r[5] + '\n+\n' + '~' * r[2] + '\n'
    for r in reads
  ]


def validate_templates_from_read_model(tplt):
  """A series of tests to make sure that the returned template locations are in a format suitable for our use

  :param tplt:
  :return:
  """
  if not isinstance(tplt, list):
    raise RuntimeError('Read model should return a list')

  if not isinstance(tplt[0], dict):
    raise RuntimeError('Read model should return a list of dicts')

  for k in ['reads', 'region']:
    if k not in tplt[0]:
      raise RuntimeError('Read model dict should contain {}'.format(k))

  if not isinstance(tplt[0]['reads'], np.recarray):
    raise RuntimeError('Reads should be in the form of a numpy recarray')
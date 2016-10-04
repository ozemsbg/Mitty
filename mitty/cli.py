import logging
import os

import click


import mitty.simulation.readgen as rgen
import mitty.empirical.bq_bam as bbq
import mitty.empirical.gc as megc


@click.group()
@click.version_option()
@click.option('-v', '--verbose', count=True)
def cli(verbose):
  """A genomic data simulator for testing and debugging bio-informatics tools"""
  if verbose == 1:
    logging.basicConfig(level=logging.ERROR)
  elif verbose == 2:
    logging.basicConfig(level=logging.WARNING)
  elif verbose == 3:
    logging.basicConfig(level=logging.INFO)
  elif verbose >= 4:
    logging.basicConfig(level=logging.DEBUG)


@cli.command('gc-cov')
@click.argument('bam', type=click.Path(exists=True))
@click.argument('fasta', type=click.Path(exists=True))
@click.argument('pkl')
@click.option('-b', '--block-len', type=int, default=10000, help='Block size for GC/cov computation')
@click.option('-t', '--threads', type=int, default=1, help='Threads to use')
def gc_cov(bam, fasta, pkl, block_len, threads):
  """Calculate GC content vs coverage from a BAM. Save in pickle file"""
  megc.process_bam_parallel(bam, fasta, pkl, block_len=block_len, threads=threads)


@cli.command('sample-fastq-base-quality')
@click.argument('fastq', type=click.File('r'))
@click.argument('outprefix')
@click.option('-t', '--threads', type=int, default=1, help='Threads to use')
@click.option('--max-reads', type=int, help='Maximum reads to process')
def sample_bq(fastq, outprefix, threads, max_reads):
  """FASTQ -> base-quality-distribution.csv + 2D histogram plot"""
  with open(outprefix + '.csv', 'wb') as out_fp:
    score = bbq.base_quality(fastq_fp=fastq, out_fp=out_fp, threads=threads, f_size=None, max_reads=max_reads)
  bbq.plot_bq_metrics(score, out_fname=outprefix + '.hist.png')


@cli.command()
def qname():
  """Display qname format"""
  click.echo(rgen.__qname_format_details__)


def print_qname(ctx, param, value):
  if not value or ctx.resilient_parsing:
    return
  click.echo(rgen.__qname_format_details__)
  ctx.exit()


@cli.command('generate-reads', short_help='Generate simulated reads.')
@click.argument('reffasta')
@click.argument('paramfile')
@click.option('--qname', is_flag=True, callback=print_qname, expose_value=False, is_eager=True, help='Print documentation for information encoded in qname')
@click.option('--seed', default=7, help='Seed for RNG')
@click.option('--reference-reads-only', is_flag=True, help='If this is set, only reference reads will be generated')
@click.option('--sample-name', '-s', type=str, help='Name of sample to put in reads')
@click.option('--vcf', type=click.Path(exists=True), help='Path to vcf file representing sample')
@click.option('--bed', type=click.Path(exists=True), help='Bed file restricting regions reads are taken from')
def generate_reads(reffasta, paramfile, sample_name, vcf, bed, reference_reads_only):
  """Generate simulated reads and write them to stdout"""
  pass


@cli.command('corrupt-reads', short_help='Apply corruption model to FASTQ file of reads')
def read_corruption():
  pass

def read_bias():
  pass


@cli.command('unpair-fastq', short_help='PE -> SE')
def unpair_fastq(fastq):
  """Rewrite qnames from interleaved PE FASTQ so file can be run as SE. Output to stdout"""
  pass


@cli.command('uninterleave-fastq', short_help='Interleaved PE 3> PE_1 4> PE_2')
@click.argument('fastq')
def uninterleave_fastq(fastq):
  """Given an interleaved paired-end FASTQ, split it out into two FASTQ files, written to streams 3 and 4"""
  pass


@cli.command()
def genomes():
  """Functions for sample/population simulations"""
  pass
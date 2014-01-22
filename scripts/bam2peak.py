#!/usr/bin/env python
# Programmer : zhuxp
# Date: 
# Last-modified: 01-16-2014, 15:49:29 EST
VERSION="0.1"
import os,sys,argparse
from xplib.Annotation import Bed
from xplib import TableIO,Tools,DBI
from xplib.Tools import IO
import signal
signal.signal(signal.SIGPIPE,signal.SIG_DFL)
import gzip
import time
import multiprocessing as mp
import array,tempfile,heapq
import xplib.Stats.prob as prob
import itertools
assert array.array('i').itemsize==4
'''
V3:
DONE: mv sorting array to Turing Module
V4:
DONE: correct the coverage calculation
DONE: report link exon and intron

V5:
TODO: same memory using numarray instead of bed?
      only using array?
      rm bed class?
      list of list ?
      bedgraph sorting array?
TODO: report if peak has intron and the possible cDNA length and gene length.
TODO: compare with known gene
TODO: trim the last intron or extend the exon? ( KEY PROBLEM. how to define the end )
'''
EXON_GROUP_CODE=1
INTRON_GROUP_CODE=0
HAS_INTRON=20
NOT_HAS_INTRON=10

POSITIVE_STRAND=1
NEGATIVE_STRAND=-1

START_INDEX=0
STOP_INDEX=1
SCORE_INDEX=2
STRAND_INDEX=3
GROUP_INDEX=4
OTHER_INDEX=5


def ParseArg():
    ''' This Function Parse the Argument '''
    p=argparse.ArgumentParser( description = 'Example: %(prog)s -h', epilog='Library dependency : xplib')
    p.add_argument('-v','--version',action='version',version='%(prog)s '+VERSION)
    p.add_argument('-i','--input',dest="input",default="stdin",type=str,help="input file DEFAULT: STDIN")
    p.add_argument('-o','--output',dest="output",type=str,default="stdout",help="output file DEFAULT: STDOUT")
    p.add_argument('-n','--num_cpus',dest="num_cpus",type=int,default=4,help="number of cpus DEFAULT: %(default)i")
    p.add_argument('-s','--strand',dest="strand",type=str,choices=["read1","read2"],default="read2",help="read1 or read2 is the positive strand , default: %(default)s")
    p.add_argument('--prefix',dest="prefix",type=str,default="R",help="prefix for bed name default: %(default)s")
    p.add_argument('--cutoff',dest="cutoff",type=int,default=1,help="only report region covrage >= cutoff : %(default)i")
    p.add_argument('--pvalue',dest="pvalue",type=float,default=1e-05,help="cutoff for calling peak : %(default)f")
    if len(sys.argv)==1:
        print >>sys.stderr,p.print_help()
        exit(0)
    return p.parse_args()
def Main():
    '''
    IO TEMPLATE
    '''
    global args,out,exon_cutoff,intron_cutoff
    args=ParseArg()
    dbi=DBI.init(args.input,"bam")
    out=IO.fopen(args.output,"w")
    '''
    END OF IO TEMPLATE 
    '''
    print >>out,"# This positive_data was generated by program ",sys.argv[0]," (version: %s)"%VERSION,
    print >>out,"in bam2x ( https://github.com/nimezhu/bam2x )"
    print >>out,"# Date: ",time.asctime()
    print >>out,"# The command line is :"
    print >>out,"#\t"," ".join(sys.argv)
    chrs=[]
    lengths=[]
    for i in dbi.query(method="references"):
        chrs.append(i)
    for i in dbi.query(method="lengths"):
        lengths.append(i)
    p=mp.Pool(processes=args.num_cpus)    
    '''
    a=process_chrom("chr1")
    for i in a:
        print i
    '''
    coverage_bedgraphs=p.map(process_chrom,chrs)
    #output(results)
    #TODO
    # BUG : coverage now related with cutoff
    # coverages=p.map(count_coverage,bedgraphs)
    bedgraphs=[]
    coverages=[]
    for i in range(len(chrs)):
        bedgraphs.append(coverage_bedgraphs[i][1])
        coverages.append(coverage_bedgraphs[i][0])
    s=0.0  # 1000.0
    l=long(0)
    for i in range(len(chrs)):
        s+=coverages[i]
        l+=lengths[i]
    l=l*2 # Double Strand
    coverage=s/l*1000.0
    threshold=1
    while 1:
        if prob.poisson_cdf(threshold,coverage,False) < args.pvalue: break
        threshold+=1
    exon_cutoff=threshold
    intron_cutoff=2 #TODO revise it
    print >>out,"# MEAN COVERAGE:",coverage
    print >>out,"# EXON COVERAGE CUTOFF:",exon_cutoff
    #call_peaks(bedgraphs[0],1)
    peaks=p.map(call_peaks_star,itertools.izip(bedgraphs,itertools.repeat(exon_cutoff)))
    output(peaks)

    #process_chrom("chr1")
def output(s):
    for i in s:
        for j in i:
            print >>out,nice_format(j)

def nice_format(a):
    return "\t".join("%s"%item for item in a)
from xplib.Turing import TuringCode
from xplib.Turing import TuringCodeBook as cb
from xplib.Turing import TuringTupleSortingArray
from operator import itemgetter

def process_chrom(chrom):
    local_dbi=DBI.init(args.input,"bam")
    retv=list()
    intron_retv=list()
    a=[]
    #positive_data=TuringSortingArray(None,500)
    positive_data=TuringTupleSortingArray()
    negative_data=TuringTupleSortingArray()
    
    positive_intron_data=TuringTupleSortingArray()
    negative_intron_data=TuringTupleSortingArray()

    for i in local_dbi.query(chrom,method="bam1",strand=args.strand):
        if i.strand=="+" or i.strand==".": 
            positive_data.append((i.start,cb.ON))
            positive_data.append((i.stop,cb.OFF))
            for j in i.Exons():
                positive_data.append((j.start,cb.BLOCKON))
                positive_data.append((j.stop,cb.BLOCKOFF))
            for j in i.Introns():
                positive_intron_data.append((j.start,cb.BLOCKON))
                positive_intron_data.append((j.stop,cb.BLOCKOFF))
        else:
            negative_data.append((i.start,cb.ON))
            negative_data.append((i.stop,cb.OFF))
            for j in i.Exons():
                negative_data.append((j.start,cb.BLOCKON))
                negative_data.append((j.stop,cb.BLOCKOFF))
            for j in i.Introns():
                negative_intron_data.append((j.start,cb.BLOCKON))
                negative_intron_data.append((j.stop,cb.BLOCKOFF))
    cutoff=args.cutoff
    coverage=0.0
    for i,x in enumerate(codesToBedGraph(positive_data.iter())):
        if x[SCORE_INDEX] >= cutoff:
            retv.append((x[0],x[1],x[2],POSITIVE_STRAND,EXON_GROUP_CODE))
        coverage+=float(x[1]-x[0])*x[2]/1000.0
    for i,x in enumerate(codesToBedGraph(negative_data.iter())):
        if x[SCORE_INDEX] >= cutoff:
            retv.append((x[0],x[1],x[2],NEGATIVE_STRAND,EXON_GROUP_CODE))
        coverage+=float(x[1]-x[0])*x[2]/1000.0
    INTRON_CUTOFF=1.0
    for i,x in enumerate(codesToBedGraph(positive_intron_data.iter())):
        if x[SCORE_INDEX] >= INTRON_CUTOFF:
            retv.append((x[0],x[1],x[2],POSITIVE_STRAND,INTRON_GROUP_CODE))
    for i,x in enumerate(codesToBedGraph(negative_intron_data.iter())):
        if x[SCORE_INDEX] >= INTRON_CUTOFF:
            retv.append((x[0],x[1],x[2],NEGATIVE_STRAND,INTRON_GROUP_CODE))
    retv.sort(key=itemgetter(0,1,2))
    #TODO how to sort!
    local_dbi.close()
    return coverage,retv
def codesToBedGraph(iter):
    a=iter.next()
    last_pos=a[0]
    counter=0
    for i in iter:
        if i[0]!=last_pos:
            #TODO using more efficient data structure
            yield (last_pos,i[0],counter)
            last_pos=i[0]
        if i[1]==cb.BLOCKON:
            counter+=1
        if i[1]==cb.BLOCKOFF:
            counter-=1
    raise StopIteration


def call_peaks_star(a_b):
    return call_peaks(*a_b)
    
def call_peaks(bedgraph,exon_cutoff):
    #TODO
    gap=10
    pos_beds=[]
    neg_beds=[]
    peaks=[]
    i_p=0
    i_n=0
    last_pos_stop=0
    last_neg_stop=0
    for i in bedgraph:
        if i[STRAND_INDEX]==POSITIVE_STRAND:
            if i[GROUP_INDEX]==EXON_GROUP_CODE:
                if i[SCORE_INDEX] >= exon_cutoff:
                    if len(pos_beds)>0:
                        if  i[START_INDEX]-last_pos_stop < gap or last_pos_stop==0:
                            pos_beds.append(i)
                            if last_pos_stop < i[STOP_INDEX]:
                                last_pos_stop=i[STOP_INDEX]
                        else:
                            peaks.append(bedsToPeak(pos_beds,"p_"+str(i_p)))
                            i_p+=1
                            pos_beds=[i]
                            last_pos_stop=i[STOP_INDEX]
                    else:
                        last_pos_stop=i[STOP_INDEX]
                        pos_beds.append(i)
            elif i[GROUP_INDEX]==INTRON_GROUP_CODE:
                if last_pos_stop < i[STOP_INDEX]:
                    last_pos_stop=i[STOP_INDEX]
                pos_beds.append(i)
        else:
            if i[GROUP_INDEX]==EXON_GROUP_CODE:
                if i[SCORE_INDEX] >= exon_cutoff:
                    if len(neg_beds)>0:
                        if  i[START_INDEX]-last_neg_stop < gap or last_neg_stop==0:
                            neg_beds.append(i)
                            if last_neg_stop < i[STOP_INDEX]:
                                last_neg_stop=i[STOP_INDEX]
                        else:
                            peaks.append(bedsToPeak(neg_beds,"n_"+str(i_n)))
                            i_n+=1
                            neg_beds=[i]
                            last_neg_stop=i[STOP_INDEX]
                    else:
                        neg_beds.append(i)
                        last_neg_stop=i[STOP_INDEX]
            elif i[GROUP_INDEX]==INTRON_GROUP_CODE:
                if last_neg_stop < i[STOP_INDEX]:
                    last_neg_stop=i[STOP_INDEX]
                pos_beds.append(i)

    if len(pos_beds)>0:
        peaks.append(bedsToPeak(pos_beds,"p_"+str(i_p)))
    if len(neg_beds)>0:
        peaks.append(bedsToPeak(neg_beds,"n_"+str(i_n)))
    peaks.sort()
    return peaks
def length(x):
    return x[STOP_INDEX]-x[START_INDEX]
def bedsToPeak(ibeds,id):
    peak=[ibeds[0][START_INDEX],ibeds[0][STOP_INDEX],float(ibeds[0][SCORE_INDEX]),ibeds[0][STRAND_INDEX],NOT_HAS_INTRON,0,id]
    cdna_length=length(peak)
    for i in ibeds[1:]:
        if i[GROUP_INDEX]==EXON_GROUP_CODE:
            peak[SCORE_INDEX]=float(peak[SCORE_INDEX]*cdna_length+i[SCORE_INDEX]*length(i))/(length(peak)+length(i))
            peak[STOP_INDEX]=i[STOP_INDEX]
            cdna_length+=length(i)
        else:
            peak[GROUP_INDEX]=HAS_INTRON
    peak[OTHER_INDEX]=cdna_length
    #print "META",peak
    #for i in ibeds:
    #    print "IN",i
    return tuple(peak)



        

    
if __name__=="__main__":
    Main()








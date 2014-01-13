#!/usr/bin/env python
# Programmer : zhuxp
# Date: 
# Last-modified: 01-13-2014, 17:05:57 EST
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
    global args,out,dbi,exon_cutoff,intron_cutoff
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
    bedgraphs=p.map(process_chrom,chrs)
    #output(results)
    
    coverages=p.map(count_coverage,bedgraphs)
    s=0.0  # 1000.0
    l=long(0)
    for i in range(len(chrs)):
        s+=coverages[i]
        l+=lengths[i]
    coverage=s/l*1000.0
    threshold=1
    while 1:
        if prob.poisson_cdf(threshold,coverage,False) < args.pvalue: break
        threshold+=1
    exon_cutoff=threshold
    intron_cutoff=2 #TODO revise it
    print >>out,"# MEAN COVERAGE:",coverage
    print >>out,"# EXON COVERAGE CUTOFF:",exon_cutoff
    peaks=p.map(call_peaks_star,itertools.izip(bedgraphs,itertools.repeat(exon_cutoff)))
    output(peaks)

    #process_chrom("chr1")
def output(s):
    for i in s:
        for j in i:
            print >>out,j

from xplib.Turing import TuringCode
from xplib.Turing import TuringCodeBook as cb

class TuringSortingArray():
    def __init__(self,a=None,MAX_ARRAY_SIZE=500000):
        self.data=[[]]
        self.files=[[]]
        self.size=0
        self.index=0
        self.MAX_ARRAY_SIZE=MAX_ARRAY_SIZE
        if a is not None:
            for i in a:
                heapq.heappush(self.data[0],i)
        self.sort()
        self.has_sorted=True
    def append(self,x):
        self.has_sorted=False
        if (self.index<self.MAX_ARRAY_SIZE):
            heapq.heappush(self.data[0],x)
            self.index+=1
        else:
            self.data[0].sort()
            f=tempfile.TemporaryFile()
            self.data.append(TuringSortingArray.file_reader(f))
            TuringSortingArray.write_file(self.data[0],f)
            f.seek(0)
            self.files.append(f)
            self.data[0]=[x]
            self.index=1

    def sort(self):
        self.data[0].sort()
        self.has_sorted=True
    def seek0(self):
        for f in self.files:
            f.seed(0)
    def iter(self):
        #yield "test"
        if not self.has_sorted:
            self.sort()
            self.has_sorted=True
        for i in heapq.merge(*self.data):
            yield i
    @staticmethod    
    def file_reader(f):
        while True:
            a = array.array("i")
            a.fromstring(f.read(4000))
            if not a:
                break
            print str(f),"DEBUG",len(a)
            for i in range(0,len(a),2):
                yield TuringCode(a[i],a[i+1])
    @staticmethod
    def write_file(a,f):
        b=array.array("i")
        for i in a:
            b.append(i.pos)
            b.append(i.code)
        b.tofile(f)


def process_chrom(chrom):
    retv=list()
    a=[]
    positive_data=TuringSortingArray(None,500)
    negative_data=TuringSortingArray()
    k=0
    negative_k=0
    for i in dbi.query(chrom,method="bam1",strand=args.strand):
        if i.strand=="+" or i.strand==".": 
            positive_data.append(TuringCode(i.start,cb.ON))
            positive_data.append(TuringCode(i.stop,cb.OFF))
            for j in i.Exons():
                positive_data.append(TuringCode(j.start,cb.BLOCKON))
                positive_data.append(TuringCode(j.stop,cb.BLOCKOFF))
        else:
            negative_data.append(TuringCode(i.start,cb.ON))
            negative_data.append(TuringCode(i.stop,cb.OFF))
            for j in i.Exons():
                negative_data.append(TuringCode(j.start,cb.BLOCKON))
                negative_data.append(TuringCode(j.stop,cb.BLOCKOFF))
    cutoff=args.cutoff
    for i,x in enumerate(codesToBedGraph(positive_data.iter(),cutoff)):
        name=args.prefix+"_"+chrom+"_p"+str(i)
        retv.append(Bed([chrom,x[0],x[1],name,x[2],"+"]))
    for i,x in enumerate(codesToBedGraph(negative_data.iter(),cutoff)):
        name=args.prefix+"_"+chrom+"_n"+str(i)
        retv.append(Bed([chrom,x[0],x[1],name,x[2],"-"]))
    retv.sort()
    return retv
def codesToBedGraph(iter,cutoff=1.0):
    a=iter.next()
    last_pos=a.pos
    counter=0
    for i in iter:
        if i.pos!=last_pos:
            if counter >= cutoff:
                yield (last_pos,i.pos,counter)
            last_pos=i.pos
        if i.code==cb.BLOCKON:
            counter+=1
        if i.code==cb.BLOCKOFF:
            counter-=1
    raise StopIteration



def count_coverage(bedgraph):
    '''
    return the total number nt in this bedgraph.
    '''
    s=0.0 # float inw5q3ne or 
    for i in bedgraph:
        s+=float (len(i)*i.score) / 1000.0
    return s
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
    for i in bedgraph:
        if i.strand=="+" or i.strand==".":
            if i.score >= exon_cutoff:
                if len(pos_beds)>0:
                    if i.chr==pos_beds[-1].chr and i.start-pos_beds[-1].stop < gap:
                        pos_beds.append(i)
                    else:
                        peaks.append(bedsToPeak(pos_beds,"p_"+str(i_p)))
                        i_p+=1
                        pos_beds=[i]
                else:
                    pos_beds.append(i)
        else:
            if i.score >= exon_cutoff:
                if len(neg_beds)>0:
                    if i.chr==neg_beds[-1].chr and i.start-neg_beds[-1].stop < gap:
                        neg_beds.append(i)
                    else:
                        peaks.append(bedsToPeak(neg_beds,"n_"+str(i_n)))
                        i_n+=1
                        neg_beds=[i]
                else:
                    neg_beds.append(i)

    if len(pos_beds)>0:
        peaks.append(bedsToPeak(pos_beds,"p_"+str(i_p)))
    if len(neg_beds)>0:
        peaks.append(bedsToPeak(neg_beds,"n_"+str(i_n)))
    peaks.sort()
    return peaks

def bedsToPeak(ibeds,id):
    peak=Bed([ibeds[0].chr,ibeds[0].start,ibeds[0].stop,id,float(ibeds[0].score),ibeds[0].strand])
    for i in ibeds[1:]:
        peak.score=float(peak.score*len(peak)+i.score*len(i))/(len(peak)+len(i))
        peak.stop=i.stop
    return peak



        

    
if __name__=="__main__":
    Main()









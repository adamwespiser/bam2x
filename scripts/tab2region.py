#!/usr/bin/python
# programmer : zhuxp
# usage:
import sys
from getopt import getopt
def show_help():
    print >>sys.stderr,"tab2region.py: extract region from table file generated by bam2tab.py"
    print >>sys.stderr,"Usage: tab2region.py -r chr:start-stop file.tab > file.region.tab"
    print >>sys.stderr,"\nOptions:"
    print >>sys.stderr,"\t-h                    show this message"
    print >>sys.stderr,"\t-r chr:start-stop     select regions"
    print >>sys.stderr,"\t-r chr                select chromosome"
    exit()
def parse(a):
    MAX=10000000000
    b=a.split(":")
    chr=b[0]
    if len(b)>1:
        c=b[1].split("-")
    else:
        c=[0,MAX]
    return (chr,int(c[0]),int(c[1]))
def Main():
    opts,restlist = getopt(sys.argv[1:],"r:h",\
                        ["region=","help"])
    for o, a in opts:
        if o in ("-h","--help"): show_help()
        if o in ("-r","--region"):
            region=a
            (chr,start,end)=parse(region)
    table_file=restlist[0]
    try: 
      f=open(table_file)
    except:
      print >>sys.stderr,"can't open file ",table_file
    for line in f:
      line=line.strip()
      if line[0]=="#":
          print line
          continue
      a=line.split("\t")
      t_chr=a[0].strip()
      t_start=int(a[1])
      t_end=int(a[2])
      if t_chr!=chr: continue
      if t_end<=start: continue
      if t_start>=end: continue
      print line

    



    
if __name__=="__main__":
    Main()

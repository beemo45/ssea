'''
Created on Dec 2, 2013

@author: mkiyer
'''
import os
import logging
import argparse
import json
from datetime import datetime
from time import time
# third-party packages
import numpy as np
# local imports
from ssea.lib.base import WeightMethod, WEIGHT_METHODS, WEIGHT_METHOD_STR

def timestamp():
    return datetime.fromtimestamp(time()).strftime('%Y-%m-%d-%H-%M-%S-%f')

class Config(object):
    # constants
    MAX_ES_POINTS = 100
    NUM_NULL_ES_BINS = 101
    NULL_ES_BINS = np.linspace(-1.0, 1.0, num=NUM_NULL_ES_BINS)
    DEFAULT_SMIN = 1
    DEFAULT_SMAX = 0
    DEFAULT_NA_VALUE = 'NA'
    SAMPLES_JSON_FILE = 'samples.json'
    METADATA_JSON_FILE = 'metadata.json'
    SAMPLE_SETS_JSON_FILE = 'sample_sets.json'
    CONFIG_JSON_FILE = 'config.json'
    MATRIX_DIR = 'matrix'
    RESULTS_JSON_FILE = 'results.json'
    OUTPUT_HISTS_FILE = 'hists.npz'
    TMP_DIR = 'tmp'
    LOG_DIR = 'log'
    
    def __init__(self):
        self.num_processes = 1
        self.output_dir = "SSEA_%s" % (timestamp())
        self.name = 'myssea'
        self.perms = 1000
        self.resampling_iterations = 100
        self.weight_miss = WeightMethod.LOG
        self.weight_hit = WeightMethod.LOG
        self.weight_param = 1.0
        self.noise_loc = 1.0
        self.noise_scale = 1.0
        self.smin = Config.DEFAULT_SMIN
        self.smax = Config.DEFAULT_SMAX
        self.smx_files = []
        self.smt_files = []
        self.col_metadata_file = None
        self.row_metadata_file = None
        self.matrix_dir = None
        self.matrix_tsv_file = None
        self.matrix_na_values = [Config.DEFAULT_NA_VALUE]
        # for running on pbs cluster
        self.cluster = None
        self.pbs_script = None

    def to_json(self):
        return json.dumps(self.__dict__)
    
    @staticmethod
    def from_json(s):
        c = Config()
        d = json.loads(s)
        c.__dict__ = d
        return c
    
    @staticmethod
    def from_dict(d):
        c = Config()
        c.__dict__ = d
        return c

    @staticmethod
    def parse_json(filename):
        with open(filename, 'r') as fp:
            line = fp.next()
            return Config.from_json(line.strip())

    def get_argument_parser(self, parser=None):
        if parser is None:
            parser = argparse.ArgumentParser()            
        parser.add_argument("-v", "--verbose", dest="verbose", 
                            action="store_true", default=False, 
                            help="set verbosity level [default: %(default)s]")
        grp = parser.add_argument_group('Output Options')
        grp.add_argument('-o', '--output-dir', dest="output_dir", 
                         help='Output directory [default=%(default)s]')
        grp.add_argument('-n', '--name', dest="name", default=self.name,
                         help='Analysis name [default=%(default)s]')        
        grp = parser.add_argument_group('Cluster Computing Options')
        grp.add_argument('-p', '--num-processes', dest='num_processes',
                         type=int, default=1,
                         help='Number of processor cores available '
                         '[default=%(default)s]')
        clustergrp = grp.add_mutually_exclusive_group()
        clustergrp.add_argument('--cluster', dest='cluster', 
                                action='store_const', const='setup',
                                help='set to run SSEA on a cluster using PBS')
        clustergrp.add_argument('--cluster-map', dest='cluster',
                                action='store_const', const='map',
                                help='[for internal use only]') 
        clustergrp.add_argument('--cluster-reduce', dest='cluster',
                                action='store_const', const='reduce',
                                help='[for internal use only]')
        grp.add_argument('--pbs-script', dest='pbs_script',
                         default=None,
                         help='Shell script containing PBS configuration '
                         'commands')
        grp = parser.add_argument_group("SSEA Options")
        grp.add_argument('--perms', type=int, default=self.perms,
                         help='Number of permutations '
                         '[default=%(default)s]')
        grp.add_argument('--weight-miss', dest='weight_miss',
                         choices=WEIGHT_METHODS.keys(), 
                         default='log',
                         help='Weighting method for elements not in set ' 
                         '[default=%(default)s]')
        grp.add_argument('--weight-hit', dest='weight_hit', 
                         choices=WEIGHT_METHODS.keys(), 
                         default='log',
                         help='Weighting method for elements in set '
                         '[default=%(default)s]')
        grp.add_argument('--weight-param', dest='weight_param', type=float, 
                         default=self.weight_param,
                         help='Either log2(n + X) for log transform or '
                         'pow(n,X) for exponential (root) transform '
                         '[default=%(default)s]')
        grp.add_argument('--smin', dest="smin", type=int,
                         default=self.smin, metavar="N",
                         help='Exclude sample sets smaller than N '
                         'from the analysis [default=%(default)s]')
        grp.add_argument('--smax', dest="smax", type=int,
                            default=self.smax, metavar="N",
                            help='Exclude sample sets larger than N '
                            'from the analysis [default=%(default)s]')
        grp.add_argument('--smx', dest="smx_files", action='append',
                            help='File(s) containing sets in column format')
        grp.add_argument('--smt', dest="smt_files", action='append',
                            help='File(s) containing sets in row format')
        grp.add_argument('--colmeta', dest='col_metadata_file',
                            help='file containing metadata corresponding to each '
                            'column of the weight matrix file')
        grp.add_argument('--rowmeta', dest='row_metadata_file',
                            help='file containing metadata corresponding to each '
                            'row of the weight matrix file')
        grp.add_argument('--na-value', dest='matrix_na_values', 
                            default=self.matrix_na_values, action='append',
                            help='Value to interpret as missing/invalid '
                            'in weight matrix [default=%(default)s]')
        grp2 = grp.add_mutually_exclusive_group()
        grp2.add_argument('--tsv', dest='tsv_file', default=None, 
                         help='Tab-delimited text file containing data matrix')
        grp2.add_argument('--matrix', dest='matrix_dir', default=None, 
                         help='Directory with binary memory-mapped matrix files')
        return parser

    def log(self, log_func=logging.info):
        log_func("Parameters")
        log_func("----------------------------------")
        log_func("name:                    %s" % (self.name))
        log_func("num processes:           %d" % (self.num_processes))
        log_func("permutations:            %d" % (self.perms))
        log_func("weight method miss:      %s" % (WEIGHT_METHOD_STR[self.weight_miss]))
        log_func("weight method hit:       %s" % (WEIGHT_METHOD_STR[self.weight_hit]))
        log_func("weight param:            %f" % (self.weight_param))
        log_func("output directory:        %s" % (self.output_dir))
        log_func("input matrix directory:  %s" % (self.matrix_dir))
        log_func("----------------------------------")

    @staticmethod
    def parse_args(parser=None):
        # create Config instance
        self = Config()
        # parse command line arguments
        parser = self.get_argument_parser(parser)
        args = parser.parse_args()
        # setup logging
        if (args.verbose > 0):
            level = logging.DEBUG
        else:
            level = logging.INFO
        logging.basicConfig(level=level,
                            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        # get cluster arguments
        self.cluster = args.cluster
        # if in cluster mode only process relevant arguments
        if self.cluster is not None:
            if self.cluster != 'setup':
                self.output_dir = os.path.abspath(args.output_dir)
                if not os.path.exists(self.output_dir):
                    parser.error("output directory '%s' not found by cluster map/reduce" % (self.output_dir))
                return self
        # not in cluster map/reduce mode
        if args.pbs_script is not None:
            if not os.path.exists(args.pbs_script):
                parser.error("pbs script '%s' not found" % (args.pbs_script))
        self.pbs_script = args.pbs_script
        # output directory
        self.output_dir = os.path.abspath(args.output_dir)
        if os.path.exists(self.output_dir):
            parser.error("output directory '%s' already exists" % 
                         (self.output_dir))
        # process and check arguments
        self.name = args.name
        self.num_processes = args.num_processes
        self.perms = max(1, args.perms)
        # sample set size limits
        self.smin = max(1, args.smin)
        self.smax = max(0, args.smax)        
        # check weight methods
        if isinstance(args.weight_miss, basestring):
            self.weight_miss = WEIGHT_METHODS[args.weight_miss]
        if isinstance(args.weight_hit, basestring):
            self.weight_hit = WEIGHT_METHODS[args.weight_hit]
        self.weight_param = args.weight_param        
        if self.weight_param < 0.0:
            parser.error('weight param < 0.0 invalid')
        elif ((self.weight_miss == 'log' or self.weight_hit == 'log')):
            if self.weight_param < 1.0:
                parser.error('weight param %f < 1.0 not allowed with '
                             'log methods' % (self.weight_param))
        # matrix input directory
        if args.matrix_dir is not None:
            if not os.path.exists(args.matrix_dir):
                parser.error('matrix path "%s" not found' % (args.matrix_dir))
            self.matrix_dir = os.path.abspath(args.matrix_dir)
        if args.tsv_file is not None:
            if not os.path.exists(args.tsv_file):
                parser.error('matrix tsv file "%s" not found' % (args.tsv_file))
            self.matrix_tsv_file = args.tsv_file
            self.matrix_na_values = args.matrix_na_values
            self.matrix_dir = os.path.join(os.path.abspath(self.output_dir), Config.MATRIX_DIR)
        # check metadata
        if args.row_metadata_file is not None:
            if not os.path.exists(args.row_metadata_file):
                parser.error('row metadata file "%s" not found' % (args.row_metadata_file))
            self.row_metadata_file = os.path.abspath(args.row_metadata_file)
        if args.col_metadata_file is not None:
            if not os.path.exists(args.col_metadata_file):
                parser.error('col metadata file "%s" not found' % (args.col_metadata_file))
            self.col_metadata_file = os.path.abspath(args.col_metadata_file)
        # check sample sets
        if args.smx_files is not None:
            for filename in args.smx_files:
                if not os.path.exists(filename):
                    parser.error("smx file '%s' not found" % (filename))
                self.smx_files.append(filename)
        if args.smt_files is not None:
            for filename in args.smt_files:
                if not os.path.exists(filename):
                    parser.error("smt file '%s' not found" % (filename))
                self.smt_files.append(filename)
        if len(self.smx_files) == 0 and len(self.smt_files) == 0:
            parser.error("No sample sets specified")
        return self
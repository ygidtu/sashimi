#!/usr/bin/env python3
# -*- coding:utf-8 -*-
u"""
This file contains the object to handle bam file related issues.

changelog:
    1. add library parameter for determining of read strand at 2022.4.28.

"""
import gzip
import os
from typing import Optional, Set

import numpy as np
import pysam
from loguru import logger

from sashimi.base.GenomicLoci import GenomicLoci
from sashimi.base.Junction import Junction
from sashimi.base.ReadDepth import ReadDepth
from sashimi.base.Readder import Reader
from sashimi.file.File import SingleCell


class Bam(SingleCell):
    def __init__(self,
                 path: str, label: str = "",
                 title: str = "", barcodes: Optional[Set[str]] = None,
                 barcode_tag: str = "CB", umi_tag: str = "UB",
                 library: str = "fru", density_by_strand: bool = False):
        u"""
        init this object
        :param label: the left axis label
        :param title: the default title to show in the upper-right of density plot
        :param barcodes: the path to barcodes,
                default: ../filtered_feature_bc_matrix/barcodes.tsv.gz of bam file according to 10X Genomics
        :param barcode_tag: the cell barcode tag, default is CB according to 10X Genomics
        :param umi_tag: the UMI barcode tag, default is UB according to 10X Genomics
        :param library: library for determining of read strand.
        :param density_by_strand: whether to draw density plot in strand-specific manner.
        """
        super().__init__(path, barcodes, barcode_tag, umi_tag)
        self.title = title
        self.label = label if label else os.path.basename(path).replace(".bam", "")
        self.library = library
        self.density_by_strand = density_by_strand

    @classmethod
    def create(cls,
               path: str,
               label: str = "",
               title: str = "",
               barcodes: Optional[Set[str]] = None,
               barcode_tag: str = "CB",
               umi_tag: str = "UB",
               library: str = "fru"
               ):
        u"""

        :param path: the path to bam file
        :param label: the left axis label
        :param title: the default title to show in the upper-right of density plot
        :param barcodes: the path to barcodes,
                default: ../filtered_feature_bc_matrix/barcodes.tsv.gz of bam file according to 10X Genomics
        :param barcode_tag: the cell barcode tag, default is CB according to 10X Genomics
        :param umi_tag: the UMI barcode tag, default is UB according to 10X Genomics
        :param library: library for determining of read strand.
        :return:
        """

        if not os.path.exists(path + ".bai"):
            pysam.index(path)

        barcode = barcodes
        path = os.path.abspath(path)
        if not barcodes:
            barcode = set()
            barcodes = os.path.join(os.path.dirname(path), "filtered_feature_bc_matrix/barcodes.tsv.gz")

            if os.path.exists(barcodes):
                with gzip.open(barcodes, "rt") as r:
                    for line in r:
                        barcode.add(line.strip())
        return cls(
            path=path,
            label=label,
            title=title,
            barcodes=barcode,
            barcode_tag=barcode_tag,
            umi_tag=umi_tag,
            library=library
        )

    def __hash__(self):
        return hash(self.label)

    def __str__(self) -> str:

        temp = []

        for x in [self.title, self.label, self.path]:
            if x is None or x == "":
                x = "None"
            temp.append(str(x))

        return "\t".join(temp)

    def to_csv(self) -> str:
        temp = []

        for x in [self.title, self.label, self.path]:
            if x is None or x == "":
                x = "None"
            if isinstance(x, list):
                x = ";".join(x)
            temp.append(str(x))

        return ",".join(temp)

    def load(self,
             region: GenomicLoci,
             threshold: int = 0,
             reads1: Optional[bool] = None,
             required_strand: Optional[str] = None,
             log_trans: Optional[str] = None,
             **kwargs
             ):
        """
            determine_depth determines the coverage at each base between start_coord and end_coord, inclusive.

            bam_file_path is the path to the bam file used to \
            determine the depth and junctions on chromosome between start_coord and end_coord

        return values:
            depth_vector,
            which is a Numpy array which contains the coverage at each base position between start_coord and end_coord

            spanned_junctions, which is a dictionary containing the junctions supported by reads.
            The keys in spanned_junctions are the
                names of the junctions, with the format chromosome:lowerBasePosition-higherBasePosition
        :param region: GenomicLoci object including the region for calculating coverage
        :param threshold: minimums counts of the given splice junction for visualization
        :param reads1: None -> all reads, True -> only R1 kept; False -> only R2 kept
        :param required_strand: None -> all reads, else reads on specific strand
        :param log_trans: should one of {"10": np.log10, "2": np.log2}
        """
        self.region = region
        self.log_trans = log_trans
        filtered_junctions = {}

        spanned_junctions = kwargs.get("junctions", {})
        included_junctions = kwargs.get("included_junctions", {})
        remove_duplicate_umi = kwargs.get("remove_duplicate_umi", False)
        spanned_junctions_plus = dict()
        spanned_junctions_minus = dict()
        plus, minus = np.zeros(len(region), dtype="f"), np.zeros(len(region), dtype="f")
        site_plus, site_minus = np.zeros(len(region), dtype="f"), np.zeros(len(region), dtype="f")

        umis = {}

        try:
            for read, strand in Reader.read_bam(path=self.path, region=region, library=self.library):
                # make sure that the read can be used
                cigar_string = read.cigartuples

                # each read must have a cigar string
                if cigar_string is None:
                    continue

                # select R1 or R2
                if reads1 is True and not read.is_read1:
                    continue

                if reads1 is False and not read.is_read2:
                    continue

                # filter reads by 10x barcodes
                # @20220924, add `not` before has_barcode and skip these reads without umi tag.
                if self.barcodes:
                    if not read.has_tag(self.barcode_tag) or not self.has_barcode(read.get_tag(self.barcode_tag)):
                        continue

                    if remove_duplicate_umi:
                        barcode = read.get_tag(self.barcode_tag)
                        if barcode not in umis.keys():
                            umis[barcode] = {}

                        # filter reads with duplicate umi by barcode
                        if read.has_tag(self.umi_tag):
                            umi = read.get_tag(self.umi_tag)

                            if umi in umis[barcode].keys() and umis[barcode][umi] != hash(read.query_name):
                                continue

                            if len(umis[barcode]) == 0:
                                umis[barcode][umi] = hash(read.query_name)
                        else:
                            continue

                start = read.reference_start
                if required_strand and strand != required_strand:
                    continue

                """
                M	BAM_CMATCH	0
                I	BAM_CINS	1
                D	BAM_CDEL	2
                N	BAM_CREF_SKIP	3
                S	BAM_CSOFT_CLIP	4
                H	BAM_CHARD_CLIP	5
                P	BAM_CPAD	6
                =	BAM_CEQUAL	7
                X	BAM_CDIFF	8
                B	BAM_CBACK	9
                """
                for cigar, length in cigar_string:
                    cur_start = start + 1
                    cur_end = start + length + 1

                    if cigar == 0:  # M
                        for i in range(length):
                            if region.start <= start + i + 1 <= region.end:
                                try:
                                    if strand == "+":
                                        plus[start + i + 1 - region.start] += 1
                                    elif strand == "-":
                                        minus[start + i + 1 - region.start] += 1
                                    else:
                                        pass
                                except IndexError as err:
                                    logger.info(region)
                                    logger.info(cigar_string)
                                    logger.info(start, i)
                                    exit(err)

                    # remove the deletion.
                    if cigar not in (1, 4, 5):  # I, S, H
                        start += length

                    if cigar == 3:  # N
                        try:
                            junction_name = Junction(region.chromosome, cur_start, cur_end)
                            if str(junction_name) not in included_junctions and len(included_junctions) != 0:
                                continue

                            if junction_name not in spanned_junctions:
                                spanned_junctions[junction_name] = 0

                            spanned_junctions[junction_name] = spanned_junctions[junction_name] + 1
                        except ValueError as err:
                            logger.warning(err)
                            continue
                start = read.reference_start + 1 if read.reference_start + 1 > region.start else region.start
                end = read.reference_end + 1 if read.reference_end + 1 < region.end else region.end
                if strand == "+" and 0 <= start - region.start < len(plus):
                    site_plus[end - region.start] += 1
                elif strand == "-" and 0 <= end - region.start < len(minus):
                    site_minus[start - region.start] += 1

            for k, v in spanned_junctions.items():
                if v >= threshold:
                    filtered_junctions[k] = v

                    if k.strand == "-":
                        if k not in spanned_junctions_plus:
                            spanned_junctions_plus[k] = -1
                        else:
                            spanned_junctions_plus[k] += -1
                    elif k.strand == "+":
                        if k not in spanned_junctions_minus:
                            spanned_junctions_minus[k] = -1
                        else:
                            spanned_junctions_minus[k] += -1
        except IOError as err:
            logger.error('There is no .bam file at {0}'.format(self.path))
            logger.error(err)
        except ValueError as err:
            logger.error(self.path)
            logger.error(err)

        self.data = ReadDepth(
            plus,
            junctions_dict=filtered_junctions,
            site_plus=site_plus,
            site_minus=site_minus,
            minus=minus,
            junction_dict_plus=spanned_junctions_plus,
            junction_dict_minus=spanned_junctions_minus,
            strand_aware=False if self.library == "fru" else True)
        return self


if __name__ == '__main__':
    bam = Bam.create(
        "../../example/bams/sc.bam",
        library="frf")
    bam.load(GenomicLoci("chr1", 1270656, 1284730, "+"), 10)

    print(str(bam))
    print(bam.to_csv())
    print(max(bam.data.wiggle), min(bam.data.wiggle))
    print(bam.data.junctions_dict)
    print(max(bam.data.plus))
    print(min(bam.data.minus))
    print(max(bam.data.site_plus))
    print(min(bam.data.site_minus))
    pass

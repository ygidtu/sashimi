#!/usr/bin/env python3
# -*- coding:utf-8 -*-
u"""
Created by ygidtu@gmail.com at 2019.12.06
"""

from src.GenomicLoci import GenomicLoci


class Transcript(GenomicLoci):
    u"""
    Created by ygidtu at 2018.12.21

    A class inherit from GenomicLoci, to collect transcript information.

    Add extending for domain region. Ran

    """

    __slots__ = [
        "gene",
        "gene_id",
        "transcript",
        "transcript_id",
        "exons",
        "is_reads",
        "show_id",
        "category",
        "domain"
    ]

    def __init__(
            self,
            chromosome: str,
            start: int,
            end: int,
            strand: str,
            exons: list,
            gene: str = "",
            gene_id: str = "",
            transcript: str = "",
            transcript_id: str = "",
            category: str = "exon",
            domain: str = "",
            is_reads: bool = False,
            show_id: bool = False
    ):
        u"""

        :param chromosome:
        :param start:
        :param end:
        :param strand:
        :param exons: A list of pysam.GTFProxy if category was exon, A nested tuple of list if category was protein
        :param gene: gene name when category is exon,such as "SAMD11"; domain's description when category is domain such as "Disordered"
        :param gene_id: gene id, such as "ENSG00000187634"
        :param transcript: transcript name, such as "SAMD11-011"
        :param transcript_id: transcript id, such as "ENST00000420190"
        :param category: exon or protein
        :param domain: if category is protein, the type information of the given domain
        :param is_reads:
        :param show_id:
        """

        super().__init__(
            chromosome=chromosome,
            start=start,
            end=end,
            strand=strand
        )
        self.transcript = transcript
        self.transcript_id = transcript_id
        self.gene = gene
        self.gene_id = gene_id
        self.exons = exons
        self.is_reads = is_reads
        self.show_id = show_id
        self.category = category
        self.domain = domain

    @property
    def exon_list(self):

        exon_nested_lst = []
        for i in self.exons:
            exon_nested_lst.append(
                tuple(
                    [i.start + 1,
                     i.end]
                )
            )
        return exon_nested_lst

    def __str__(self):
        exons_str = []
        for i in self.exons:
            exons_str.append("{}-{}".format(i.start, i.end))

        return "{}:{}-{}:{} {} {}".format(
            self.chromosome,
            self.start,
            self.end,
            self.strand,
            self.transcript,
            "|".join(exons_str)
        )

    def __hash__(self):
        exons = sorted([str(x.__hash__()) for x in self.exons])
        return hash((self.chromosome, self.start, self.end, self.strand, " ".join(exons)))


if __name__ == "__main__":
    pass

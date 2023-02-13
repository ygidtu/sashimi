#!/usr/bin/pyton3
# -*- coding:utf-8 -*-
u"""

"""
import os

from sashimi.base.GenomicLoci import GenomicLoci
from sashimi.base.Readder import Reader
from sashimi.file.File import File


class Motif(File):

    __slots__ = "path", "region", "label", "data"

    def __init__(self,
                 path: str,
                 region: GenomicLoci,
                 ):
        u"""
        the plot region
        """
        super().__init__(path, region=region)
        self.data = {}  # List[List[base, score]]

    @classmethod
    def create(cls, path: str, region: GenomicLoci):
        assert os.path.exists(path), f"{path} is not exists."
        return cls(path=path, region=region)

    def load(self, region: GenomicLoci, **kwargs):
        data = {}
        keys = ["A", "T", "C", "G"]
        for record in Reader.read_depth(self.path, region):
            start = record[1]
            data[int(start)] = {x: float(y) for x, y in zip(keys, record[3:7])}
        self.data = data


if __name__ == '__main__':
    pass

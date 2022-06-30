#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"""
Created at 2022.05.31

This script contains all the command line parameters
"""
import gzip
import os

from multiprocessing import cpu_count
from typing import Optional, Dict, Set

import click
import matplotlib as mpl
import matplotlib.font_manager

from click_option_group import optgroup

from conf.logger import init_logger, logger
from conf.config import CLUSTERING_METHOD, COLORS, COLORMAP, DISTANCE_METRIC, IMAGE_TYPE
from sashimi.plot import Plot

mpl.use('Agg')
mpl.rcParams['pdf.fonttype'] = 42

if any(["Arial" in f.name for f in matplotlib.font_manager.fontManager.ttflist]):
    mpl.rcParams['font.family'] = 'Arial'


def decode_region(region: str):
    regions = region.split(":")

    if len(regions) < 3:
        strand = "+"
    else:
        strand = regions[-1]

    sites = [int(x) for x in regions[1].split("-")]
    return regions[0], sites[0], sites[1], strand


class FileList(object):
    def __init__(self,
                 path: str,
                 category: str,
                 color: str = "black",
                 label: Optional[str] = None,
                 group: Optional[str] = None,
                 library: str = "fr-unstrand"):
        self.path = os.path.abspath(path)
        self.label = label if label else os.path.basename(path)
        self.group = group
        self.color = color
        self.category = category
        self.library = library

    def __str__(self):
        return f"path: {self.path} \nlabel: {self.label} \ngroup: {self.group} \n" \
               f"color: {self.color} \ncategory: {self.category} \nlibrary: {self.library}"


def load_barcodes(barcode: str) -> Dict[str, Dict[str, Set[str]]]:
    u"""
    as name says
    :param barcode: the path to barcode file
    """
    r = gzip.open(barcode, "rt") if barcode.endswith(".gz") else open(barcode, "r")
    res = {}
    for line in r:
        line = line.strip().split()
        if len(line) >= 3:
            key, bc, group = line
        elif len(line) == 2:
            key, bc = line
            group = ""
        else:
            continue

        if key not in res.keys():
            res[key] = {}

        if group not in res[key]:
            res[key][group] = set()

        res[key][group].add(bc)

    r.close()
    return res


def process_file_list(infile: str, category: str = "density"):
    u"""
    Process and check the file list format
    :param infile: path to input file list
    :param category: the image type of file list used for
    """

    if category in ["density", "igv"]:
        with open(infile) as r:
            for idx, line in enumerate(r):
                if line.startswith("#"):
                    continue
                line = line.split()
                path, category = line[0], line[1]

                if category not in ["bam", "bigwig", "bw", "depth", "igv"]:
                    raise ValueError(f"{category} is not supported in density plot.")

                if len(line) < 3:
                    yield FileList(path=path, category=category, color=COLORS[idx % len(COLORS)])
                elif len(line) < 4:
                    yield FileList(path=path, category=category, color=COLORS[idx % len(COLORS)], label=line[2])
                elif len(line) < 5:
                    yield FileList(path=path, category=category, color=line[3], label=line[2])
                else:
                    yield FileList(path=path, category=category, color=line[3], label=line[2], library=line[4])
    elif category in ["heatmap"]:
        groups = {}
        with open(infile) as r:
            for idx, line in enumerate(r):
                if line.startswith("#"):
                    continue
                line = line.split()
                path, category = line[0], line[1]

                if category not in ["bam", "bigwig", "bw", "depth"]:
                    raise ValueError(f"{category} is not supported in density plot.")

                if len(line) < 3:
                    yield FileList(path=path, category=category, color=COLORMAP[0])
                elif len(line) < 4:
                    groups[line[2]] = 0
                    yield FileList(path=path, category=category,
                                   color=COLORMAP[len(groups) % len(COLORMAP)], group=line[2])
                else:
                    groups[line[2]] = 0
                    yield FileList(path=path, category=category,
                                   color=line[3], group=line[2], library=line[4] if len(line) > 4 else "fr-unstrand")

    elif category in ["line"]:
        groups = {}
        with open(infile) as r:
            for idx, line in enumerate(r):
                if line.startswith("#"):
                    continue
                line = line.split()
                path, category = line[0], line[1]

                if category not in ["bam", "bigwig", "bw", "depth"]:
                    raise ValueError(f"{category} is not supported in density plot.")

                if len(line) < 3:
                    yield FileList(path=path, category=category, color=COLORS[idx % len(COLORS)])
                elif len(line) < 4:
                    if line[2] not in groups:
                        groups[line[2]] = 0
                    groups[line[2]] += 1
                    yield FileList(path=path, category=category,
                                   color=COLORS[groups[line[2]] % len(COLORS)], group=line[2])
                elif len(line) < 5:
                    if line[2] not in groups:
                        groups[line[2]] = 0
                    groups[line[2]] += 1
                    yield FileList(path=path, category=category, label=line[3],
                                   color=COLORS[groups[line[2]] % len(COLORS)], group=line[2])
                elif len(line) < 6:
                    if line[2] not in groups:
                        groups[line[2]] = 0
                    groups[line[2]] += 1
                    yield FileList(path=path, category=category, label=line[3],
                                   color=line[4], group=line[2])
    elif category in ["interval"]:
        with open(infile) as r:
            for idx, line in enumerate(r):
                if line.startswith("#"):
                    continue
                line = line.split()
                if len(line) < 2:
                    yield FileList(path=line[0], category="interval")
                else:
                    yield FileList(path=line[0], category="interval", label=line[1])
    return None


@click.command(context_settings=dict(help_option_names=['-h', '--help']), )
@click.version_option("0.0.1", message="Current version %(version)s")
@click.option("--debug", is_flag=True, help="enable debug level log")
@click.option("-e", "--event", type=click.STRING, required=True,
              help="Event range eg: chr1:100-200:+")
@optgroup.group("Common input files configuration")
@optgroup.option("--color-factor", default=1, type=click.IntRange(min=1),
                 help="Index of column with color levels (1-based); "
                      "NOTE: LUAD|red -> LUAD while be labeled in plots and red while be the fill color",
                 show_default=True)
@optgroup.group("Output settings")
@optgroup.option("-o", "--output", type=click.Path(),
                 help="Path to output graph file", show_default=True)
@optgroup.option("-d", "--dpi", default=300, type=click.IntRange(min=1, clamp=True),
                 help="The resolution of output file", show_default=True)
@optgroup.option("--raster", is_flag=True, show_default=True,
                 help="The would convert heatmap and side plot to raster image "
                      "(speed up rendering and produce smaller files), only affects pdf, svg and PS")
@optgroup.option("--height", default=0, type=click.IntRange(min=0, clamp=True),
                 help="The height of output file, default adjust image height by content", show_default=True)
@optgroup.option("--width", default=0, type=click.IntRange(min=0, clamp=True),
                 help="The width of output file, default adjust image width by content", show_default=True)
@optgroup.group("Density plot settings")
@optgroup.option("--density", type=click.Path(exists=True),
                 help="""
                 The path to list of input files, a tab separated text file, \b 
                 - 1st column is path to input file, \b
                 - 2nd column is the file category, \b
                 - 3rd column is input file alias (optional), \b
                 - 4th column is color of input files (optional),
                 - 5th column is the library of input file (optional, only required by bam file). \b
                 """)
@optgroup.option("--customized-junction", type=click.STRING, default=None, show_default=True,
                 help="Path to junction table column name needs to be bam name or bam alias.")
@optgroup.option("-t", "--threshold", default=0, type=click.IntRange(min=0, clamp=True),
                 show_default=True, help="Threshold to filter low abundance junctions")
@optgroup.option("--show-side", is_flag=True, type=click.BOOL,
                 show_default=True, help="Whether to draw additional side plot")
@optgroup.option("--side-strand", type=click.Choice(["all", "+", "-"]), default="all", show_default=True,
                 help="Which strand kept for side plot, default use all")
@optgroup.option("--show-junction-num", type=click.BOOL, is_flag=True, show_default=True,
                 help="Whether to show the number of junctions")
@optgroup.group("Reference settings")
@optgroup.option("-r", "--reference", type=click.Path(exists=True),
                 help="Path to gtf file, both transcript and exon tags are necessary")
@optgroup.option("--interval", type=click.Path(exists=True),
                 help="Path to list of interval files in bed format, "
                      "1st column is path to file, 2nd column is the label [optional]")
@optgroup.option("--show-id", is_flag=True, show_default=True, help="Whether show gene id or gene name")
@optgroup.option("--show-exon-id", is_flag=True, show_default=True, help="Whether show gene id or gene name")
@optgroup.option("--no-gene", is_flag=True, type=click.BOOL, show_default=True,
                 help="Do not show gene id next to transcript id")
@optgroup.option("--domain", default=False, is_flag=True, type=click.BOOL, show_default=True,
                 help="Add domain information into reference track")
@optgroup.option("--remove-empty", is_flag=True, type=click.BOOL, show_default=True,
                 help="Whether to plot empty transcript")
@optgroup.option("--transcripts-to-show", default="", show_default=True,
                 help="Which transcript to show, transcript name or id in gtf file, eg: transcript1,transcript2")
@optgroup.option("--ref-color", default="black", type=click.STRING,
                 show_default=True, help="The color of exons")
@optgroup.option("--intron-scale", type=click.FLOAT, default=0.5, help="The scale of intron", show_default=True)
@optgroup.option("--exon-scale", type=click.FLOAT, default=1, help="The scale of exon", show_default=True)
@optgroup.group("Heatmap plot settings")
@optgroup.option("--heatmap", type=click.Path(exists=True),
                 help="""
                 The path to list of input files, a tab separated text file, \b 
                 - 1st column is path to input file, \b
                 - 2nd column is the file category, \b
                 - 3rd column is input file group (optional), \b
                 - 4th column is color platte of corresponding group.
                 """)
@optgroup.option("--clustering", is_flag=True, show_default=True, help="Enable clustering of the heatmap")
@optgroup.option("--clustering-method", type=click.Choice(CLUSTERING_METHOD), default="ward",
                 show_default=True, help="The clustering method for the heatmap files")
@optgroup.option("--distance-metric", type=click.Choice(DISTANCE_METRIC), default="euclidean",
                 show_default=True, help="The clustering method for the heatmap")
@optgroup.group("Line plot settings")
@optgroup.option("--line", type=click.Path(exists=True),
                 help="""
                 The path to list of input files, a tab separated text file, \b 
                 - 1st column is path to input file, \b
                 - 2nd column is the file category, \b
                 - 3rd column is input file group (optional), \b
                 - 4th column is input file alias (optional), 
                 - 5th column is color platte of corresponding group (optional).
                 """)
@optgroup.option("--hide-legend", default=False, is_flag=True, type=click.BOOL, help="Whether to hide legend")
@optgroup.option("--legend-position", default="upper right", type=click.STRING, help="The legend position")
@optgroup.option("--legend-ncol", default=0, type=click.IntRange(min=0, clamp=True),
                 help="The number of columns of legend")
@optgroup.group("IGV settings")
@optgroup.option("--igv", type=click.Path(exists=True),
                 help="""
                 The path to list of input files,
                 The path to list of input files, a tab separated text file, \b 
                 - 1st column is path to input file, \b
                 - 2nd column is the file category, \b
                 - 3rd column is input file alias (optional), \b
                 - 4th column is color of input files (optional),
                 """)
# @optgroup.option("--reads-strand", type=click.Choice(["All", "R1", "R2"]), default="All",
#                  show_default=True, help="Show the reads from specific strand")
@optgroup.option("-T", "--threshold-of-reads", default=0, type=click.IntRange(min=0, clamp=True),
                 show_default=True, help="Threshold to filter low abundance reads for stacked plot")
@optgroup.group("Additional annotation")
@optgroup.option("-f", "--genome", type=click.Path(), default=None,
                 show_default=True, help="Path to genome fasta")
@optgroup.option("--sites", default=None, type=click.STRING,
                 help="Where to plot additional indicator lines, comma separated int")
@optgroup.option("--stroke", type=click.STRING, show_default=True,
                 help="The stroke regions: start1-end1:start2-end2@color-label, "
                      "draw a stroke line at bottom, default color is red")
@optgroup.option("--focus", type=click.STRING, show_default=True, help="The highlight regions: 100-200:300-400")
@optgroup.group("Layout settings")
@optgroup.option("--n-y-ticks", default=4, type=click.IntRange(min=0, clamp=True),
                 help="The number of ticks of y-axis")
@optgroup.option("--distance-ratio", type=click.FLOAT, default=0.3,
                 help="distance between transcript label and transcript line", show_default=True)
@optgroup.option("--reference-scale", type=click.FLOAT, default=.25,
                 help="The size of reference plot in final plot", show_default=True)
@optgroup.option("--stroke-scale", type=click.FLOAT, default=.25,
                 help="The size of stroke plot in final image", show_default=True)
@optgroup.group("Overall settings")
@optgroup.option("--barcode", type=click.Path(), show_default=True,
                 help="Path to barcode list file, At list two columns were required, "
                      "- 1st The name of bam file; \b"
                      "- 2nd the barcode; \b"
                      "- 3rd The group label, optional.")
@optgroup.option("--barcode-tag", type=click.STRING, default="CB", show_default=True,
                 help="The default cell barcode tag label")
@optgroup.option("--umi-tag", type=click.STRING, default="UB", show_default=True,
                 help="The default UMI barcode tag label")
@optgroup.option("--font-size", default=8, type=click.IntRange(min=1, clamp=True),
                 help="The font size of x, y-axis and so on")
@optgroup.option("--reverse-minus", default=False, is_flag=True, type=click.BOOL,
                 help="Whether to reverse strand of bam/reference file")
@optgroup.option("--hide-y-label", default=False, is_flag=True, type=click.BOOL,
                 help="Whether hide y-axis label")
@optgroup.option("--same-y", default=False, is_flag=True, type=click.BOOL,
                 help="Whether different sashimi/line plots shared same y-axis boundaries")
@optgroup.option('--log', type=click.Choice(["0", "2", "10", "zscore"]), default="0",
                 help="y axis log transformed, 0 -> not log transform; 2 -> log2; 10 -> log10")
@optgroup.option("-p", "--process", type=click.IntRange(min=1, max=cpu_count()), default=1,
                 help="How many cpu to use")
@optgroup.option("--title", type=click.STRING, default=None, help="Title", show_default=True)
def main(**kwargs):
    u"""
    Welcome to use sashimi
    \f
    """
    init_logger("DEBUG" if kwargs["debug"] else "INFO")

    for k, v in kwargs.items():
        logger.debug(f"{k} => {v}")

    p = Plot()

    chrom, start, end, strand = decode_region(kwargs["event"])
    p.set_region(chrom, start, end, strand)

    barcodes = None
    if kwargs.get("barcode") and os.path.exists(kwargs.get("barcode")):
        barcodes = load_barcodes(kwargs.get("barcode"))

    # add reference
    for key in kwargs.keys():
        if key in IMAGE_TYPE and kwargs[key] and os.path.exists(kwargs[key]):
            if key == "reference":
                p.set_reference(kwargs["reference"],
                                show_gene=not kwargs["no_gene"],
                                color=kwargs["ref_color"],
                                remove_empty_transcripts=kwargs["remove_empty"],
                                font_size=kwargs["font_size"],
                                show_id=kwargs["show_id"],
                                reverse_minus=kwargs["reverse_minus"],
                                show_exon_id=kwargs["show_exon_id"],
                                transcripts=kwargs["transcripts_to_show"],
                                add_domain=kwargs["domain"]
                                )

            elif key == "interval":
                for f in process_file_list(kwargs[key], key):
                    p.add_interval(f.path, f.label)
            elif key == "density":
                for f in process_file_list(kwargs[key], key):
                    if barcodes and f.label in barcodes.keys() and f.category == "bam":
                        for group, bcs in barcodes[f.label].items():
                            p.add_density(f.path,
                                          category=f.category,
                                          label=f"{f.label} - {group}" if group else f.label,
                                          barcodes=bcs,
                                          barcode_tag=kwargs["barcode_tag"],
                                          umi_tag=kwargs["umi_tag"],
                                          library=f.library,
                                          color=f.color,
                                          font_size=kwargs["font_size"],
                                          show_junction_number=kwargs["show_junction_num"],
                                          n_y_ticks=kwargs["n_y_ticks"],
                                          distance_between_label_axis=kwargs["distance_ratio"],
                                          show_y_label=not kwargs["hide_y_label"],
                                          show_side_plot=kwargs["show_side"],
                                          strand_choice=kwargs["side_strand"])
                    else:
                        p.add_density(f.path,
                                      category=f.category,
                                      label=f.label,
                                      barcode_tag=kwargs["barcode_tag"],
                                      umi_tag=kwargs["umi_tag"],
                                      library=f.library,
                                      color=f.color,
                                      font_size=kwargs["font_size"],
                                      show_junction_number=kwargs["show_junction_num"],
                                      n_y_ticks=kwargs["n_y_ticks"],
                                      distance_between_label_axis=kwargs["distance_ratio"],
                                      show_y_label=not kwargs["hide_y_label"],
                                      show_side_plot=kwargs["show_side"],
                                      strand_choice=kwargs["side_strand"])
            elif key == "heatmap":
                for f in process_file_list(kwargs[key], key):
                    if barcodes and f.label in barcodes.keys() and f.category == "bam":
                        for group, bcs in barcodes[f.label].items():
                            p.add_heatmap(f.path,
                                          category=f.category,
                                          label=f"{f.label} - {group}" if group else f.label,
                                          barcodes=bcs,
                                          group=f.group,
                                          barcode_tag=kwargs["barcode_tag"],
                                          umi_tag=kwargs["umi_tag"],
                                          library=f.library,
                                          color=f.color,
                                          distance_between_label_axis=kwargs["distance_ratio"],
                                          show_y_label=not kwargs["hide_y_label"],
                                          clustering=kwargs["clustering"],
                                          clustering_method=kwargs["clustering_method"],
                                          distance_metric=kwargs["distance_metric"],
                                          font_size=kwargs["font_size"])
                    else:
                        p.add_heatmap(f.path,
                                      category=f.category,
                                      group=f.group,
                                      label=f.label,
                                      barcode_tag=kwargs["barcode_tag"],
                                      umi_tag=kwargs["umi_tag"],
                                      library=f.library,
                                      color=f.color,
                                      distance_between_label_axis=kwargs["distance_ratio"],
                                      show_y_label=not kwargs["hide_y_label"],
                                      clustering=kwargs["clustering"],
                                      clustering_method=kwargs["clustering_method"],
                                      distance_metric=kwargs["distance_metric"],
                                      font_size=kwargs["font_size"])
            elif key == "line":
                for f in process_file_list(kwargs[key], key):
                    if barcodes and f.label in barcodes.keys() and f.category == "bam":
                        for group, bcs in barcodes[f.label].items():
                            p.add_line(f.path,
                                       category=f.category,
                                       label=f"{f.label} - {group}" if group else f.label,
                                       barcodes=bcs,
                                       group=f.group,
                                       barcode_tag=kwargs["barcode_tag"],
                                       umi_tag=kwargs["umi_tag"],
                                       library=f.library,
                                       color=f.color,
                                       distance_between_label_axis=kwargs["distance_ratio"],
                                       show_y_label=not kwargs["hide_y_label"],
                                       font_size=kwargs["font_size"],
                                       n_y_ticks=kwargs["n_y_ticks"],
                                       show_legend=not kwargs["hide_legend"],
                                       legend_position=kwargs["legend_position"],
                                       legend_ncol=kwargs["legend_ncol"])
                    else:
                        p.add_line(f.path,
                                   category=f.category,
                                   group=f.group,
                                   label=f.label,
                                   barcode_tag=kwargs["barcode_tag"],
                                   umi_tag=kwargs["umi_tag"],
                                   library=f.library,
                                   color=f.color,
                                   distance_between_label_axis=kwargs["distance_ratio"],
                                   show_y_label=not kwargs["hide_y_label"],
                                   font_size=kwargs["font_size"],
                                   n_y_ticks=kwargs["n_y_ticks"],
                                   show_legend=not kwargs["hide_legend"],
                                   legend_position=kwargs["legend_position"],
                                   legend_ncol=kwargs["legend_ncol"])
            elif key == "igv":
                for f in process_file_list(kwargs[key], "density"):
                    p.add_igv(f.path,
                              category=f.category,
                              label=f.label,
                              exon_color=f.color,
                              intron_color=f.color)
        elif key == "focus":
            p.add_focus(kwargs[key])
        elif key == "stroke":
            p.add_stroke(kwargs[key])
        elif key == "sites":
            p.add_sites(kwargs[key])

    p.plot(
        kwargs["output"],
        fig_width=kwargs["width"],
        fig_height=kwargs["height"],
        dpi=kwargs["dpi"],
        raster=kwargs["raster"],
        intron_scale=kwargs["intron_scale"],
        exon_scale=kwargs["exon_scale"],
        reference_scale=kwargs["reference_scale"],
        strock_scale=kwargs["stroke_scale"],
        same_y=kwargs["same_y"]
    )


if __name__ == '__main__':
    main()
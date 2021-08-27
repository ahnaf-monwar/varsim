#!/usr/bin/env python

import argparse
import os
import sys
import json
import logging
import shutil
import utils
import re
LOGGER = None

def merge_results(outdir, varsim_tp, varsim_fn, vcfeval_tp,
                  varsim_fp, vcfeval_tp_predict):
    '''
    generate augmented TP, FN, FP
    :param varsim_tp:
    :param varsim_fn:
    :param vcfeval_tp:
    :param varsim_fp:
    :param vcfeval_tp_predict:
    :return:
    '''
    #some implementation philosiphy (subject to change)
    #retain any variant recognized by VarSim (they might not be recognized by vcfeval, e.g. <DUP>)
    #assume variants are uniquely identifiable by chr+pos+ref+alt
    #varsim_tp + vcfeval_tp = augmented_tp
    #varsim_tp + varsim_fn = T
    #T - augmented_tp = augmented_fn
    #varsim_fp - vcfeval_tp_predict = augmented_fp
    augmented_tp = os.path.join(outdir, "merge_tp.vcf")
    augmented_t = os.path.join(outdir, "merge_t.vcf")
    augmented_fn = os.path.join(outdir, "merge_fn.vcf")
    augmented_fp = os.path.join(outdir, "merge_fp.vcf")
    augmented_tp = utils.combine_vcf(augmented_tp, [varsim_tp, vcfeval_tp], duplicate_handling_mode=utils.COMBINE_KEEP_FIRST_DUPLICATE)
    augmented_t = utils.combine_vcf(augmented_t, [varsim_tp, varsim_fn], duplicate_handling_mode=utils.COMBINE_KEEP_FIRST_DUPLICATE)

    #assumption: augmented_tp is subset of augmented_t
    augmented_fn = utils.combine_vcf(augmented_fn, [augmented_t, augmented_tp], duplicate_handling_mode=utils.COMBINE_KEEP_NO_DUPLICATE)
    #assumption: vcfeval_tp_predict is subset of varsim_fp
    augmented_fp = utils.combine_vcf(augmented_fp, [varsim_fp, vcfeval_tp_predict], duplicate_handling_mode=utils.COMBINE_KEEP_NO_DUPLICATE)

    return augmented_tp, augmented_fn, augmented_fp, augmented_t


class VCFComparator(object):
    def __init__(self, prefix, true_vcf, reference, regions, sample, vcfs, exclude_filtered, match_geno, log_to_file, opts, java = "java"):
        self.prefix = prefix
        self.true_vcf = true_vcf
        self.reference = reference
        self.sample = sample
        self.vcfs = vcfs
        self.exclude_filtered = exclude_filtered
        self.match_geno = match_geno
        self.log_to_file = log_to_file
        self.regions = regions
        self.opts = opts #additional options
        self.tp,self.tp_predict,self.fp,self.fn = None, None, None, None
        self.java = java

    def run(self):
        '''
        generate TP, FN, FP
        :return:
        '''
        pass

    def get_tp(self):
        '''
        :return: TP (based on truth) file
        '''
        if not self.tp:
            self.run()
        return self.tp

    def get_tp_predict(self):
        '''
        :return: TP (based on prediction) file
        '''
        if not self.tp_predict:
            self.run()
        return self.tp_predict

    def get_fp(self):
        '''
        :return: FP file
        '''
        if not self.fp:
            self.run()
        return self.fp

    def get_fn(self):
        '''
        :return: FN file
        '''
        if not self.fn:
            self.run()
        return self.fn

class VarSimVCFComparator(VCFComparator):
    def __init__(self, prefix, true_vcf, reference, regions, sample, vcfs, exclude_filtered, disallow_partial_fp, match_geno, log_to_file, opts, java = 'java', sv_length = 100):
        VCFComparator.__init__(self, prefix, true_vcf, reference, regions, sample, vcfs, exclude_filtered, match_geno, log_to_file, opts, java)
        self.disallow_partial_fp = disallow_partial_fp
        self.sv_length = sv_length
    def get_tp_predict(self):
        '''
        varsim does not generate TP based off of predictions
        :return:
        '''
        return None

    def run(self):
        '''

        :return:
        '''
        cmd = [self.java, utils.JAVA_XMX, '-jar', utils.VARSIMJAR, 'vcfcompare',
           '-prefix', self.prefix, '-true_vcf',
           self.true_vcf,
           '-reference', self.reference,
           ]
        if self.exclude_filtered:
            cmd.append('-exclude_filtered')
        if self.match_geno:
            cmd.append('-match_geno')
        if self.sample:
            cmd.append('-sample')
            cmd.append(self.sample)
        if self.regions:
            cmd.append('-bed')
            cmd.append(self.regions)
        if self.disallow_partial_fp:
            cmd.append('-disallow_partial_fp')
        if str(self.sv_length):
            cmd.append('-sv_length {}'.format(self.sv_length))
        if self.opts:
            cmd.append(self.opts)
        cmd.extend(self.vcfs)

        if self.log_to_file:
            with utils.versatile_open(self.log_to_file, 'a') as logout:
                utils.run_shell_command(cmd, sys.stdout, logout)
        else:
            utils.run_shell_command(cmd, sys.stdout, sys.stderr)
        tp = self.prefix + '_TP.vcf'
        fn = self.prefix + '_FN.vcf'
        fp = self.prefix + '_FP.vcf'
        for i in (tp, fn, fp):
            if not os.path.exists(i):
                raise Exception('{0} was not generated by VarSim vcfcompare. Please check and rerun.'.format(i))
        self.tp, self.fn, self.fp = tp, fn, fp

class RTGVCFComparator(VCFComparator):
    def run(self):
        '''

        :return:
        '''
        #command example
        #rtg-tools-3.8.4-bdba5ea_install/rtg vcfeval --baseline truth.vcf.gz \
        #--calls compare1.vcf.gz -o vcfeval_split_snp -t ref.sdf --output-mode=annotate --sample xx --squash-ploidy --regions ?? \
        cmd = [self.java, utils.JAVA_XMX, '-jar', utils.RTGJAR, 'vcfeval',
               '-o', self.prefix, '--baseline',
               self.true_vcf,
               '-t', self.reference,
               ]
        if not self.exclude_filtered:
            cmd.append('--all-records')
        if not self.match_geno:
            cmd.append('--squash-ploidy')
        if self.sample:
            cmd.append('--sample')
            cmd.append(self.sample)
        if self.regions:
            cmd.append('--bed-regions')
            cmd.append(self.regions)
        if self.opts:
            cmd.append(self.opts)
        if len(self.vcfs) != 1:
            raise ValueError('vcfeval only takes 1 prediction VCF and 1 truth VCF: {0}'.format(self.vcfs))
        cmd.append('--calls')
        cmd.append(self.vcfs[0])

        tp = os.path.join(self.prefix, 'tp-baseline.vcf.gz')
        tp_predict = os.path.join(self.prefix, 'tp.vcf.gz')
        fn = os.path.join(self.prefix, 'fn.vcf.gz')
        fp = os.path.join(self.prefix, 'fp.vcf.gz')

        #vcfeval refuses to run if true_vcf contains 0 variants
        if utils.count_variants(self.true_vcf) == 0:
            utils.makedirs([self.prefix])
            #because there is 0 ground truth variants, TP and FN will be empty
            shutil.copyfile(self.true_vcf, tp)
            shutil.copyfile(self.true_vcf, fn)
            if utils.count_variants(self.vcfs[0]) == 0:
                #if calls are empty, then TP_PREDICT and FP will for sure be empty
                shutil.copyfile(self.vcfs[0], tp_predict)
                shutil.copyfile(self.vcfs[0], fp)
            else:
                #if calls are not empty, then all calls will be FP due to 0 ground truth, TP_PREDICT will be empty
                shutil.copyfile(self.vcfs[0], fp)
                with utils.versatile_open(tp_predict, "w") as output, utils.versatile_open(self.vcfs[0], "r") as input:
                    for i in input:
                        if i.startswith('#'):
                            output.write(i)
                        else:
                            break
        else:
            if self.log_to_file:
                with utils.versatile_open(self.log_to_file, 'a') as logout:
                    utils.run_shell_command(cmd, sys.stderr, logout)
            else:
                utils.run_shell_command(cmd, sys.stderr, sys.stderr)
        for i in (tp, tp_predict, fn, fp):
            if not os.path.exists(i):
                raise Exception('{0} was not generated by vcfeval. Please check and rerun.'.format(i))
        self.tp, self.tp_predict, self.fn, self.fp = tp, tp_predict, fn, fp

def generate_sdf(reference, log, java = 'java'):
    '''
    take reference and generate SDF
    :param reference:
    :return:
    '''
    sdf = reference + '.sdf'
    if os.path.exists(sdf):
        LOGGER.info('{0} exists, doing nothing'.format(sdf))
        LOGGER.info('to rerun SDF generation, please remove or rename {0}'.format(sdf))
        return sdf
    cmd = [java, utils.JAVA_XMX, '-jar',utils.RTGJAR,'format',
           '-o', sdf, reference]
    if log:
        with utils.versatile_open(log, 'a') as logout:
            utils.run_shell_command(cmd, logout, logout)
    else:
        utils.run_shell_command(cmd, sys.stdout, sys.stderr)
    return sdf

def process(args):
    '''
    main
    :param args:
    :return:
    '''
    args.java = utils.get_java(args.java)
    utils.check_java(args.java)

    # Setup logging
    FORMAT = '%(levelname)s %(asctime)-15s %(name)-20s %(message)s'
    loglevel = utils.get_loglevel(args.loglevel)
    if args.log_to_file:
        logging.basicConfig(filename=args.log_to_file, filemode="w", level=loglevel, format=FORMAT)
    else:
        logging.basicConfig(level=loglevel, format=FORMAT)

    if len(args.vcfs) > 1:
        raise NotImplementedError('right now only support one prediction VCF. Quick workaround: src/sort_vcf.sh vcf1 vcf2 > merged.vcf')

    global LOGGER
    LOGGER = logging.getLogger(__name__)
    LOGGER.info('working hard ...')

    utils.JAVA_XMX = utils.JAVA_XMX + args.java_max_mem
    args.out_dir = os.path.abspath(args.out_dir)
    args.reference = os.path.abspath(args.reference)
    utils.makedirs([args.out_dir])

    varsim_prefix = os.path.join(args.out_dir, 'varsim_compare_results')
    varsim_comparator = VarSimVCFComparator(prefix=varsim_prefix, true_vcf = args.true_vcf, reference = args.reference,
                                            regions = None,
               sample = args.sample, vcfs = args.vcfs,
               exclude_filtered = args.exclude_filtered,
               disallow_partial_fp = args.disallow_partial_fp,
               match_geno = args.match_geno, log_to_file= args.log_to_file, opts = args.vcfcompare_options, java = args.java,
                                            sv_length=args.sv_length)
    varsim_tp, varsim_fn, varsim_fp = varsim_comparator.get_tp(), varsim_comparator.get_fn(), varsim_comparator.get_fp()
    varsim_tp = utils.sort_and_compress(varsim_tp)
    varsim_fn = utils.sort_and_compress(varsim_fn)
    varsim_fp = utils.sort_and_compress(varsim_fp)
    #run vcfeval
    sdf = args.sdf
    if not sdf:
        LOGGER.info("user did not supply SDF-formatted reference, trying to generate one...")
        sdf = generate_sdf(args.reference, args.log_to_file, java = args.java)

    '''for vcfeval
    sample column must be present, and not empty
    if single-sample vcf, vcfeval doesn't check if samples match in truth and call
    in multi-sample vcf, sample name must be specified
    right now
    '''
    vcfeval_prefix = os.path.join(args.out_dir, 'vcfeval_compare_results')
    if os.path.exists(vcfeval_prefix):
        LOGGER.warn('{0} exists, removing ...'.format(vcfeval_prefix))
        shutil.rmtree(vcfeval_prefix)
    vcfeval_comparator = RTGVCFComparator(prefix=vcfeval_prefix, true_vcf = varsim_fn, reference = sdf,
                                          regions = None,
                                            sample = args.sample, vcfs = [varsim_fp],
                                            exclude_filtered = args.exclude_filtered,
                                            match_geno = args.match_geno, log_to_file= args.log_to_file,
                                          opts = args.vcfeval_options, java = args.java)
    vcfeval_tp, vcfeval_tp_predict = vcfeval_comparator.get_tp(), vcfeval_comparator.get_tp_predict()
    augmented_tp, augmented_fn, augmented_fp, augmented_t = merge_results(
                      outdir = args.out_dir,
                      varsim_tp = varsim_tp, varsim_fn = varsim_fn,
                      vcfeval_tp = vcfeval_tp, varsim_fp = varsim_fp, vcfeval_tp_predict = vcfeval_tp_predict)
    augmented_tp, augmented_fn, augmented_fp, augmented_t = summarize_results(os.path.join(args.out_dir,"augmented"), augmented_tp, augmented_fn, augmented_fp, augmented_t,
                      var_types= args.var_types, sv_length= args.sv_length, regions = args.regions, bed_either = args.bed_either, java = args.java)


    if args.master_vcf and args.call_vcf:
        match_false(augmented_fp, [args.call_vcf, args.master_vcf, augmented_fn], args.out_dir, args.sample, args.log_to_file, args.vcfeval_options, sdf, args.java)
        match_false(augmented_fn, [args.call_vcf], args.out_dir, args.sample, args.log_to_file, args.vcfeval_options, sdf, args.java)

    LOGGER.info("Variant comparison done.\nTrue positive: {0}\nFalse negative: {1}\nFalse positive: {2}\n".
                format(augmented_tp, augmented_fn, augmented_fp))


def match_false(augmented_file, files_to_pair_with, out_dir, sample, log_to_file, vcfeval_options, sdf, java = "java"):
    """Try to pair up each false call in a file (augmented_file) with a variant in the other files provided in a list (files_to_pair_with) to create an annotated version of the first file.
    By default the the first variant in the list is provided to get an AF, the 2nd to determine the simulated variant (for false positives) and the 3rd to determine if a false positive is
    a pure false positive (not simulated) or not (wrong genotype)"""
    files_to_pair_with_clean = []
    for item in files_to_pair_with:
        files_to_pair_with_clean.append(utils.make_clean_vcf(item, out_dir))

    content = []
    annotated_content = []

    with utils.versatile_open(augmented_file, "rt") as augmented_file_handle:
        for line in augmented_file_handle.readlines():
            line_strip = line.strip()
            line_split = line_strip.split()

            if line_strip[0] == "#":
                annotated_content.append(line_strip)
                content.append(line_strip)

            else:
                if content[-1][0] != "#":
                    del content[-1]
                content.append(line_strip)

                single_var_file = utils.write_vcf(content, os.path.join(out_dir, "single.vcf"))
                single_var_file = utils.sort_and_compress(single_var_file)

                single_var_chr = line_split[0]
                info = ''

                for i, item in enumerate(files_to_pair_with_clean):

                    nonmatching_gt_variant = None

                    if item:
                        vcfeval_prefix = os.path.join(out_dir, 'vcfeval_compare_results_annotate')

                        #Restrict the comparison to just the chromosome of the single variant by creating a filtered comparison file
                        filtered_true_vcf = utils.write_filtered_vcf(item, single_var_chr, os.path.join(out_dir, "filtered.vcf"))
                        filtered_true_vcf = utils.sort_and_compress(filtered_true_vcf)

                        vcfeval_comparator = RTGVCFComparator(prefix=vcfeval_prefix, true_vcf = filtered_true_vcf, reference = sdf,
                                         regions = None,
                                         sample = sample, vcfs = [single_var_file],
                                         exclude_filtered = False,
                                         match_geno = False,
                                         log_to_file= log_to_file,
                                         opts = vcfeval_options, java = java)

                        nonmatching_gt_variant = utils.get_closest_variant(line_split, vcfeval_comparator.get_tp())

                        #if not nonmatching_gt_variant, check for matching alt and ref at the same position. Example of when this could be applicable is a 0/0 call when vcfeval will not pair up variants at the same locus with the same alt and ref even with match_geno=False
                        if not nonmatching_gt_variant:
                            nonmatching_gt_variant = utils.get_matching_alt_ref(line_split, filtered_true_vcf)

                        #clean up
                        if os.path.exists(vcfeval_prefix):
                            LOGGER.warn('{0} exists, removing ...'.format(vcfeval_prefix))
                            shutil.rmtree(vcfeval_prefix)

                    if i == 0:
                        AO_RO_DP_AD = {"AO": None, "RO": None, "DP": None, "AD": None}
                        if nonmatching_gt_variant:
                            for entry in AO_RO_DP_AD:
                                AO_RO_DP_AD[entry] = utils.get_info(nonmatching_gt_variant, entry)

                        # gatk4 format
                        if AO_RO_DP_AD["AD"]:
                            AD_split = AO_RO_DP_AD["AD"].split(',')
                            AO = list(map(int, AD_split[1:]))
                            RO = int(AD_split[0])
                            for i, item in enumerate(AO):
                                comma = ',' if i < len(AO)-1 else ''
                                if item+RO == 0:
                                    info += "0.0" + comma

                                else:
                                    info += str(float(item)/(item+RO)) + comma
                        #freebayes
                        elif AO_RO_DP_AD["AO"] and AO_RO_DP_AD["RO"]:
                            for i, item in enumerate(AO_RO_DP_AD["AO"].split(',')):
                                comma = ',' if i < len(AO_RO_DP_AD["AO"].split(','))-1 else ''
                                denominator = int(item)+int(AO_RO_DP_AD["RO"])
                                if denominator == 0:
                                    info += "0.0" + comma

                                else:
                                    info += str(float(item)/denominator) + comma
                        else:
                            info += "N/A"

                        info += ';'
                        info += "N/A" if not AO_RO_DP_AD["DP"] else str(AO_RO_DP_AD["DP"])
                        info += ';'
                    elif i == 1:
                        if nonmatching_gt_variant:
                            info += nonmatching_gt_variant[0]+'_'+nonmatching_gt_variant[1]+'_'+nonmatching_gt_variant[3]+'_'+nonmatching_gt_variant[4]+'_'+nonmatching_gt_variant[-1] + ";"
                        else:
                            info += "N/A;"

                    elif i == 2:
                        info += "pure;" if not nonmatching_gt_variant else "not;"

                line_split[6] = info
                annotated_content.append('\t'.join(line_split))

                #clean up
                for fil in [single_var_file, filtered_true_vcf]:
                    if os.path.isfile(fil):
                        os.remove(fil)
                        os.remove(fil+".tbi")

    annotated_file = utils.write_vcf(annotated_content, os.path.join(args.out_dir, "{}_annotated.vcf".format(os.path.splitext(os.path.splitext(os.path.basename(augmented_file))[0])[0])))
    annotated_file = utils.sort_and_compress(annotated_file)

    #clean up
    for item in files_to_pair_with_clean:
        if item and os.path.isfile(item):
            os.remove(item)
            os.remove(item+".tbi")


def print_stats(stats):
    '''
    print nice stats
    adapted from Roger Liu's code.
    '''
    print ("{0: <15}\t{1: <10}\t{2: <10}\t{3: <10}\t{4: <5}\t{5: <5}\t{6: <5}".format("VariantType","Recall","Precision","F1", "TP","T", "FP"))
    for vartype, value in stats.iteritems():
        try:
            recall = value['tp'] / float(value['t']) if float(value['t']) != 0 else float('NaN')
            precision = float(value['tp']) / (value['tp'] + value['fp']) if value['tp'] + value['fp'] != 0 else float('NaN')
            f1 = float('NaN') if recall == float('NaN') or precision == float('NaN') or (recall + precision) == 0 else 2 * recall * precision / (recall + precision)
        except ValueError:
            sys.stderr.write("invalide values\n")
        #precision 00.00000% to handle (in worst case) 1 out of 3 million mutations in human genome
        print ("{0: <15}\t{1:.5%}\t{2:.5%}\t{3:.5%}\t{4:<5}\t{5:<5}\t{6: <5}".format(vartype, recall, precision, f1, value['tp'], value['t'], value['fp']))

def parse_jsons(jsonfile, stats, count_sv = False, count_all = False):
    '''
    parse json, extract T, TP, FP stats for various variant types
    
    adapted from Roger Liu's code.
    :param jsonfile:
    :param stats:
    :param count_sv:
    :param count_all:
    :return:
    '''
    var_types = stats.keys()
    metrics = stats[var_types[0]].keys()
    with utils.versatile_open(jsonfile, 'r') as fh:
        data = json.load(fh)
        for vt in var_types:
            if vt in data['num_true_correct']['data']:
                for mt in metrics:
                    try:
                        if count_all:
                            stats[vt][mt] += data['num_true_correct']['data'][vt]['sum_count'][mt]
                        elif count_sv:
                            stats[vt][mt] += data['num_true_correct']['data'][vt]['svSumCount'][mt]
                        else:
                            stats[vt][mt] += data['num_true_correct']['data'][vt]['sum_count'][mt]
                            stats[vt][mt] -= data['num_true_correct']['data'][vt]['svSumCount'][mt]
                    except KeyError as err:
                        print ("error in {}. No {} field".format(jsonfile, err))
                        stats[vt][mt] += 0

def summarize_results(prefix, tp, fn, fp, t, var_types, sv_length = 100, regions = None, bed_either = False, java = 'java', bin_breaks = None):
    '''
    count variants by type and tabulate
    :param augmented_tp:
    :param augmented_fn:
    :param augmented_fp:
    :param augmented_t:
    :return:
    '''
    cmd = [java, utils.JAVA_XMX, '-jar', utils.VARSIMJAR, 'vcfcompareresultsparser',
           '-prefix', prefix, '-tp',tp,
           '-fn', fn, '-fp', fp,
           '-t', t, 
           '-sv_length', str(sv_length),
           ]
    if regions:
        cmd = cmd + ['-bed', regions]
    if bed_either:
        cmd = cmd + ['-bed_either']
    if bin_breaks:
            cmd = cmd + ['-bin_breaks', bin_breaks]
    utils.run_shell_command(cmd, cmd_stdout=sys.stdout, cmd_stderr=sys.stderr)

    tp = prefix + "_tp.vcf"
    fn = prefix + "_fn.vcf"
    fp = prefix + "_fp.vcf"
    t = prefix + "_t.vcf"

    tp = utils.sort_and_compress(tp)
    fn = utils.sort_and_compress(fn)
    fp = utils.sort_and_compress(fp)
    t = utils.sort_and_compress(t)

    jsonfile = "{0}_report.json".format(prefix)
    metrics = ['tp', 'fp', 't', 'fn']
    stats = {k: {ii: 0 for ii in metrics} for k in var_types}
    parse_jsons(jsonfile, stats)
    print("Non-SV stats")
    print_stats(stats)
    sv_stats = {k: {ii: 0 for ii in metrics} for k in var_types}
    parse_jsons(jsonfile, sv_stats, count_sv=True)
    print("SV stats")
    print_stats(sv_stats)
    all_stats = {k: {ii: 0 for ii in metrics} for k in var_types}
    parse_jsons(jsonfile, all_stats, count_all=True)
    print("Overall stats")
    print_stats(all_stats)
    return tp, fn, fp, t


if __name__ == "__main__":
    main_parser = argparse.ArgumentParser(description="VarSim: A high-fidelity simulation validation framework",
                                          formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    main_parser.add_argument("--reference", metavar="FASTA", help="reference filename", required=True, type=str)
    main_parser.add_argument("--sdf", metavar="SDF", help="SDF formatted reference folder", required=False, type=str, default='')
    main_parser.add_argument("--out_dir", metavar="OUTDIR", help="output folder", required=True, type=str)
    main_parser.add_argument("--vcfs", metavar="VCF", help="variant calls to be evaluated", nargs="+", default=[], required = True)
    main_parser.add_argument("--var_types", metavar="VARTYPE", help="variant types", nargs="+",
                             default=['SNP','Insertion','Complex','Deletion'],
                             choices = ['SNP', 'Deletion', 'Insertion', 'Inversion', 'TandemDup',
                                       'Complex', 'TransDup', 'TansDel', 'InterDup', 'Translocation'], required = False)
    main_parser.add_argument("--true_vcf", metavar="VCF", help="Input small variant sampling VCF, usually dbSNP", required = True)
    main_parser.add_argument("--master_vcf", metavar="MASTER_VCF", help="Master whitelist, if applicable", required = False)
    main_parser.add_argument("--call_vcf", metavar="CALL_VCF", help="Original, VCF output by variant caller, if applicable", required = False)
    main_parser.add_argument("--regions", help="BED file to restrict analysis [Optional]", required = False, type=str)
    main_parser.add_argument("--sample", metavar = "SAMPLE", help="sample name", required = False, type=str)
    main_parser.add_argument("--exclude_filtered", action = 'store_true', help="only consider variants with PASS or . in FILTER column", required = False)
    main_parser.add_argument("--disallow_partial_fp", action = 'store_true', help="For a partially-matched false negative variant, output all matching variants as false positive", required = False)
    main_parser.add_argument("--match_geno", action = 'store_true', help="compare genotype in addition to alleles", required = False)
    main_parser.add_argument("--sv_length", type = int, help="length cutoff for SV (only effective for counting, not comparison). For comparison, please add -sv_length to --vcfcompare_options.", required = False, default = 100)
    main_parser.add_argument('--version', action='version', version=utils.get_version())
    main_parser.add_argument("--log_to_file", metavar="LOGFILE", help="logfile. If not specified, log to stderr", required=False, type=str, default="")
    main_parser.add_argument("--loglevel", help="Set logging level", choices=["debug", "warn", "info"], default="info")
    main_parser.add_argument("--vcfcompare_options", metavar="OPT", help="additional options for VarSim vcfcompare", default="", type = str)
    main_parser.add_argument("--vcfeval_options", metavar="OPT", help="additional options for RTG vcfeval", default="", type = str)
    main_parser.add_argument("--bed_either", action = 'store_true', help="Use either break-end of the variant for filtering instead of both")
    main_parser.add_argument("--java_max_mem", metavar="XMX", help="max java memory", default="10g", type = str)
    main_parser.add_argument("--java", metavar="PATH", help="path to java", default="java", type = str)
    main_parser.add_argument("--bin_breaks", metavar="INPUT_STR", help="user defined bin breaks", required = False, type = str)

    args = main_parser.parse_args()
    process(args)

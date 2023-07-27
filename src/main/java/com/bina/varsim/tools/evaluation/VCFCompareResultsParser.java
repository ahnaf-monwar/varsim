package com.bina.varsim.tools.evaluation;

import com.bina.varsim.VarSimTool;
import com.bina.varsim.VarSimToolNamespace;
import com.bina.varsim.constants.Constant;
import com.bina.varsim.types.BedFile;
import com.bina.varsim.types.stats.EnumStatsRatioCounter;
import com.bina.varsim.types.stats.StatsNamespace;
import com.bina.varsim.types.variant.Variant;
import com.bina.varsim.types.variant.VariantOverallType;
import com.bina.varsim.util.*;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.commons.io.FileUtils;
import org.apache.log4j.Logger;
import org.kohsuke.args4j.Option;

import java.io.File;
import java.io.IOException;
import java.io.PrintWriter;
import java.util.stream.Stream;

import static com.bina.varsim.types.ComparisonResultWriter.*;


/**
 * counts TP, FN, FP and generate reports
 * <p>
 *
 * @author Yunfei Guo
 */

// TODO this class does not yet compare the contents of the larger variants
    //TODO refactor variable naming
public class VCFCompareResultsParser extends VarSimTool {
    private final static Logger log = Logger.getLogger(VCFCompareResultsParser.class.getName());

    @Option(name = "-tp", usage = "True positive VCF file", metaVar = "file", required = true)
    String tpVcfFilename;

    @Option(name = "-fn", usage = "False negative VCF file", metaVar = "file", required = true)
    String fnVcfFilename;

    @Option(name = "-fp", usage = "False positive VCF file", metaVar = "file", required = true)
    String fpVcfFilename;

    @Option(name = "-t", usage = "truth VCF file", metaVar = "file", required = true)
    String tVcfFilename;

    @Option(name = "-prefix", usage = "prefix for output", metaVar = "string", required = true)
    String outPrefix = null;

    @Option(name = "-html", usage = "Insert JSON to HTML file [Optional, internal]", metaVar = "HTML_file", hidden = true)
    File htmlFile = null;

    @Option(name = "-sv_length", usage = "SV length cutoff", metaVar = "SVLEN", hidden = false)
    public int SVLEN = Constant.SVLEN;

    @Option(name = "-ignore_ins_len", usage = "Ignores insertion length when comparing")
    boolean ignoreInsertionLength = false;

    @Option(name = "-bed", usage = "BED file to restrict the analysis [Optional]", metaVar = "BED_file")
    String bedFilename = null;

    @Option(name = "-bed_either", usage = "Use either break-end of the variant for filtering instead of both")
    boolean bedEither;

    @Option(name = "-bin_breaks", usage = "Bin breaks passed by user, for example pass in '500,1000' as bin_breaks. Then bins wil be 0-500,500-1000, gt1000")
    String binBreaksStr = null;

    int[] BIN_BREAKS = null;

    public VCFCompareResultsParser(final String command, final String description) {
        super(command, description);
    }

    public static int[] StringArrayToIntArray(String[] stringArray)
    {
        return Stream.of(stringArray).mapToInt(Integer::parseInt).toArray();
    }

    public static void main(String[] args) {
        new VCFCompareResultsParser("", VarSimToolNamespace.VCFCompareResultsParser.description).run(args);
    }

    /**
     * Main method
     * first put all true variants into chromosome-indexed interval tree
     * then scan all comparison variants to find overlaps
     *
     */
    public void run(String[] args) {
        if (!parseArguments(args)) {
            return;
        }

        if (binBreaksStr != null && !binBreaksStr.equals("")){
            this.BIN_BREAKS = StringArrayToIntArray(binBreaksStr.split(","));
        }

        outputClass outputBlob = new outputClass();

        outputBlob.setParams(new CompareParams());
        // TODO: make it output the full list if variants in JSON
        outputBlob.setNumberOfTrueCorrect(new EnumStatsRatioCounter<VariantOverallType>(this.SVLEN,this.BIN_BREAKS));
        log.info("Using " + bedFilename + " to intersect.");
        BedFile intersector = bedFilename == null ? null : new BedFile(bedFilename, bedEither);

        countVariants(new countVariantsParameters(StatsNamespace.TP, tpVcfFilename, outputBlob, intersector, ignoreInsertionLength));
        countVariants(new countVariantsParameters(StatsNamespace.FP, fpVcfFilename, outputBlob, intersector, ignoreInsertionLength));
        countVariants(new countVariantsParameters(StatsNamespace.FN, fnVcfFilename, outputBlob, intersector, ignoreInsertionLength));
        countVariants(new countVariantsParameters(StatsNamespace.T, tVcfFilename, outputBlob, intersector, ignoreInsertionLength));

        try(
                PrintWriter jsonWriter = JSON_WRITER.getWriter(outPrefix);) {


            // output the stats
            log.info(outputBlob.getNumberOfTrueCorrect());

            ObjectMapper mapper = new ObjectMapper();
            mapper.configure(JsonGenerator.Feature.AUTO_CLOSE_TARGET, false);

            String jsonStr = "";
            try {
                jsonStr = mapper.writeValueAsString(outputBlob);
                jsonWriter.print(jsonStr);
            } catch (Exception e) {
                e.printStackTrace();
            }

            if (htmlFile != null) {
                try {
                    FileUtils.writeStringToFile(new File(outPrefix + "_varcomp.html"),
                            JSONInserter.insertJSON(FileUtils.readFileToString(htmlFile), jsonStr));
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }

        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
        log.info("Done!"); // used to record the time
    }

    /**
     * count variants per resultClass, optionally filter against a BED file if specified
     *
     * @param countVariantsParameters
     */
    private void countVariants(countVariantsParameters countVariantsParameters) {
        VCFparser vcfParser = new VCFparser(countVariantsParameters.getFilename(), null, false, countVariantsParameters.isIgnoreInsertionLength());
        PrintWriter vcfWriter = null;
        try {
            if (countVariantsParameters.getResultClass() == StatsNamespace.TP) {
                vcfWriter = tp_WRITER.getWriter(outPrefix);
            } else if (countVariantsParameters.getResultClass() == StatsNamespace.T) {
                vcfWriter = t_WRITER.getWriter(outPrefix);
            } else if (countVariantsParameters.getResultClass() == StatsNamespace.FN) {
                vcfWriter = fn_WRITER.getWriter(outPrefix);
            } else if (countVariantsParameters.getResultClass() == StatsNamespace.FP) {
                vcfWriter = fp_WRITER.getWriter(outPrefix);
            } else {
                throw new IllegalArgumentException();
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        vcfWriter.write(new VCFparser(countVariantsParameters.getFilename(), null, false).extractHeader());
        while (vcfParser.hasMoreInput()) {
            Variant currentVariant = vcfParser.parseLine();
            if (countVariantsParameters.getIntersector() != null && currentVariant != null) {
                if (countVariantsParameters.getIntersector().containsEndpoints(currentVariant.getChr(),
                        currentVariant.getGenotypeUnionAlternativeInterval())) {
                } else {
                    currentVariant = null;
                }
            }
            if (currentVariant == null) {
                continue;
            }
            vcfWriter.write(currentVariant.toString() + "\n");
            if (countVariantsParameters.getResultClass() == StatsNamespace.FP) {
                countVariantsParameters.getOutputBlob().getNumberOfTrueCorrect().incFP(currentVariant.getType(), currentVariant.maxLen());
            } else if (countVariantsParameters.getResultClass() == StatsNamespace.TP) {
                countVariantsParameters.getOutputBlob().getNumberOfTrueCorrect().incTP(currentVariant.getType(), currentVariant.maxLen());
                countVariantsParameters.getOutputBlob().getNumberOfTrueCorrect().incT(currentVariant.getType(), currentVariant.maxLen());
            } else if (countVariantsParameters.getResultClass() == StatsNamespace.FN) {
                countVariantsParameters.getOutputBlob().getNumberOfTrueCorrect().incT(currentVariant.getType(), currentVariant.maxLen());
            } else if (countVariantsParameters.getResultClass() == StatsNamespace.T) {
              //do nothing assuming FN+TP=T
            } else {
                throw new IllegalArgumentException();
            }
        }
        vcfWriter.close();
    }
}
class CompareParams {
    @JsonProperty(value = "true_vcf_filename")
    String trueVcfFilename;
    @JsonProperty(value = "new_vcf_filename")
    String newVcfFilename;
    @JsonProperty(value = "overlap_percent")
    Double overlapRatio;
    int wiggle;
    @JsonProperty(value = "bed_filename")
    String bedFilename;

    public CompareParams() {
    }

    public CompareParams(String trueVcfFilename, String newVcfFilename, Double overlapRatio, int wiggle, String bedFilename) {
        this.trueVcfFilename = trueVcfFilename;
        this.newVcfFilename = newVcfFilename;
        this.overlapRatio = overlapRatio;
        this.wiggle = wiggle;
        this.bedFilename = bedFilename;
    }


    public String getTrueVcfFilename() {
        return trueVcfFilename;
    }

    public void setTrueVcfFilename(String trueVcfFilename) {
        this.trueVcfFilename = trueVcfFilename;
    }

    public String getNewVcfFilename() {
        return newVcfFilename;
    }

    public void setNewVcfFilename(String newVcfFilename) {
        this.newVcfFilename = newVcfFilename;
    }

    public Double getOverlapPercent() {
        return overlapRatio;
    }

    public void setOverlapPercent(Double overlapRatio) {
        this.overlapRatio = overlapRatio;
    }

    public int getWiggle() {
        return wiggle;
    }

    public void setWiggle(int wiggle) {
        this.wiggle = wiggle;
    }

    public String getBedFilename() {
        return bedFilename;
    }

    public void setBedFilename(String bedFilename) {
        this.bedFilename = bedFilename;
    }
}
/**
 * This is just for outputting to JSON
 */
class outputClass {
    CompareParams params;
    @JsonProperty(value = "num_true_correct")
    EnumStatsRatioCounter<VariantOverallType> numberOfTrueCorrect;

    outputClass(CompareParams params, EnumStatsRatioCounter<VariantOverallType> numberOfTrueCorrect) {
        this.params = params;
        this.numberOfTrueCorrect = numberOfTrueCorrect;
    }

    outputClass() {
    }

    public CompareParams getParams() {
        return params;
    }

    public void setParams(CompareParams params) {
        this.params = params;
    }

    public EnumStatsRatioCounter<VariantOverallType> getNumberOfTrueCorrect() {
        return numberOfTrueCorrect;
    }

    public void setNumberOfTrueCorrect(EnumStatsRatioCounter<VariantOverallType> numberOfTrueCorrect) {
        this.numberOfTrueCorrect = numberOfTrueCorrect;
    }
}

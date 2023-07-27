package com.bina.varsim.tools.evaluation;

import com.bina.varsim.types.BedFile;
import com.bina.varsim.types.stats.StatsNamespace;

public class countVariantsParameters {
    private final StatsNamespace resultClass;
    private final String filename;
    private final outputClass outputBlob;
    private final BedFile intersector;
    private final boolean ignoreInsertionLength;

    /**
     * @param resultClass class of the file, i.e. true positive, false positive or false negative
     * @param filename VCF containing variants
     * @param intersector BED file object
     */
    public countVariantsParameters(StatsNamespace resultClass, String filename, outputClass outputBlob, BedFile intersector, boolean ignoreInsertionLength) {
        this.resultClass = resultClass;
        this.filename = filename;
        this.outputBlob = outputBlob;
        this.intersector = intersector;
        this.ignoreInsertionLength = ignoreInsertionLength;
    }

    public StatsNamespace getResultClass() {
        return resultClass;
    }

    public String getFilename() {
        return filename;
    }

    public outputClass getOutputBlob() {
        return outputBlob;
    }

    public BedFile getIntersector() {
        return intersector;
    }

    public boolean isIgnoreInsertionLength() {
        return ignoreInsertionLength;
    }
}

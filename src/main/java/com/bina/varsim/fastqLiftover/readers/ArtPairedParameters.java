package com.bina.varsim.fastqLiftover.readers;

import java.io.LineNumberReader;

public class ArtPairedParameters {
    private final LineNumberReader aln1;
    private final LineNumberReader fastq1;
    private final LineNumberReader aln2;
    private final LineNumberReader fastq2;

    public ArtPairedParameters(LineNumberReader aln1, LineNumberReader fastq1, LineNumberReader aln2, LineNumberReader fastq2) {
        this.aln1 = aln1;
        this.fastq1 = fastq1;
        this.aln2 = aln2;
        this.fastq2 = fastq2;
    }

    public LineNumberReader getAln1() {
        return aln1;
    }

    public LineNumberReader getFastq1() {
        return fastq1;
    }

    public LineNumberReader getAln2() {
        return aln2;
    }

    public LineNumberReader getFastq2() {
        return fastq2;
    }
}

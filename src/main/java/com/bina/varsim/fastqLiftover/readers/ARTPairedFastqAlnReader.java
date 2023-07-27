package com.bina.varsim.fastqLiftover.readers;

import com.bina.varsim.fastqLiftover.types.SimulatedRead;
import com.bina.varsim.fastqLiftover.types.SimulatedReadPair;

import java.io.IOException;

public class ARTPairedFastqAlnReader implements PairedFastqReader {
    private ARTFastqAlnReader r1;
    private ARTFastqAlnReader r2;

    public ARTPairedFastqAlnReader(ArtPairedParameters artPairedParameters, boolean forceFiveBaseEncoding) throws IOException {
        r1 = new ARTFastqAlnReader(artPairedParameters.getAln1(), artPairedParameters.getFastq1(), forceFiveBaseEncoding);
        r2 = new ARTFastqAlnReader(artPairedParameters.getAln2(), artPairedParameters.getFastq2(), forceFiveBaseEncoding);
    }

    public SimulatedReadPair getNextReadPair() throws IOException {
        final SimulatedRead read1 = r1.getNextRead();
        final SimulatedRead read2 = r2.getNextRead();

        if (read1 == null || read2 == null) {
            return null;
        }
        return new SimulatedReadPair(read1, read2);
    }
}

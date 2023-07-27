package com.bina.varsim.fastqLiftover.types;

import com.bina.varsim.types.ChrString;

public class MapParameters {
    private final int size;
    private final ChrString srcChr;
    private final int srcLocation;
    private final ChrString dstChr;

    public MapParameters(int size, ChrString srcChr, int srcLocation, ChrString dstChr) {
        this.size = size;
        this.srcChr = srcChr;
        this.srcLocation = srcLocation;
        this.dstChr = dstChr;
    }

    public int getSize() {
        return size;
    }

    public ChrString getSrcChr() {
        return srcChr;
    }

    public int getSrcLocation() {
        return srcLocation;
    }

    public ChrString getDstChr() {
        return dstChr;
    }
}

# References

[Contents](../README.md#contents) · previous: [7. Choosing an architecture](07-choosing.md)

The BibTeX entries are in [`references.bib`](../references.bib).

## Adaptive filtering

<a id="widrow1975"></a>
**[Widrow et al. 1975]** B. Widrow, J. R. Glover, J. M. McCool, J. Kaunitz, C. S. Williams, R. H. Hearn,
J. R. Zeidler, E. Dong and R. C. Goodlin, "Adaptive noise cancelling: Principles and applications,"
*Proceedings of the IEEE*, vol. 63, no. 12, pp. 1692–1716, Dec. 1975. [doi:10.1109/PROC.1975.10036](https://doi.org/10.1109/PROC.1975.10036)
The canceller, the notch with synthetic references and the line enhancer that the six scenarios build on.

<a id="glover1977"></a>
**[Glover 1977]** J. R. Glover, "Adaptive noise canceling applied to sinusoidal interferences," *IEEE Transactions on
Acoustics, Speech, and Signal Processing*, vol. 25, no. 6, pp. 484–491, Dec. 1977.
[doi:10.1109/TASSP.1977.1162997](https://doi.org/10.1109/TASSP.1977.1162997)
The transfer function of the LMS notch (scenario A).

<a id="zeidler1990"></a>
**[Zeidler 1990]** J. R. Zeidler, "Performance analysis of LMS adaptive prediction filters," *Proceedings of the
IEEE*, vol. 78, no. 12, pp. 1781–1806, Dec. 1990. [doi:10.1109/5.60921](https://doi.org/10.1109/5.60921)
The adaptive line enhancer (scenario E).

<a id="regalia1991"></a>
**[Regalia 1991]** P. A. Regalia, "An improved lattice-based adaptive IIR notch filter," *IEEE Transactions on Signal
Processing*, vol. 39, no. 9, pp. 2124–2128, Sep. 1991. [doi:10.1109/78.134453](https://doi.org/10.1109/78.134453)
The lattice notch with independent frequency and bandwidth (architecture A4).

<a id="haykin2014"></a>
**[Haykin 2014]** S. Haykin, *Adaptive Filter Theory*, 5th ed. Upper Saddle River, NJ: Pearson, 2014.
The LMS algorithm, its convergence in the mean and the eigenvalue conditions used throughout.

## Delayed, block and fixed-point LMS

<a id="long1989"></a>
**[Long, Ling and Proakis 1989]** G. Long, F. Ling and J. G. Proakis, "The LMS algorithm with delayed coefficient
adaptation," *IEEE Transactions on Acoustics, Speech, and Signal Processing*, vol. 37, no. 9, pp. 1397–1405,
Sep. 1989. [doi:10.1109/29.31293](https://doi.org/10.1109/29.31293)
Corrections: *IEEE Transactions on Signal Processing*, vol. 40, no. 1, pp. 230–232, Jan. 1992.
[doi:10.1109/78.157202](https://doi.org/10.1109/78.157202)
Delayed LMS and its step-size bound ([1.3](01-foundations.md#13-delaying-the-update-dlms)).

<a id="clark1981"></a>
**[Clark, Mitra and Parker 1981]** G. A. Clark, S. K. Mitra and S. R. Parker, "Block implementation of adaptive digital
filters," *IEEE Transactions on Acoustics, Speech, and Signal Processing*, vol. 29, no. 3, pp. 744–752, Jun. 1981.
[doi:10.1109/TASSP.1981.1163603](https://doi.org/10.1109/TASSP.1981.1163603)
Block LMS ([1.4](01-foundations.md#14-blocking-the-update-row-block-lms)).

<a id="gitlin1973"></a>
**[Gitlin, Mazo and Taylor 1973]** R. D. Gitlin, J. E. Mazo and M. G. Taylor, "On the design of gradient algorithms for
digitally implemented adaptive filters," *IEEE Transactions on Circuit Theory*, vol. 20, no. 2, pp. 125–136,
Mar. 1973. [doi:10.1109/TCT.1973.1083627](https://doi.org/10.1109/TCT.1973.1083627)
The digital residual error: updates below half an LSB are lost ([2.3](02-fixed-point.md#23-stalling-in-a-weight-register)).

<a id="caraiscos1984"></a>
**[Caraiscos and Liu 1984]** C. Caraiscos and B. Liu, "A roundoff error analysis of the LMS adaptive algorithm,"
*IEEE Transactions on Acoustics, Speech, and Signal Processing*, vol. 32, no. 1, pp. 34–41, Feb. 1984.
[doi:10.1109/TASSP.1984.1164286](https://doi.org/10.1109/TASSP.1984.1164286)
Finite-precision LMS and the stalling of adaptation ([2.3](02-fixed-point.md#23-stalling-in-a-weight-register)).

## Architectures

<a id="parhi1999"></a>
**[Parhi 1999]** K. K. Parhi, *VLSI Digital Signal Processing Systems: Design and Implementation*. New York: Wiley,
1999. Iteration bound, retiming, folding, look-ahead and pipelined adaptive filters; used in [chapter 1](01-foundations.md).

<a id="leiserson1991"></a>
**[Leiserson and Saxe 1991]** C. E. Leiserson and J. B. Saxe, "Retiming synchronous circuitry," *Algorithmica*,
vol. 6, no. 1, pp. 5–35, 1991. [doi:10.1007/BF01759032](https://doi.org/10.1007/BF01759032)
Retiming preserves the number of registers in every loop ([1.1](01-foundations.md#11-the-loop)).

<a id="meyer1993"></a>
**[Meyer and Agrawal 1993]** M. D. Meyer and D. P. Agrawal, "A high sampling rate delayed LMS filter architecture,"
*IEEE Transactions on Circuits and Systems II: Analog and Digital Signal Processing*, vol. 40, no. 11, pp. 727–729,
Nov. 1993. A systolic array of identical DLMS modules, the ancestor of `lms_systolic`.

<a id="van2001"></a>
**[Van and Feng 2001]** L.-D. Van and W.-S. Feng, "An efficient systolic architecture for the DLMS adaptive filter
and its applications," *IEEE Transactions on Circuits and Systems II: Analog and Digital Signal Processing*,
vol. 48, no. 4, pp. 359–366, Apr. 2001. [doi:10.1109/82.933794](https://doi.org/10.1109/82.933794)
Tree-systolic DLMS: trading the delay of the systolic chain against an adder tree.

<a id="meher2014"></a>
**[Meher and Park 2014]** P. K. Meher and S. Y. Park, "Critical-path analysis and low-complexity implementation of the
LMS adaptive algorithm," *IEEE Transactions on Circuits and Systems I: Regular Papers*, vol. 61, no. 3,
pp. 778–788, Mar. 2014. [doi:10.1109/TCSI.2013.2284173](https://doi.org/10.1109/TCSI.2013.2284173)
The critical path of direct-form LMS and designs with zero to two adaptation delays.

<a id="white1989"></a>
**[White 1989]** S. A. White, "Applications of distributed arithmetic to digital signal processing: A tutorial
review," *IEEE ASSP Magazine*, vol. 6, no. 3, pp. 4–19, Jul. 1989. [doi:10.1109/53.29648](https://doi.org/10.1109/53.29648)
Distributed arithmetic ([3.6](03-engines.md#36-lms_da)).

<a id="mohanty2013"></a>
**[Mohanty and Meher 2013]** B. K. Mohanty and P. K. Meher, "A high-performance energy-efficient architecture for FIR
adaptive filter based on new distributed arithmetic formulation of block LMS algorithm," *IEEE Transactions on
Signal Processing*, vol. 61, no. 4, pp. 921–932, Feb. 2013. [doi:10.1109/TSP.2012.2226453](https://doi.org/10.1109/TSP.2012.2226453)
Distributed arithmetic paired with block LMS (`lms_da`).

## Image processing on FPGAs

<a id="bailey2023"></a>
**[Bailey 2023]** D. G. Bailey, *Design for Embedded Image Processing on FPGAs*, 2nd ed. Hoboken, NJ: Wiley, 2023.
Stream processing, row buffers and window filters, as in the front ends of [chapter 4](04-front-ends.md).

<a id="paeth1990"></a>
**[Paeth 1990]** A. W. Paeth, "Median finding on a 3 × 3 grid," in *Graphics Gems*, A. S. Glassner, Ed.
Academic Press, 1990, pp. 171–175. The median of nine by successive min–max elimination.

<a id="devillard1998"></a>
**[Devillard 1998]** N. Devillard, "Fast median search: an ANSI C implementation," Jul. 1998,
<http://ndevilla.free.fr/median/median/index.html>. Its `opt_med9`, a network of 19 compare-exchanges taken from the
Graphics Gems source code, is the median of the baseline (`rtl/baselines/median3x3_top.v`).

<a id="wang2004"></a>
**[Wang et al. 2004]** Z. Wang, A. C. Bovik, H. R. Sheikh and E. P. Simoncelli, "Image quality assessment: From error
visibility to structural similarity," *IEEE Transactions on Image Processing*, vol. 13, no. 4, pp. 600–612,
Apr. 2004. [doi:10.1109/TIP.2003.819861](https://doi.org/10.1109/TIP.2003.819861)
SSIM, reported next to PSNR.

## Devices and tools

<a id="ug479"></a>
**[UG479]** Xilinx, *7 Series DSP48E1 Slice User Guide*, UG479 (v1.10), Mar. 2018. The 25 x 18 multiplier, the
48-bit accumulator, the pre-adder and the PCOUT-to-PCIN cascade that the engines map onto.

<a id="ug474"></a>
**[UG474]** AMD Xilinx, *7 Series FPGAs Configurable Logic Block User Guide*, UG474 (v1.9), 2025. LUTs, carry
chains, shift registers (SRL) and distributed RAM.

<a id="yosys"></a>
**[Yosys]** C. Wolf et al., *Yosys Open SYnthesis Suite*, <https://yosyshq.net/yosys/>. Version 0.71 is used for
every resource count of this repository.

<a id="iverilog"></a>
**[Icarus Verilog]** S. Williams et al., *Icarus Verilog*, <https://steveicarus.github.io/iverilog/>. Version 12.0
runs every RTL test.

## Companion work

<a id="khalilisadaghiani2026"></a>
**[Khalili Sadaghiani 2026]** A. Khalili Sadaghiani, *Adaptive Filters for Image Denoising*, GitHub repository, 2026.
<https://github.com/VKHS/Adaptive-Filters-for-Image-Denoising>
The six scenarios as algorithms, in Python and MATLAB; this repository is their hardware counterpart.

"""afarch: bit-accurate models of FPGA architectures for adaptive image-denoising filters.

fxp        fixed-point formats and the arithmetic contract shared with the RTL
engines    the six engine architectures as three algorithmic classes (exact, delayed and block LMS)
frontends  windows, delay lines, high band, plane-wave references, optical-black mean
scenarios  the fixed-point pipelines of scenarios A-F
cost       throughput, latency and resource models of the architectures
reference  floating-point references, metrics and baselines
scenes     the corrupted scenes of the application examples
lattice    architecture A4, the lattice IIR notch that tracks a frequency (floating point)
plotstyle  figure style and block-diagram primitives
hdl, synth Icarus Verilog and Yosys runners
"""

# Vitis HLS run of one smoke case: C simulation, C synthesis, C/RTL co-simulation and IP export.
#
#   python smoke/smoke.py --only hls D                    # writes build/smoke/<case>/ (inputs, vitis_case.tcl)
#   vitis_hls -f hls/scripts/run_vitis_hls.tcl -tclargs D_gated_df [flow] [part] [period_ns]
#   python smoke/smoke.py --vitis D                       # compares build/smoke/<case>/vitis_out.txt
#
#   case     a case name printed by smoke/smoke.py (A_serial, C_df, D_gated_df, E_rowblock, F_online, ...)
#   flow     csim | syn | cosim | export     each includes the steps before it (default cosim)
#   part     default xc7a200tsbg484-1        the part of syn/vivado_ooc.tcl
#   period   default 4.0 (ns)
#
# The same four values can be given as environment variables AF_CASE, AF_FLOW, AF_PART and AF_PERIOD, for
# releases that run HLS Tcl scripts as   vitis-run --mode hls --tcl hls/scripts/run_vitis_hls.tcl
#
# The design and the testbench are compiled with -DAFHLS_AP_TYPES: every signal is an ap_int of its exact width.
# The testbench writes the output stream to build/smoke/<case>/vitis_out.txt, in C simulation and again in
# co-simulation, where the values come from the generated RTL. The project is build/vitis_hls/<case>; the
# synthesis report is in build/vitis_hls/<case>/sol/syn/report/.

proc arg_or_env {i name default} {
    global argv
    if {[info exists argv] && [llength $argv] > $i && [lindex $argv $i] ne ""} {
        return [lindex $argv $i]
    }
    if {[info exists ::env($name)] && $::env($name) ne ""} {
        return $::env($name)
    }
    return $default
}

set repo   [file dirname [file dirname [file dirname [file normalize [info script]]]]]
set case   [arg_or_env 0 AF_CASE ""]
set flow   [arg_or_env 1 AF_FLOW cosim]
set part   [arg_or_env 2 AF_PART xc7a200tsbg484-1]
set period [arg_or_env 3 AF_PERIOD 4.0]

set steps {csim syn cosim export}
set last [lsearch -exact $steps $flow]
if {$case eq "" || $last < 0} {
    puts "usage: vitis_hls -f hls/scripts/run_vitis_hls.tcl -tclargs <case> \[csim|syn|cosim|export\] \[part\] \[period_ns\]"
    exit 1
}
set cfg [file join $repo build smoke $case vitis_case.tcl]
if {![file exists $cfg]} {
    puts "$cfg not found: run  python smoke/smoke.py --only hls  first (it writes every case)"
    exit 1
}
source $cfg

open_project -reset [file join $repo build vitis_hls $case]
set_top $af_top
add_files $af_src -cflags $af_cflags
add_files -tb $af_tb -cflags $af_cflags
open_solution -reset sol -flow_target vivado
set_part $part
create_clock -period $period -name default

csim_design -argv $af_argv
if {$last >= 1} { csynth_design }
if {$last >= 2} { cosim_design -argv $af_argv -trace_level none }
if {$last >= 3} { export_design -format ip_catalog }

puts "case $case: $flow done; compare with  python smoke/smoke.py --vitis [string index $case 0]"
exit

# Vivado out-of-context run of one module: synthesis, placement, routing, utilisation and timing.
#
#   vivado -mode batch -source syn/vivado_ooc.tcl -tclargs <top> <part> <period_ns> [PARAM=value ...]
#
# Examples
#   vivado -mode batch -source syn/vivado_ooc.tcl -tclargs lms_engine xc7a200tsbg484-1 4.0 ENGINE=2 L=24
#   vivado -mode batch -source syn/vivado_ooc.tcl -tclargs scen_de_top xc7a200tsbg484-1 4.0 W=512 HH=512 R=2 ENGINE=1 P=6
#
# Every Verilog file of rtl/ is read; the parameters become synthesis generics (Verilog constants such as
# UINC=64'd79456894 are accepted); one clock constraint is put on port clk. Reports go to
# build/vivado/<top>_<params>/. The script runs from rtl/scenarios so that the ROM table of scen_a_top
# ($readmemh "cos1024_q12.hex") is found. The results in results/ come from Yosys (syn/*.py), not from this script.

if {[llength $argv] < 3} {
    puts "usage: vivado -mode batch -source syn/vivado_ooc.tcl -tclargs <top> <part> <period_ns> \[PARAM=value ...\]"
    exit 1
}
set repo   [file dirname [file dirname [file normalize [info script]]]]
set top    [lindex $argv 0]
set part   [lindex $argv 1]
set period [lindex $argv 2]
set params [lrange $argv 3 end]

set tag $top
set generics {}
foreach kv $params {
    lappend generics -generic $kv
    append tag "_" [string map {= "" ' "" " " ""} $kv]
}
set out [file join $repo build vivado $tag]
file mkdir $out

foreach dir {common engines scenarios baselines} {
    foreach f [lsort [glob -nocomplain [file join $repo rtl $dir *.v]]] {
        read_verilog $f
    }
}
cd [file join $repo rtl scenarios]

synth_design -top $top -part $part -mode out_of_context \
    -include_dirs [list [file join $repo rtl common]] {*}$generics
create_clock -name clk -period $period [get_ports clk]
report_utilization -file [file join $out utilization_synth.rpt]

opt_design
place_design
route_design

report_utilization -file [file join $out utilization.rpt]
report_timing_summary -file [file join $out timing.rpt]
set wns [get_property SLACK [get_timing_paths -max_paths 1 -nworst 1 -setup]]
set fmax [expr {1000.0 / ($period - $wns)}]
puts [format "%s: WNS %.3f ns at a %.3f ns clock, Fmax about %.1f MHz (reports in %s)" $tag $wns $period $fmax $out]

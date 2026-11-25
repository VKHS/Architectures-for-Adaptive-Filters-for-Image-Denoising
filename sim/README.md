# sim/: bit-exact regressions of the RTL

[Repository](../README.md) · [RTL](../rtl/README.md) · [testbenches](../tb/README.md) · [verification](../docs/05-verification.md)

| script | what it runs | cases | output |
|---|---|---|---|
| [`test_engines.py`](test_engines.py) | the six engines through [`tb/tb_engine.v`](../tb/tb_engine.v) on random, hostile step streams (rows of random length, drain bursts, idle cycles, pre-roll shifts, full-scale and saturating inputs, outliers for the gate, adaptation switched off); then the handshake engines back to back, to measure their initiation interval | 24 + 8 | [`results/rtl_engine_tests.json`](../results/rtl_engine_tests.json) |
| [`test_scenarios.py`](test_scenarios.py) | the complete scenario tops and the median baseline on image crops, several passes, every engine | 32 | [`results/rtl_scenario_tests.json`](../results/rtl_scenario_tests.json) |

```bash
python sim/test_engines.py              # all, a few seconds
python sim/test_engines.py df da        # some engines
python sim/test_scenarios.py            # all, about a minute
python sim/test_scenarios.py de c       # some groups: a, b, c, de, f, median
```

Every output word must equal the model's (`np.array_equal`). The case tables are in
[5.1](../docs/05-verification.md#51-engines) and [5.2](../docs/05-verification.md#52-scenario-tops). The smoke
test of [`smoke/`](../smoke/README.md) adds the HLS C++ to the same kind of check, scenario by scenario.

# Benchmarks

This contains some crude benchmarks comparing ratpack against JSON and other common serialization
formats and their pure python implementations (if available).

## Size Comparison

![](./chart.png)

## Full Results
```
Taking the best time out of 10 enc/dec iterations

file: data/apache.json (101711)
          Enc Size    Enc Time    Dec Time
   JSON   99949       0.001991    0.000400
 ubjson   91963       0.001670    0.002546
  cbor2   84282       0.000697    0.000475
msgpack   84082       0.003430    0.005499
ratpack   84037       0.002842    0.002719

file: data/mesh.json (752407)
          Enc Size    Enc Time    Dec Time
   JSON   723597      0.030070    0.005061
 ubjson   435754      0.022043    0.019023
  cbor2   414605      0.007666    0.002476
msgpack   413633      0.030888    0.066090
ratpack   393670      0.025022    0.019418

file: data/instruments.json (122717)
          Enc Size    Enc Time    Dec Time
   JSON   120693      0.004137    0.000851
 ubjson   97367       0.003013    0.004189
  cbor2   85507       0.001502    0.000781
msgpack   84565       0.005906    0.010019
ratpack   84463       0.005341    0.005405

file: data/sample.json (687491)
          Enc Size    Enc Time    Dec Time
   JSON   275084      0.022103    0.001369
 ubjson   148687      0.001927    0.002273
  cbor2   147095      0.000701    maximum container nesting depth (400) exceeded
msgpack   recursion limit exceeded
ratpack   147291      0.002306    0.002730

file: data/canada.json (2251051)
          Enc Size    Enc Time    Dec Time
   JSON   2201371     0.119699    0.024205
 ubjson   1112030     0.077560    0.059466
  cbor2   1056200     0.027243    0.008401
msgpack   1056793     0.084862    0.136954
ratpack   1055469     0.068109    0.052259

file: data/github.json (55827)
          Enc Size    Enc Time    Dec Time
   JSON   55467       0.000728    0.000192
 ubjson   51384       0.000580    0.000900
  cbor2   48973       0.000243    0.000181
msgpack   48969       0.001217    0.002147
ratpack   48932       0.001074    0.001097

file: data/twitter.json (631514)
          Enc Size    Enc Time    Dec Time
   JSON   588098      0.008456    0.002194
 ubjson   426156      0.006253    0.009680
  cbor2   402814      0.002643    0.002113
msgpack   401510      0.012539    0.023076
ratpack   401002      0.011987    0.012381

file: data/citm_catalog.json (1727204)
          Enc Size    Enc Time    Dec Time
   JSON   551950      0.028027    0.004089
 ubjson   391463      0.024288    0.026466
  cbor2   342373      0.011606    0.004460
msgpack   342473      0.035739    0.052798
ratpack   342109      0.027322    0.026493
```

## JSON inputs used
 - canada.json, citm_catalog.json, twitter.json (https://github.com/miloyip/nativejson-benchmark/tree/master/data)
 - apache.json, github.json, insturments.json, mesh.json (https://github.com/python-rapidjson/python-rapidjson/tree/master/benchmarks/json)
 - sample.json (source https://code.google.com/archive/p/json-test-suite/downloads)

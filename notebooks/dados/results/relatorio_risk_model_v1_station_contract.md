# Relatório Risk Model V1 — Station Contract

**Data:** 2026-05-20

## 1. Configuração

- Treino: até 2023-07-02
- Test histórico: após corte até 2025-12-31
- Holdout 2026: 2026-01-01 a 2026-05-19 (dados parciais)
- Modelos: ['gradboost', 'logreg']
- Variantes: ['CEMADEN_ONLY', 'CEMADEN_OM', 'ALL']
- Labels: ['pancada', 'prolongada', 'saturante', 'perigoso_any']

## 2. Cobertura 2026

```
      bacia  mes  n_stations_contract  n_stations_present  total_registros
    guarara    1                   17                  13            13129
    guarara    2                   17                  13            11101
    guarara    3                   17                  13            12372
    guarara    4                   17                  13             9531
    guarara    5                   17                  12             6452
    meninos    1                   10                   8             7887
    meninos    2                   10                   8             6744
    meninos    3                   10                   8             7254
    meninos    4                   10                   8             5851
    meninos    5                   10                   8             4121
   oratorio    1                   11                  10             9810
   oratorio    2                   11                  10             8441
   oratorio    3                   11                  10             9021
   oratorio    4                   11                  10             7257
   oratorio    5                   11                  10             5416
tamanduatei    1                   19                  16            15473
tamanduatei    2                   19                  16            13384
tamanduatei    3                   19                  16            14578
tamanduatei    4                   19                  16            11336
tamanduatei    5                   19                  15             8028
```

## 3. Métricas Test Histórico (até 2025)

```
      bacia        label     variante    modelo    prauc  spearman_rho   recall  precision       f1
    guarara      pancada   CEMADEN_OM    logreg 0.083182      0.380067 0.580645   0.070866 0.126316
    guarara      pancada CEMADEN_ONLY    logreg 0.083182      0.380067 0.580645   0.070866 0.126316
    guarara      pancada          ALL    logreg 0.078753      0.366799 0.516129   0.067511 0.119403
    guarara      pancada CEMADEN_ONLY gradboost 0.074927      0.286492 0.387097   0.109091 0.170213
    guarara      pancada          ALL gradboost 0.073050      0.282631 0.064516   0.068966 0.066667
    guarara      pancada   CEMADEN_OM gradboost 0.069100      0.291357 0.096774   0.076923 0.085714
    guarara perigoso_any CEMADEN_ONLY gradboost 0.581241      0.425730 0.529412   0.486486 0.507042
    guarara perigoso_any   CEMADEN_OM gradboost 0.574672      0.418413 0.500000   0.515152 0.507463
    guarara perigoso_any          ALL gradboost 0.571583      0.430240 0.519608   0.460870 0.488479
    guarara perigoso_any   CEMADEN_OM    logreg 0.571101      0.471513 0.480392   0.604938 0.535519
    guarara perigoso_any CEMADEN_ONLY    logreg 0.571101      0.471513 0.480392   0.604938 0.535519
    guarara perigoso_any          ALL    logreg 0.569762      0.473468 0.480392   0.569767 0.521277
    guarara   prolongada   CEMADEN_OM    logreg 0.219703      0.450273 0.333333   0.237624 0.277457
    guarara   prolongada CEMADEN_ONLY    logreg 0.219703      0.450273 0.333333   0.237624 0.277457
    guarara   prolongada          ALL    logreg 0.216387      0.459217 0.472222   0.182796 0.263566
    guarara   prolongada   CEMADEN_OM gradboost 0.175823      0.398973 0.763889   0.128205 0.219561
    guarara   prolongada CEMADEN_ONLY gradboost 0.174427      0.406228 0.611111   0.134146 0.220000
    guarara   prolongada          ALL gradboost 0.172377      0.388973 0.625000   0.141509 0.230769
    guarara    saturante   CEMADEN_OM gradboost 0.725736      0.443399 0.628571   0.656716 0.642336
    guarara    saturante   CEMADEN_OM    logreg 0.716468      0.478656 0.628571   0.698413 0.661654
    guarara    saturante CEMADEN_ONLY    logreg 0.716468      0.478656 0.628571   0.698413 0.661654
    guarara    saturante          ALL gradboost 0.715727      0.428172 0.657143   0.516854 0.578616
    guarara    saturante          ALL    logreg 0.715534      0.479346 0.614286   0.704918 0.656489
    guarara    saturante CEMADEN_ONLY gradboost 0.711115      0.442244 0.642857   0.548780 0.592105
    meninos      pancada   CEMADEN_OM    logreg 0.122213      0.377749 0.125000   0.153846 0.137931
    meninos      pancada CEMADEN_ONLY    logreg 0.122213      0.377749 0.125000   0.153846 0.137931
    meninos      pancada          ALL    logreg 0.108799      0.396532 0.125000   0.142857 0.133333
    meninos      pancada   CEMADEN_OM gradboost 0.065557      0.347786 0.281250   0.058065 0.096257
    meninos      pancada          ALL gradboost 0.061820      0.376030 0.125000   0.070175 0.089888
    meninos      pancada CEMADEN_ONLY gradboost 0.058892      0.348889 0.156250   0.063291 0.090090
    meninos perigoso_any          ALL    logreg 0.555058      0.477669 0.398058   0.683333 0.503067
    meninos perigoso_any   CEMADEN_OM    logreg 0.551044      0.471557 0.446602   0.528736 0.484211
    meninos perigoso_any CEMADEN_ONLY    logreg 0.551044      0.471557 0.446602   0.528736 0.484211
    meninos perigoso_any          ALL gradboost 0.524127      0.425674 0.378641   0.590909 0.461538
    meninos perigoso_any   CEMADEN_OM gradboost 0.512540      0.417180 0.436893   0.500000 0.466321
    meninos perigoso_any CEMADEN_ONLY gradboost 0.510608      0.423963 0.427184   0.505747 0.463158
    meninos   prolongada   CEMADEN_OM    logreg 0.246416      0.457999 0.272727   0.304348 0.287671
    meninos   prolongada CEMADEN_ONLY    logreg 0.246416      0.457999 0.272727   0.304348 0.287671
    meninos   prolongada          ALL    logreg 0.238264      0.467271 0.298701   0.287500 0.292994
    meninos   prolongada CEMADEN_ONLY gradboost 0.170655      0.391897 0.376623   0.207143 0.267281
    meninos   prolongada   CEMADEN_OM gradboost 0.169098      0.412319 0.220779   0.195402 0.207317
    meninos   prolongada          ALL gradboost 0.164325      0.417389 0.285714   0.157143 0.202765
    meninos    saturante          ALL    logreg 0.717002      0.475817 0.553846   0.837209 0.666667
    meninos    saturante   CEMADEN_OM    logreg 0.713973      0.471593 0.630769   0.732143 0.677686
    meninos    saturante CEMADEN_ONLY    logreg 0.713973      0.471593 0.630769   0.732143 0.677686
    meninos    saturante          ALL gradboost 0.677130      0.459350 0.553846   0.750000 0.637168
    meninos    saturante CEMADEN_ONLY gradboost 0.674375      0.471060 0.600000   0.609375 0.604651
    meninos    saturante   CEMADEN_OM gradboost 0.654037      0.463102 0.584615   0.690909 0.633333
   oratorio      pancada CEMADEN_ONLY gradboost 0.105440      0.355270 0.709677   0.051765 0.096491
   oratorio      pancada   CEMADEN_OM gradboost 0.100353      0.351523 0.741935   0.058524 0.108491
   oratorio      pancada          ALL gradboost 0.098304      0.340409 0.354839   0.075862 0.125000
   oratorio      pancada          ALL    logreg 0.086411      0.393735 0.322581   0.136986 0.192308
   oratorio      pancada   CEMADEN_OM    logreg 0.082472      0.371814 0.225806   0.122807 0.159091
   oratorio      pancada CEMADEN_ONLY    logreg 0.082472      0.371814 0.225806   0.122807 0.159091
   oratorio perigoso_any          ALL    logreg 0.535654      0.431177 0.409091   0.576923 0.478723
   oratorio perigoso_any   CEMADEN_OM    logreg 0.530822      0.428530 0.418182   0.560976 0.479167
   oratorio perigoso_any CEMADEN_ONLY    logreg 0.530822      0.428530 0.418182   0.560976 0.479167
   oratorio perigoso_any          ALL gradboost 0.513467      0.399446 0.400000   0.676923 0.502857
   oratorio perigoso_any   CEMADEN_OM gradboost 0.510261      0.390589 0.445455   0.480392 0.462264
   oratorio perigoso_any CEMADEN_ONLY gradboost 0.505803      0.405885 0.500000   0.436508 0.466102
   oratorio   prolongada          ALL    logreg 0.178075      0.414620 0.337500   0.236842 0.278351
   oratorio   prolongada   CEMADEN_OM    logreg 0.175667      0.397484 0.350000   0.171779 0.230453
   oratorio   prolongada CEMADEN_ONLY    logreg 0.175667      0.397484 0.350000   0.171779 0.230453
   oratorio   prolongada   CEMADEN_OM gradboost 0.169759      0.374780 0.650000   0.140541 0.231111
   oratorio   prolongada          ALL gradboost 0.159806      0.388461 0.537500   0.142384 0.225131
   oratorio   prolongada CEMADEN_ONLY gradboost 0.157091      0.376952 0.475000   0.136691 0.212291
   oratorio    saturante          ALL    logreg 0.672306      0.455690 0.600000   0.617647 0.608696
   oratorio    saturante   CEMADEN_OM    logreg 0.669715      0.453527 0.600000   0.666667 0.631579
   oratorio    saturante CEMADEN_ONLY    logreg 0.669715      0.453527 0.600000   0.666667 0.631579
   oratorio    saturante   CEMADEN_OM gradboost 0.657215      0.439697 0.657143   0.500000 0.567901
   oratorio    saturante          ALL gradboost 0.651423      0.430929 0.642857   0.454545 0.532544
   oratorio    saturante CEMADEN_ONLY gradboost 0.649154      0.435001 0.671429   0.479592 0.559524
tamanduatei      pancada   CEMADEN_OM gradboost 0.107748      0.319124 0.441176   0.099338 0.162162
tamanduatei      pancada   CEMADEN_OM    logreg 0.104689      0.384361 0.235294   0.102564 0.142857
tamanduatei      pancada CEMADEN_ONLY    logreg 0.104689      0.384361 0.235294   0.102564 0.142857
tamanduatei      pancada          ALL    logreg 0.104380      0.387451 0.294118   0.098039 0.147059
tamanduatei      pancada          ALL gradboost 0.097062      0.324737 0.205882   0.085366 0.120690
tamanduatei      pancada CEMADEN_ONLY gradboost 0.077311      0.322554 0.352941   0.080000 0.130435
tamanduatei perigoso_any   CEMADEN_OM    logreg 0.565835      0.469337 0.464286   0.597701 0.522613
tamanduatei perigoso_any CEMADEN_ONLY    logreg 0.565835      0.469337 0.464286   0.597701 0.522613
tamanduatei perigoso_any          ALL    logreg 0.565642      0.471048 0.473214   0.595506 0.527363
tamanduatei perigoso_any   CEMADEN_OM gradboost 0.563118      0.429171 0.500000   0.523364 0.511416
tamanduatei perigoso_any CEMADEN_ONLY gradboost 0.556596      0.412028 0.482143   0.534653 0.507042
tamanduatei perigoso_any          ALL gradboost 0.544278      0.418310 0.437500   0.597561 0.505155
tamanduatei   prolongada          ALL    logreg 0.209254      0.453542 0.389610   0.252101 0.306122
tamanduatei   prolongada   CEMADEN_OM gradboost 0.207740      0.407158 0.844156   0.137421 0.236364
tamanduatei   prolongada   CEMADEN_OM    logreg 0.202707      0.443976 0.350649   0.264706 0.301676
tamanduatei   prolongada CEMADEN_ONLY    logreg 0.202707      0.443976 0.350649   0.264706 0.301676
tamanduatei   prolongada          ALL gradboost 0.185035      0.426013 0.597403   0.175573 0.271386
tamanduatei   prolongada CEMADEN_ONLY gradboost 0.178622      0.411118 0.844156   0.144444 0.246679
tamanduatei    saturante          ALL    logreg 0.711677      0.484644 0.644737   0.628205 0.636364
tamanduatei    saturante   CEMADEN_OM    logreg 0.710944      0.484102 0.644737   0.671233 0.657718
tamanduatei    saturante CEMADEN_ONLY    logreg 0.710944      0.484102 0.644737   0.671233 0.657718
tamanduatei    saturante   CEMADEN_OM gradboost 0.683435      0.461239 0.657895   0.543478 0.595238
tamanduatei    saturante          ALL gradboost 0.680342      0.443880 0.644737   0.583333 0.612500
tamanduatei    saturante CEMADEN_ONLY gradboost 0.645472      0.447775 0.631579   0.564706 0.596273
```

## 4. Métricas Holdout 2026

```
      bacia        label     variante    modelo    prauc  spearman_rho   recall  precision       f1  n_test
    guarara      pancada CEMADEN_ONLY gradboost 0.295735      0.314922 0.750000   0.077922 0.141176     139
    guarara      pancada   CEMADEN_OM gradboost 0.245612      0.311877 0.125000   1.000000 0.222222     139
    guarara      pancada          ALL gradboost 0.141745      0.229734 0.625000   0.096154 0.166667     139
    guarara      pancada   CEMADEN_OM    logreg 0.139028      0.415808 0.625000   0.125000 0.208333     139
    guarara      pancada CEMADEN_ONLY    logreg 0.139028      0.415808 0.625000   0.125000 0.208333     139
    guarara      pancada          ALL    logreg 0.136551      0.403327 0.625000   0.119048 0.200000     139
    guarara perigoso_any   CEMADEN_OM    logreg 0.872227      0.430327 0.603175   0.904762 0.723810     139
    guarara perigoso_any CEMADEN_ONLY    logreg 0.872227      0.430327 0.603175   0.904762 0.723810     139
    guarara perigoso_any          ALL    logreg 0.870069      0.423863 0.603175   0.904762 0.723810     139
    guarara perigoso_any          ALL gradboost 0.864468      0.390655 0.492063   0.939394 0.645833     139
    guarara perigoso_any CEMADEN_ONLY gradboost 0.863810      0.392102 0.396825   0.961538 0.561798     139
    guarara perigoso_any   CEMADEN_OM gradboost 0.853661      0.390963 0.396825   0.925926 0.555556     139
    guarara   prolongada   CEMADEN_OM    logreg 0.563967      0.427250 0.409091   0.514286 0.455696     139
    guarara   prolongada CEMADEN_ONLY    logreg 0.563967      0.427250 0.409091   0.514286 0.455696     139
    guarara   prolongada          ALL    logreg 0.555738      0.419821 0.477273   0.538462 0.506024     139
    guarara   prolongada CEMADEN_ONLY gradboost 0.508827      0.380657 0.431818   0.558824 0.487179     139
    guarara   prolongada   CEMADEN_OM gradboost 0.504734      0.368386 0.204545   0.562500 0.300000     139
    guarara   prolongada          ALL gradboost 0.498156      0.379091 0.295455   0.684211 0.412698     139
    guarara    saturante          ALL    logreg 0.898697      0.433184 0.714286   0.888889 0.792079     139
    guarara    saturante   CEMADEN_OM    logreg 0.897269      0.432030 0.714286   0.930233 0.808081     139
    guarara    saturante CEMADEN_ONLY    logreg 0.897269      0.432030 0.714286   0.930233 0.808081     139
    guarara    saturante          ALL gradboost 0.876543      0.416288 0.535714   0.937500 0.681818     139
    guarara    saturante CEMADEN_ONLY gradboost 0.874235      0.445615 0.464286   0.962963 0.626506     139
    guarara    saturante   CEMADEN_OM gradboost 0.861620      0.440787 0.482143   0.964286 0.642857     139
    meninos      pancada   CEMADEN_OM    logreg 0.156817      0.506706 0.250000   0.153846 0.190476     139
    meninos      pancada CEMADEN_ONLY    logreg 0.156817      0.506706 0.250000   0.153846 0.190476     139
    meninos      pancada   CEMADEN_OM gradboost 0.126357      0.346725 0.125000   0.111111 0.117647     139
    meninos      pancada          ALL    logreg 0.123040      0.480031 0.125000   0.166667 0.142857     139
    meninos      pancada          ALL gradboost 0.120691      0.223591 0.125000   0.200000 0.153846     139
    meninos      pancada CEMADEN_ONLY gradboost 0.113196      0.298087 0.125000   0.250000 0.166667     139
    meninos perigoso_any   CEMADEN_OM    logreg 0.877196      0.494243 0.615385   0.914286 0.735632     139
    meninos perigoso_any CEMADEN_ONLY    logreg 0.877196      0.494243 0.615385   0.914286 0.735632     139
    meninos perigoso_any          ALL    logreg 0.876866      0.495837 0.596154   1.000000 0.746988     139
    meninos perigoso_any   CEMADEN_OM gradboost 0.841990      0.463892 0.403846   0.913043 0.560000     139
    meninos perigoso_any CEMADEN_ONLY gradboost 0.836572      0.472047 0.423077   0.956522 0.586667     139
    meninos perigoso_any          ALL gradboost 0.829740      0.402846 0.538462   0.875000 0.666667     139
    meninos   prolongada   CEMADEN_OM    logreg 0.613560      0.513456 0.564103   0.478261 0.517647     139
    meninos   prolongada CEMADEN_ONLY    logreg 0.613560      0.513456 0.564103   0.478261 0.517647     139
    meninos   prolongada          ALL    logreg 0.613527      0.512614 0.564103   0.468085 0.511628     139
    meninos   prolongada          ALL gradboost 0.496039      0.349477 0.179487   0.500000 0.264151     139
    meninos   prolongada CEMADEN_ONLY gradboost 0.489314      0.443470 0.538462   0.552632 0.545455     139
    meninos   prolongada   CEMADEN_OM gradboost 0.471393      0.426039 0.153846   0.400000 0.222222     139
    meninos    saturante   CEMADEN_OM    logreg 0.888666      0.357126 0.644444   1.000000 0.783784     139
    meninos    saturante CEMADEN_ONLY    logreg 0.888666      0.357126 0.644444   1.000000 0.783784     139
    meninos    saturante          ALL    logreg 0.886501      0.362962 0.577778   1.000000 0.732394     139
    meninos    saturante CEMADEN_ONLY gradboost 0.868783      0.419088 0.311111   1.000000 0.474576     139
    meninos    saturante   CEMADEN_OM gradboost 0.858143      0.429002 0.222222   1.000000 0.363636     139
    meninos    saturante          ALL gradboost 0.840680      0.457153 0.200000   1.000000 0.333333     139
   oratorio      pancada   CEMADEN_OM gradboost 0.069174      0.193182 0.000000   0.000000 0.000000     139
   oratorio      pancada          ALL    logreg 0.066782      0.027395 0.000000   0.000000 0.000000     139
   oratorio      pancada   CEMADEN_OM    logreg 0.065726     -0.017551 0.000000   0.000000 0.000000     139
   oratorio      pancada CEMADEN_ONLY    logreg 0.065726     -0.017551 0.000000   0.000000 0.000000     139
   oratorio      pancada          ALL gradboost 0.063243     -0.002051 0.000000   0.000000 0.000000     139
   oratorio      pancada CEMADEN_ONLY gradboost 0.060854      0.226092 0.000000   0.000000 0.000000     139
   oratorio perigoso_any   CEMADEN_OM    logreg 0.871432      0.439944 0.578947   0.970588 0.725275     139
   oratorio perigoso_any CEMADEN_ONLY    logreg 0.871432      0.439944 0.578947   0.970588 0.725275     139
   oratorio perigoso_any          ALL    logreg 0.870497      0.440289 0.649123   0.948718 0.770833     139
   oratorio perigoso_any          ALL gradboost 0.810373      0.377856 0.298246   1.000000 0.459459     139
   oratorio perigoso_any CEMADEN_ONLY gradboost 0.804801      0.395717 0.298246   0.944444 0.453333     139
   oratorio perigoso_any   CEMADEN_OM gradboost 0.795829      0.370412 0.333333   1.000000 0.500000     139
   oratorio   prolongada          ALL    logreg 0.528640      0.448659 0.142857   0.545455 0.226415     139
   oratorio   prolongada   CEMADEN_OM    logreg 0.422398      0.334619 0.000000   0.000000 0.000000     139
   oratorio   prolongada CEMADEN_ONLY    logreg 0.422398      0.334619 0.000000   0.000000 0.000000     139
   oratorio   prolongada   CEMADEN_OM gradboost 0.396381      0.182507 0.190476   0.500000 0.275862     139
   oratorio   prolongada CEMADEN_ONLY gradboost 0.383756      0.152943 0.071429   0.300000 0.115385     139
   oratorio   prolongada          ALL gradboost 0.382768      0.123002 0.071429   0.333333 0.117647     139
   oratorio    saturante          ALL    logreg 0.889453      0.422464 0.711538   0.925000 0.804348     139
   oratorio    saturante   CEMADEN_OM    logreg 0.888967      0.414873 0.711538   0.925000 0.804348     139
   oratorio    saturante CEMADEN_ONLY    logreg 0.888967      0.414873 0.711538   0.925000 0.804348     139
   oratorio    saturante   CEMADEN_OM gradboost 0.809910      0.372677 0.307692   1.000000 0.470588     139
   oratorio    saturante CEMADEN_ONLY gradboost 0.783404      0.311871 0.269231   1.000000 0.424242     139
   oratorio    saturante          ALL gradboost 0.783196      0.303358 0.269231   1.000000 0.424242     139
tamanduatei      pancada          ALL    logreg 0.184659      0.352798 0.428571   0.125000 0.193548     139
tamanduatei      pancada   CEMADEN_OM    logreg 0.182360      0.347537 0.571429   0.142857 0.228571     139
tamanduatei      pancada CEMADEN_ONLY    logreg 0.182360      0.347537 0.571429   0.142857 0.228571     139
tamanduatei      pancada CEMADEN_ONLY gradboost 0.110069      0.172652 0.285714   0.117647 0.166667     139
tamanduatei      pancada          ALL gradboost 0.079143      0.230225 0.000000   0.000000 0.000000     139
tamanduatei      pancada   CEMADEN_OM gradboost 0.078830      0.305975 0.428571   0.058824 0.103448     139
tamanduatei perigoso_any   CEMADEN_OM    logreg 0.875845      0.451671 0.645161   0.869565 0.740741     139
tamanduatei perigoso_any CEMADEN_ONLY    logreg 0.875845      0.451671 0.645161   0.869565 0.740741     139
tamanduatei perigoso_any          ALL    logreg 0.875301      0.452971 0.629032   0.951220 0.757282     139
tamanduatei perigoso_any          ALL gradboost 0.853611      0.450684 0.370968   1.000000 0.541176     139
tamanduatei perigoso_any   CEMADEN_OM gradboost 0.851489      0.467541 0.403226   1.000000 0.574713     139
tamanduatei perigoso_any CEMADEN_ONLY gradboost 0.834021      0.442283 0.532258   0.916667 0.673469     139
tamanduatei   prolongada CEMADEN_ONLY gradboost 0.631520      0.462835 0.652174   0.500000 0.566038     139
tamanduatei   prolongada   CEMADEN_OM gradboost 0.595629      0.515139 0.760870   0.492958 0.598291     139
tamanduatei   prolongada   CEMADEN_OM    logreg 0.564088      0.460373 0.413043   0.542857 0.469136     139
tamanduatei   prolongada CEMADEN_ONLY    logreg 0.564088      0.460373 0.413043   0.542857 0.469136     139
tamanduatei   prolongada          ALL    logreg 0.558716      0.464967 0.304348   0.608696 0.405797     139
tamanduatei   prolongada          ALL gradboost 0.555013      0.456010 0.304348   0.608696 0.405797     139
tamanduatei    saturante          ALL    logreg 0.897025      0.431963 0.714286   0.851064 0.776699     139
tamanduatei    saturante   CEMADEN_OM    logreg 0.896886      0.430891 0.767857   0.860000 0.811321     139
tamanduatei    saturante CEMADEN_ONLY    logreg 0.896886      0.430891 0.767857   0.860000 0.811321     139
tamanduatei    saturante          ALL gradboost 0.882053      0.462254 0.375000   0.954545 0.538462     139
tamanduatei    saturante CEMADEN_ONLY gradboost 0.867205      0.465717 0.589286   0.942857 0.725275     139
tamanduatei    saturante   CEMADEN_OM gradboost 0.855610      0.454801 0.410714   1.000000 0.582278     139
```

## 5. Estabilidade (std prob em 2026)

```
      bacia        label     variante    modelo  prob_std  prob_mean   n
    guarara      pancada          ALL gradboost  0.099330   0.120438 139
    guarara      pancada          ALL    logreg  0.190984   0.317262 139
    guarara      pancada   CEMADEN_OM gradboost  0.113379   0.135954 139
    guarara      pancada   CEMADEN_OM    logreg  0.197452   0.325508 139
    guarara      pancada CEMADEN_ONLY gradboost  0.113728   0.133643 139
    guarara      pancada CEMADEN_ONLY    logreg  0.197452   0.325508 139
    guarara perigoso_any          ALL gradboost  0.325708   0.404235 139
    guarara perigoso_any          ALL    logreg  0.324626   0.556906 139
    guarara perigoso_any   CEMADEN_OM gradboost  0.302593   0.389526 139
    guarara perigoso_any   CEMADEN_OM    logreg  0.322972   0.558852 139
    guarara perigoso_any CEMADEN_ONLY gradboost  0.322612   0.366162 139
    guarara perigoso_any CEMADEN_ONLY    logreg  0.322972   0.558852 139
    guarara   prolongada          ALL gradboost  0.170471   0.214468 139
    guarara   prolongada          ALL    logreg  0.273404   0.444669 139
    guarara   prolongada   CEMADEN_OM gradboost  0.183988   0.210031 139
    guarara   prolongada   CEMADEN_OM    logreg  0.275187   0.451216 139
    guarara   prolongada CEMADEN_ONLY gradboost  0.177983   0.202332 139
    guarara   prolongada CEMADEN_ONLY    logreg  0.275187   0.451216 139
    guarara    saturante          ALL gradboost  0.336755   0.260892 139
    guarara    saturante          ALL    logreg  0.381197   0.502086 139
    guarara    saturante   CEMADEN_OM gradboost  0.330068   0.274856 139
    guarara    saturante   CEMADEN_OM    logreg  0.380676   0.503071 139
    guarara    saturante CEMADEN_ONLY gradboost  0.340675   0.262914 139
    guarara    saturante CEMADEN_ONLY    logreg  0.380676   0.503071 139
    meninos      pancada          ALL gradboost  0.086465   0.087723 139
    meninos      pancada          ALL    logreg  0.154145   0.300779 139
    meninos      pancada   CEMADEN_OM gradboost  0.112248   0.108327 139
    meninos      pancada   CEMADEN_OM    logreg  0.169922   0.316495 139
    meninos      pancada CEMADEN_ONLY gradboost  0.073898   0.079010 139
    meninos      pancada CEMADEN_ONLY    logreg  0.169922   0.316495 139
    meninos perigoso_any          ALL gradboost  0.318847   0.339697 139
    meninos perigoso_any          ALL    logreg  0.304980   0.547783 139
    meninos perigoso_any   CEMADEN_OM gradboost  0.309427   0.370966 139
    meninos perigoso_any   CEMADEN_OM    logreg  0.305605   0.551256 139
    meninos perigoso_any CEMADEN_ONLY gradboost  0.307804   0.335904 139
    meninos perigoso_any CEMADEN_ONLY    logreg  0.305605   0.551256 139
    meninos   prolongada          ALL gradboost  0.196588   0.195627 139
    meninos   prolongada          ALL    logreg  0.282279   0.556846 139
    meninos   prolongada   CEMADEN_OM gradboost  0.175947   0.222527 139
    meninos   prolongada   CEMADEN_OM    logreg  0.281554   0.567691 139
    meninos   prolongada CEMADEN_ONLY gradboost  0.210789   0.253809 139
    meninos   prolongada CEMADEN_ONLY    logreg  0.281554   0.567691 139
    meninos    saturante          ALL gradboost  0.258565   0.139495 139
    meninos    saturante          ALL    logreg  0.383506   0.314567 139
    meninos    saturante   CEMADEN_OM gradboost  0.287985   0.174601 139
    meninos    saturante   CEMADEN_OM    logreg  0.387155   0.321311 139
    meninos    saturante CEMADEN_ONLY gradboost  0.271727   0.155422 139
    meninos    saturante CEMADEN_ONLY    logreg  0.387155   0.321311 139
   oratorio      pancada          ALL gradboost  0.081374   0.066731 139
   oratorio      pancada          ALL    logreg  0.144723   0.208972 139
   oratorio      pancada   CEMADEN_OM gradboost  0.092899   0.068984 139
   oratorio      pancada   CEMADEN_OM    logreg  0.151669   0.222893 139
   oratorio      pancada CEMADEN_ONLY gradboost  0.085152   0.065005 139
   oratorio      pancada CEMADEN_ONLY    logreg  0.151669   0.222893 139
   oratorio perigoso_any          ALL gradboost  0.294339   0.306780 139
   oratorio perigoso_any          ALL    logreg  0.306876   0.531362 139
   oratorio perigoso_any   CEMADEN_OM gradboost  0.282721   0.290098 139
   oratorio perigoso_any   CEMADEN_OM    logreg  0.306014   0.533907 139
   oratorio perigoso_any CEMADEN_ONLY gradboost  0.285478   0.291624 139
   oratorio perigoso_any CEMADEN_ONLY    logreg  0.306014   0.533907 139
   oratorio   prolongada          ALL gradboost  0.122402   0.110922 139
   oratorio   prolongada          ALL    logreg  0.168831   0.449226 139
   oratorio   prolongada   CEMADEN_OM gradboost  0.128782   0.143092 139
   oratorio   prolongada   CEMADEN_OM    logreg  0.134764   0.409475 139
   oratorio   prolongada CEMADEN_ONLY gradboost  0.128585   0.108721 139
   oratorio   prolongada CEMADEN_ONLY    logreg  0.134764   0.409475 139
   oratorio    saturante          ALL gradboost  0.286704   0.191500 139
   oratorio    saturante          ALL    logreg  0.356889   0.520345 139
   oratorio    saturante   CEMADEN_OM gradboost  0.298691   0.231025 139
   oratorio    saturante   CEMADEN_OM    logreg  0.356736   0.524564 139
   oratorio    saturante CEMADEN_ONLY gradboost  0.286339   0.192859 139
   oratorio    saturante CEMADEN_ONLY    logreg  0.356736   0.524564 139
tamanduatei      pancada          ALL gradboost  0.096888   0.092519 139
tamanduatei      pancada          ALL    logreg  0.230862   0.274167 139
tamanduatei      pancada   CEMADEN_OM gradboost  0.107719   0.128482 139
tamanduatei      pancada   CEMADEN_OM    logreg  0.232817   0.272301 139
tamanduatei      pancada CEMADEN_ONLY gradboost  0.094031   0.100430 139
tamanduatei      pancada CEMADEN_ONLY    logreg  0.232817   0.272301 139
tamanduatei perigoso_any          ALL gradboost  0.310478   0.352424 139
tamanduatei perigoso_any          ALL    logreg  0.322030   0.551997 139
tamanduatei perigoso_any   CEMADEN_OM gradboost  0.288434   0.346758 139
tamanduatei perigoso_any   CEMADEN_OM    logreg  0.324585   0.549458 139
tamanduatei perigoso_any CEMADEN_ONLY gradboost  0.315796   0.376284 139
tamanduatei perigoso_any CEMADEN_ONLY    logreg  0.324585   0.549458 139
tamanduatei   prolongada          ALL gradboost  0.183479   0.205903 139
tamanduatei   prolongada          ALL    logreg  0.226453   0.415129 139
tamanduatei   prolongada   CEMADEN_OM gradboost  0.231308   0.311447 139
tamanduatei   prolongada   CEMADEN_OM    logreg  0.243999   0.437965 139
tamanduatei   prolongada CEMADEN_ONLY gradboost  0.210155   0.244583 139
tamanduatei   prolongada CEMADEN_ONLY    logreg  0.243999   0.437965 139
tamanduatei    saturante          ALL gradboost  0.328466   0.248117 139
tamanduatei    saturante          ALL    logreg  0.360269   0.555758 139
tamanduatei    saturante   CEMADEN_OM gradboost  0.317068   0.249732 139
tamanduatei    saturante   CEMADEN_OM    logreg  0.360128   0.556857 139
tamanduatei    saturante CEMADEN_ONLY gradboost  0.331109   0.257359 139
tamanduatei    saturante CEMADEN_ONLY    logreg  0.360128   0.556857 139
```

## 6. Inversões (Spearman negativo)

```
      bacia        label     variante    modelo  spearman_rho  inversao
    guarara      pancada          ALL gradboost      0.229734     False
    guarara      pancada          ALL    logreg      0.403327     False
    guarara      pancada   CEMADEN_OM gradboost      0.311877     False
    guarara      pancada   CEMADEN_OM    logreg      0.415808     False
    guarara      pancada CEMADEN_ONLY gradboost      0.314922     False
    guarara      pancada CEMADEN_ONLY    logreg      0.415808     False
    guarara perigoso_any          ALL gradboost      0.390655     False
    guarara perigoso_any          ALL    logreg      0.423863     False
    guarara perigoso_any   CEMADEN_OM gradboost      0.390963     False
    guarara perigoso_any   CEMADEN_OM    logreg      0.430327     False
    guarara perigoso_any CEMADEN_ONLY gradboost      0.392102     False
    guarara perigoso_any CEMADEN_ONLY    logreg      0.430327     False
    guarara   prolongada          ALL gradboost      0.379091     False
    guarara   prolongada          ALL    logreg      0.419821     False
    guarara   prolongada   CEMADEN_OM gradboost      0.368386     False
    guarara   prolongada   CEMADEN_OM    logreg      0.427250     False
    guarara   prolongada CEMADEN_ONLY gradboost      0.380657     False
    guarara   prolongada CEMADEN_ONLY    logreg      0.427250     False
    guarara    saturante          ALL gradboost      0.416288     False
    guarara    saturante          ALL    logreg      0.433184     False
    guarara    saturante   CEMADEN_OM gradboost      0.440787     False
    guarara    saturante   CEMADEN_OM    logreg      0.432030     False
    guarara    saturante CEMADEN_ONLY gradboost      0.445615     False
    guarara    saturante CEMADEN_ONLY    logreg      0.432030     False
    meninos      pancada          ALL gradboost      0.223591     False
    meninos      pancada          ALL    logreg      0.480031     False
    meninos      pancada   CEMADEN_OM gradboost      0.346725     False
    meninos      pancada   CEMADEN_OM    logreg      0.506706     False
    meninos      pancada CEMADEN_ONLY gradboost      0.298087     False
    meninos      pancada CEMADEN_ONLY    logreg      0.506706     False
    meninos perigoso_any          ALL gradboost      0.402846     False
    meninos perigoso_any          ALL    logreg      0.495837     False
    meninos perigoso_any   CEMADEN_OM gradboost      0.463892     False
    meninos perigoso_any   CEMADEN_OM    logreg      0.494243     False
    meninos perigoso_any CEMADEN_ONLY gradboost      0.472047     False
    meninos perigoso_any CEMADEN_ONLY    logreg      0.494243     False
    meninos   prolongada          ALL gradboost      0.349477     False
    meninos   prolongada          ALL    logreg      0.512614     False
    meninos   prolongada   CEMADEN_OM gradboost      0.426039     False
    meninos   prolongada   CEMADEN_OM    logreg      0.513456     False
    meninos   prolongada CEMADEN_ONLY gradboost      0.443470     False
    meninos   prolongada CEMADEN_ONLY    logreg      0.513456     False
    meninos    saturante          ALL gradboost      0.457153     False
    meninos    saturante          ALL    logreg      0.362962     False
    meninos    saturante   CEMADEN_OM gradboost      0.429002     False
    meninos    saturante   CEMADEN_OM    logreg      0.357126     False
    meninos    saturante CEMADEN_ONLY gradboost      0.419088     False
    meninos    saturante CEMADEN_ONLY    logreg      0.357126     False
   oratorio      pancada          ALL gradboost     -0.002051      True
   oratorio      pancada          ALL    logreg      0.027395     False
   oratorio      pancada   CEMADEN_OM gradboost      0.193182     False
   oratorio      pancada   CEMADEN_OM    logreg     -0.017551      True
   oratorio      pancada CEMADEN_ONLY gradboost      0.226092     False
   oratorio      pancada CEMADEN_ONLY    logreg     -0.017551      True
   oratorio perigoso_any          ALL gradboost      0.377856     False
   oratorio perigoso_any          ALL    logreg      0.440289     False
   oratorio perigoso_any   CEMADEN_OM gradboost      0.370412     False
   oratorio perigoso_any   CEMADEN_OM    logreg      0.439944     False
   oratorio perigoso_any CEMADEN_ONLY gradboost      0.395717     False
   oratorio perigoso_any CEMADEN_ONLY    logreg      0.439944     False
   oratorio   prolongada          ALL gradboost      0.123002     False
   oratorio   prolongada          ALL    logreg      0.448659     False
   oratorio   prolongada   CEMADEN_OM gradboost      0.182507     False
   oratorio   prolongada   CEMADEN_OM    logreg      0.334619     False
   oratorio   prolongada CEMADEN_ONLY gradboost      0.152943     False
   oratorio   prolongada CEMADEN_ONLY    logreg      0.334619     False
   oratorio    saturante          ALL gradboost      0.303358     False
   oratorio    saturante          ALL    logreg      0.422464     False
   oratorio    saturante   CEMADEN_OM gradboost      0.372677     False
   oratorio    saturante   CEMADEN_OM    logreg      0.414873     False
   oratorio    saturante CEMADEN_ONLY gradboost      0.311871     False
   oratorio    saturante CEMADEN_ONLY    logreg      0.414873     False
tamanduatei      pancada          ALL gradboost      0.230225     False
tamanduatei      pancada          ALL    logreg      0.352798     False
tamanduatei      pancada   CEMADEN_OM gradboost      0.305975     False
tamanduatei      pancada   CEMADEN_OM    logreg      0.347537     False
tamanduatei      pancada CEMADEN_ONLY gradboost      0.172652     False
tamanduatei      pancada CEMADEN_ONLY    logreg      0.347537     False
tamanduatei perigoso_any          ALL gradboost      0.450684     False
tamanduatei perigoso_any          ALL    logreg      0.452971     False
tamanduatei perigoso_any   CEMADEN_OM gradboost      0.467541     False
tamanduatei perigoso_any   CEMADEN_OM    logreg      0.451671     False
tamanduatei perigoso_any CEMADEN_ONLY gradboost      0.442283     False
tamanduatei perigoso_any CEMADEN_ONLY    logreg      0.451671     False
tamanduatei   prolongada          ALL gradboost      0.456010     False
tamanduatei   prolongada          ALL    logreg      0.464967     False
tamanduatei   prolongada   CEMADEN_OM gradboost      0.515139     False
tamanduatei   prolongada   CEMADEN_OM    logreg      0.460373     False
tamanduatei   prolongada CEMADEN_ONLY gradboost      0.462835     False
tamanduatei   prolongada CEMADEN_ONLY    logreg      0.460373     False
tamanduatei    saturante          ALL gradboost      0.462254     False
tamanduatei    saturante          ALL    logreg      0.431963     False
tamanduatei    saturante   CEMADEN_OM gradboost      0.454801     False
tamanduatei    saturante   CEMADEN_OM    logreg      0.430891     False
tamanduatei    saturante CEMADEN_ONLY gradboost      0.465717     False
tamanduatei    saturante CEMADEN_ONLY    logreg      0.430891     False
```


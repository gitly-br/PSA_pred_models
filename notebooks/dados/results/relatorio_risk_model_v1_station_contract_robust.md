# Relatório Risk Model V1 — Station Contract ROBUST

**Data:** 2026-05-20

## 1. Configuração

- Treino: até 2023-07-02
- Test histórico: após corte até 2025-12-31
- Holdout 2026: 2026-01-01 a 2026-05-19 (dados parciais)
- Modelos: ['gradboost_cons', 'gradboost_std', 'logreg_cons', 'logreg_std']
- Variantes: ['CEMADEN_ONLY', 'CEMADEN_OM', 'ALL']
- Labels: ['pancada', 'prolongada', 'saturante', 'perigoso_any']
- Regularização: gradboost_cons (max_depth=2, min_samples_leaf=20); logreg_cons (C=0.1)

## 2. Cobertura 2026 (contrato atualizado)

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

### Análise de proxies

- **guarara** mês 1: 13/17 estações presentes (4 ausente(s)) — 13129 registros
- **guarara** mês 2: 13/17 estações presentes (4 ausente(s)) — 11101 registros
- **guarara** mês 3: 13/17 estações presentes (4 ausente(s)) — 12372 registros
- **guarara** mês 4: 13/17 estações presentes (4 ausente(s)) — 9531 registros
- **guarara** mês 5: 12/17 estações presentes (5 ausente(s)) — 6452 registros
- **meninos** mês 1: 8/10 estações presentes (2 ausente(s)) — 7887 registros
- **meninos** mês 2: 8/10 estações presentes (2 ausente(s)) — 6744 registros
- **meninos** mês 3: 8/10 estações presentes (2 ausente(s)) — 7254 registros
- **meninos** mês 4: 8/10 estações presentes (2 ausente(s)) — 5851 registros
- **meninos** mês 5: 8/10 estações presentes (2 ausente(s)) — 4121 registros
- **oratorio** mês 1: 10/11 estações presentes (1 ausente(s)) — 9810 registros
- **oratorio** mês 2: 10/11 estações presentes (1 ausente(s)) — 8441 registros
- **oratorio** mês 3: 10/11 estações presentes (1 ausente(s)) — 9021 registros
- **oratorio** mês 4: 10/11 estações presentes (1 ausente(s)) — 7257 registros
- **oratorio** mês 5: 10/11 estações presentes (1 ausente(s)) — 5416 registros
- **tamanduatei** mês 1: 16/19 estações presentes (3 ausente(s)) — 15473 registros
- **tamanduatei** mês 2: 16/19 estações presentes (3 ausente(s)) — 13384 registros
- **tamanduatei** mês 3: 16/19 estações presentes (3 ausente(s)) — 14578 registros
- **tamanduatei** mês 4: 16/19 estações presentes (3 ausente(s)) — 11336 registros
- **tamanduatei** mês 5: 15/19 estações presentes (4 ausente(s)) — 8028 registros

## 3. Métricas Test Histórico (até 2025)

```
      bacia        label     variante         modelo    prauc  spearman_rho   recall  precision       f1
    guarara      pancada CEMADEN_ONLY gradboost_cons 0.092877      0.378959 0.032258   0.038462 0.035088
    guarara      pancada          ALL gradboost_cons 0.091111      0.374801 0.225806   0.095890 0.134615
    guarara      pancada          ALL  gradboost_std 0.089159      0.350355 0.419355   0.080745 0.135417
    guarara      pancada   CEMADEN_OM     logreg_std 0.085035      0.376672 0.451613   0.063927 0.112000
    guarara      pancada CEMADEN_ONLY     logreg_std 0.085035      0.376672 0.451613   0.063927 0.112000
    guarara      pancada   CEMADEN_OM gradboost_cons 0.082796      0.381685 0.161290   0.084746 0.111111
    guarara      pancada          ALL     logreg_std 0.082482      0.359944 0.419355   0.064356 0.111588
    guarara      pancada   CEMADEN_OM    logreg_cons 0.082445      0.381695 0.612903   0.069091 0.124183
    guarara      pancada CEMADEN_ONLY    logreg_cons 0.082445      0.381695 0.612903   0.069091 0.124183
    guarara      pancada   CEMADEN_OM  gradboost_std 0.081767      0.348192 0.483871   0.073892 0.128205
    guarara      pancada          ALL    logreg_cons 0.081542      0.372740 0.193548   0.065934 0.098361
    guarara      pancada CEMADEN_ONLY  gradboost_std 0.075714      0.345352 0.451613   0.070707 0.122271
    guarara perigoso_any   CEMADEN_OM gradboost_cons 0.606306      0.484567 0.519608   0.540816 0.530000
    guarara perigoso_any CEMADEN_ONLY gradboost_cons 0.600500      0.485535 0.549020   0.513761 0.530806
    guarara perigoso_any   CEMADEN_OM  gradboost_std 0.594345      0.466525 0.450980   0.621622 0.522727
    guarara perigoso_any          ALL gradboost_cons 0.592826      0.485873 0.539216   0.474138 0.504587
    guarara perigoso_any CEMADEN_ONLY  gradboost_std 0.581377      0.466406 0.450980   0.575000 0.505495
    guarara perigoso_any          ALL  gradboost_std 0.578839      0.462326 0.470588   0.571429 0.516129
    guarara perigoso_any          ALL     logreg_std 0.572214      0.474002 0.450980   0.676471 0.541176
    guarara perigoso_any          ALL    logreg_cons 0.571713      0.477814 0.401961   0.706897 0.512500
    guarara perigoso_any   CEMADEN_OM     logreg_std 0.571460      0.472907 0.500000   0.520408 0.510000
    guarara perigoso_any CEMADEN_ONLY     logreg_std 0.571460      0.472907 0.500000   0.520408 0.510000
    guarara perigoso_any   CEMADEN_OM    logreg_cons 0.571054      0.477136 0.450980   0.707692 0.550898
    guarara perigoso_any CEMADEN_ONLY    logreg_cons 0.571054      0.477136 0.450980   0.707692 0.550898
    guarara   prolongada   CEMADEN_OM     logreg_std 0.218199      0.448318 0.402778   0.228346 0.291457
    guarara   prolongada CEMADEN_ONLY     logreg_std 0.218199      0.448318 0.402778   0.228346 0.291457
    guarara   prolongada          ALL    logreg_cons 0.214795      0.454032 0.250000   0.264706 0.257143
    guarara   prolongada          ALL     logreg_std 0.213072      0.457830 0.527778   0.167401 0.254181
    guarara   prolongada   CEMADEN_OM    logreg_cons 0.210821      0.445663 0.250000   0.257143 0.253521
    guarara   prolongada CEMADEN_ONLY    logreg_cons 0.210821      0.445663 0.250000   0.257143 0.253521
    guarara   prolongada CEMADEN_ONLY gradboost_cons 0.208824      0.474079 0.611111   0.196429 0.297297
    guarara   prolongada   CEMADEN_OM gradboost_cons 0.206715      0.480573 0.416667   0.245902 0.309278
    guarara   prolongada CEMADEN_ONLY  gradboost_std 0.203095      0.457856 0.444444   0.250000 0.320000
    guarara   prolongada   CEMADEN_OM  gradboost_std 0.191417      0.455817 0.500000   0.192513 0.277992
    guarara   prolongada          ALL gradboost_cons 0.189944      0.483929 0.555556   0.216216 0.311284
    guarara   prolongada          ALL  gradboost_std 0.186983      0.447250 0.486111   0.233333 0.315315
    guarara    saturante   CEMADEN_OM gradboost_cons 0.736472      0.470384 0.600000   0.656250 0.626866
    guarara    saturante CEMADEN_ONLY gradboost_cons 0.733298      0.475915 0.657143   0.613333 0.634483
    guarara    saturante CEMADEN_ONLY  gradboost_std 0.731295      0.457757 0.642857   0.625000 0.633803
    guarara    saturante          ALL  gradboost_std 0.729812      0.458290 0.585714   0.706897 0.640625
    guarara    saturante          ALL gradboost_cons 0.727367      0.460668 0.585714   0.672131 0.625954
    guarara    saturante   CEMADEN_OM  gradboost_std 0.726939      0.473757 0.600000   0.626866 0.613139
    guarara    saturante   CEMADEN_OM     logreg_std 0.721493      0.482500 0.600000   0.700000 0.646154
    guarara    saturante CEMADEN_ONLY     logreg_std 0.721493      0.482500 0.600000   0.700000 0.646154
    guarara    saturante          ALL     logreg_std 0.720481      0.482454 0.614286   0.704918 0.656489
    guarara    saturante   CEMADEN_OM    logreg_cons 0.718449      0.487428 0.600000   0.656250 0.626866
    guarara    saturante CEMADEN_ONLY    logreg_cons 0.718449      0.487428 0.600000   0.656250 0.626866
    guarara    saturante          ALL    logreg_cons 0.718389      0.487415 0.600000   0.656250 0.626866
    meninos      pancada          ALL    logreg_cons 0.128630      0.388194 0.125000   0.121212 0.123077
    meninos      pancada   CEMADEN_OM    logreg_cons 0.127077      0.376714 0.125000   0.125000 0.125000
    meninos      pancada CEMADEN_ONLY    logreg_cons 0.127077      0.376714 0.125000   0.125000 0.125000
    meninos      pancada   CEMADEN_OM     logreg_std 0.122575      0.371510 0.156250   0.142857 0.149254
    meninos      pancada CEMADEN_ONLY     logreg_std 0.122575      0.371510 0.156250   0.142857 0.149254
    meninos      pancada          ALL     logreg_std 0.110796      0.391552 0.218750   0.090909 0.128440
    meninos      pancada          ALL gradboost_cons 0.091288      0.431857 0.375000   0.084507 0.137931
    meninos      pancada          ALL  gradboost_std 0.075444      0.419497 0.343750   0.067073 0.112245
    meninos      pancada CEMADEN_ONLY gradboost_cons 0.075396      0.433012 0.562500   0.072000 0.127660
    meninos      pancada   CEMADEN_OM  gradboost_std 0.074796      0.413517 0.187500   0.081081 0.113208
    meninos      pancada   CEMADEN_OM gradboost_cons 0.072661      0.434955 0.250000   0.076190 0.116788
    meninos      pancada CEMADEN_ONLY  gradboost_std 0.069140      0.399401 0.187500   0.058252 0.088889
    meninos perigoso_any          ALL     logreg_std 0.553667      0.475519 0.436893   0.569620 0.494505
    meninos perigoso_any   CEMADEN_OM     logreg_std 0.550034      0.469076 0.398058   0.732143 0.515723
    meninos perigoso_any CEMADEN_ONLY     logreg_std 0.550034      0.469076 0.398058   0.732143 0.515723
    meninos perigoso_any          ALL    logreg_cons 0.547936      0.477107 0.407767   0.666667 0.506024
    meninos perigoso_any   CEMADEN_OM    logreg_cons 0.547260      0.472741 0.398058   0.732143 0.515723
    meninos perigoso_any CEMADEN_ONLY    logreg_cons 0.547260      0.472741 0.398058   0.732143 0.515723
    meninos perigoso_any   CEMADEN_OM gradboost_cons 0.546963      0.508887 0.466019   0.521739 0.492308
    meninos perigoso_any CEMADEN_ONLY  gradboost_std 0.546899      0.486413 0.436893   0.562500 0.491803
    meninos perigoso_any   CEMADEN_OM  gradboost_std 0.543974      0.473319 0.485437   0.531915 0.507614
    meninos perigoso_any          ALL gradboost_cons 0.531310      0.501636 0.427184   0.611111 0.502857
    meninos perigoso_any CEMADEN_ONLY gradboost_cons 0.530101      0.502429 0.417476   0.581081 0.485876
    meninos perigoso_any          ALL  gradboost_std 0.523975      0.468296 0.368932   0.678571 0.477987
    meninos   prolongada   CEMADEN_OM     logreg_std 0.242885      0.453399 0.272727   0.295775 0.283784
    meninos   prolongada CEMADEN_ONLY     logreg_std 0.242885      0.453399 0.272727   0.295775 0.283784
    meninos   prolongada          ALL     logreg_std 0.239561      0.463374 0.272727   0.308824 0.289655
    meninos   prolongada   CEMADEN_OM    logreg_cons 0.237146      0.451716 0.298701   0.261364 0.278788
    meninos   prolongada CEMADEN_ONLY    logreg_cons 0.237146      0.451716 0.298701   0.261364 0.278788
    meninos   prolongada          ALL    logreg_cons 0.237036      0.459081 0.298701   0.267442 0.282209
    meninos   prolongada   CEMADEN_OM gradboost_cons 0.206391      0.510094 0.324675   0.240385 0.276243
    meninos   prolongada          ALL gradboost_cons 0.204877      0.494323 0.454545   0.228758 0.304348
    meninos   prolongada   CEMADEN_OM  gradboost_std 0.198359      0.479856 0.337662   0.238532 0.279570
    meninos   prolongada CEMADEN_ONLY  gradboost_std 0.196374      0.480134 0.233766   0.250000 0.241611
    meninos   prolongada CEMADEN_ONLY gradboost_cons 0.193153      0.504123 0.428571   0.198795 0.271605
    meninos   prolongada          ALL  gradboost_std 0.186520      0.480026 0.350649   0.216000 0.267327
    meninos    saturante          ALL     logreg_std 0.713664      0.475983 0.630769   0.640625 0.635659
    meninos    saturante   CEMADEN_OM     logreg_std 0.713348      0.472056 0.630769   0.745455 0.683333
    meninos    saturante CEMADEN_ONLY     logreg_std 0.713348      0.472056 0.630769   0.745455 0.683333
    meninos    saturante          ALL    logreg_cons 0.710082      0.477060 0.630769   0.694915 0.661290
    meninos    saturante   CEMADEN_OM    logreg_cons 0.708041      0.476385 0.584615   0.791667 0.672566
    meninos    saturante CEMADEN_ONLY    logreg_cons 0.708041      0.476385 0.584615   0.791667 0.672566
    meninos    saturante          ALL gradboost_cons 0.689374      0.507088 0.661538   0.558442 0.605634
    meninos    saturante   CEMADEN_OM  gradboost_std 0.685725      0.525065 0.569231   0.685185 0.621849
    meninos    saturante          ALL  gradboost_std 0.684910      0.506446 0.600000   0.629032 0.614173
    meninos    saturante CEMADEN_ONLY  gradboost_std 0.684906      0.501702 0.569231   0.649123 0.606557
    meninos    saturante CEMADEN_ONLY gradboost_cons 0.679963      0.522681 0.615385   0.645161 0.629921
    meninos    saturante   CEMADEN_OM gradboost_cons 0.675851      0.527295 0.615385   0.625000 0.620155
   oratorio      pancada CEMADEN_ONLY gradboost_cons 0.131154      0.389537 0.354839   0.108911 0.166667
   oratorio      pancada CEMADEN_ONLY  gradboost_std 0.113687      0.393327 0.548387   0.073593 0.129771
   oratorio      pancada   CEMADEN_OM gradboost_cons 0.110842      0.404263 0.612903   0.053977 0.099217
   oratorio      pancada   CEMADEN_OM  gradboost_std 0.103845      0.394418 0.483871   0.089820 0.151515
   oratorio      pancada          ALL gradboost_cons 0.103120      0.399767 0.322581   0.106383 0.160000
   oratorio      pancada          ALL    logreg_cons 0.090278      0.383502 0.354839   0.113402 0.171875
   oratorio      pancada          ALL  gradboost_std 0.089285      0.383151 0.322581   0.109890 0.163934
   oratorio      pancada          ALL     logreg_std 0.087186      0.394098 0.387097   0.075472 0.126316
   oratorio      pancada   CEMADEN_OM    logreg_cons 0.084755      0.369132 0.322581   0.102041 0.155039
   oratorio      pancada CEMADEN_ONLY    logreg_cons 0.084755      0.369132 0.322581   0.102041 0.155039
   oratorio      pancada   CEMADEN_OM     logreg_std 0.082821      0.369489 0.387097   0.074534 0.125000
   oratorio      pancada CEMADEN_ONLY     logreg_std 0.082821      0.369489 0.387097   0.074534 0.125000
   oratorio perigoso_any          ALL  gradboost_std 0.541760      0.429717 0.390909   0.614286 0.477778
   oratorio perigoso_any CEMADEN_ONLY  gradboost_std 0.536593      0.427652 0.500000   0.478261 0.488889
   oratorio perigoso_any   CEMADEN_OM gradboost_cons 0.535068      0.456116 0.400000   0.611111 0.483516
   oratorio perigoso_any CEMADEN_ONLY gradboost_cons 0.534255      0.454776 0.490909   0.495413 0.493151
   oratorio perigoso_any          ALL     logreg_std 0.533755      0.433410 0.418182   0.560976 0.479167
   oratorio perigoso_any          ALL    logreg_cons 0.531111      0.434965 0.454545   0.531915 0.490196
   oratorio perigoso_any   CEMADEN_OM     logreg_std 0.530832      0.430498 0.418182   0.560976 0.479167
   oratorio perigoso_any CEMADEN_ONLY     logreg_std 0.530832      0.430498 0.418182   0.560976 0.479167
   oratorio perigoso_any          ALL gradboost_cons 0.530216      0.456970 0.400000   0.628571 0.488889
   oratorio perigoso_any   CEMADEN_OM    logreg_cons 0.528491      0.433795 0.454545   0.531915 0.490196
   oratorio perigoso_any CEMADEN_ONLY    logreg_cons 0.528491      0.433795 0.454545   0.531915 0.490196
   oratorio perigoso_any   CEMADEN_OM  gradboost_std 0.511952      0.429197 0.490909   0.461538 0.475771
   oratorio   prolongada   CEMADEN_OM gradboost_cons 0.192746      0.449815 0.637500   0.178947 0.279452
   oratorio   prolongada          ALL gradboost_cons 0.191726      0.456961 0.600000   0.184615 0.282353
   oratorio   prolongada   CEMADEN_OM    logreg_cons 0.190381      0.396350 0.300000   0.226415 0.258065
   oratorio   prolongada CEMADEN_ONLY    logreg_cons 0.190381      0.396350 0.300000   0.226415 0.258065
   oratorio   prolongada CEMADEN_ONLY gradboost_cons 0.187751      0.457523 0.625000   0.167224 0.263852
   oratorio   prolongada          ALL     logreg_std 0.179545      0.413413 0.325000   0.230088 0.269430
   oratorio   prolongada          ALL    logreg_cons 0.179303      0.409561 0.325000   0.242991 0.278075
   oratorio   prolongada   CEMADEN_OM     logreg_std 0.178413      0.394690 0.287500   0.219048 0.248649
   oratorio   prolongada CEMADEN_ONLY     logreg_std 0.178413      0.394690 0.287500   0.219048 0.248649
   oratorio   prolongada   CEMADEN_OM  gradboost_std 0.177291      0.428055 0.700000   0.153425 0.251685
   oratorio   prolongada          ALL  gradboost_std 0.167930      0.423189 0.575000   0.178988 0.272997
   oratorio   prolongada CEMADEN_ONLY  gradboost_std 0.167468      0.414267 0.500000   0.160000 0.242424
   oratorio    saturante          ALL  gradboost_std 0.686223      0.449054 0.642857   0.562500 0.600000
   oratorio    saturante   CEMADEN_OM  gradboost_std 0.685145      0.465080 0.685714   0.480000 0.564706
   oratorio    saturante          ALL    logreg_cons 0.678951      0.459859 0.600000   0.583333 0.591549
   oratorio    saturante   CEMADEN_OM    logreg_cons 0.678407      0.458955 0.600000   0.583333 0.591549
   oratorio    saturante CEMADEN_ONLY    logreg_cons 0.678407      0.458955 0.600000   0.583333 0.591549
   oratorio    saturante          ALL     logreg_std 0.677694      0.458501 0.600000   0.677419 0.636364
   oratorio    saturante   CEMADEN_OM     logreg_std 0.675278      0.457033 0.600000   0.700000 0.646154
   oratorio    saturante CEMADEN_ONLY     logreg_std 0.675278      0.457033 0.600000   0.700000 0.646154
   oratorio    saturante   CEMADEN_OM gradboost_cons 0.663962      0.460645 0.542857   0.826087 0.655172
   oratorio    saturante CEMADEN_ONLY gradboost_cons 0.661544      0.461273 0.557143   0.780000 0.650000
   oratorio    saturante CEMADEN_ONLY  gradboost_std 0.661221      0.457915 0.657143   0.474227 0.550898
   oratorio    saturante          ALL gradboost_cons 0.641403      0.462635 0.542857   0.826087 0.655172
tamanduatei      pancada          ALL    logreg_cons 0.105910      0.387036 0.205882   0.107692 0.141414
tamanduatei      pancada          ALL     logreg_std 0.105731      0.384300 0.235294   0.121212 0.160000
tamanduatei      pancada   CEMADEN_OM    logreg_cons 0.104980      0.385053 0.205882   0.104478 0.138614
tamanduatei      pancada CEMADEN_ONLY    logreg_cons 0.104980      0.385053 0.205882   0.104478 0.138614
tamanduatei      pancada          ALL  gradboost_std 0.104114      0.388923 0.176471   0.113208 0.137931
tamanduatei      pancada   CEMADEN_OM     logreg_std 0.103872      0.380343 0.235294   0.111111 0.150943
tamanduatei      pancada CEMADEN_ONLY     logreg_std 0.103872      0.380343 0.235294   0.111111 0.150943
tamanduatei      pancada CEMADEN_ONLY gradboost_cons 0.101326      0.401352 0.264706   0.094737 0.139535
tamanduatei      pancada          ALL gradboost_cons 0.097556      0.414040 0.294118   0.091743 0.139860
tamanduatei      pancada   CEMADEN_OM  gradboost_std 0.088332      0.366596 0.411765   0.097902 0.158192
tamanduatei      pancada   CEMADEN_OM gradboost_cons 0.085562      0.402199 0.235294   0.081633 0.121212
tamanduatei      pancada CEMADEN_ONLY  gradboost_std 0.084965      0.384329 0.117647   0.071429 0.088889
tamanduatei perigoso_any   CEMADEN_OM gradboost_cons 0.587309      0.479530 0.455357   0.593023 0.515152
tamanduatei perigoso_any          ALL gradboost_cons 0.586867      0.475207 0.553571   0.512397 0.532189
tamanduatei perigoso_any   CEMADEN_OM  gradboost_std 0.583433      0.469525 0.455357   0.607143 0.520408
tamanduatei perigoso_any CEMADEN_ONLY gradboost_cons 0.577408      0.474191 0.437500   0.636364 0.518519
tamanduatei perigoso_any          ALL    logreg_cons 0.567684      0.474307 0.464286   0.604651 0.525253
tamanduatei perigoso_any   CEMADEN_OM    logreg_cons 0.567232      0.473499 0.446429   0.666667 0.534759
tamanduatei perigoso_any CEMADEN_ONLY    logreg_cons 0.567232      0.473499 0.446429   0.666667 0.534759
tamanduatei perigoso_any          ALL     logreg_std 0.565634      0.470753 0.464286   0.634146 0.536082
tamanduatei perigoso_any   CEMADEN_OM     logreg_std 0.565172      0.470131 0.455357   0.653846 0.536842
tamanduatei perigoso_any CEMADEN_ONLY     logreg_std 0.565172      0.470131 0.455357   0.653846 0.536842
tamanduatei perigoso_any          ALL  gradboost_std 0.563644      0.440719 0.562500   0.463235 0.508065
tamanduatei perigoso_any CEMADEN_ONLY  gradboost_std 0.551326      0.452773 0.491071   0.500000 0.495495
tamanduatei   prolongada   CEMADEN_OM gradboost_cons 0.232361      0.484936 0.597403   0.180392 0.277108
tamanduatei   prolongada   CEMADEN_OM  gradboost_std 0.216583      0.458693 0.480519   0.185930 0.268116
tamanduatei   prolongada CEMADEN_ONLY gradboost_cons 0.214148      0.480978 0.519481   0.224719 0.313725
tamanduatei   prolongada          ALL gradboost_cons 0.211273      0.476065 0.506494   0.213115 0.300000
tamanduatei   prolongada          ALL     logreg_std 0.207323      0.451690 0.480519   0.200000 0.282443
tamanduatei   prolongada          ALL    logreg_cons 0.203570      0.449009 0.363636   0.247788 0.294737
tamanduatei   prolongada   CEMADEN_OM    logreg_cons 0.201627      0.440888 0.298701   0.242105 0.267442
tamanduatei   prolongada CEMADEN_ONLY    logreg_cons 0.201627      0.440888 0.298701   0.242105 0.267442
tamanduatei   prolongada   CEMADEN_OM     logreg_std 0.201230      0.441783 0.480519   0.222892 0.304527
tamanduatei   prolongada CEMADEN_ONLY     logreg_std 0.201230      0.441783 0.480519   0.222892 0.304527
tamanduatei   prolongada CEMADEN_ONLY  gradboost_std 0.198134      0.443723 0.480519   0.171296 0.252560
tamanduatei   prolongada          ALL  gradboost_std 0.194964      0.448103 0.506494   0.190244 0.276596
tamanduatei    saturante          ALL     logreg_std 0.713076      0.487067 0.644737   0.653333 0.649007
tamanduatei    saturante          ALL    logreg_cons 0.712601      0.488847 0.631579   0.666667 0.648649
tamanduatei    saturante   CEMADEN_OM     logreg_std 0.712164      0.486404 0.631579   0.705882 0.666667
tamanduatei    saturante CEMADEN_ONLY     logreg_std 0.712164      0.486404 0.631579   0.705882 0.666667
tamanduatei    saturante   CEMADEN_OM    logreg_cons 0.712081      0.489278 0.644737   0.636364 0.640523
tamanduatei    saturante CEMADEN_ONLY    logreg_cons 0.712081      0.489278 0.644737   0.636364 0.640523
tamanduatei    saturante   CEMADEN_OM gradboost_cons 0.699829      0.466197 0.644737   0.597561 0.620253
tamanduatei    saturante   CEMADEN_OM  gradboost_std 0.694887      0.465068 0.644737   0.576471 0.608696
tamanduatei    saturante          ALL gradboost_cons 0.691355      0.480536 0.644737   0.620253 0.632258
tamanduatei    saturante CEMADEN_ONLY gradboost_cons 0.688381      0.475934 0.723684   0.561224 0.632184
tamanduatei    saturante CEMADEN_ONLY  gradboost_std 0.684859      0.461814 0.631579   0.615385 0.623377
tamanduatei    saturante          ALL  gradboost_std 0.667253      0.447852 0.618421   0.610390 0.614379
```

## 4. Métricas Holdout 2026

```
      bacia        label     variante         modelo    prauc  spearman_rho   recall  precision       f1  n_test
    guarara      pancada          ALL gradboost_cons 0.287284      0.417367 0.125000   0.200000 0.153846     139
    guarara      pancada   CEMADEN_OM gradboost_cons 0.209639      0.399996 0.250000   0.500000 0.333333     139
    guarara      pancada CEMADEN_ONLY  gradboost_std 0.192753      0.400973 0.500000   0.105263 0.173913     139
    guarara      pancada CEMADEN_ONLY gradboost_cons 0.190211      0.401487 0.000000   0.000000 0.000000     139
    guarara      pancada   CEMADEN_OM  gradboost_std 0.157685      0.390428 0.500000   0.078431 0.135593     139
    guarara      pancada   CEMADEN_OM     logreg_std 0.144704      0.397496 0.625000   0.185185 0.285714     139
    guarara      pancada CEMADEN_ONLY     logreg_std 0.144704      0.397496 0.625000   0.185185 0.285714     139
    guarara      pancada          ALL    logreg_cons 0.143212      0.412107 0.375000   0.142857 0.206897     139
    guarara      pancada   CEMADEN_OM    logreg_cons 0.139151      0.415611 0.625000   0.121951 0.204082     139
    guarara      pancada CEMADEN_ONLY    logreg_cons 0.139151      0.415611 0.625000   0.121951 0.204082     139
    guarara      pancada          ALL     logreg_std 0.136536      0.356459 0.625000   0.200000 0.303030     139
    guarara      pancada          ALL  gradboost_std 0.104981      0.343625 0.500000   0.088889 0.150943     139
    guarara perigoso_any   CEMADEN_OM gradboost_cons 0.888852      0.464660 0.634921   0.930233 0.754717     139
    guarara perigoso_any          ALL gradboost_cons 0.886809      0.446360 0.682540   0.914894 0.781818     139
    guarara perigoso_any   CEMADEN_OM  gradboost_std 0.885229      0.440949 0.539683   0.944444 0.686869     139
    guarara perigoso_any CEMADEN_ONLY gradboost_cons 0.884528      0.450511 0.650794   0.911111 0.759259     139
    guarara perigoso_any   CEMADEN_OM    logreg_cons 0.879095      0.460833 0.492063   1.000000 0.659574     139
    guarara perigoso_any CEMADEN_ONLY    logreg_cons 0.879095      0.460833 0.492063   1.000000 0.659574     139
    guarara perigoso_any          ALL    logreg_cons 0.877776      0.457309 0.444444   1.000000 0.615385     139
    guarara perigoso_any CEMADEN_ONLY  gradboost_std 0.877142      0.422592 0.523810   0.942857 0.673469     139
    guarara perigoso_any          ALL  gradboost_std 0.874760      0.403663 0.476190   0.967742 0.638298     139
    guarara perigoso_any   CEMADEN_OM     logreg_std 0.870744      0.418285 0.682540   0.860000 0.761062     139
    guarara perigoso_any CEMADEN_ONLY     logreg_std 0.870744      0.418285 0.682540   0.860000 0.761062     139
    guarara perigoso_any          ALL     logreg_std 0.868192      0.410104 0.603175   0.904762 0.723810     139
    guarara   prolongada          ALL    logreg_cons 0.575123      0.455375 0.340909   0.517241 0.410959     139
    guarara   prolongada   CEMADEN_OM    logreg_cons 0.575075      0.454360 0.340909   0.500000 0.405405     139
    guarara   prolongada CEMADEN_ONLY    logreg_cons 0.575075      0.454360 0.340909   0.500000 0.405405     139
    guarara   prolongada          ALL     logreg_std 0.554985      0.417922 0.500000   0.536585 0.517647     139
    guarara   prolongada   CEMADEN_OM     logreg_std 0.552549      0.415796 0.386364   0.515152 0.441558     139
    guarara   prolongada CEMADEN_ONLY     logreg_std 0.552549      0.415796 0.386364   0.515152 0.441558     139
    guarara   prolongada CEMADEN_ONLY gradboost_cons 0.552427      0.480195 0.704545   0.492063 0.579439     139
    guarara   prolongada          ALL  gradboost_std 0.534269      0.433477 0.204545   0.642857 0.310345     139
    guarara   prolongada          ALL gradboost_cons 0.521250      0.444065 0.681818   0.545455 0.606061     139
    guarara   prolongada   CEMADEN_OM  gradboost_std 0.517646      0.434037 0.454545   0.540541 0.493827     139
    guarara   prolongada CEMADEN_ONLY  gradboost_std 0.511958      0.442314 0.409091   0.620690 0.493151     139
    guarara   prolongada   CEMADEN_OM gradboost_cons 0.474703      0.477891 0.409091   0.562500 0.473684     139
    guarara    saturante   CEMADEN_OM    logreg_cons 0.903043      0.446206 0.607143   0.971429 0.747253     139
    guarara    saturante CEMADEN_ONLY    logreg_cons 0.903043      0.446206 0.607143   0.971429 0.747253     139
    guarara    saturante          ALL    logreg_cons 0.902847      0.445395 0.625000   0.972222 0.760870     139
    guarara    saturante          ALL     logreg_std 0.897134      0.433621 0.714286   0.888889 0.792079     139
    guarara    saturante          ALL gradboost_cons 0.895887      0.452414 0.571429   0.969697 0.719101     139
    guarara    saturante   CEMADEN_OM     logreg_std 0.895746      0.428530 0.714286   0.888889 0.792079     139
    guarara    saturante CEMADEN_ONLY     logreg_std 0.895746      0.428530 0.714286   0.888889 0.792079     139
    guarara    saturante   CEMADEN_OM gradboost_cons 0.891478      0.442578 0.642857   0.923077 0.757895     139
    guarara    saturante   CEMADEN_OM  gradboost_std 0.885351      0.413398 0.625000   0.945946 0.752688     139
    guarara    saturante          ALL  gradboost_std 0.883380      0.461584 0.535714   0.967742 0.689655     139
    guarara    saturante CEMADEN_ONLY gradboost_cons 0.881240      0.446261 0.589286   0.942857 0.725275     139
    guarara    saturante CEMADEN_ONLY  gradboost_std 0.876287      0.435313 0.589286   0.942857 0.725275     139
    meninos      pancada   CEMADEN_OM gradboost_cons 0.237491      0.498967 0.125000   0.071429 0.090909     139
    meninos      pancada   CEMADEN_OM  gradboost_std 0.197592      0.426470 0.125000   0.076923 0.095238     139
    meninos      pancada          ALL  gradboost_std 0.195642      0.390868 0.375000   0.187500 0.250000     139
    meninos      pancada          ALL gradboost_cons 0.186227      0.517964 0.250000   0.111111 0.153846     139
    meninos      pancada CEMADEN_ONLY gradboost_cons 0.165258      0.535171 0.500000   0.114286 0.186047     139
    meninos      pancada          ALL    logreg_cons 0.150148      0.500842 0.125000   0.100000 0.111111     139
    meninos      pancada   CEMADEN_OM    logreg_cons 0.149110      0.497571 0.125000   0.090909 0.105263     139
    meninos      pancada CEMADEN_ONLY    logreg_cons 0.149110      0.497571 0.125000   0.090909 0.105263     139
    meninos      pancada   CEMADEN_OM     logreg_std 0.139528      0.411743 0.125000   0.166667 0.142857     139
    meninos      pancada CEMADEN_ONLY     logreg_std 0.139528      0.411743 0.125000   0.166667 0.142857     139
    meninos      pancada CEMADEN_ONLY  gradboost_std 0.137301      0.476980 0.125000   0.052632 0.074074     139
    meninos      pancada          ALL     logreg_std 0.134696      0.395620 0.125000   0.142857 0.133333     139
    meninos perigoso_any   CEMADEN_OM    logreg_cons 0.878412      0.512997 0.557692   1.000000 0.716049     139
    meninos perigoso_any CEMADEN_ONLY    logreg_cons 0.878412      0.512997 0.557692   1.000000 0.716049     139
    meninos perigoso_any          ALL    logreg_cons 0.877680      0.514595 0.557692   1.000000 0.716049     139
    meninos perigoso_any   CEMADEN_OM     logreg_std 0.876731      0.491697 0.615385   0.914286 0.735632     139
    meninos perigoso_any CEMADEN_ONLY     logreg_std 0.876731      0.491697 0.615385   0.914286 0.735632     139
    meninos perigoso_any          ALL     logreg_std 0.875768      0.492742 0.673077   0.875000 0.760870     139
    meninos perigoso_any   CEMADEN_OM gradboost_cons 0.870470      0.515262 0.692308   0.837209 0.757895     139
    meninos perigoso_any          ALL gradboost_cons 0.860374      0.524415 0.615385   0.969697 0.752941     139
    meninos perigoso_any CEMADEN_ONLY gradboost_cons 0.858993      0.525039 0.576923   0.937500 0.714286     139
    meninos perigoso_any          ALL  gradboost_std 0.850922      0.462904 0.442308   1.000000 0.613333     139
    meninos perigoso_any CEMADEN_ONLY  gradboost_std 0.847940      0.506941 0.576923   0.810811 0.674157     139
    meninos perigoso_any   CEMADEN_OM  gradboost_std 0.834679      0.486456 0.673077   0.760870 0.714286     139
    meninos   prolongada   CEMADEN_OM     logreg_std 0.612510      0.513425 0.564103   0.523810 0.543210     139
    meninos   prolongada CEMADEN_ONLY     logreg_std 0.612510      0.513425 0.564103   0.523810 0.543210     139
    meninos   prolongada          ALL    logreg_cons 0.609758      0.510833 0.512821   0.526316 0.519481     139
    meninos   prolongada   CEMADEN_OM    logreg_cons 0.607623      0.513979 0.564103   0.523810 0.543210     139
    meninos   prolongada CEMADEN_ONLY    logreg_cons 0.607623      0.513979 0.564103   0.523810 0.543210     139
    meninos   prolongada          ALL     logreg_std 0.605315      0.511165 0.512821   0.540541 0.526316     139
    meninos   prolongada   CEMADEN_OM gradboost_cons 0.581315      0.527273 0.487179   0.500000 0.493506     139
    meninos   prolongada CEMADEN_ONLY gradboost_cons 0.554610      0.530995 0.717949   0.500000 0.589474     139
    meninos   prolongada          ALL gradboost_cons 0.551322      0.516983 0.615385   0.521739 0.564706     139
    meninos   prolongada   CEMADEN_OM  gradboost_std 0.525920      0.467596 0.589744   0.522727 0.554217     139
    meninos   prolongada          ALL  gradboost_std 0.510120      0.476531 0.307692   0.571429 0.400000     139
    meninos   prolongada CEMADEN_ONLY  gradboost_std 0.475180      0.476445 0.358974   0.482759 0.411765     139
    meninos    saturante   CEMADEN_OM    logreg_cons 0.899177      0.441089 0.444444   1.000000 0.615385     139
    meninos    saturante CEMADEN_ONLY    logreg_cons 0.899177      0.441089 0.444444   1.000000 0.615385     139
    meninos    saturante          ALL    logreg_cons 0.895219      0.430128 0.555556   1.000000 0.714286     139
    meninos    saturante   CEMADEN_OM  gradboost_std 0.886256      0.472533 0.355556   1.000000 0.524590     139
    meninos    saturante   CEMADEN_OM     logreg_std 0.886099      0.342900 0.622222   1.000000 0.767123     139
    meninos    saturante CEMADEN_ONLY     logreg_std 0.886099      0.342900 0.622222   1.000000 0.767123     139
    meninos    saturante CEMADEN_ONLY gradboost_cons 0.885119      0.472344 0.400000   1.000000 0.571429     139
    meninos    saturante          ALL     logreg_std 0.884827      0.344422 0.622222   1.000000 0.767123     139
    meninos    saturante CEMADEN_ONLY  gradboost_std 0.884161      0.464460 0.377778   1.000000 0.548387     139
    meninos    saturante   CEMADEN_OM gradboost_cons 0.884128      0.475105 0.422222   1.000000 0.593750     139
    meninos    saturante          ALL  gradboost_std 0.882768      0.470862 0.466667   1.000000 0.636364     139
    meninos    saturante          ALL gradboost_cons 0.874054      0.442728 0.466667   1.000000 0.636364     139
   oratorio      pancada   CEMADEN_OM gradboost_cons 0.077792      0.366562 0.571429   0.071429 0.126984     139
   oratorio      pancada          ALL  gradboost_std 0.069663      0.272815 0.000000   0.000000 0.000000     139
   oratorio      pancada          ALL    logreg_cons 0.067222      0.285918 0.000000   0.000000 0.000000     139
   oratorio      pancada   CEMADEN_OM    logreg_cons 0.067122      0.251907 0.000000   0.000000 0.000000     139
   oratorio      pancada CEMADEN_ONLY    logreg_cons 0.067122      0.251907 0.000000   0.000000 0.000000     139
   oratorio      pancada          ALL     logreg_std 0.064419     -0.013686 0.000000   0.000000 0.000000     139
   oratorio      pancada CEMADEN_ONLY gradboost_cons 0.064202      0.372176 0.000000   0.000000 0.000000     139
   oratorio      pancada   CEMADEN_OM  gradboost_std 0.064034      0.359243 0.000000   0.000000 0.000000     139
   oratorio      pancada CEMADEN_ONLY  gradboost_std 0.061579      0.335866 0.000000   0.000000 0.000000     139
   oratorio      pancada   CEMADEN_OM     logreg_std 0.059739     -0.072345 0.000000   0.000000 0.000000     139
   oratorio      pancada CEMADEN_ONLY     logreg_std 0.059739     -0.072345 0.000000   0.000000 0.000000     139
   oratorio      pancada          ALL gradboost_cons 0.059192      0.357568 0.000000   0.000000 0.000000     139
   oratorio perigoso_any          ALL     logreg_std 0.870545      0.439305 0.578947   0.970588 0.725275     139
   oratorio perigoso_any   CEMADEN_OM     logreg_std 0.870199      0.437292 0.578947   0.970588 0.725275     139
   oratorio perigoso_any CEMADEN_ONLY     logreg_std 0.870199      0.437292 0.578947   0.970588 0.725275     139
   oratorio perigoso_any   CEMADEN_OM    logreg_cons 0.868855      0.444777 0.491228   0.965517 0.651163     139
   oratorio perigoso_any CEMADEN_ONLY    logreg_cons 0.868855      0.444777 0.491228   0.965517 0.651163     139
   oratorio perigoso_any          ALL    logreg_cons 0.867456      0.442746 0.491228   0.965517 0.651163     139
   oratorio perigoso_any CEMADEN_ONLY gradboost_cons 0.862569      0.462153 0.543860   0.968750 0.696629     139
   oratorio perigoso_any          ALL gradboost_cons 0.854666      0.454349 0.526316   1.000000 0.689655     139
   oratorio perigoso_any   CEMADEN_OM gradboost_cons 0.854231      0.447934 0.438596   1.000000 0.609756     139
   oratorio perigoso_any          ALL  gradboost_std 0.837459      0.422248 0.403509   1.000000 0.575000     139
   oratorio perigoso_any CEMADEN_ONLY  gradboost_std 0.818252      0.426127 0.403509   0.920000 0.560976     139
   oratorio perigoso_any   CEMADEN_OM  gradboost_std 0.815055      0.434880 0.438596   0.961538 0.602410     139
   oratorio   prolongada   CEMADEN_OM gradboost_cons 0.564269      0.439607 0.476190   0.606061 0.533333     139
   oratorio   prolongada          ALL gradboost_cons 0.559193      0.461154 0.357143   0.555556 0.434783     139
   oratorio   prolongada CEMADEN_ONLY gradboost_cons 0.555099      0.466997 0.547619   0.534884 0.541176     139
   oratorio   prolongada          ALL    logreg_cons 0.513841      0.428294 0.214286   0.600000 0.315789     139
   oratorio   prolongada   CEMADEN_OM  gradboost_std 0.506167      0.438582 0.666667   0.437500 0.528302     139
   oratorio   prolongada   CEMADEN_OM    logreg_cons 0.501689      0.396551 0.190476   0.571429 0.285714     139
   oratorio   prolongada CEMADEN_ONLY    logreg_cons 0.501689      0.396551 0.190476   0.571429 0.285714     139
   oratorio   prolongada          ALL  gradboost_std 0.490973      0.416412 0.214286   0.529412 0.305085     139
   oratorio   prolongada CEMADEN_ONLY  gradboost_std 0.466994      0.399555 0.142857   0.375000 0.206897     139
   oratorio   prolongada          ALL     logreg_std 0.421041      0.299212 0.023810   0.333333 0.044444     139
   oratorio   prolongada   CEMADEN_OM     logreg_std 0.326178      0.065101 0.000000   0.000000 0.000000     139
   oratorio   prolongada CEMADEN_ONLY     logreg_std 0.326178      0.065101 0.000000   0.000000 0.000000     139
   oratorio    saturante          ALL     logreg_std 0.893529      0.422414 0.711538   0.925000 0.804348     139
   oratorio    saturante   CEMADEN_OM     logreg_std 0.893140      0.419594 0.711538   0.925000 0.804348     139
   oratorio    saturante CEMADEN_ONLY     logreg_std 0.893140      0.419594 0.711538   0.925000 0.804348     139
   oratorio    saturante   CEMADEN_OM    logreg_cons 0.892071      0.430234 0.557692   1.000000 0.716049     139
   oratorio    saturante CEMADEN_ONLY    logreg_cons 0.892071      0.430234 0.557692   1.000000 0.716049     139
   oratorio    saturante          ALL    logreg_cons 0.891609      0.431601 0.576923   1.000000 0.731707     139
   oratorio    saturante   CEMADEN_OM gradboost_cons 0.867110      0.400467 0.346154   1.000000 0.514286     139
   oratorio    saturante CEMADEN_ONLY gradboost_cons 0.865228      0.421277 0.423077   1.000000 0.594595     139
   oratorio    saturante          ALL gradboost_cons 0.863001      0.412250 0.307692   1.000000 0.470588     139
   oratorio    saturante   CEMADEN_OM  gradboost_std 0.852938      0.433133 0.500000   0.962963 0.658228     139
   oratorio    saturante CEMADEN_ONLY  gradboost_std 0.838006      0.391615 0.461538   0.960000 0.623377     139
   oratorio    saturante          ALL  gradboost_std 0.817870      0.398732 0.480769   0.961538 0.641026     139
tamanduatei      pancada          ALL    logreg_cons 0.191438      0.400507 0.285714   0.133333 0.181818     139
tamanduatei      pancada   CEMADEN_OM    logreg_cons 0.189158      0.410590 0.285714   0.133333 0.181818     139
tamanduatei      pancada CEMADEN_ONLY    logreg_cons 0.189158      0.410590 0.285714   0.133333 0.181818     139
tamanduatei      pancada   CEMADEN_OM     logreg_std 0.154818      0.272464 0.285714   0.142857 0.190476     139
tamanduatei      pancada CEMADEN_ONLY     logreg_std 0.154818      0.272464 0.285714   0.142857 0.190476     139
tamanduatei      pancada          ALL     logreg_std 0.152918      0.275930 0.285714   0.142857 0.190476     139
tamanduatei      pancada          ALL gradboost_cons 0.124817      0.441115 0.142857   0.125000 0.133333     139
tamanduatei      pancada   CEMADEN_OM gradboost_cons 0.098798      0.447780 0.142857   0.100000 0.117647     139
tamanduatei      pancada CEMADEN_ONLY gradboost_cons 0.088799      0.436327 0.142857   0.100000 0.117647     139
tamanduatei      pancada CEMADEN_ONLY  gradboost_std 0.085555      0.470088 0.000000   0.000000 0.000000     139
tamanduatei      pancada          ALL  gradboost_std 0.075411      0.465206 0.000000   0.000000 0.000000     139
tamanduatei      pancada   CEMADEN_OM  gradboost_std 0.067994      0.389781 0.142857   0.029412 0.048780     139
tamanduatei perigoso_any   CEMADEN_OM gradboost_cons 0.879551      0.483369 0.612903   0.950000 0.745098     139
tamanduatei perigoso_any   CEMADEN_OM    logreg_cons 0.878626      0.468051 0.564516   0.945946 0.707071     139
tamanduatei perigoso_any CEMADEN_ONLY    logreg_cons 0.878626      0.468051 0.564516   0.945946 0.707071     139
tamanduatei perigoso_any   CEMADEN_OM     logreg_std 0.877409      0.455971 0.629032   0.906977 0.742857     139
tamanduatei perigoso_any CEMADEN_ONLY     logreg_std 0.877409      0.455971 0.629032   0.906977 0.742857     139
tamanduatei perigoso_any          ALL    logreg_cons 0.877053      0.465491 0.612903   0.926829 0.737864     139
tamanduatei perigoso_any          ALL     logreg_std 0.876294      0.456153 0.645161   0.888889 0.747664     139
tamanduatei perigoso_any          ALL gradboost_cons 0.872482      0.464554 0.741935   0.807018 0.773109     139
tamanduatei perigoso_any CEMADEN_ONLY gradboost_cons 0.869131      0.487773 0.548387   0.944444 0.693878     139
tamanduatei perigoso_any          ALL  gradboost_std 0.861487      0.482578 0.693548   0.781818 0.735043     139
tamanduatei perigoso_any   CEMADEN_OM  gradboost_std 0.856405      0.477544 0.483871   0.967742 0.645161     139
tamanduatei perigoso_any CEMADEN_ONLY  gradboost_std 0.837634      0.471847 0.629032   0.866667 0.728972     139
tamanduatei   prolongada   CEMADEN_OM gradboost_cons 0.616859      0.496179 0.804348   0.474359 0.596774     139
tamanduatei   prolongada          ALL gradboost_cons 0.610790      0.484788 0.739130   0.507463 0.601770     139
tamanduatei   prolongada   CEMADEN_OM  gradboost_std 0.592478      0.489367 0.739130   0.515152 0.607143     139
tamanduatei   prolongada CEMADEN_ONLY gradboost_cons 0.591568      0.478784 0.695652   0.492308 0.576577     139
tamanduatei   prolongada          ALL  gradboost_std 0.589655      0.495757 0.630435   0.557692 0.591837     139
tamanduatei   prolongada          ALL    logreg_cons 0.588718      0.478502 0.456522   0.552632 0.500000     139
tamanduatei   prolongada   CEMADEN_OM    logreg_cons 0.586425      0.476539 0.456522   0.552632 0.500000     139
tamanduatei   prolongada CEMADEN_ONLY    logreg_cons 0.586425      0.476539 0.456522   0.552632 0.500000     139
tamanduatei   prolongada CEMADEN_ONLY  gradboost_std 0.581019      0.519786 0.695652   0.516129 0.592593     139
tamanduatei   prolongada          ALL     logreg_std 0.563180      0.470003 0.413043   0.575758 0.481013     139
tamanduatei   prolongada   CEMADEN_OM     logreg_std 0.558709      0.460690 0.369565   0.566667 0.447368     139
tamanduatei   prolongada CEMADEN_ONLY     logreg_std 0.558709      0.460690 0.369565   0.566667 0.447368     139
tamanduatei    saturante          ALL gradboost_cons 0.905081      0.470032 0.678571   0.950000 0.791667     139
tamanduatei    saturante   CEMADEN_OM     logreg_std 0.896035      0.432920 0.714286   0.869565 0.784314     139
tamanduatei    saturante CEMADEN_ONLY     logreg_std 0.896035      0.432920 0.714286   0.869565 0.784314     139
tamanduatei    saturante          ALL     logreg_std 0.895967      0.433766 0.750000   0.840000 0.792453     139
tamanduatei    saturante   CEMADEN_OM gradboost_cons 0.895641      0.470966 0.660714   0.948718 0.778947     139
tamanduatei    saturante          ALL    logreg_cons 0.895105      0.440092 0.678571   0.883721 0.767677     139
tamanduatei    saturante   CEMADEN_OM    logreg_cons 0.894904      0.439370 0.678571   0.904762 0.775510     139
tamanduatei    saturante CEMADEN_ONLY    logreg_cons 0.894904      0.439370 0.678571   0.904762 0.775510     139
tamanduatei    saturante CEMADEN_ONLY gradboost_cons 0.891987      0.478129 0.678571   0.883721 0.767677     139
tamanduatei    saturante          ALL  gradboost_std 0.885022      0.458023 0.571429   0.969697 0.719101     139
tamanduatei    saturante   CEMADEN_OM  gradboost_std 0.884504      0.463461 0.678571   0.883721 0.767677     139
tamanduatei    saturante CEMADEN_ONLY  gradboost_std 0.878001      0.475849 0.642857   0.947368 0.765957     139
```

## 5. Estabilidade (std prob em 2026)

```
      bacia        label     variante         modelo  prob_std  prob_mean   n
    guarara      pancada          ALL gradboost_cons  0.081598   0.109449 139
    guarara      pancada          ALL  gradboost_std  0.098546   0.155385 139
    guarara      pancada          ALL    logreg_cons  0.152875   0.191323 139
    guarara      pancada          ALL     logreg_std  0.127198   0.157406 139
    guarara      pancada   CEMADEN_OM gradboost_cons  0.082835   0.121573 139
    guarara      pancada   CEMADEN_OM  gradboost_std  0.098790   0.143168 139
    guarara      pancada   CEMADEN_OM    logreg_cons  0.154839   0.199976 139
    guarara      pancada   CEMADEN_OM     logreg_std  0.137723   0.165110 139
    guarara      pancada CEMADEN_ONLY gradboost_cons  0.088524   0.119468 139
    guarara      pancada CEMADEN_ONLY  gradboost_std  0.084750   0.127123 139
    guarara      pancada CEMADEN_ONLY    logreg_cons  0.154839   0.199976 139
    guarara      pancada CEMADEN_ONLY     logreg_std  0.137723   0.165110 139
    guarara perigoso_any          ALL gradboost_cons  0.305437   0.427036 139
    guarara perigoso_any          ALL  gradboost_std  0.293312   0.343257 139
    guarara perigoso_any          ALL    logreg_cons  0.320831   0.425622 139
    guarara perigoso_any          ALL     logreg_std  0.359504   0.446424 139
    guarara perigoso_any   CEMADEN_OM gradboost_cons  0.294325   0.427538 139
    guarara perigoso_any   CEMADEN_OM  gradboost_std  0.292161   0.390264 139
    guarara perigoso_any   CEMADEN_OM    logreg_cons  0.319612   0.424884 139
    guarara perigoso_any   CEMADEN_OM     logreg_std  0.359017   0.447435 139
    guarara perigoso_any CEMADEN_ONLY gradboost_cons  0.289037   0.411710 139
    guarara perigoso_any CEMADEN_ONLY  gradboost_std  0.292532   0.368666 139
    guarara perigoso_any CEMADEN_ONLY    logreg_cons  0.319612   0.424884 139
    guarara perigoso_any CEMADEN_ONLY     logreg_std  0.359017   0.447435 139
    guarara   prolongada          ALL gradboost_cons  0.191359   0.302806 139
    guarara   prolongada          ALL  gradboost_std  0.137350   0.212546 139
    guarara   prolongada          ALL    logreg_cons  0.253629   0.358597 139
    guarara   prolongada          ALL     logreg_std  0.262116   0.306892 139
    guarara   prolongada   CEMADEN_OM gradboost_cons  0.179213   0.307795 139
    guarara   prolongada   CEMADEN_OM  gradboost_std  0.170356   0.247031 139
    guarara   prolongada   CEMADEN_OM    logreg_cons  0.254306   0.363162 139
    guarara   prolongada   CEMADEN_OM     logreg_std  0.258676   0.299706 139
    guarara   prolongada CEMADEN_ONLY gradboost_cons  0.209412   0.325165 139
    guarara   prolongada CEMADEN_ONLY  gradboost_std  0.171353   0.257789 139
    guarara   prolongada CEMADEN_ONLY    logreg_cons  0.254306   0.363162 139
    guarara   prolongada CEMADEN_ONLY     logreg_std  0.258676   0.299706 139
    guarara    saturante          ALL gradboost_cons  0.334925   0.319256 139
    guarara    saturante          ALL  gradboost_std  0.314866   0.297918 139
    guarara    saturante          ALL    logreg_cons  0.365793   0.367160 139
    guarara    saturante          ALL     logreg_std  0.398787   0.416733 139
    guarara    saturante   CEMADEN_OM gradboost_cons  0.347052   0.347806 139
    guarara    saturante   CEMADEN_OM  gradboost_std  0.320673   0.304681 139
    guarara    saturante   CEMADEN_OM    logreg_cons  0.364866   0.369215 139
    guarara    saturante   CEMADEN_OM     logreg_std  0.399116   0.414979 139
    guarara    saturante CEMADEN_ONLY gradboost_cons  0.318214   0.318166 139
    guarara    saturante CEMADEN_ONLY  gradboost_std  0.307886   0.305175 139
    guarara    saturante CEMADEN_ONLY    logreg_cons  0.364866   0.369215 139
    guarara    saturante CEMADEN_ONLY     logreg_std  0.399116   0.414979 139
    meninos      pancada          ALL gradboost_cons  0.098464   0.122706 139
    meninos      pancada          ALL  gradboost_std  0.080760   0.098017 139
    meninos      pancada          ALL    logreg_cons  0.142762   0.194599 139
    meninos      pancada          ALL     logreg_std  0.083790   0.134914 139
    meninos      pancada   CEMADEN_OM gradboost_cons  0.096415   0.116026 139
    meninos      pancada   CEMADEN_OM  gradboost_std  0.103856   0.128343 139
    meninos      pancada   CEMADEN_OM    logreg_cons  0.144689   0.198495 139
    meninos      pancada   CEMADEN_OM     logreg_std  0.088418   0.143298 139
    meninos      pancada CEMADEN_ONLY gradboost_cons  0.110368   0.122572 139
    meninos      pancada CEMADEN_ONLY  gradboost_std  0.099494   0.132572 139
    meninos      pancada CEMADEN_ONLY    logreg_cons  0.144689   0.198495 139
    meninos      pancada CEMADEN_ONLY     logreg_std  0.088418   0.143298 139
    meninos perigoso_any          ALL gradboost_cons  0.311567   0.383767 139
    meninos perigoso_any          ALL  gradboost_std  0.284295   0.363132 139
    meninos perigoso_any          ALL    logreg_cons  0.310236   0.415620 139
    meninos perigoso_any          ALL     logreg_std  0.340616   0.420916 139
    meninos perigoso_any   CEMADEN_OM gradboost_cons  0.307068   0.392611 139
    meninos perigoso_any   CEMADEN_OM  gradboost_std  0.297536   0.369555 139
    meninos perigoso_any   CEMADEN_OM    logreg_cons  0.310216   0.417782 139
    meninos perigoso_any   CEMADEN_OM     logreg_std  0.341825   0.424899 139
    meninos perigoso_any CEMADEN_ONLY gradboost_cons  0.311850   0.386824 139
    meninos perigoso_any CEMADEN_ONLY  gradboost_std  0.290899   0.343360 139
    meninos perigoso_any CEMADEN_ONLY    logreg_cons  0.310216   0.417782 139
    meninos perigoso_any CEMADEN_ONLY     logreg_std  0.341825   0.424899 139
    meninos   prolongada          ALL gradboost_cons  0.211450   0.279887 139
    meninos   prolongada          ALL  gradboost_std  0.152497   0.236856 139
    meninos   prolongada          ALL    logreg_cons  0.265453   0.405465 139
    meninos   prolongada          ALL     logreg_std  0.304090   0.410384 139
    meninos   prolongada   CEMADEN_OM gradboost_cons  0.199004   0.304883 139
    meninos   prolongada   CEMADEN_OM  gradboost_std  0.193981   0.270855 139
    meninos   prolongada   CEMADEN_OM    logreg_cons  0.265149   0.409770 139
    meninos   prolongada   CEMADEN_OM     logreg_std  0.305604   0.421143 139
    meninos   prolongada CEMADEN_ONLY gradboost_cons  0.220198   0.305995 139
    meninos   prolongada CEMADEN_ONLY  gradboost_std  0.185345   0.261945 139
    meninos   prolongada CEMADEN_ONLY    logreg_cons  0.265149   0.409770 139
    meninos   prolongada CEMADEN_ONLY     logreg_std  0.305604   0.421143 139
    meninos    saturante          ALL gradboost_cons  0.278113   0.198904 139
    meninos    saturante          ALL  gradboost_std  0.289898   0.227181 139
    meninos    saturante          ALL    logreg_cons  0.350996   0.255803 139
    meninos    saturante          ALL     logreg_std  0.374136   0.256862 139
    meninos    saturante   CEMADEN_OM gradboost_cons  0.291215   0.230688 139
    meninos    saturante   CEMADEN_OM  gradboost_std  0.281859   0.208049 139
    meninos    saturante   CEMADEN_OM    logreg_cons  0.351768   0.260389 139
    meninos    saturante   CEMADEN_OM     logreg_std  0.378131   0.262778 139
    meninos    saturante CEMADEN_ONLY gradboost_cons  0.289309   0.205107 139
    meninos    saturante CEMADEN_ONLY  gradboost_std  0.278065   0.194144 139
    meninos    saturante CEMADEN_ONLY    logreg_cons  0.351768   0.260389 139
    meninos    saturante CEMADEN_ONLY     logreg_std  0.378131   0.262778 139
   oratorio      pancada          ALL gradboost_cons  0.093391   0.132849 139
   oratorio      pancada          ALL  gradboost_std  0.064162   0.099233 139
   oratorio      pancada          ALL    logreg_cons  0.093454   0.175804 139
   oratorio      pancada          ALL     logreg_std  0.089011   0.113703 139
   oratorio      pancada   CEMADEN_OM gradboost_cons  0.092884   0.131267 139
   oratorio      pancada   CEMADEN_OM  gradboost_std  0.069346   0.104368 139
   oratorio      pancada   CEMADEN_OM    logreg_cons  0.098822   0.186631 139
   oratorio      pancada   CEMADEN_OM     logreg_std  0.101573   0.124539 139
   oratorio      pancada CEMADEN_ONLY gradboost_cons  0.099518   0.127694 139
   oratorio      pancada CEMADEN_ONLY  gradboost_std  0.069295   0.078070 139
   oratorio      pancada CEMADEN_ONLY    logreg_cons  0.098822   0.186631 139
   oratorio      pancada CEMADEN_ONLY     logreg_std  0.101573   0.124539 139
   oratorio perigoso_any          ALL gradboost_cons  0.283366   0.381672 139
   oratorio perigoso_any          ALL  gradboost_std  0.280063   0.331735 139
   oratorio perigoso_any          ALL    logreg_cons  0.284694   0.370875 139
   oratorio perigoso_any          ALL     logreg_std  0.335849   0.407640 139
   oratorio perigoso_any   CEMADEN_OM gradboost_cons  0.269741   0.357356 139
   oratorio perigoso_any   CEMADEN_OM  gradboost_std  0.258010   0.319222 139
   oratorio perigoso_any   CEMADEN_OM    logreg_cons  0.286719   0.373726 139
   oratorio perigoso_any   CEMADEN_OM     logreg_std  0.334791   0.415674 139
   oratorio perigoso_any CEMADEN_ONLY gradboost_cons  0.273453   0.348410 139
   oratorio perigoso_any CEMADEN_ONLY  gradboost_std  0.245804   0.285006 139
   oratorio perigoso_any CEMADEN_ONLY    logreg_cons  0.286719   0.373726 139
   oratorio perigoso_any CEMADEN_ONLY     logreg_std  0.334791   0.415674 139
   oratorio   prolongada          ALL gradboost_cons  0.141552   0.223630 139
   oratorio   prolongada          ALL  gradboost_std  0.106603   0.178227 139
   oratorio   prolongada          ALL    logreg_cons  0.140541   0.305973 139
   oratorio   prolongada          ALL     logreg_std  0.098204   0.228918 139
   oratorio   prolongada   CEMADEN_OM gradboost_cons  0.135148   0.225068 139
   oratorio   prolongada   CEMADEN_OM  gradboost_std  0.135217   0.241433 139
   oratorio   prolongada   CEMADEN_OM    logreg_cons  0.138720   0.311030 139
   oratorio   prolongada   CEMADEN_OM     logreg_std  0.107577   0.214629 139
   oratorio   prolongada CEMADEN_ONLY gradboost_cons  0.143433   0.247745 139
   oratorio   prolongada CEMADEN_ONLY  gradboost_std  0.103204   0.180458 139
   oratorio   prolongada CEMADEN_ONLY    logreg_cons  0.138720   0.311030 139
   oratorio   prolongada CEMADEN_ONLY     logreg_std  0.107577   0.214629 139
   oratorio    saturante          ALL gradboost_cons  0.294779   0.270351 139
   oratorio    saturante          ALL  gradboost_std  0.290666   0.237705 139
   oratorio    saturante          ALL    logreg_cons  0.338320   0.353782 139
   oratorio    saturante          ALL     logreg_std  0.374324   0.413812 139
   oratorio    saturante   CEMADEN_OM gradboost_cons  0.309903   0.276874 139
   oratorio    saturante   CEMADEN_OM  gradboost_std  0.270941   0.239560 139
   oratorio    saturante   CEMADEN_OM    logreg_cons  0.338377   0.346801 139
   oratorio    saturante   CEMADEN_OM     logreg_std  0.374458   0.409397 139
   oratorio    saturante CEMADEN_ONLY gradboost_cons  0.306533   0.266279 139
   oratorio    saturante CEMADEN_ONLY  gradboost_std  0.277911   0.232773 139
   oratorio    saturante CEMADEN_ONLY    logreg_cons  0.338377   0.346801 139
   oratorio    saturante CEMADEN_ONLY     logreg_std  0.374458   0.409397 139
tamanduatei      pancada          ALL gradboost_cons  0.081063   0.113709 139
tamanduatei      pancada          ALL  gradboost_std  0.098599   0.134556 139
tamanduatei      pancada          ALL    logreg_cons  0.174539   0.171082 139
tamanduatei      pancada          ALL     logreg_std  0.161630   0.140577 139
tamanduatei      pancada   CEMADEN_OM gradboost_cons  0.098077   0.138437 139
tamanduatei      pancada   CEMADEN_OM  gradboost_std  0.102299   0.147060 139
tamanduatei      pancada   CEMADEN_OM    logreg_cons  0.174517   0.175560 139
tamanduatei      pancada   CEMADEN_OM     logreg_std  0.151359   0.134257 139
tamanduatei      pancada CEMADEN_ONLY gradboost_cons  0.094477   0.125721 139
tamanduatei      pancada CEMADEN_ONLY  gradboost_std  0.079913   0.116388 139
tamanduatei      pancada CEMADEN_ONLY    logreg_cons  0.174517   0.175560 139
tamanduatei      pancada CEMADEN_ONLY     logreg_std  0.151359   0.134257 139
tamanduatei perigoso_any          ALL gradboost_cons  0.311455   0.467920 139
tamanduatei perigoso_any          ALL  gradboost_std  0.297463   0.392078 139
tamanduatei perigoso_any          ALL    logreg_cons  0.320497   0.447875 139
tamanduatei perigoso_any          ALL     logreg_std  0.354886   0.453965 139
tamanduatei perigoso_any   CEMADEN_OM gradboost_cons  0.298575   0.453484 139
tamanduatei perigoso_any   CEMADEN_OM  gradboost_std  0.281585   0.392686 139
tamanduatei perigoso_any   CEMADEN_OM    logreg_cons  0.319708   0.448022 139
tamanduatei perigoso_any   CEMADEN_OM     logreg_std  0.355210   0.453213 139
tamanduatei perigoso_any CEMADEN_ONLY gradboost_cons  0.305309   0.433416 139
tamanduatei perigoso_any CEMADEN_ONLY  gradboost_std  0.275457   0.388353 139
tamanduatei perigoso_any CEMADEN_ONLY    logreg_cons  0.319708   0.448022 139
tamanduatei perigoso_any CEMADEN_ONLY     logreg_std  0.355210   0.453213 139
tamanduatei   prolongada          ALL gradboost_cons  0.223068   0.355186 139
tamanduatei   prolongada          ALL  gradboost_std  0.171935   0.280837 139
tamanduatei   prolongada          ALL    logreg_cons  0.236227   0.374695 139
tamanduatei   prolongada          ALL     logreg_std  0.194467   0.280690 139
tamanduatei   prolongada   CEMADEN_OM gradboost_cons  0.227197   0.350065 139
tamanduatei   prolongada   CEMADEN_OM  gradboost_std  0.211535   0.322826 139
tamanduatei   prolongada   CEMADEN_OM    logreg_cons  0.237737   0.378393 139
tamanduatei   prolongada   CEMADEN_OM     logreg_std  0.198908   0.279539 139
tamanduatei   prolongada CEMADEN_ONLY gradboost_cons  0.234763   0.348559 139
tamanduatei   prolongada CEMADEN_ONLY  gradboost_std  0.199227   0.295085 139
tamanduatei   prolongada CEMADEN_ONLY    logreg_cons  0.237737   0.378393 139
tamanduatei   prolongada CEMADEN_ONLY     logreg_std  0.198908   0.279539 139
tamanduatei    saturante          ALL gradboost_cons  0.350569   0.365212 139
tamanduatei    saturante          ALL  gradboost_std  0.311785   0.279267 139
tamanduatei    saturante          ALL    logreg_cons  0.367127   0.417869 139
tamanduatei    saturante          ALL     logreg_std  0.388225   0.454464 139
tamanduatei    saturante   CEMADEN_OM gradboost_cons  0.345219   0.350803 139
tamanduatei    saturante   CEMADEN_OM  gradboost_std  0.339897   0.328625 139
tamanduatei    saturante   CEMADEN_OM    logreg_cons  0.366081   0.413373 139
tamanduatei    saturante   CEMADEN_OM     logreg_std  0.388347   0.456908 139
tamanduatei    saturante CEMADEN_ONLY gradboost_cons  0.321048   0.326982 139
tamanduatei    saturante CEMADEN_ONLY  gradboost_std  0.315376   0.291042 139
tamanduatei    saturante CEMADEN_ONLY    logreg_cons  0.366081   0.413373 139
tamanduatei    saturante CEMADEN_ONLY     logreg_std  0.388347   0.456908 139
```

## 6. Inversões (Spearman negativo)

```
      bacia        label     variante         modelo  spearman_rho  inversao
    guarara      pancada          ALL gradboost_cons      0.417367     False
    guarara      pancada          ALL  gradboost_std      0.343625     False
    guarara      pancada          ALL    logreg_cons      0.412107     False
    guarara      pancada          ALL     logreg_std      0.356459     False
    guarara      pancada   CEMADEN_OM gradboost_cons      0.399996     False
    guarara      pancada   CEMADEN_OM  gradboost_std      0.390428     False
    guarara      pancada   CEMADEN_OM    logreg_cons      0.415611     False
    guarara      pancada   CEMADEN_OM     logreg_std      0.397496     False
    guarara      pancada CEMADEN_ONLY gradboost_cons      0.401487     False
    guarara      pancada CEMADEN_ONLY  gradboost_std      0.400973     False
    guarara      pancada CEMADEN_ONLY    logreg_cons      0.415611     False
    guarara      pancada CEMADEN_ONLY     logreg_std      0.397496     False
    guarara perigoso_any          ALL gradboost_cons      0.446360     False
    guarara perigoso_any          ALL  gradboost_std      0.403663     False
    guarara perigoso_any          ALL    logreg_cons      0.457309     False
    guarara perigoso_any          ALL     logreg_std      0.410104     False
    guarara perigoso_any   CEMADEN_OM gradboost_cons      0.464660     False
    guarara perigoso_any   CEMADEN_OM  gradboost_std      0.440949     False
    guarara perigoso_any   CEMADEN_OM    logreg_cons      0.460833     False
    guarara perigoso_any   CEMADEN_OM     logreg_std      0.418285     False
    guarara perigoso_any CEMADEN_ONLY gradboost_cons      0.450511     False
    guarara perigoso_any CEMADEN_ONLY  gradboost_std      0.422592     False
    guarara perigoso_any CEMADEN_ONLY    logreg_cons      0.460833     False
    guarara perigoso_any CEMADEN_ONLY     logreg_std      0.418285     False
    guarara   prolongada          ALL gradboost_cons      0.444065     False
    guarara   prolongada          ALL  gradboost_std      0.433477     False
    guarara   prolongada          ALL    logreg_cons      0.455375     False
    guarara   prolongada          ALL     logreg_std      0.417922     False
    guarara   prolongada   CEMADEN_OM gradboost_cons      0.477891     False
    guarara   prolongada   CEMADEN_OM  gradboost_std      0.434037     False
    guarara   prolongada   CEMADEN_OM    logreg_cons      0.454360     False
    guarara   prolongada   CEMADEN_OM     logreg_std      0.415796     False
    guarara   prolongada CEMADEN_ONLY gradboost_cons      0.480195     False
    guarara   prolongada CEMADEN_ONLY  gradboost_std      0.442314     False
    guarara   prolongada CEMADEN_ONLY    logreg_cons      0.454360     False
    guarara   prolongada CEMADEN_ONLY     logreg_std      0.415796     False
    guarara    saturante          ALL gradboost_cons      0.452414     False
    guarara    saturante          ALL  gradboost_std      0.461584     False
    guarara    saturante          ALL    logreg_cons      0.445395     False
    guarara    saturante          ALL     logreg_std      0.433621     False
    guarara    saturante   CEMADEN_OM gradboost_cons      0.442578     False
    guarara    saturante   CEMADEN_OM  gradboost_std      0.413398     False
    guarara    saturante   CEMADEN_OM    logreg_cons      0.446206     False
    guarara    saturante   CEMADEN_OM     logreg_std      0.428530     False
    guarara    saturante CEMADEN_ONLY gradboost_cons      0.446261     False
    guarara    saturante CEMADEN_ONLY  gradboost_std      0.435313     False
    guarara    saturante CEMADEN_ONLY    logreg_cons      0.446206     False
    guarara    saturante CEMADEN_ONLY     logreg_std      0.428530     False
    meninos      pancada          ALL gradboost_cons      0.517964     False
    meninos      pancada          ALL  gradboost_std      0.390868     False
    meninos      pancada          ALL    logreg_cons      0.500842     False
    meninos      pancada          ALL     logreg_std      0.395620     False
    meninos      pancada   CEMADEN_OM gradboost_cons      0.498967     False
    meninos      pancada   CEMADEN_OM  gradboost_std      0.426470     False
    meninos      pancada   CEMADEN_OM    logreg_cons      0.497571     False
    meninos      pancada   CEMADEN_OM     logreg_std      0.411743     False
    meninos      pancada CEMADEN_ONLY gradboost_cons      0.535171     False
    meninos      pancada CEMADEN_ONLY  gradboost_std      0.476980     False
    meninos      pancada CEMADEN_ONLY    logreg_cons      0.497571     False
    meninos      pancada CEMADEN_ONLY     logreg_std      0.411743     False
    meninos perigoso_any          ALL gradboost_cons      0.524415     False
    meninos perigoso_any          ALL  gradboost_std      0.462904     False
    meninos perigoso_any          ALL    logreg_cons      0.514595     False
    meninos perigoso_any          ALL     logreg_std      0.492742     False
    meninos perigoso_any   CEMADEN_OM gradboost_cons      0.515262     False
    meninos perigoso_any   CEMADEN_OM  gradboost_std      0.486456     False
    meninos perigoso_any   CEMADEN_OM    logreg_cons      0.512997     False
    meninos perigoso_any   CEMADEN_OM     logreg_std      0.491697     False
    meninos perigoso_any CEMADEN_ONLY gradboost_cons      0.525039     False
    meninos perigoso_any CEMADEN_ONLY  gradboost_std      0.506941     False
    meninos perigoso_any CEMADEN_ONLY    logreg_cons      0.512997     False
    meninos perigoso_any CEMADEN_ONLY     logreg_std      0.491697     False
    meninos   prolongada          ALL gradboost_cons      0.516983     False
    meninos   prolongada          ALL  gradboost_std      0.476531     False
    meninos   prolongada          ALL    logreg_cons      0.510833     False
    meninos   prolongada          ALL     logreg_std      0.511165     False
    meninos   prolongada   CEMADEN_OM gradboost_cons      0.527273     False
    meninos   prolongada   CEMADEN_OM  gradboost_std      0.467596     False
    meninos   prolongada   CEMADEN_OM    logreg_cons      0.513979     False
    meninos   prolongada   CEMADEN_OM     logreg_std      0.513425     False
    meninos   prolongada CEMADEN_ONLY gradboost_cons      0.530995     False
    meninos   prolongada CEMADEN_ONLY  gradboost_std      0.476445     False
    meninos   prolongada CEMADEN_ONLY    logreg_cons      0.513979     False
    meninos   prolongada CEMADEN_ONLY     logreg_std      0.513425     False
    meninos    saturante          ALL gradboost_cons      0.442728     False
    meninos    saturante          ALL  gradboost_std      0.470862     False
    meninos    saturante          ALL    logreg_cons      0.430128     False
    meninos    saturante          ALL     logreg_std      0.344422     False
    meninos    saturante   CEMADEN_OM gradboost_cons      0.475105     False
    meninos    saturante   CEMADEN_OM  gradboost_std      0.472533     False
    meninos    saturante   CEMADEN_OM    logreg_cons      0.441089     False
    meninos    saturante   CEMADEN_OM     logreg_std      0.342900     False
    meninos    saturante CEMADEN_ONLY gradboost_cons      0.472344     False
    meninos    saturante CEMADEN_ONLY  gradboost_std      0.464460     False
    meninos    saturante CEMADEN_ONLY    logreg_cons      0.441089     False
    meninos    saturante CEMADEN_ONLY     logreg_std      0.342900     False
   oratorio      pancada          ALL gradboost_cons      0.357568     False
   oratorio      pancada          ALL  gradboost_std      0.272815     False
   oratorio      pancada          ALL    logreg_cons      0.285918     False
   oratorio      pancada          ALL     logreg_std     -0.013686      True
   oratorio      pancada   CEMADEN_OM gradboost_cons      0.366562     False
   oratorio      pancada   CEMADEN_OM  gradboost_std      0.359243     False
   oratorio      pancada   CEMADEN_OM    logreg_cons      0.251907     False
   oratorio      pancada   CEMADEN_OM     logreg_std     -0.072345      True
   oratorio      pancada CEMADEN_ONLY gradboost_cons      0.372176     False
   oratorio      pancada CEMADEN_ONLY  gradboost_std      0.335866     False
   oratorio      pancada CEMADEN_ONLY    logreg_cons      0.251907     False
   oratorio      pancada CEMADEN_ONLY     logreg_std     -0.072345      True
   oratorio perigoso_any          ALL gradboost_cons      0.454349     False
   oratorio perigoso_any          ALL  gradboost_std      0.422248     False
   oratorio perigoso_any          ALL    logreg_cons      0.442746     False
   oratorio perigoso_any          ALL     logreg_std      0.439305     False
   oratorio perigoso_any   CEMADEN_OM gradboost_cons      0.447934     False
   oratorio perigoso_any   CEMADEN_OM  gradboost_std      0.434880     False
   oratorio perigoso_any   CEMADEN_OM    logreg_cons      0.444777     False
   oratorio perigoso_any   CEMADEN_OM     logreg_std      0.437292     False
   oratorio perigoso_any CEMADEN_ONLY gradboost_cons      0.462153     False
   oratorio perigoso_any CEMADEN_ONLY  gradboost_std      0.426127     False
   oratorio perigoso_any CEMADEN_ONLY    logreg_cons      0.444777     False
   oratorio perigoso_any CEMADEN_ONLY     logreg_std      0.437292     False
   oratorio   prolongada          ALL gradboost_cons      0.461154     False
   oratorio   prolongada          ALL  gradboost_std      0.416412     False
   oratorio   prolongada          ALL    logreg_cons      0.428294     False
   oratorio   prolongada          ALL     logreg_std      0.299212     False
   oratorio   prolongada   CEMADEN_OM gradboost_cons      0.439607     False
   oratorio   prolongada   CEMADEN_OM  gradboost_std      0.438582     False
   oratorio   prolongada   CEMADEN_OM    logreg_cons      0.396551     False
   oratorio   prolongada   CEMADEN_OM     logreg_std      0.065101     False
   oratorio   prolongada CEMADEN_ONLY gradboost_cons      0.466997     False
   oratorio   prolongada CEMADEN_ONLY  gradboost_std      0.399555     False
   oratorio   prolongada CEMADEN_ONLY    logreg_cons      0.396551     False
   oratorio   prolongada CEMADEN_ONLY     logreg_std      0.065101     False
   oratorio    saturante          ALL gradboost_cons      0.412250     False
   oratorio    saturante          ALL  gradboost_std      0.398732     False
   oratorio    saturante          ALL    logreg_cons      0.431601     False
   oratorio    saturante          ALL     logreg_std      0.422414     False
   oratorio    saturante   CEMADEN_OM gradboost_cons      0.400467     False
   oratorio    saturante   CEMADEN_OM  gradboost_std      0.433133     False
   oratorio    saturante   CEMADEN_OM    logreg_cons      0.430234     False
   oratorio    saturante   CEMADEN_OM     logreg_std      0.419594     False
   oratorio    saturante CEMADEN_ONLY gradboost_cons      0.421277     False
   oratorio    saturante CEMADEN_ONLY  gradboost_std      0.391615     False
   oratorio    saturante CEMADEN_ONLY    logreg_cons      0.430234     False
   oratorio    saturante CEMADEN_ONLY     logreg_std      0.419594     False
tamanduatei      pancada          ALL gradboost_cons      0.441115     False
tamanduatei      pancada          ALL  gradboost_std      0.465206     False
tamanduatei      pancada          ALL    logreg_cons      0.400507     False
tamanduatei      pancada          ALL     logreg_std      0.275930     False
tamanduatei      pancada   CEMADEN_OM gradboost_cons      0.447780     False
tamanduatei      pancada   CEMADEN_OM  gradboost_std      0.389781     False
tamanduatei      pancada   CEMADEN_OM    logreg_cons      0.410590     False
tamanduatei      pancada   CEMADEN_OM     logreg_std      0.272464     False
tamanduatei      pancada CEMADEN_ONLY gradboost_cons      0.436327     False
tamanduatei      pancada CEMADEN_ONLY  gradboost_std      0.470088     False
tamanduatei      pancada CEMADEN_ONLY    logreg_cons      0.410590     False
tamanduatei      pancada CEMADEN_ONLY     logreg_std      0.272464     False
tamanduatei perigoso_any          ALL gradboost_cons      0.464554     False
tamanduatei perigoso_any          ALL  gradboost_std      0.482578     False
tamanduatei perigoso_any          ALL    logreg_cons      0.465491     False
tamanduatei perigoso_any          ALL     logreg_std      0.456153     False
tamanduatei perigoso_any   CEMADEN_OM gradboost_cons      0.483369     False
tamanduatei perigoso_any   CEMADEN_OM  gradboost_std      0.477544     False
tamanduatei perigoso_any   CEMADEN_OM    logreg_cons      0.468051     False
tamanduatei perigoso_any   CEMADEN_OM     logreg_std      0.455971     False
tamanduatei perigoso_any CEMADEN_ONLY gradboost_cons      0.487773     False
tamanduatei perigoso_any CEMADEN_ONLY  gradboost_std      0.471847     False
tamanduatei perigoso_any CEMADEN_ONLY    logreg_cons      0.468051     False
tamanduatei perigoso_any CEMADEN_ONLY     logreg_std      0.455971     False
tamanduatei   prolongada          ALL gradboost_cons      0.484788     False
tamanduatei   prolongada          ALL  gradboost_std      0.495757     False
tamanduatei   prolongada          ALL    logreg_cons      0.478502     False
tamanduatei   prolongada          ALL     logreg_std      0.470003     False
tamanduatei   prolongada   CEMADEN_OM gradboost_cons      0.496179     False
tamanduatei   prolongada   CEMADEN_OM  gradboost_std      0.489367     False
tamanduatei   prolongada   CEMADEN_OM    logreg_cons      0.476539     False
tamanduatei   prolongada   CEMADEN_OM     logreg_std      0.460690     False
tamanduatei   prolongada CEMADEN_ONLY gradboost_cons      0.478784     False
tamanduatei   prolongada CEMADEN_ONLY  gradboost_std      0.519786     False
tamanduatei   prolongada CEMADEN_ONLY    logreg_cons      0.476539     False
tamanduatei   prolongada CEMADEN_ONLY     logreg_std      0.460690     False
tamanduatei    saturante          ALL gradboost_cons      0.470032     False
tamanduatei    saturante          ALL  gradboost_std      0.458023     False
tamanduatei    saturante          ALL    logreg_cons      0.440092     False
tamanduatei    saturante          ALL     logreg_std      0.433766     False
tamanduatei    saturante   CEMADEN_OM gradboost_cons      0.470966     False
tamanduatei    saturante   CEMADEN_OM  gradboost_std      0.463461     False
tamanduatei    saturante   CEMADEN_OM    logreg_cons      0.439370     False
tamanduatei    saturante   CEMADEN_OM     logreg_std      0.432920     False
tamanduatei    saturante CEMADEN_ONLY gradboost_cons      0.478129     False
tamanduatei    saturante CEMADEN_ONLY  gradboost_std      0.475849     False
tamanduatei    saturante CEMADEN_ONLY    logreg_cons      0.439370     False
tamanduatei    saturante CEMADEN_ONLY     logreg_std      0.432920     False
```

## 7. Sensibilidade operacional (perda de estações)

```
      bacia  drop_frac         modelo    prauc  spearman_rho       f1
    guarara       0.00 gradboost_cons 0.600500      0.485535 0.530806
    guarara       0.25 gradboost_cons 0.525130      0.484393 0.444444
    guarara       0.50 gradboost_cons 0.441963      0.469209 0.371429
    meninos       0.00 gradboost_cons 0.530101      0.502429 0.485876
    meninos       0.25 gradboost_cons 0.492270      0.490519 0.404908
    meninos       0.50 gradboost_cons 0.335256      0.459967 0.361905
   oratorio       0.00 gradboost_cons 0.522255      0.456965 0.490909
   oratorio       0.25 gradboost_cons 0.487358      0.451424 0.440476
   oratorio       0.50 gradboost_cons 0.407920      0.436252 0.375000
tamanduatei       0.00 gradboost_cons 0.577408      0.474191 0.518519
tamanduatei       0.25 gradboost_cons 0.555895      0.460493 0.502674
tamanduatei       0.50 gradboost_cons 0.483992      0.486773 0.433735
```

## 8. Comparação com rodada anterior

Comparando modelos standard (gradboost_std/logreg_std) com resultados anteriores (gradboost/logreg).

### test_hist

**pancada**: média PR-AUC robust=0.095 vs prev=0.090 (delta=+0.005)
**prolongada**: média PR-AUC robust=0.203 vs prev=0.192 (delta=+0.011)
**saturante**: média PR-AUC robust=0.699 vs prev=0.690 (delta=+0.008)
**perigoso_any**: média PR-AUC robust=0.557 vs prev=0.547 (delta=+0.010)

### holdout_2026

**pancada**: média PR-AUC robust=0.132 vs prev=0.129 (delta=+0.003)
**prolongada**: média PR-AUC robust=0.544 vs prev=0.521 (delta=+0.023)
**saturante**: média PR-AUC robust=0.886 vs prev=0.870 (delta=+0.016)
**perigoso_any**: média PR-AUC robust=0.867 vs prev=0.855 (delta=+0.012)


# Módulo *Harvest*

> **Estágio 1 - Leitor de yaml**

Esse diretório contem módulo *Harvest*; um microsserviço para buscar
dados brutos de diferentes fontes e jogá-los no mongoDB para consumo de curto
prazo.

Como usar:

```sh
python -m harvest.cli --city {NomeDaCidade} --config {ArquivoDeConfig}
```

---
title: Harvest
slug: /harvest
sidebar_position: 2
---

# Módulo Harvest

O módulo `harvest` é o componente do backend responsável pela coleta de dados de diversas fontes externas. Ele foi projetado com uma arquitetura extensível que permite a fácil adição de novas fontes de dados sem a necessidade de modificar o código principal do coletor.

## 1. Arquitetura e Escolhas de Design

A principal característica da arquitetura do `harvest` é o uso de abstrações para desacoplar o coletor principal das fontes de dados específicas. Isso é alcançado através do uso de uma classe base abstrata e um padrão de fábrica.

### 1.1. `harvester.py`

O `Harvester` é a classe central do módulo. Ele orquestra o processo de coleta de dados, que consiste em:

1.  Carregar a configuração das fontes de dados a partir de um arquivo YAML.
2.  Iterar sobre as fontes de dados configuradas.
3.  Para cada fonte, instanciar a classe correspondente (usando um padrão de fábrica).
4.  Chamar o método `get_data` da instância da fonte para obter os dados.
5.  Salvar os dados coletados no MongoDB.

### 1.2. `sources/source_base.py`

A extensibilidade do `harvest` é garantida pela classe base abstrata `SourceBase`. Esta classe define um contrato que todas as fontes de dados devem seguir, que é a implementação do método `get_data`. Qualquer nova fonte de dados deve herdar de `SourceBase` e implementar este método.

Essa abordagem, que segue o Princípio Aberto/Fechado (Open/Closed Principle), permite que o sistema seja estendido com novas funcionalidades (fontes de dados) sem que o código existente precise ser alterado.

### 1.3. `sources/openweather_source.py`

Este arquivo é um exemplo de uma implementação concreta de uma fonte de dados. A classe `OpenWeatherSource` herda de `SourceBase` e implementa o método `get_data` para buscar dados da API do OpenWeather.

## 2. Como Adicionar uma Nova Fonte de Dados

Para adicionar uma nova fonte de dados ao `harvest`, siga os seguintes passos:

1.  **Crie uma nova classe de fonte:**
    - Crie um novo arquivo Python no diretório `sources` (e.g., `minha_fonte_source.py`).
    - Dentro deste arquivo, crie uma classe que herde de `SourceBase` (e.g., `MinhaFonteSource`).
    - Implemente o método `get_data` na sua nova classe. Este método deve conter a lógica para buscar e retornar os dados da sua nova fonte.

2.  **Atualize a configuração:**
    - Abra o arquivo de configuração YAML (`config.yaml`).
    - Adicione uma nova entrada na seção `sources` com o nome da sua nova fonte e os parâmetros necessários (como chaves de API, URLs, etc.).

Com isso, o `Harvester` irá automaticamente reconhecer e começar a coletar dados da sua nova fonte na próxima vez que for executado.

## 3. Componentes Adicionais

- **`main.py`**: O ponto de entrada do módulo, responsável por iniciar o `Harvester`.
- **`config_loader.py`**: Carrega e valida o arquivo de configuração YAML.
- **`mongo_client.py`**: Fornece uma interface para a comunicação com o banco de dados MongoDB, onde os dados coletados são armazenados.
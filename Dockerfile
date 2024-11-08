#FROM python:3.11.5-bullseye
FROM sanicframework/sanic:lts-py3.11
# Definir o argumento ENVIRONMENT
ARG ENVIRONMENT

# Usar o argumento para definir uma variável de ambiente
ENV NODE_ENV=${ENVIRONMENT}

# Instalando dependências Python do seu projeto
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# CI / CD - Copiando as chaves SSH para o container
RUN mkdir /keys
COPY keys /keys

RUN  mkdir /deployment
COPY deployment/ /deployment
RUN ls /deployment
RUN chmod +x /deployment/github_pull.sh

RUN echo "*/1 * * * * /bin/bash /deployment/github_pull.sh" > /var/spool/cron/crontabs/root

COPY source/ source/
WORKDIR /source

# Definindo o diretório /source como um volume
VOLUME /source

# Definindo o ponto de entrada para executar o seu run.py
#ENTRYPOINT ["python", "/source/run.py", "--env", NODE_ENV]
CMD ["python", "/source/source/run.py", "--env", "$NODE_ENV" ]

# Porta em que o seu aplicativo SANIC estará rodando, ajuste conforme necessário
EXPOSE 8000
EXPOSE 6457

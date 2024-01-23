FROM python:3.9.16-slim
WORKDIR /usr/src
USER root
RUN pip install --upgrade pip
RUN pip install pyyaml
RUN pip install aiohttp
COPY . .
EXPOSE 9000
CMD [ "python", "-u", "/usr/src/main.py" ]

FROM python:3.13-slim-bookworm

RUN apt-get update

RUN apt-get install -y tzdata
ENV TZ=Asia/Tokyo
RUN ln -sf /usr/share/zoneinfo/Japan /etc/localtime && \
    echo $TZ > /etc/timezone


RUN apt-get install -y \
    sqlite3 procps locales
RUN echo "ja_JP.UTF-8 UTF-8" >> /etc/locale.gen && locale-gen

ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:en
ENV LC_ALL ja_JP.UTF-8

WORKDIR /app
RUN mkdir /app/db && mkdir /app/log

COPY requirements.txt ./

RUN python3 -m venv /app/venv && . /app/venv/bin/activate && pip install -Ur requirements.txt

ENV PATH /app/venv/bin:$PATH

COPY . .

EXPOSE 8060

WORKDIR /app/ex_search

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8060"]
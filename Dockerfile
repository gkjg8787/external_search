FROM python:3.13-slim-trixie

RUN pip install uv
RUN apt-get update && \
    apt-get install -y tzdata
ENV TZ=Asia/Tokyo
RUN ln -sf /usr/share/zoneinfo/Japan /etc/localtime && \
    echo $TZ > /etc/timezone


RUN apt-get install -y \
    sqlite3 procps
RUN apt-get -y install locales && \
    localedef -f UTF-8 -i ja_JP ja_JP.UTF-8

ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:en
ENV LC_ALL ja_JP.UTF-8

WORKDIR /app
RUN mkdir /app/db && mkdir /app/log

COPY requirements.txt ./

RUN uv venv /app/venv && . /app/venv/bin/activate && uv pip install -r requirements.txt

ENV PATH /app/venv/bin:$PATH

COPY . .

EXPOSE 8060

WORKDIR /app/ex_search

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8060"]
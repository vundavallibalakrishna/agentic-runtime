# Fail-closed egress proxy. Squid 7.7 is the stack pin; Debian's package is installed here.
FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends squid \
    && rm -rf /var/lib/apt/lists/*
COPY images/squid/squid.conf /etc/squid/squid.conf
EXPOSE 3128
USER proxy
CMD ["squid", "-N", "-d1"]

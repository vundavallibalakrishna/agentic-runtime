# Fail-closed egress proxy. The helper denies when the manager cannot be reached.
FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends squid python3 \
    && rm -rf /var/lib/apt/lists/*
COPY images/squid/squid.conf /etc/squid/squid.conf
COPY images/squid/ar-egress-helper.py /usr/local/bin/ar-egress-helper
RUN chmod 755 /usr/local/bin/ar-egress-helper
EXPOSE 3128
USER proxy
CMD ["squid", "-N", "-d1"]

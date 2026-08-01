FROM debian:bookworm-slim AS build

# Base game is tbaMUD (CircleMUD's official successor): ships DG Scripts and the
# quest engine fully integrated. Pin TBAMUD_REF to a tag/commit for reproducibility.
ARG TBAMUD_REF=master
# Previous base was stock CircleMUD 3.1 (no DG Scripts). To roll back, restore:
#   ARG CIRCLEMUD_URL=https://www.circlemud.org/pub/CircleMUD/3.x/circle-3.1.tar.gz
# and the wget/tarball fetch below.

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp
RUN git clone --depth 1 --branch "$TBAMUD_REF" \
        https://github.com/tbamud/tbamud.git circlemud

WORKDIR /tmp/circlemud
# nameserver_is_slow defaults to NO (config.c), which means every new
# connection blocks the entire single-threaded game loop on a synchronous
# gethostbyaddr() reverse-DNS lookup (new_descriptor() in comm.c). Docker's
# bridge network has no usable reverse DNS for its gateway IP, so this stalls
# unpredictably (sometimes past a client's login timeout) on every single
# connect/reconnect — exactly the pattern the eval harness's rapid
# reconnect cycle hits hardest. Flipping the default skips the lookup
# entirely and uses the numeric IP, same as toggling it live via CEDIT.
RUN sed -i 's/int nameserver_is_slow = NO;/int nameserver_is_slow = YES;/' src/config.c
RUN ./configure \
    && make -C src

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/circlemud
COPY --from=build /tmp/circlemud /opt/circlemud
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN cp -a /opt/circlemud/lib /opt/circlemud/lib.dist \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 4000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["bin/circle", "-q", "4000"]

FROM golang:1.27.3-alpine AS builder
RUN apk add --no-cache git
WORKDIR /build
RUN git clone https://github.com/teslamotors/vehicle-command.git . && \
    git fetch origin 281b3a70caaef258e2f7dfe0136a2a192b8cb017 && \
    git checkout --detach 281b3a70caaef258e2f7dfe0136a2a192b8cb017 && \
    go build -o tesla-http-proxy ./cmd/tesla-http-proxy

FROM alpine:latest
RUN apk add --no-cache openssl ca-certificates
COPY --from=builder /build/tesla-http-proxy /usr/local/bin/tesla-http-proxy
COPY run.sh /run.sh
RUN chmod +x /run.sh
EXPOSE 4443
CMD ["/run.sh"]

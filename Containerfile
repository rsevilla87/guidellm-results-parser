FROM ghcr.io/vllm-project/guidellm:latest

USER root
RUN pip install opensearch-py
COPY --chmod=0755 benchmark_parser.py /usr/bin/benchmark_parser.py

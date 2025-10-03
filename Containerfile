FROM ghcr.io/vllm-project/guidellm:latest

USER root
RUN pip install opensearch-py
COPY --chmod=0755 guidellm_parser.py /usr/bin/guidellm_parser.py

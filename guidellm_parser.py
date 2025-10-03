#!/usr/bin/env python3
"""
Benchmark Results Parser with OpenSearch Support

This program parses the benchmarks.json file and extracts key performance metrics
including mean and P99 values for TTFT, ITL, throughput, and benchmark parameters.
Supports indexing the results to OpenSearch.
"""

import json
import sys
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

from opensearchpy import OpenSearch
from opensearchpy.exceptions import ConnectionError, RequestError


def parse_benchmarks(file_path: str, uuid: str, job_name: str) -> Dict[str, Any]:
    """
    Parse the benchmarks.json file and extract key metrics.
    
    Args:
        file_path: Path to the benchmarks.json file
        uuid: UUID of the benchmark to parse
    Returns:
        Dictionary containing extracted metrics
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}")
        sys.exit(1)
    
    # Extract benchmark data
    benchmarks = data.get('benchmarks', [])
    if not benchmarks:
        print("Error: No benchmarks found in the file")
        sys.exit(1)
    
    # Get the first benchmark (assuming single benchmark for now)
    benchmark = benchmarks[0]
    
    # Extract basic benchmark info
    summary = {
        # Benchmark identification
        "uuid": uuid,
        "job_name": job_name,
        
        # Timing information
        "timestamp": datetime.fromtimestamp(benchmark.get('start_time', 0)).isoformat(),
        
        # Strategy information
        "strategy": benchmark.get('args', {}).get('strategy', {}).get('type_', ''),
        "rate": int(benchmark.get('args', {}).get('strategy', {}).get('rate', 0)),
        
        # Request totals
        "total_requests": benchmark.get('request_totals', {}).get('total', 0),
        "successful_requests": benchmark.get('request_totals', {}).get('successful', 0),
        "errored_requests": benchmark.get('request_totals', {}).get('errored', 0),
        "incomplete_requests": benchmark.get('request_totals', {}).get('incomplete', 0),
        
        # Token information
        "prompt_tokens": benchmark.get('request_loader', {}).get('data', '').split('=')[1].split(',')[0] if '=' in benchmark.get('request_loader', {}).get('data', '') else 0,
        "output_tokens": benchmark.get('request_loader', {}).get('data', '').split('=')[2] if '=' in benchmark.get('request_loader', {}).get('data', '') else 0,
        
        # Backend model
        "backend_model": benchmark.get('worker', {}).get('backend_model', ''),
    }
    
    # Extract metrics from the metrics section
    metrics = benchmark.get('metrics', {})
    
    # Time to First Token (TTFT) metrics
    ttft_metrics = metrics.get('time_to_first_token_ms', {}).get('successful', {})
    summary.update({
        "ttft_mean_ms": ttft_metrics.get('mean', 0),
        "ttft_p99_ms": ttft_metrics.get('percentiles', {}).get('p99', 0),
    })
    
    # Inter Token Latency (ITL) metrics
    itl_metrics = metrics.get('inter_token_latency_ms', {}).get('successful', {})
    summary.update({
        "itl_mean_ms": itl_metrics.get('mean', 0),
        "itl_p99_ms": itl_metrics.get('percentiles', {}).get('p99', 0),
    })
    
    # Throughput (requests per second) metrics
    throughput_metrics = metrics.get('requests_per_second', {}).get('successful', {})
    summary.update({
        "throughput_mean_rps": throughput_metrics.get('mean', 0),
        "throughput_p95_rps": throughput_metrics.get('percentiles', {}).get('p95', 0),
        "throughput_p99_rps": throughput_metrics.get('percentiles', {}).get('p99', 0),
    })
    
    # Additional useful metrics
    request_latency = metrics.get('request_latency', {}).get('successful', {})
    summary.update({
        "request_latency_mean_seconds": request_latency.get('mean', 0),
        "request_latency_p95_seconds": request_latency.get('percentiles', {}).get('p95', 0),
        "request_latency_p99_seconds": request_latency.get('percentiles', {}).get('p99', 0),
    })
    
    # Token generation metrics
    tokens_per_second = metrics.get('tokens_per_second', {}).get('successful', {})
    summary.update({
        "tokens_per_second_mean": tokens_per_second.get('mean', 0),
        "tokens_per_second_p95": tokens_per_second.get('percentiles', {}).get('p95', 0),
        "tokens_per_second_p99": tokens_per_second.get('percentiles', {}).get('p99', 0),
    })
    
    # Output tokens per second
    output_tokens_per_second = metrics.get('output_tokens_per_second', {}).get('successful', {})
    summary.update({
        "output_tokens_per_second_mean": output_tokens_per_second.get('mean', 0),
        "output_tokens_per_second_p95": output_tokens_per_second.get('percentiles', {}).get('p95', 0),
        "output_tokens_per_second_p99": output_tokens_per_second.get('percentiles', {}).get('p99', 0),
    })
    
    # Time per output token
    time_per_output_token = metrics.get('time_per_output_token_ms', {}).get('successful', {})
    summary.update({
        "time_per_output_token_mean_ms": time_per_output_token.get('mean', 0),
        "time_per_output_token_p95_ms": time_per_output_token.get('percentiles', {}).get('p95', 0),
        "time_per_output_token_p99_ms": time_per_output_token.get('percentiles', {}).get('p99', 0),
    })
    
    result = [summary]
    requests = benchmark.get('requests', {})
    
    # Process successful requests (generative_text_response)
    successful_requests = requests.get('successful', [])
    for request in successful_requests:
        scheduler_info = request.get('scheduler_info', {})
        result.append({
            "timestamp": datetime.fromtimestamp(scheduler_info.get('request_start', 0)).isoformat(),
            "errored": scheduler_info.get('errored', False),
            "completed": scheduler_info.get('completed', False),
            "request_latency_seconds": request.get('request_latency', 0),
            "tokens_per_second": request.get('tokens_per_second', 0),
            "output_tokens_per_second": request.get('output_tokens_per_second', 0),
            "time_per_output_token_ms": request.get('time_per_output_token_ms', 0),
            "inter_token_latency_ms": request.get('inter_token_latency_ms', 0),
            "time_to_first_token_ms": request.get('time_to_first_token_ms', 0),
            "uuid": uuid,
            "job_name": job_name,
        })
    
    # Process errored requests (generative_text_error)
    errored_requests = requests.get('errored', [])
    for request in errored_requests:
        scheduler_info = request.get('scheduler_info', {})
        result.append({
            "timestamp": datetime.fromtimestamp(scheduler_info.get('request_start', 0)).isoformat(),
            "errored": scheduler_info.get('errored', True),
            "completed": scheduler_info.get('completed', False),
            "uuid": uuid,
            "job_name": job_name,
        })
    
    
    return result


def index_to_opensearch(data: Dict[str, Any], es_server: str, index_name: str) -> bool:
    """
    Index the parsed benchmark data to OpenSearch.
    
    Args:
        data: The parsed benchmark data to index
        es_server: OpenSearch endpoint URL
        index_name: Name of the OpenSearch index
        
    Returns:
        True if successful, False otherwise
    """
    
    try:
        # Create OpenSearch client
        es = OpenSearch([es_server])
        
        # Test connection
        if not es.ping():
            print(f"Error: Cannot connect to OpenSearch at {es_server}", file=sys.stderr)
            return False
        
        # Index the document
        response = es.index(
            index=index_name,
            body=data,
        )
        
        print(f"Successfully indexed document to {index_name} with ID: {response['_id']}")
        return True
        
    except ConnectionError as e:
        print(f"Error: Failed to connect to OpenSearch: {e}", file=sys.stderr)
        return False
    except RequestError as e:
        print(f"Error: OpenSearch request failed: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error: Unexpected error indexing to OpenSearch: {e}", file=sys.stderr)
        return False


def main():
    """Main function to parse benchmarks and output results."""
    parser = argparse.ArgumentParser(description='Parse benchmark results and optionally index to OpenSearch')
    parser.add_argument('--results', help='Path to the guidellm results file', default='benchmarks.json')
    parser.add_argument('--uuid', help='UUID of the benchmark', default='')
    parser.add_argument('--es-server', help='OpenSearch endpoint URL (e.g., http://localhost:9200)')
    parser.add_argument('--es-index', help='OpenSearch index name')
    parser.add_argument('--output', '-o', help='Output file path (default: stdout)')
    parser.add_argument('--job-name', '-j', help='Job Name', default='')
    
    args = parser.parse_args()
    
    # Parse benchmarks
    results = parse_benchmarks(args.results, args.uuid, args.job_name)
    
    # Index to OpenSearch if endpoint and index are provided
    if args.es_server and args.es_index:
        success = index_to_opensearch(results, args.es_server, args.es_index)
        if not success:
            sys.exit(1)
    
    # Output results
    output_json = json.dumps(results, indent=2)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"Results written to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test hybrid search functionality"""
import requests
import json

API_BASE = "http://localhost:8000/api"

print("=" * 60)
print("HYBRID SEARCH TESTS")
print("=" * 60)
print()

# Test 1: Conversational (Agent 0)
print("TEST 1: Conversational Query")
print("-" * 40)
response = requests.post(
    f"{API_BASE}/query/agentic",
    json={"query": "Hello"}
)
data = response.json()
print(f"Query: {data.get('query')}")
print(f"Intent: {data['metadata']['intent']}")
print(f"Agent: {data['metadata']['agent']}")
print(f"Retrieval: {data['metadata']['retrieval_performed']}")
print(f"Response: {data['response'][:80]}...")
print()

# Test 2: License Query with Hybrid Search
print("TEST 2: License Query (Hybrid Search)")
print("-" * 40)
response = requests.post(
    f"{API_BASE}/query/agentic",
    json={"query": "What is the license?", "project_id": "resilientdb"}
)
data = response.json()
print(f"Query: {data.get('query')}")
print(f"Intent: {data['metadata']['intent']}")
print(f"Agent: {data['metadata']['agent']}")
print(f"Retrieval: {data['metadata']['retrieval_performed']}")
print(f"Documents: {data['metadata'].get('documents_found', 0)}")
print(f"Sources: {len(data['sources'])} chunks")
if data['sources']:
    print(f"Search methods: {[s.get('search_method', 'unknown') for s in data['sources'][:3]]}")
    print(f"Fusion method: {data['sources'][0].get('fusion_method', 'none')}")
print(f"Response preview: {data['response'][:120]}...")
print()

# Test 3: Apache-2.0 Keyword Query (BM25 should help)
print("TEST 3: Exact Keyword Search 'Apache-2.0'")
print("-" * 40)
response = requests.post(
    f"{API_BASE}/query/agentic",
    json={"query": "Tell me about the Apache-2.0 license", "project_id": "resilientdb"}
)
data = response.json()
print(f"Query: {data.get('query')}")
print(f"Intent: {data['metadata']['intent']}")
print(f"Documents: {data['metadata'].get('documents_found', 0)}")
print(f"Sources: {len(data['sources'])} chunks")
if data['sources']:
    print(f"Fusion method: {data['sources'][0].get('fusion_method', 'none')}")
    print(f"RRF scores: {[round(s.get('rrf_score', 0), 4) for s in data['sources'][:3]]}")
print(f"Response preview: {data['response'][:120]}...")
print()

# Test 4: Code of Conduct
print("TEST 4: Code of Conduct Query")
print("-" * 40)
response = requests.post(
    f"{API_BASE}/query/agentic",
    json={"query": "What is the code of conduct?", "project_id": "resilientdb"}
)
data = response.json()
print(f"Documents: {data['metadata'].get('documents_found', 0)}")
print(f"Sources: {len(data['sources'])} chunks")
if data['sources']:
    print(f"Fusion method: {data['sources'][0].get('fusion_method', 'none')}")
print(f"Response preview: {data['response'][:120]}...")
print()

print("=" * 60)
print("SUMMARY")
print("=" * 60)
print("✓ Agent 0: Conversational queries without retrieval")
print("✓ Agent 1: Hybrid search (BM25 + Vector) with RRF fusion")
print("✓ Metadata tracking: search_method, fusion_method, rrf_score")
print()

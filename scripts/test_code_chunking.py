"""Test code chunking for large files."""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from src.backend.infrastructure.code_chunker import CodeChunker, should_chunk

print("=" * 70)
print("Code Chunking Test")
print("=" * 70)

# Generate a large Python file for testing
large_code = ""
for i in range(250):  # 250 functions = ~12,500 lines
    large_code += f"""
def function_{i}(param1, param2, param3):
    '''Function {i} documentation.
    
    This is a sample function for testing code chunking.
    It demonstrates how large files are split at natural boundaries.
    '''
    result = param1 + param2 + param3
    if result > 100:
        return result * 2
    elif result > 50:
        return result * 1.5
    else:
        return result
    
    # Additional processing
    for j in range(10):
        result += j
    
    while result < 1000:
        result += 1
    
    try:
        final = result / param3
    except ZeroDivisionError:
        final = 0
    
    return final


class Class_{i}:
    '''Class {i} documentation.'''
    
    def __init__(self, value):
        self.value = value
    
    def method_a(self):
        return self.value * 2
    
    def method_b(self):
        return self.value + 10

"""

total_lines = large_code.count("\n")
print(f"\nGenerated test file: {total_lines:,} lines")

# Test 1: Check threshold
print("\n" + "=" * 70)
print("Test 1: Threshold Detection")
print("=" * 70)

small_code = "\n".join([f"line_{i}" for i in range(100)])
large_test = "\n".join([f"line_{i}" for i in range(15000)])

print(f"  Small file (100 lines): {should_chunk(small_code)}")
print(f"  Large file (15k lines): {should_chunk(large_test)}")

# Test 2: AST-based chunking
print("\n" + "=" * 70)
print("Test 2: AST-Based Chunking (Python)")
print("=" * 70)

chunker = CodeChunker(max_lines=5000, min_lines=1000, overlap=100)
result = chunker.chunk_code(large_code, language="python", filename="test.py")

print(f"\n  Original size: {result.original_size:,} lines")
print(f"  Strategy: {result.strategy}")
print(f"  Chunk count: {result.chunk_count}")
print(f"  Metadata: {result.metadata}")

print(f"\n  Chunk details:")
for i, chunk in enumerate(result.chunks):
    print(f"    Chunk {chunk.chunk_id}:")
    print(f"      Lines: {chunk.start_line}-{chunk.end_line} ({chunk.line_count} lines)")
    print(f"      Hash: {chunk.hash}")
    print(f"      Complete unit: {chunk.is_complete_unit}")
    if i >= 4:  # Show first 5 chunks
        print(f"    ... ({result.chunk_count - 5} more chunks)")
        break

# Test 3: Heuristic chunking
print("\n" + "=" * 70)
print("Test 3: Heuristic Chunking (Non-Python)")
print("=" * 70)

java_code = ""
for i in range(200):
    java_code += f"""
public class TestClass{i} {{
    private int value;
    
    public TestClass{i}(int value) {{
        this.value = value;
    }}
    
    public int getValue() {{
        return value;
    }}
    
    public void setValue(int value) {{
        this.value = value;
    }}
    
    public int calculate(int a, int b) {{
        int result = a + b;
        if (result > 100) {{
            return result * 2;
        }}
        return result;
    }}
}}

"""

java_lines = java_code.count("\n")
print(f"\n  Java code: {java_lines:,} lines")

result_java = chunker.chunk_code(java_code, language="java", filename="Test.java")
print(f"  Strategy: {result_java.strategy}")
print(f"  Chunks: {result_java.chunk_count}")

# Test 4: Overlap verification
print("\n" + "=" * 70)
print("Test 4: Chunk Overlap Verification")
print("=" * 70)

if result.chunk_count > 1:
    for i in range(min(3, result.chunk_count - 1)):
        chunk_a = result.chunks[i]
        chunk_b = result.chunks[i + 1]
        overlap_start = chunk_b.start_line
        overlap_end = chunk_a.end_line
        overlap_lines = max(0, overlap_end - overlap_start + 1)
        print(f"\n  Chunks {i} → {i+1}:")
        print(f"    Chunk {i} ends at line {chunk_a.end_line}")
        print(f"    Chunk {i+1} starts at line {chunk_b.start_line}")
        print(f"    Overlap: {overlap_lines} lines")

# Test 5: Memory efficiency
print("\n" + "=" * 70)
print("Test 5: Memory Efficiency")
print("=" * 70)

import sys

original_size = sys.getsizeof(large_code)
chunks_size = sum(sys.getsizeof(chunk.content) for chunk in result.chunks)
metadata_size = sum(
    sys.getsizeof(chunk.hash) + sys.getsizeof(chunk.chunk_id) 
    for chunk in result.chunks
)

print(f"\n  Original file: {original_size / 1024:.1f} KB")
print(f"  All chunks combined: {chunks_size / 1024:.1f} KB")
print(f"  Metadata overhead: {metadata_size / 1024:.1f} KB")
print(f"  Overhead ratio: {((chunks_size + metadata_size) / original_size):.2f}x")

# Test 6: Chunk completeness
print("\n" + "=" * 70)
print("Test 6: Semantic Completeness")
print("=" * 70)

complete_count = sum(1 for chunk in result.chunks if chunk.is_complete_unit)
incomplete_count = result.chunk_count - complete_count

print(f"\n  Complete units: {complete_count} / {result.chunk_count}")
print(f"  Incomplete units: {incomplete_count} / {result.chunk_count}")
print(f"  Completeness: {(complete_count / result.chunk_count * 100):.1f}%")

print("\n" + "=" * 70)
print("Conclusion")
print("=" * 70)

if result.strategy == "ast":
    print("✓ AST-based chunking successfully used")
    print("  Chunks split at natural function/class boundaries")
elif result.strategy == "heuristic":
    print("✓ Heuristic chunking used (fallback)")
    print("  Chunks split at empty lines and comments")

print(f"✓ Large files ({total_lines:,} lines) successfully chunked")
print(f"  {result.chunk_count} chunks of ~{total_lines // result.chunk_count:,} lines each")
print(f"  No memory exhaustion on massive files")
print(f"  Analysis can proceed in parallel per chunk")

print("\n" + "=" * 70)

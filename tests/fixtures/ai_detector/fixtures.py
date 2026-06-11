"""Test fixtures for AI Detector feature.

Provides synthetic code samples for testing signal computation, calibration,
and edge case handling. Includes both AI-generated and human-written code
samples across multiple programming languages.
"""

from typing import Dict, List, Tuple


# ============================================================================
# HUMAN-WRITTEN CODE SAMPLES (Low AI probability expected)
# ============================================================================

HUMAN_PYTHON_SIMPLE = """
def calculate_sum(numbers):
    total = 0
    for n in numbers:
        total += n
    return total

result = calculate_sum([1, 2, 3, 4, 5])
print(result)
"""

HUMAN_PYTHON_COMPLEX = """
class DataProcessor:
    def __init__(self, data):
        self.data = data
        self.cache = {}
    
    def process(self):
        # First pass: validate
        if not self._validate():
            raise ValueError("Invalid data")
        
        # Second pass: transform
        transformed = self._transform()
        
        # Third pass: aggregate
        return self._aggregate(transformed)
    
    def _validate(self):
        # Check for empty data
        if not self.data:
            return False
        
        # Check for required fields
        for item in self.data:
            if 'id' not in item:
                return False
        
        return True
    
    def _transform(self):
        result = []
        for item in self.data:
            # Skip duplicates
            if item['id'] in self.cache:
                continue
            
            # Transform item
            transformed = {
                'id': item['id'],
                'value': item.get('value', 0) * 2,
                'timestamp': item.get('timestamp', None)
            }
            result.append(transformed)
            self.cache[item['id']] = True
        
        return result
    
    def _aggregate(self, items):
        # Group by timestamp
        groups = {}
        for item in items:
            ts = item['timestamp']
            if ts not in groups:
                groups[ts] = []
            groups[ts].append(item)
        
        return groups
"""

HUMAN_PYTHON_BUGGY = """
def find_max(arr):
    if len(arr) == 0:
        return None
    
    max_val = arr[0]
    for i in range(1, len(arr)):
        if arr[i] > max_val:
            max_val = arr[i]
    
    return max_val

# Test
print(find_max([3, 1, 4, 1, 5, 9, 2, 6]))
print(find_max([]))
"""

HUMAN_JAVASCRIPT_SIMPLE = """
function greet(name) {
  return `Hello, ${name}!`;
}

console.log(greet('World'));
"""

HUMAN_JAVASCRIPT_COMPLEX = """
class UserManager {
  constructor(database) {
    this.db = database;
    this.users = new Map();
  }

  async addUser(id, userData) {
    if (this.users.has(id)) {
      throw new Error('User already exists');
    }

    const user = {
      id,
      name: userData.name,
      email: userData.email,
      createdAt: new Date()
    };

    this.users.set(id, user);
    await this.db.save(user);
    return user;
  }

  async getUser(id) {
    if (!this.users.has(id)) {
      const user = await this.db.load(id);
      if (!user) return null;
      this.users.set(id, user);
    }
    return this.users.get(id);
  }

  async deleteUser(id) {
    this.users.delete(id);
    await this.db.delete(id);
  }
}
"""


# ============================================================================
# AI-GENERATED CODE SAMPLES (High AI probability expected)
# ============================================================================

AI_PYTHON_SIMPLE = """
def calculate_sum(numbers):
    \"\"\"Calculate the sum of a list of numbers.
    
    Args:
        numbers: A list of numbers to sum.
    
    Returns:
        The sum of all numbers in the list.
    \"\"\"
    result = 0
    for number in numbers:
        result = result + number
    return result

# Test the function
test_numbers = [1, 2, 3, 4, 5]
output = calculate_sum(test_numbers)
print(output)
"""

AI_PYTHON_COMPLEX = """
class DataProcessor:
    \"\"\"Process and transform data from various sources.\"\"\"
    
    def __init__(self, data):
        \"\"\"Initialize the processor with data.\"\"\"
        self.data = data
        self.cache = {}
    
    def process(self):
        \"\"\"Process the data through multiple stages.\"\"\"
        if not self._validate():
            raise ValueError("Data validation failed")
        
        transformed = self._transform()
        return self._aggregate(transformed)
    
    def _validate(self):
        \"\"\"Validate the input data.\"\"\"
        if not self.data:
            return False
        
        for item in self.data:
            if 'id' not in item:
                return False
        
        return True
    
    def _transform(self):
        \"\"\"Transform the data.\"\"\"
        result = []
        for item in self.data:
            if item['id'] in self.cache:
                continue
            
            transformed = {
                'id': item['id'],
                'value': item.get('value', 0) * 2,
                'timestamp': item.get('timestamp', None)
            }
            result.append(transformed)
            self.cache[item['id']] = True
        
        return result
    
    def _aggregate(self, items):
        \"\"\"Aggregate the transformed data.\"\"\"
        groups = {}
        for item in items:
            ts = item['timestamp']
            if ts not in groups:
                groups[ts] = []
            groups[ts].append(item)
        
        return groups
"""

AI_PYTHON_GENERIC = """
def process_data(input_data):
    \"\"\"Process input data and return results.\"\"\"
    result = []
    for item in input_data:
        processed_item = {
            'id': item.get('id'),
            'value': item.get('value', 0),
            'status': 'processed'
        }
        result.append(processed_item)
    return result

def validate_input(data):
    \"\"\"Validate the input data.\"\"\"
    if not isinstance(data, list):
        return False
    if len(data) == 0:
        return False
    return True

def main():
    \"\"\"Main function.\"\"\"
    input_data = [{'id': 1, 'value': 10}, {'id': 2, 'value': 20}]
    if validate_input(input_data):
        output = process_data(input_data)
        print(output)

if __name__ == '__main__':
    main()
"""

AI_JAVASCRIPT_SIMPLE = """
function greet(name) {
    \"\"\"Greet a person by name.\"\"\"
    return `Hello, ${name}!`;
}

function main() {
    \"\"\"Main function.\"\"\"
    const name = 'World';
    const greeting = greet(name);
    console.log(greeting);
}

main();
"""


# ============================================================================
# EDGE CASE SAMPLES
# ============================================================================

EDGE_EMPTY_CODE = ""

EDGE_VERY_SHORT_CODE = "x = 1"

EDGE_SINGLE_LINE = "print('hello')"

EDGE_SYNTAX_ERROR_PYTHON = """
def broken_function(
    x = 1
    y = 2
    return x + y
"""

EDGE_ONLY_COMMENTS = """
# This is a comment
# Another comment
# Yet another comment
"""

EDGE_ONLY_WHITESPACE = """


    
    
"""

EDGE_MIXED_LANGUAGES = """
def python_func():
    return 42

function javascript_func() {
    return 42;
}
"""

EDGE_VERY_LONG_LINES = """
def process_data(input_data): result = [{'id': item.get('id'), 'value': item.get('value', 0), 'status': 'processed', 'timestamp': item.get('timestamp', None), 'metadata': item.get('metadata', {})} for item in input_data if item.get('id') is not None and item.get('value', 0) > 0]
"""

EDGE_HIGHLY_REPETITIVE = """
x = 1
x = x + 1
x = x + 1
x = x + 1
x = x + 1
x = x + 1
x = x + 1
x = x + 1
x = x + 1
x = x + 1
"""

EDGE_UNIFORM_INDENTATION = """
def func1():
    x = 1
    y = 2
    z = 3
    return x + y + z

def func2():
    a = 1
    b = 2
    c = 3
    return a + b + c

def func3():
    p = 1
    q = 2
    r = 3
    return p + q + r
"""


# ============================================================================
# FIXTURE COLLECTIONS
# ============================================================================

def get_human_samples() -> Dict[str, str]:
    """Return a collection of human-written code samples."""
    return {
        'human_python_simple': HUMAN_PYTHON_SIMPLE,
        'human_python_complex': HUMAN_PYTHON_COMPLEX,
        'human_python_buggy': HUMAN_PYTHON_BUGGY,
        'human_javascript_simple': HUMAN_JAVASCRIPT_SIMPLE,
        'human_javascript_complex': HUMAN_JAVASCRIPT_COMPLEX,
    }


def get_ai_samples() -> Dict[str, str]:
    """Return a collection of AI-generated code samples."""
    return {
        'ai_python_simple': AI_PYTHON_SIMPLE,
        'ai_python_complex': AI_PYTHON_COMPLEX,
        'ai_python_generic': AI_PYTHON_GENERIC,
        'ai_javascript_simple': AI_JAVASCRIPT_SIMPLE,
    }


def get_edge_case_samples() -> Dict[str, str]:
    """Return a collection of edge case code samples."""
    return {
        'edge_empty': EDGE_EMPTY_CODE,
        'edge_very_short': EDGE_VERY_SHORT_CODE,
        'edge_single_line': EDGE_SINGLE_LINE,
        'edge_syntax_error': EDGE_SYNTAX_ERROR_PYTHON,
        'edge_only_comments': EDGE_ONLY_COMMENTS,
        'edge_only_whitespace': EDGE_ONLY_WHITESPACE,
        'edge_mixed_languages': EDGE_MIXED_LANGUAGES,
        'edge_very_long_lines': EDGE_VERY_LONG_LINES,
        'edge_highly_repetitive': EDGE_HIGHLY_REPETITIVE,
        'edge_uniform_indentation': EDGE_UNIFORM_INDENTATION,
    }


def get_all_samples() -> Dict[str, str]:
    """Return all code samples."""
    samples = {}
    samples.update(get_human_samples())
    samples.update(get_ai_samples())
    samples.update(get_edge_case_samples())
    return samples


def get_sample_by_name(name: str) -> str:
    """Get a specific sample by name."""
    all_samples = get_all_samples()
    return all_samples.get(name, "")


def get_samples_by_category(category: str) -> Dict[str, str]:
    """Get samples by category (human, ai, edge_case)."""
    if category == 'human':
        return get_human_samples()
    elif category == 'ai':
        return get_ai_samples()
    elif category == 'edge_case':
        return get_edge_case_samples()
    else:
        return {}

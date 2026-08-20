from locust import HttpUser, task, between
import json


class PlagiarismDetectionUser(HttpUser):
    wait_time = between(1, 3)
    base_url = "http://localhost:8000"

    @task(50)
    def check_similarity_small(self):
        """Check similarity for small code samples"""
        code = """
def find_max(numbers):
    if not numbers:
        return None
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    return max_val
"""
        payload = {
            "code_a": code,
            "code_b": code.replace("def ", "def_"),
            "domain": "code",
        }
        with self.client.post(
            "/api/v1/similarity/check", json=payload, catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "verdict" in data:
                    response.success()
                else:
                    response.failure("Missing verdict in response")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(30)
    def check_similarity_medium(self):
        """Check similarity for medium code samples"""
        code = """
class TreeNode:
    def __init__(self, value=0, left=None, right=None):
        self.val = value
        self.left = left
        self.right = right

def max_path_sum(root):
    if not root:
        return 0
    return max(max_path_sum(root.left), max_path_sum(root.right)) + root.val
"""
        payload = {"code_a": code, "code_b": code, "domain": "code"}
        self.client.post("/api/v1/similarity/check", json=payload)

    @task(10)
    def get_results(self):
        """Fetch recent results"""
        self.client.get("/api/v1/results?limit=10")

    @task(5)
    def health_check(self):
        """Health check endpoint"""
        self.client.get("/health")


class AdminUser(HttpUser):
    wait_time = between(5, 10)

    @task
    def get_settings(self):
        self.client.get("/api/v1/settings")

    @task
    def get_users(self):
        self.client.get("/api/v1/users")

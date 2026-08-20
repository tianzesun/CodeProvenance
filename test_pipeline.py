from src.backend.engines.scoring.fusion_engine import FusionEngine

engine = FusionEngine()
code_a = 'def foo(): return 1'
code_b = 'def foo(): return 1'
engine_scores = {'fingerprint': 1.0, 'ngram': 0.998, 'winnowing': 0.90, 'ast': 0.56, 'embedding': 0.0}

result = engine.run_three_layer_pipeline(code_a, code_b, engine_scores)
print('Verdict:', result.get('verdict'))
print('Score:', result.get('score', 0))
print('Risk Level:', result.get('risk_level'))
print('Decision Path:', result.get('fusion_debug', {}).get('decision_path'))

# Also test direct fusion
class MockFeatures:
    def as_dict(self):
        return engine_scores

result2 = engine.fuse(MockFeatures())
print()
print('=== Direct Fusion ===')
print(f'Score: {result2.final_score:.2f}')
print(f'Verdict: {result2.verdict}')
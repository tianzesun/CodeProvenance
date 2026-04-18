"""Similarity Registry - extensible registry for all similarity algorithms."""


class SimilarityRegistry:
    _engines = {}

    @classmethod
    def register(cls, name, engine):
        cls._engines[name] = engine

    @classmethod
    def get(cls, name):
        return cls._engines.get(name)

    @classmethod
    def list(cls):
        return list(cls._engines.keys())

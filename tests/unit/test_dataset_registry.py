"""Tests for the cross-dataset registry built by ``build_default_registry``."""

from __future__ import annotations

from unittest import mock

from src.backend.benchmark.cross_dataset import dataset_registry as dr


def test_default_registry_loaders_keep_their_own_dataset_name() -> None:
    """Each loader labels its dataset with its own name, not the last one registered."""
    with (
        mock.patch.object(
            dr.UnifiedDataset, "from_canonical", side_effect=lambda canonical, name: name
        ),
        mock.patch("src.backend.benchmark.pipeline.external_loader.ExternalDatasetLoader"),
    ):
        registry = dr.build_default_registry()
        loaded = {name: loader() for name, loader in registry._loaders.items()}

    assert len(loaded) > 1, "expected several default datasets"
    assert loaded == {name: name for name in loaded}

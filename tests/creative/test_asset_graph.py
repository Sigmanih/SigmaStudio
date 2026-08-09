import pytest
import os
import sqlite3
import shutil
from pathlib import Path
from core.creative.asset_graph import AssetGraph, AssetType, Asset

@pytest.fixture
def asset_graph(tmp_path):
    db_path = tmp_path / "test_assets.db"
    # We patch the hardcoded assets_dir temporarily
    ag = AssetGraph(db_path=str(db_path))
    ag.assets_dir = tmp_path / "assets"
    ag.assets_dir.mkdir(exist_ok=True)
    yield ag
    
def test_create_and_get_asset(asset_graph):
    asset = asset_graph.create_asset(AssetType.IMAGE, "test_image", metadata={"key": "value"})
    assert asset.name == "test_image"
    assert asset.type == AssetType.IMAGE
    assert asset.metadata == {"key": "value"}
    
    fetched = asset_graph.get_asset(asset.asset_id)
    assert fetched.asset_id == asset.asset_id
    assert fetched.name == "test_image"
    assert fetched.metadata == {"key": "value"}

def test_update_asset(asset_graph):
    asset = asset_graph.create_asset(AssetType.IMAGE, "test_image")
    updated = asset_graph.update_asset(asset.asset_id, name="new_name", tags=["tag1"])
    assert updated.name == "new_name"
    assert updated.tags == ["tag1"]

def test_delete_asset(asset_graph):
    asset = asset_graph.create_asset(AssetType.IMAGE, "test_image")
    asset_graph.delete_asset(asset.asset_id)
    assert asset_graph.get_asset(asset.asset_id) is None

def test_list_assets(asset_graph):
    asset_graph.create_asset(AssetType.IMAGE, "img1", tags=["cool"])
    asset_graph.create_asset(AssetType.MESH, "mesh1", tags=["cool"])
    
    assets = asset_graph.list_assets()
    assert len(assets) == 2
    
    # Check type filter
    images = asset_graph.list_assets(type_filter=AssetType.IMAGE.value)
    assert len(images) == 1
    
    # Check tag filter
    cool_assets = asset_graph.list_assets(tag_filter="cool")
    assert len(cool_assets) == 2

def test_create_version(asset_graph):
    asset = asset_graph.create_asset(AssetType.IMAGE, "v1_img")
    new_asset = asset_graph.create_version(asset.asset_id, files={"image": "v2.png"})
    
    assert new_asset.current_version == 2
    assert new_asset.files == {"image": "v2.png"}
    
    versions = asset_graph.get_versions(asset.asset_id)
    assert len(versions) == 2
    assert versions[0]["version"] == 2
    assert versions[1]["version"] == 1

def test_get_stats(asset_graph):
    asset_graph.create_asset(AssetType.IMAGE, "i1")
    asset_graph.create_asset(AssetType.IMAGE, "i2")
    asset_graph.create_asset(AssetType.MESH, "m1")
    
    stats = asset_graph.get_stats()
    assert stats["total"] == 3
    assert stats["by_type"][AssetType.IMAGE.value] == 2
    assert stats["by_type"][AssetType.MESH.value] == 1

def test_to_dict():
    asset = Asset("id", "image", "name", None, 1, None, None, None, None, "2026", "2026")
    d = asset.to_dict()
    assert d["asset_id"] == "id"

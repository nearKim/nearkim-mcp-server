"""Tests for domain value objects."""

import pytest

from src.domain.value_objects import EntityId, EntityName, LabelMatch, ProjectMatch


class TestEntityId:
    """Test EntityId value object."""
    
    def test_valid_entity_id(self):
        """Test creating a valid EntityId."""
        entity_id = EntityId("123")
        assert entity_id.value == "123"
    
    def test_empty_entity_id_raises_error(self):
        """Test that empty EntityId raises ValueError."""
        with pytest.raises(ValueError, match="EntityId cannot be empty"):
            EntityId("")
    
    def test_whitespace_entity_id_raises_error(self):
        """Test that whitespace-only EntityId raises ValueError."""
        with pytest.raises(ValueError, match="EntityId cannot be empty"):
            EntityId("   ")
    
    def test_entity_id_immutable(self):
        """Test that EntityId is immutable (frozen dataclass)."""
        entity_id = EntityId("123")
        with pytest.raises(AttributeError):
            entity_id.value = "456"
    
    def test_entity_id_equality(self):
        """Test EntityId equality."""
        id1 = EntityId("123")
        id2 = EntityId("123")
        id3 = EntityId("456")
        
        assert id1 == id2
        assert id1 != id3


class TestEntityName:
    """Test EntityName value object."""
    
    def test_valid_entity_name(self):
        """Test creating a valid EntityName."""
        name = EntityName("Project Alpha")
        assert name.value == "Project Alpha"
    
    def test_empty_entity_name_raises_error(self):
        """Test that empty EntityName raises ValueError."""
        with pytest.raises(ValueError, match="EntityName cannot be empty"):
            EntityName("")
    
    def test_whitespace_entity_name_raises_error(self):
        """Test that whitespace-only EntityName raises ValueError."""
        with pytest.raises(ValueError, match="EntityName cannot be empty"):
            EntityName("   ")
    
    def test_entity_name_immutable(self):
        """Test that EntityName is immutable."""
        name = EntityName("Test")
        with pytest.raises(AttributeError):
            name.value = "Changed"
    
    def test_entity_name_with_special_chars(self):
        """Test EntityName with special characters."""
        name = EntityName("Project @#$%")
        assert name.value == "Project @#$%"


class TestProjectMatch:
    """Test ProjectMatch value object."""
    
    def test_project_match_creation(self):
        """Test creating a ProjectMatch."""
        match = ProjectMatch(project_id="proj_123")
        assert match.project_id == "proj_123"
    
    def test_project_match_immutable(self):
        """Test that ProjectMatch is immutable."""
        match = ProjectMatch(project_id="proj_123")
        with pytest.raises(AttributeError):
            match.project_id = "proj_456"


class TestLabelMatch:
    """Test LabelMatch value object."""
    
    def test_label_match_creation(self):
        """Test creating a LabelMatch."""
        match = LabelMatch(label_ids=["label1", "label2"])
        assert match.label_ids == ["label1", "label2"]
    
    def test_label_match_empty_list(self):
        """Test LabelMatch with empty list."""
        match = LabelMatch(label_ids=[])
        assert match.label_ids == []
    
    def test_label_match_immutable(self):
        """Test that LabelMatch is immutable."""
        match = LabelMatch(label_ids=["label1"])
        with pytest.raises(AttributeError):
            match.label_ids = ["label2"]
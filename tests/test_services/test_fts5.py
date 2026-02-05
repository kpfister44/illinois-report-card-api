# ABOUTME: Tests for FTS5 full-text search index
# ABOUTME: Validates FTS5 virtual table creation and sync triggers

import pytest
from sqlalchemy import text
from app.models.database import EntitiesMaster
from app.services.fts5 import rebuild_fts5_index


def test_fts5_index_created_and_synced(db_session):
    """Test #46: FTS5 full-text search index is created and synced."""
    # Step 1: Import entities into entities_master
    entities = [
        EntitiesMaster(
            rcdts="15-016-0010-22",
            entity_type="school",
            name="Lincoln Elementary School",
            city="Chicago",
            county="Cook"
        ),
        EntitiesMaster(
            rcdts="15-016-0000-26",
            entity_type="district",
            name="Chicago Public Schools",
            city="Chicago",
            county="Cook"
        )
    ]

    for entity in entities:
        db_session.add(entity)
    db_session.commit()

    # Step 2: Verify FTS5 virtual table exists
    result = db_session.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='entities_fts'"
    ))
    fts_table = result.fetchone()
    assert fts_table is not None, "FTS5 virtual table 'entities_fts' should exist"

    # Verify initial entities are in FTS5 index
    result = db_session.execute(text(
        "SELECT COUNT(*) FROM entities_fts"
    ))
    count = result.scalar()
    assert count == 2, "FTS5 index should contain 2 entities"

    # Step 3: Insert new entity into entities_master
    new_entity = EntitiesMaster(
        rcdts="46-062-0020-22",
        entity_type="school",
        name="Springfield High School",
        city="Springfield",
        county="Sangamon"
    )
    db_session.add(new_entity)
    db_session.commit()

    # Step 4: Verify FTS5 index updated via trigger
    result = db_session.execute(text(
        "SELECT COUNT(*) FROM entities_fts WHERE name MATCH 'Springfield'"
    ))
    count = result.scalar()
    assert count == 1, "FTS5 index should contain newly inserted entity"

    # Verify total count increased
    result = db_session.execute(text(
        "SELECT COUNT(*) FROM entities_fts"
    ))
    count = result.scalar()
    assert count == 3, "FTS5 index should now contain 3 entities"

    # Step 5: Update entity name in entities_master
    entity_to_update = db_session.query(EntitiesMaster).filter(
        EntitiesMaster.rcdts == "15-016-0010-22"
    ).first()
    entity_to_update.name = "Lincoln Elementary Academy"
    db_session.commit()

    # Step 6: Verify FTS5 index reflects change
    result = db_session.execute(text(
        "SELECT name FROM entities_fts WHERE name MATCH 'Academy'"
    ))
    updated_name = result.fetchone()
    assert updated_name is not None, "FTS5 index should reflect updated name"
    assert "Academy" in updated_name[0], "FTS5 should contain the updated name"

    # Step 7: Delete entity from entities_master
    entity_to_delete = db_session.query(EntitiesMaster).filter(
        EntitiesMaster.rcdts == "46-062-0020-22"
    ).first()
    db_session.delete(entity_to_delete)
    db_session.commit()

    # Step 8: Verify FTS5 index removes entry
    result = db_session.execute(text(
        "SELECT COUNT(*) FROM entities_fts WHERE entities_fts MATCH 'Springfield'"
    ))
    count = result.scalar()
    assert count == 0, "FTS5 index should no longer contain deleted entity"

    # Verify total count decreased
    result = db_session.execute(text(
        "SELECT COUNT(*) FROM entities_fts"
    ))
    count = result.scalar()
    assert count == 2, "FTS5 index should now contain 2 entities after deletion"


def test_rebuild_fts5_index(db_session):
    """Test rebuild_fts5_index function clears and rebuilds FTS5 index from entities_master."""
    from tests.conftest import engine

    # Add some entities to entities_master
    entities = [
        EntitiesMaster(
            rcdts="15-016-0010-22",
            entity_type="school",
            name="Lincoln Elementary School",
            city="Chicago",
            county="Cook"
        ),
        EntitiesMaster(
            rcdts="15-016-0000-26",
            entity_type="district",
            name="Chicago Public Schools",
            city="Chicago",
            county="Cook"
        ),
        EntitiesMaster(
            rcdts="46-062-0020-22",
            entity_type="school",
            name="Springfield High School",
            city="Springfield",
            county="Sangamon"
        )
    ]

    for entity in entities:
        db_session.add(entity)
    db_session.commit()

    # Verify FTS5 has 3 entities (via triggers)
    result = db_session.execute(text("SELECT COUNT(*) FROM entities_fts"))
    assert result.scalar() == 3

    # Manually corrupt FTS5 by deleting an entry
    db_session.execute(text("DELETE FROM entities_fts WHERE rcdts = '15-016-0010-22'"))
    db_session.commit()

    # Verify FTS5 is now out of sync (only 2 entries)
    result = db_session.execute(text("SELECT COUNT(*) FROM entities_fts"))
    assert result.scalar() == 2

    # Rebuild FTS5 index
    rebuild_fts5_index(engine)

    # Verify FTS5 is back in sync (all 3 entities restored)
    result = db_session.execute(text("SELECT COUNT(*) FROM entities_fts"))
    assert result.scalar() == 3

    # Verify the previously deleted entry is back
    result = db_session.execute(text(
        "SELECT COUNT(*) FROM entities_fts WHERE rcdts = '15-016-0010-22'"
    ))
    assert result.scalar() == 1

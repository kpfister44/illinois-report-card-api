# ABOUTME: FTS5 full-text search setup and management
# ABOUTME: Creates FTS5 virtual table and sync triggers for entities_master

from sqlalchemy import text


def setup_fts5(engine):
    """
    Create FTS5 virtual table and triggers for full-text search.

    Creates:
    - entities_fts: FTS5 virtual table for searching entity names
    - Triggers to keep FTS5 in sync with entities_master (insert, update, delete)
    """
    with engine.connect() as conn:
        # Create FTS5 virtual table for entity search
        # This indexes: rcdts, entity_type, name, city, county
        # Note: Not using external content table for simplicity
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
                rcdts UNINDEXED,
                entity_type UNINDEXED,
                name,
                city,
                county
            )
        """))

        # Trigger to keep FTS5 in sync on INSERT
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS entities_fts_insert
            AFTER INSERT ON entities_master
            BEGIN
                INSERT INTO entities_fts(rcdts, entity_type, name, city, county)
                VALUES (new.rcdts, new.entity_type, new.name, new.city, new.county);
            END
        """))

        # Trigger to keep FTS5 in sync on UPDATE
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS entities_fts_update
            AFTER UPDATE ON entities_master
            BEGIN
                UPDATE entities_fts
                SET rcdts = new.rcdts,
                    entity_type = new.entity_type,
                    name = new.name,
                    city = new.city,
                    county = new.county
                WHERE rcdts = old.rcdts;
            END
        """))

        # Trigger to keep FTS5 in sync on DELETE
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS entities_fts_delete
            AFTER DELETE ON entities_master
            BEGIN
                DELETE FROM entities_fts WHERE rcdts = old.rcdts;
            END
        """))

        conn.commit()


def rebuild_fts5_index(engine):
    """
    Rebuild FTS5 index from entities_master.

    Useful after bulk imports or if the index gets out of sync.
    """
    with engine.connect() as conn:
        # Clear existing FTS5 data
        conn.execute(text("DELETE FROM entities_fts"))

        # Rebuild from entities_master
        conn.execute(text("""
            INSERT INTO entities_fts(rcdts, entity_type, name, city, county)
            SELECT rcdts, entity_type, name, city, county
            FROM entities_master
        """))

        conn.commit()

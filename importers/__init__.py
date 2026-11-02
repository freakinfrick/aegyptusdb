"""Shared importer utilities."""

from sqlalchemy.dialects.postgresql import insert as pg_insert


def pg_flush(session, table, batch: list[dict], conflict_cols=None) -> int:
    """Bulk-insert a batch into *table* with ON CONFLICT DO NOTHING.

    Args:
        session: SQLAlchemy session.
        table: ORM ``__table__`` attribute (or a Table object).
        batch: List of row dicts.
        conflict_cols: Column names for the conflict target.  Pass ``None`` to
            let PostgreSQL infer the primary-key constraint.  Pass a list such
            as ``["canonical_id"]`` to target a specific unique index.

    Returns:
        Number of rows actually inserted (may be less than len(batch) when rows
        already exist).
    """
    if not batch:
        return 0
    stmt = pg_insert(table).values(batch)
    if conflict_cols is not None:
        stmt = stmt.on_conflict_do_nothing(index_elements=conflict_cols)
    else:
        stmt = stmt.on_conflict_do_nothing()
    result = session.execute(stmt)
    session.commit()
    return result.rowcount

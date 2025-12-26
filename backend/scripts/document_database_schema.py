"""Script to document Railway database schemas for rollback reference."""
import asyncio
import asyncpg
import json
from datetime import datetime
from pathlib import Path

# This script should be run with Railway database credentials
# Usage: python backend/scripts/document_database_schema.py


async def get_table_schema(conn, schema_name: str = 'public'):
    """Get all tables and their structure."""
    tables = await conn.fetch("""
        SELECT 
            table_name,
            table_type
        FROM information_schema.tables
        WHERE table_schema = $1
        ORDER BY table_name
    """, schema_name)
    
    result = {}
    for table in tables:
        table_name = table['table_name']
        
        # Get columns
        columns = await conn.fetch("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default,
                udt_name
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            ORDER BY ordinal_position
        """, schema_name, table_name)
        
        # Get primary keys
        primary_keys = await conn.fetch("""
            SELECT 
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = $1
                AND tc.table_name = $2
        """, schema_name, table_name)
        
        # Get foreign keys
        foreign_keys = await conn.fetch("""
            SELECT
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.update_rule,
                rc.delete_rule
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            JOIN information_schema.referential_constraints AS rc
                ON rc.constraint_name = tc.constraint_name
                AND rc.constraint_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = $1
                AND tc.table_name = $2
        """, schema_name, table_name)
        
        # Get indexes
        indexes = await conn.fetch("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = $1 AND tablename = $2
            ORDER BY indexname
        """, schema_name, table_name)
        
        # Get constraints (check, unique, etc.)
        constraints = await conn.fetch("""
            SELECT
                constraint_name,
                constraint_type,
                check_clause
            FROM information_schema.table_constraints
            WHERE table_schema = $1
                AND table_name = $2
                AND constraint_type IN ('CHECK', 'UNIQUE')
            ORDER BY constraint_name
        """, schema_name, table_name)
        
        result[table_name] = {
            'type': table['table_type'],
            'columns': [
                {
                    'name': col['column_name'],
                    'type': col['data_type'],
                    'udt_name': col['udt_name'],
                    'max_length': col['character_maximum_length'],
                    'nullable': col['is_nullable'] == 'YES',
                    'default': col['column_default']
                }
                for col in columns
            ],
            'primary_keys': [pk['column_name'] for pk in primary_keys],
            'foreign_keys': [
                {
                    'column': fk['column_name'],
                    'references': f"{fk['foreign_table_schema']}.{fk['foreign_table_name']}({fk['foreign_column_name']})",
                    'on_update': fk['update_rule'],
                    'on_delete': fk['delete_rule']
                }
                for fk in foreign_keys
            ],
            'indexes': [
                {
                    'name': idx['indexname'],
                    'definition': idx['indexdef']
                }
                for idx in indexes
            ],
            'constraints': [
                {
                    'name': con['constraint_name'],
                    'type': con['constraint_type'],
                    'check_clause': con['check_clause']
                }
                for con in constraints
            ]
        }
    
    return result


async def get_enums(conn, schema_name: str = 'public'):
    """Get all enum types."""
    enums = await conn.fetch("""
        SELECT
            t.typname AS enum_name,
            e.enumlabel AS enum_value
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = $1
        ORDER BY t.typname, e.enumsortorder
    """, schema_name)
    
    result = {}
    for enum in enums:
        enum_name = enum['enum_name']
        if enum_name not in result:
            result[enum_name] = []
        result[enum_name].append(enum['enum_value'])
    
    return result


def generate_markdown(ephemeral_schema, persistent_schema, ephemeral_enums=None, persistent_enums=None):
    """Generate markdown documentation."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    
    md = f"""# Database Schema Documentation
## Fact Atom Based Architecture - Contradiction Detection MVP

**Documented:** {timestamp}
**Purpose:** Rollback reference for database structure restoration

---

## Ephemeral Database Schema
**Database:** `depodigest_ephemeral` (or Railway auto-generated name)
**Purpose:** Transcript/document data that can be cleared without losing user data

### Tables

"""
    
    # Ephemeral tables
    for table_name, table_info in sorted(ephemeral_schema.items()):
        md += f"### `{table_name}`\n\n"
        md += f"**Type:** {table_info['type']}\n\n"
        
        md += "**Columns:**\n\n"
        md += "| Column Name | Data Type | Nullable | Default | Description |\n"
        md += "|-------------|-----------|----------|---------|-------------|\n"
        
        for col in table_info['columns']:
            type_str = col['type']
            if col['max_length']:
                type_str += f"({col['max_length']})"
            if col['udt_name'] and col['udt_name'] != col['type']:
                type_str += f" ({col['udt_name']})"
            
            default = col['default'] or ''
            nullable = 'YES' if col['nullable'] else 'NO'
            md += f"| `{col['name']}` | {type_str} | {nullable} | {default} | |\n"
        
        if table_info['primary_keys']:
            md += f"\n**Primary Key:** {', '.join([f'`{pk}`' for pk in table_info['primary_keys']])}\n"
        
        if table_info['foreign_keys']:
            md += "\n**Foreign Keys:**\n\n"
            for fk in table_info['foreign_keys']:
                md += f"- `{fk['column']}` → {fk['references']} (ON UPDATE {fk['on_update']}, ON DELETE {fk['on_delete']})\n"
        
        if table_info['indexes']:
            md += "\n**Indexes:**\n\n"
            for idx in table_info['indexes']:
                md += f"- `{idx['name']}`: `{idx['definition']}`\n"
        
        if table_info['constraints']:
            md += "\n**Constraints:**\n\n"
            for con in table_info['constraints']:
                if con['type'] == 'CHECK' and con['check_clause']:
                    md += f"- `{con['name']}` (CHECK): {con['check_clause']}\n"
                else:
                    md += f"- `{con['name']}` ({con['type']})\n"
        
        md += "\n---\n\n"
    
    # Ephemeral enums
    if ephemeral_enums:
        md += "### Enum Types\n\n"
        for enum_name, enum_values in sorted(ephemeral_enums.items()):
            md += f"**`{enum_name}`:**\n"
            md += f"- {', '.join([f'`{v}`' for v in enum_values])}\n\n"
    
    md += """---

## Persistent Database Schema
**Database:** `depodigest_persistent` (or Railway auto-generated name)
**Purpose:** User data, authentication, settings, feedback (NEVER cleared)

### Tables

"""
    
    # Persistent tables
    for table_name, table_info in sorted(persistent_schema.items()):
        md += f"### `{table_name}`\n\n"
        md += f"**Type:** {table_info['type']}\n\n"
        
        md += "**Columns:**\n\n"
        md += "| Column Name | Data Type | Nullable | Default | Description |\n"
        md += "|-------------|-----------|----------|---------|-------------|\n"
        
        for col in table_info['columns']:
            type_str = col['type']
            if col['max_length']:
                type_str += f"({col['max_length']})"
            if col['udt_name'] and col['udt_name'] != col['type']:
                type_str += f" ({col['udt_name']})"
            
            default = col['default'] or ''
            nullable = 'YES' if col['nullable'] else 'NO'
            md += f"| `{col['name']}` | {type_str} | {nullable} | {default} | |\n"
        
        if table_info['primary_keys']:
            md += f"\n**Primary Key:** {', '.join([f'`{pk}`' for pk in table_info['primary_keys']])}\n"
        
        if table_info['foreign_keys']:
            md += "\n**Foreign Keys:**\n\n"
            for fk in table_info['foreign_keys']:
                md += f"- `{fk['column']}` → {fk['references']} (ON UPDATE {fk['on_update']}, ON DELETE {fk['on_delete']})\n"
        
        if table_info['indexes']:
            md += "\n**Indexes:**\n\n"
            for idx in table_info['indexes']:
                md += f"- `{idx['name']}`: `{idx['definition']}`\n"
        
        if table_info['constraints']:
            md += "\n**Constraints:**\n\n"
            for con in table_info['constraints']:
                if con['type'] == 'CHECK' and con['check_clause']:
                    md += f"- `{con['name']}` (CHECK): {con['check_clause']}\n"
                else:
                    md += f"- `{con['name']}` ({con['type']})\n"
        
        md += "\n---\n\n"
    
    # Persistent enums
    if persistent_enums:
        md += "### Enum Types\n\n"
        for enum_name, enum_values in sorted(persistent_enums.items()):
            md += f"**`{enum_name}`:**\n"
            md += f"- {', '.join([f'`{v}`' for v in enum_values])}\n\n"
    
    md += """---

## Restoration Instructions

To restore the database structure to this state:

1. **Connect to Railway databases** using Railway CLI or dashboard
2. **Run the SQL CREATE statements** from `backend/services/db_service.py`:
   - Ephemeral database: `init_db()` function
   - Persistent database: `init_persistent_db()` function
3. **Verify indexes** are created correctly
4. **Check constraints** match documented structure

### Quick Restore Commands

```bash
# Connect to ephemeral database
railway connect --service depodigest-ephemeral

# Connect to persistent database  
railway connect --service depodigest-persistent

# Run schema initialization
# (The db_service.py init functions will create all tables)
```

---

## Notes

- This schema represents the **Fact Atom Based Architecture** state
- Includes new tables: `claims`, `claim_entities`, `contradictions`
- Date provenance fields: `explicit_date`, `inferred_date`, `date_source`, `date_anchor`
- Designed for future multi-transcript contradiction detection
"""
    
    return md


async def main():
    """Main function to document databases."""
    import os
    
    # Get database URLs from environment
    ephemeral_url = os.getenv('DATABASE_URL')
    persistent_url = os.getenv('PERSISTENT_DATABASE_URL')
    
    if not ephemeral_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Set it to your Railway ephemeral database connection string")
        return
    
    if not persistent_url:
        print("ERROR: PERSISTENT_DATABASE_URL environment variable not set")
        print("Set it to your Railway persistent database connection string")
        return
    
    print("Connecting to ephemeral database...")
    ephemeral_conn = await asyncpg.connect(ephemeral_url)
    
    print("Connecting to persistent database...")
    persistent_conn = await asyncpg.connect(persistent_url)
    
    try:
        print("Fetching ephemeral database schema...")
        ephemeral_schema = await get_table_schema(ephemeral_conn)
        ephemeral_enums = await get_enums(ephemeral_conn)
        
        print("Fetching persistent database schema...")
        persistent_schema = await get_table_schema(persistent_conn)
        persistent_enums = await get_enums(persistent_conn)
        
        print("Generating markdown documentation...")
        md_content = generate_markdown(
            ephemeral_schema,
            persistent_schema,
            ephemeral_enums,
            persistent_enums
        )
        
        # Write to file
        output_path = Path('DATABASE_SCHEMA_BACKUP.md')
        output_path.write_text(md_content, encoding='utf-8')
        
        print(f"\n✅ Database schema documented successfully!")
        print(f"📄 Output file: {output_path.absolute()}")
        print(f"📊 Ephemeral tables: {len(ephemeral_schema)}")
        print(f"📊 Persistent tables: {len(persistent_schema)}")
        
    finally:
        await ephemeral_conn.close()
        await persistent_conn.close()


if __name__ == '__main__':
    asyncio.run(main())


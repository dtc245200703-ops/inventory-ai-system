"""Read-only SQLite consistency audit. Exit 1 on findings, 0 otherwise."""
import json
from sqlalchemy import text
from app.database import engine


def main():
    findings = []
    with engine.connect() as db:
        if engine.dialect.name != "sqlite":
            raise SystemExit("This audit supports SQLite only.")
        for row in db.execute(text("PRAGMA integrity_check")):
            if row[0] != "ok":
                findings.append({"integrity": row[0]})
        for row in db.execute(text("PRAGMA foreign_key_check")):
            findings.append({"foreign_key": list(row)})
        queries = {
            "missing_inventory": "SELECT p.product_id FROM products p LEFT JOIN inventory i ON i.product_id=p.product_id WHERE i.product_id IS NULL",
            "negative_inventory": "SELECT product_id FROM inventory WHERE quantity_available < 0",
            "invalid_minimum": "SELECT product_id FROM products WHERE min_stock_level < 0 OR min_stock_level IS NULL",
            "latest_balance_mismatch": "SELECT i.product_id FROM inventory i JOIN stock_movements m ON m.id=(SELECT MAX(s.id) FROM stock_movements s WHERE s.product_id=i.product_id) WHERE i.quantity_available != m.balance_after",
            "inventory_without_history": "SELECT i.product_id FROM inventory i WHERE i.quantity_available != 0 AND NOT EXISTS (SELECT 1 FROM stock_movements m WHERE m.product_id=i.product_id)",
        }
        for name, sql in queries.items():
            for row in db.execute(text(sql)):
                findings.append({name: row[0]})
    print(json.dumps({"findings": findings, "count": len(findings)}, ensure_ascii=False, indent=2))
    return bool(findings)


if __name__ == "__main__":
    raise SystemExit(main())

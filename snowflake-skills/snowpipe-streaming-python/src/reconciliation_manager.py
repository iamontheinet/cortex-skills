"""Post-ingestion reconciliation manager.

Connects to Snowflake via snowflake-connector-python to verify row counts
and detect orphaned order items after streaming completes.
"""

import logging

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)


class ReconciliationManager:
    """Verifies data integrity after streaming ingestion."""

    def __init__(self, profile: dict):
        self.profile = profile
        self.conn = None

    def connect(self):
        """Open a connector connection using the profile's RSA key."""
        key_file = self.profile.get("private_key_file", "streaming_key.p8")
        with open(key_file, "rb") as f:
            p_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
        pkb = p_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        self.conn = snowflake.connector.connect(
            user=self.profile["user"],
            account=self.profile["account"],
            private_key=pkb,
            role=self.profile["role"],
            warehouse=self.profile.get("warehouse", "COMPUTE_WH"),
            database=self.profile["database"],
            schema=self.profile["schema"],
        )
        logger.info("Reconciliation connected to %s.%s", self.profile["database"], self.profile["schema"])

    def get_row_counts(self, orders_table: str = "ORDERS", items_table: str = "ORDER_ITEMS") -> dict:
        """Return row counts for both tables."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {orders_table}")
            orders_count = cursor.fetchone()[0]
            cursor.execute(f"SELECT COUNT(*) FROM {items_table}")
            items_count = cursor.fetchone()[0]
            return {"orders": orders_count, "order_items": items_count}
        finally:
            cursor.close()

    def check_orphaned_items(self, orders_table: str = "ORDERS", items_table: str = "ORDER_ITEMS") -> int:
        """Count order items whose ORDER_ID does not exist in the orders table."""
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"SELECT COUNT(*) FROM {items_table} i "
                f"WHERE NOT EXISTS (SELECT 1 FROM {orders_table} o WHERE o.ORDER_ID = i.ORDER_ID)"
            )
            return cursor.fetchone()[0]
        finally:
            cursor.close()

    def run(self, orders_table: str = "ORDERS", items_table: str = "ORDER_ITEMS") -> dict:
        """Run full reconciliation: counts + orphan check.

        Returns:
            dict with keys: orders, order_items, orphaned_items, ratio, status
        """
        if not self.conn:
            self.connect()

        counts = self.get_row_counts(orders_table, items_table)
        orphaned = self.check_orphaned_items(orders_table, items_table)

        ratio = round(counts["order_items"] / counts["orders"], 2) if counts["orders"] > 0 else 0
        status = "PASS" if orphaned == 0 else "FAIL"

        result = {
            **counts,
            "orphaned_items": orphaned,
            "ratio": ratio,
            "status": status,
        }
        logger.info("Reconciliation result: %s", result)
        return result

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

"""Single-instance Snowpipe Streaming entry point.

Usage:
    python src/streaming_app.py <num_orders> [config_file] [profile_file]

Example:
    python src/streaming_app.py 1000
    python src/streaming_app.py 5000 config_staging.properties profile_staging.json
"""

import logging
import sys
import time
import uuid

from config_manager import build_config
from data_generator import generate_orders
from snowpipe_streaming_manager import SnowpipeStreamingManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def stream_orders(num_orders: int, config_file: str = "config.properties", profile_file: str = "profile.json"):
    config = build_config(config_file, profile_file)
    profile = config["profile"]
    sdk_props = config["sdk_properties"]

    database = profile["database"]
    schema = profile["schema"]
    batch_size = int(config.get("orders.batch.size", "10000"))
    max_retries = int(config.get("max.retries", "3"))
    retry_delay_ms = int(config.get("retry.delay.ms", "1000"))

    uid = uuid.uuid4().hex[:8]
    orders_channel = config.get("channel.orders.name", "orders_channel")
    items_channel = config.get("channel.order_items.name", "order_items_channel")
    orders_pipe = config.get("pipe.orders.name", "ORDERS-STREAMING")
    items_pipe = config.get("pipe.order_items.name", "ORDER_ITEMS-STREAMING")

    # --- Generate data ---
    logger.info("Generating %d orders...", num_orders)
    start = time.time()
    orders, items = generate_orders(num_orders)
    logger.info("Generated %d orders, %d items in %.2fs", len(orders), len(items), time.time() - start)

    # --- Stream orders ---
    orders_mgr = SnowpipeStreamingManager(
        client_name=f"ORDERS_CLIENT_{uid}",
        database=database,
        schema=schema,
        pipe_name=orders_pipe,
        sdk_properties=sdk_props,
        max_retries=max_retries,
        retry_delay_ms=retry_delay_ms,
    )

    items_mgr = SnowpipeStreamingManager(
        client_name=f"ITEMS_CLIENT_{uid}",
        database=database,
        schema=schema,
        pipe_name=items_pipe,
        sdk_properties=sdk_props,
        max_retries=max_retries,
        retry_delay_ms=retry_delay_ms,
    )

    try:
        orders_mgr.open_client()
        orders_mgr.open_channel(orders_channel)
        items_mgr.open_client()
        items_mgr.open_channel(items_channel)

        # Stream order rows in batches
        order_rows = [o.to_row() for o in orders]
        start = time.time()
        for i in range(0, len(order_rows), batch_size):
            batch = order_rows[i : i + batch_size]
            orders_mgr.send_rows(
                orders_channel,
                batch,
                start_offset=f"orders_{i}",
                end_offset=f"orders_{i + len(batch) - 1}",
            )
        logger.info("Streamed %d orders in %.2fs", len(order_rows), time.time() - start)

        # Stream order item rows in batches
        item_rows = [it.to_row() for it in items]
        start = time.time()
        for i in range(0, len(item_rows), batch_size):
            batch = item_rows[i : i + batch_size]
            items_mgr.send_rows(
                items_channel,
                batch,
                start_offset=f"items_{i}",
                end_offset=f"items_{i + len(batch) - 1}",
            )
        logger.info("Streamed %d order items in %.2fs", len(item_rows), time.time() - start)

    finally:
        orders_mgr.close()
        items_mgr.close()

    logger.info("Streaming complete. Data may take 1-3 minutes to be queryable.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    num_orders = int(sys.argv[1])
    config_file = sys.argv[2] if len(sys.argv) > 2 else "config.properties"
    profile_file = sys.argv[3] if len(sys.argv) > 3 else "profile.json"

    stream_orders(num_orders, config_file, profile_file)


if __name__ == "__main__":
    main()

"""Parallel Snowpipe Streaming orchestrator.

Distributes orders across multiple streaming instances using multiprocessing,
then runs reconciliation after a configurable wait.

Usage:
    python src/parallel_streaming_orchestrator.py <total_orders> <num_instances> [config_file] [profile_file]

Example:
    python src/parallel_streaming_orchestrator.py 10000 5
    python src/parallel_streaming_orchestrator.py 100000 10 config_staging.properties profile_staging.json
"""

import logging
import multiprocessing
import sys
import time
import uuid

from config_manager import build_config
from data_generator import generate_orders
from reconciliation_manager import ReconciliationManager
from snowpipe_streaming_manager import SnowpipeStreamingManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

RECONCILIATION_WAIT_SECONDS = 65


def stream_instance(
    instance_id: int,
    num_orders: int,
    order_id_offset: int,
    customer_id_start: int,
    customer_id_end: int,
    config_file: str,
    profile_file: str,
):
    """Worker function for one streaming instance."""
    config = build_config(config_file, profile_file)
    profile = config["profile"]
    sdk_props = config["sdk_properties"]
    database = profile["database"]
    schema = profile["schema"]
    batch_size = int(config.get("orders.batch.size", "10000"))
    max_retries = int(config.get("max.retries", "3"))
    retry_delay_ms = int(config.get("retry.delay.ms", "1000"))

    uid = uuid.uuid4().hex[:8]
    orders_pipe = config.get("pipe.orders.name", "ORDERS-STREAMING")
    items_pipe = config.get("pipe.order_items.name", "ORDER_ITEMS-STREAMING")
    orders_channel = f"orders_channel_instance_{instance_id}"
    items_channel = f"order_items_channel_instance_{instance_id}"

    logger.info(
        "Instance %d: generating %d orders (offset %d, customers %d-%d)",
        instance_id, num_orders, order_id_offset, customer_id_start, customer_id_end,
    )
    orders, items = generate_orders(
        num_orders,
        customer_id_start=customer_id_start,
        customer_id_end=customer_id_end,
        order_id_offset=order_id_offset,
    )

    orders_mgr = SnowpipeStreamingManager(
        client_name=f"ORDERS_CLIENT_{instance_id}_{uid}",
        database=database, schema=schema, pipe_name=orders_pipe,
        sdk_properties=sdk_props, max_retries=max_retries, retry_delay_ms=retry_delay_ms,
    )
    items_mgr = SnowpipeStreamingManager(
        client_name=f"ITEMS_CLIENT_{instance_id}_{uid}",
        database=database, schema=schema, pipe_name=items_pipe,
        sdk_properties=sdk_props, max_retries=max_retries, retry_delay_ms=retry_delay_ms,
    )

    try:
        orders_mgr.open_client()
        orders_mgr.open_channel(orders_channel)
        items_mgr.open_client()
        items_mgr.open_channel(items_channel)

        order_rows = [o.to_row() for o in orders]
        for i in range(0, len(order_rows), batch_size):
            batch = order_rows[i : i + batch_size]
            orders_mgr.send_rows(
                orders_channel, batch,
                start_offset=f"orders_{instance_id}_{i}",
                end_offset=f"orders_{instance_id}_{i + len(batch) - 1}",
            )

        item_rows = [it.to_row() for it in items]
        for i in range(0, len(item_rows), batch_size):
            batch = item_rows[i : i + batch_size]
            items_mgr.send_rows(
                items_channel, batch,
                start_offset=f"items_{instance_id}_{i}",
                end_offset=f"items_{instance_id}_{i + len(batch) - 1}",
            )

        logger.info("Instance %d: streamed %d orders, %d items", instance_id, len(order_rows), len(item_rows))
    finally:
        orders_mgr.close()
        items_mgr.close()


def run_parallel(total_orders: int, num_instances: int, config_file: str, profile_file: str):
    orders_per_instance = total_orders // num_instances
    remainder = total_orders % num_instances
    customer_range = 10000
    customers_per_instance = customer_range // num_instances

    tasks = []
    offset = 0
    for i in range(num_instances):
        n = orders_per_instance + (1 if i < remainder else 0)
        cust_start = i * customers_per_instance + 1
        cust_end = (i + 1) * customers_per_instance if i < num_instances - 1 else customer_range
        tasks.append((i, n, offset, cust_start, cust_end, config_file, profile_file))
        offset += n

    logger.info("Starting %d instances for %d total orders", num_instances, total_orders)
    start = time.time()

    with multiprocessing.Pool(num_instances) as pool:
        pool.starmap(stream_instance, tasks)

    elapsed = time.time() - start
    logger.info("All %d instances completed in %.2fs", num_instances, elapsed)

    # Wait before reconciliation to allow data to become visible
    logger.info("Waiting %ds before reconciliation...", RECONCILIATION_WAIT_SECONDS)
    time.sleep(RECONCILIATION_WAIT_SECONDS)

    # Run reconciliation
    config = build_config(config_file, profile_file)
    recon = ReconciliationManager(config["profile"])
    try:
        result = recon.run()
        logger.info("Reconciliation: %s", result)
        if result["status"] == "PASS":
            logger.info("SUCCESS: %d orders, %d items (ratio %.2f)", result["orders"], result["order_items"], result["ratio"])
        else:
            logger.warning("RECONCILIATION FAILED: %d orphaned items detected", result["orphaned_items"])
    finally:
        recon.close()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    total_orders = int(sys.argv[1])
    num_instances = int(sys.argv[2])
    config_file = sys.argv[3] if len(sys.argv) > 3 else "config.properties"
    profile_file = sys.argv[4] if len(sys.argv) > 4 else "profile.json"

    run_parallel(total_orders, num_instances, config_file, profile_file)


if __name__ == "__main__":
    main()

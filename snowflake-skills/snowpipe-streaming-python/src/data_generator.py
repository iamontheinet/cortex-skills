"""Synthetic e-commerce data generator."""

import random
import uuid
from datetime import datetime, timedelta
from typing import List, Tuple

from models import Customer, Order, OrderItem

CATEGORIES = {
    "Electronics": ["Laptop", "Smartphone", "Tablet", "Headphones", "Monitor", "Keyboard", "Mouse", "Webcam"],
    "Clothing": ["T-Shirt", "Jeans", "Jacket", "Sneakers", "Hat", "Scarf", "Hoodie", "Socks"],
    "Home": ["Lamp", "Pillow", "Blanket", "Mug", "Plate Set", "Cutting Board", "Towel Set", "Candle"],
    "Books": ["Novel", "Cookbook", "Textbook", "Biography", "Comic Book", "Journal", "Planner", "Art Book"],
}

STATUSES = ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED"]


def generate_orders(
    num_orders: int,
    customer_id_start: int = 1,
    customer_id_end: int = 10000,
    order_id_offset: int = 0,
) -> Tuple[List[Order], List[OrderItem]]:
    """Generate synthetic orders with 1-7 items each.

    Args:
        num_orders: Number of orders to generate.
        customer_id_start: Start of customer ID range (inclusive).
        customer_id_end: End of customer ID range (inclusive).
        order_id_offset: Offset added to order sequence numbers for unique IDs across instances.

    Returns:
        Tuple of (orders, all_order_items).
    """
    orders = []
    all_items = []
    base_date = datetime.now() - timedelta(days=30)

    for i in range(num_orders):
        order_id = f"ORD-{order_id_offset + i + 1:08d}-{uuid.uuid4().hex[:8]}"
        customer_id = f"CUST-{random.randint(customer_id_start, customer_id_end):05d}"
        order_date = base_date + timedelta(
            days=random.randint(0, 30),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
        status = random.choice(STATUSES)

        num_items = random.randint(1, 7)
        items = []
        for j in range(num_items):
            category = random.choice(list(CATEGORIES.keys()))
            product = random.choice(CATEGORIES[category])
            quantity = random.randint(1, 5)
            unit_price = round(random.uniform(5.0, 500.0), 2)
            total_price = round(quantity * unit_price, 2)

            item = OrderItem(
                order_item_id=f"ITEM-{order_id_offset + i + 1:08d}-{j + 1:03d}",
                order_id=order_id,
                product_name=product,
                category=category,
                quantity=quantity,
                unit_price=unit_price,
                total_price=total_price,
            )
            items.append(item)

        total_amount = round(sum(it.total_price for it in items), 2)
        order = Order(
            order_id=order_id,
            customer_id=customer_id,
            order_date=order_date,
            status=status,
            total_amount=total_amount,
            items=items,
        )
        orders.append(order)
        all_items.extend(items)

    return orders, all_items

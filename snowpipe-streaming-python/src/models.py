"""Data models for Snowpipe Streaming demo."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class Customer:
    customer_id: str


@dataclass
class OrderItem:
    order_item_id: str
    order_id: str
    product_name: str
    category: str
    quantity: int
    unit_price: float
    total_price: float

    def to_row(self) -> dict:
        return {
            "ORDER_ITEM_ID": self.order_item_id,
            "ORDER_ID": self.order_id,
            "PRODUCT_NAME": self.product_name,
            "CATEGORY": self.category,
            "QUANTITY": self.quantity,
            "UNIT_PRICE": self.unit_price,
            "TOTAL_PRICE": self.total_price,
        }


@dataclass
class Order:
    order_id: str
    customer_id: str
    order_date: datetime
    status: str
    total_amount: float
    items: List[OrderItem] = field(default_factory=list)

    def to_row(self) -> dict:
        return {
            "ORDER_ID": self.order_id,
            "CUSTOMER_ID": self.customer_id,
            "ORDER_DATE": self.order_date.isoformat(),
            "STATUS": self.status,
            "TOTAL_AMOUNT": self.total_amount,
        }

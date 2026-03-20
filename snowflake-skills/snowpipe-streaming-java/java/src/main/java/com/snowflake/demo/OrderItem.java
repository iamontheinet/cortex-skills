package com.snowflake.demo;

import java.util.HashMap;
import java.util.Map;

public class OrderItem {
    private final String orderItemId;
    private final String orderId;
    private final int productId;
    private final String productName;
    private final String productCategory;
    private final int quantity;
    private final double unitPrice;
    private final double lineTotal;

    public OrderItem(String orderItemId, String orderId, int productId, String productName,
                     String productCategory, int quantity, double unitPrice, double lineTotal) {
        this.orderItemId = orderItemId;
        this.orderId = orderId;
        this.productId = productId;
        this.productName = productName;
        this.productCategory = productCategory;
        this.quantity = quantity;
        this.unitPrice = unitPrice;
        this.lineTotal = lineTotal;
    }

    public String getOrderItemId() { return orderItemId; }

    public Map<String, Object> toMap() {
        Map<String, Object> row = new HashMap<>();
        row.put("ORDER_ITEM_ID", orderItemId);
        row.put("ORDER_ID", orderId);
        row.put("PRODUCT_ID", productId);
        row.put("PRODUCT_NAME", productName);
        row.put("PRODUCT_CATEGORY", productCategory);
        row.put("QUANTITY", quantity);
        row.put("UNIT_PRICE", unitPrice);
        row.put("LINE_TOTAL", lineTotal);
        return row;
    }
}

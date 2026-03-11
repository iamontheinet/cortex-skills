package com.snowflake.demo;

import java.sql.Timestamp;
import java.util.HashMap;
import java.util.Map;

public class Order {
    private final String orderId;
    private final long customerId;
    private final Timestamp orderDate;
    private final String orderStatus;
    private final double totalAmount;
    private final double discountPercent;
    private final double shippingCost;

    public Order(String orderId, long customerId, Timestamp orderDate, String orderStatus,
                 double totalAmount, double discountPercent, double shippingCost) {
        this.orderId = orderId;
        this.customerId = customerId;
        this.orderDate = orderDate;
        this.orderStatus = orderStatus;
        this.totalAmount = totalAmount;
        this.discountPercent = discountPercent;
        this.shippingCost = shippingCost;
    }

    public String getOrderId() { return orderId; }
    public long getCustomerId() { return customerId; }

    public Map<String, Object> toMap() {
        Map<String, Object> row = new HashMap<>();
        row.put("ORDER_ID", orderId);
        row.put("CUSTOMER_ID", customerId);
        row.put("ORDER_DATE", orderDate.toLocalDateTime().toString());
        row.put("ORDER_STATUS", orderStatus);
        row.put("TOTAL_AMOUNT", totalAmount);
        row.put("DISCOUNT_PERCENT", discountPercent);
        row.put("SHIPPING_COST", shippingCost);
        return row;
    }
}

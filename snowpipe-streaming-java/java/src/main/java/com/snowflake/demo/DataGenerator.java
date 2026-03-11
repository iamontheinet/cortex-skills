package com.snowflake.demo;

import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.UUID;

public class DataGenerator {
    private static final String[] STATUSES = {"PENDING", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"};
    private static final String[][] PRODUCTS = {
        {"Laptop", "Electronics"}, {"Phone", "Electronics"}, {"Tablet", "Electronics"},
        {"Headphones", "Electronics"}, {"Monitor", "Electronics"}, {"Keyboard", "Electronics"},
        {"Mouse", "Electronics"}, {"Webcam", "Electronics"}, {"T-Shirt", "Clothing"},
        {"Jeans", "Clothing"}, {"Jacket", "Clothing"}, {"Sneakers", "Clothing"},
        {"Coffee Maker", "Home"}, {"Blender", "Home"}, {"Toaster", "Home"},
        {"Desk Lamp", "Home"}, {"Novel", "Books"}, {"Textbook", "Books"},
        {"Cookbook", "Books"}, {"Notebook", "Office"}, {"Pen Set", "Office"},
        {"Backpack", "Accessories"}, {"Watch", "Accessories"}, {"Sunglasses", "Accessories"}
    };

    private final Random random;
    private final int minCustomerId;
    private final int maxCustomerId;

    public DataGenerator(int minCustomerId, int maxCustomerId) {
        this.random = new Random();
        this.minCustomerId = minCustomerId;
        this.maxCustomerId = maxCustomerId;
    }

    public DataGenerator() {
        this(1, 10000);
    }

    public Order generateOrder() {
        String orderId = UUID.randomUUID().toString();
        long customerId = random.nextInt(maxCustomerId - minCustomerId + 1) + minCustomerId;
        LocalDateTime orderDate = LocalDateTime.now().minusDays(random.nextInt(30));
        String status = STATUSES[random.nextInt(STATUSES.length)];
        double totalAmount = Math.round((random.nextDouble() * 990 + 10) * 100.0) / 100.0;
        double discountPercent = random.nextInt(4) == 0 ? random.nextInt(31) : 0;
        double shippingCost = totalAmount > 100 ? 0 : Math.round((random.nextDouble() * 15 + 5) * 100.0) / 100.0;

        return new Order(orderId, customerId, Timestamp.valueOf(orderDate), status,
                totalAmount, discountPercent, shippingCost);
    }

    public List<OrderItem> generateOrderItems(String orderId) {
        int numItems = random.nextInt(5) + 1;
        List<OrderItem> items = new ArrayList<>();
        for (int i = 0; i < numItems; i++) {
            String[] product = PRODUCTS[random.nextInt(PRODUCTS.length)];
            int quantity = random.nextInt(5) + 1;
            double unitPrice = Math.round((random.nextDouble() * 490 + 10) * 100.0) / 100.0;
            double lineTotal = Math.round(quantity * unitPrice * 100.0) / 100.0;
            items.add(new OrderItem(UUID.randomUUID().toString(), orderId, random.nextInt(1000) + 1,
                    product[0], product[1], quantity, unitPrice, lineTotal));
        }
        return items;
    }
}

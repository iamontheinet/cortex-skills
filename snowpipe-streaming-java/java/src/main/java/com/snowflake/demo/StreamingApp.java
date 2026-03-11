package com.snowflake.demo;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;

public class StreamingApp {
    private static final Logger logger = LoggerFactory.getLogger(StreamingApp.class);

    public static void main(String[] args) throws Exception {
        int numOrders = args.length > 0 ? Integer.parseInt(args[0]) : 1000;
        String configFile = args.length > 1 ? args[1] : "config.properties";
        String profileFile = args.length > 2 ? args[2] : "profile.json";

        logger.info("Starting Snowpipe Streaming: {} orders, config={}, profile={}", numOrders, configFile, profileFile);

        ConfigManager config = new ConfigManager(configFile, profileFile);

        try (SnowpipeStreamingManager manager = new SnowpipeStreamingManager(config, "")) {
            DataGenerator generator = new DataGenerator();

            long startTime = System.currentTimeMillis();
            int orderCount = 0;
            int itemCount = 0;

            for (int i = 0; i < numOrders; i++) {
                Order order = generator.generateOrder();
                manager.insertOrder(order);
                orderCount++;

                List<OrderItem> items = generator.generateOrderItems(order.getOrderId());
                manager.insertOrderItems(items);
                itemCount += items.size();

                if ((i + 1) % 100 == 0) {
                    double elapsed = (System.currentTimeMillis() - startTime) / 1000.0;
                    double rate = orderCount / elapsed;
                    logger.info("Progress: {}/{} orders ({} items) | {} orders/sec",
                            orderCount, numOrders, itemCount, String.format("%.0f", rate));
                }
            }

            double totalTime = (System.currentTimeMillis() - startTime) / 1000.0;
            logger.info("Streaming complete: {} orders, {} items in {}s ({} orders/sec)",
                    orderCount, itemCount, String.format("%.1f", totalTime), String.format("%.0f", orderCount / totalTime));

            logger.info("Waiting 65 seconds for data flush...");
            Thread.sleep(65000);

            logger.info("Latest committed offsets - Orders: {}, Items: {}",
                    manager.getOrdersLatestOffset(), manager.getOrderItemsLatestOffset());
        }
    }
}

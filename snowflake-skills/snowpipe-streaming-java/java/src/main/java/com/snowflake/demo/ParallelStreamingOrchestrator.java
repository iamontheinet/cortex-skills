package com.snowflake.demo;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;

public class ParallelStreamingOrchestrator {
    private static final Logger logger = LoggerFactory.getLogger(ParallelStreamingOrchestrator.class);

    public static void main(String[] args) throws Exception {
        int totalOrders = args.length > 0 ? Integer.parseInt(args[0]) : 10000;
        int numInstances = args.length > 1 ? Integer.parseInt(args[1]) : 5;
        String configFile = args.length > 2 ? args[2] : "config.properties";
        String profileFile = args.length > 3 ? args[3] : "profile.json";

        int ordersPerInstance = totalOrders / numInstances;
        int customerRange = 10000 / numInstances;

        logger.info("Parallel streaming: {} total orders, {} instances, {} orders/instance",
                totalOrders, numInstances, ordersPerInstance);

        ConfigManager config = new ConfigManager(configFile, profileFile);
        ExecutorService executor = Executors.newFixedThreadPool(numInstances);
        List<Future<int[]>> futures = new ArrayList<>();

        long startTime = System.currentTimeMillis();

        for (int i = 0; i < numInstances; i++) {
            final int instanceId = i;
            final int minCustId = i * customerRange + 1;
            final int maxCustId = (i + 1) * customerRange;
            final int orderCount = (i == numInstances - 1) ? totalOrders - (ordersPerInstance * i) : ordersPerInstance;

            futures.add(executor.submit(() -> runInstance(config, instanceId, orderCount, minCustId, maxCustId)));
        }

        int totalOrdersInserted = 0;
        int totalItemsInserted = 0;
        for (Future<int[]> future : futures) {
            int[] counts = future.get();
            totalOrdersInserted += counts[0];
            totalItemsInserted += counts[1];
        }

        double totalTime = (System.currentTimeMillis() - startTime) / 1000.0;
        logger.info("All instances complete: {} orders, {} items in {}s ({} orders/sec)",
                totalOrdersInserted, totalItemsInserted, String.format("%.1f", totalTime), String.format("%.0f", totalOrdersInserted / totalTime));

        logger.info("Waiting 65 seconds for final flush...");
        Thread.sleep(65000);

        executor.shutdown();
        logger.info("Done.");
    }

    private static int[] runInstance(ConfigManager config, int instanceId, int numOrders,
                                     int minCustId, int maxCustId) {
        String suffix = "_instance_" + instanceId;
        int orderCount = 0;
        int itemCount = 0;

        try (SnowpipeStreamingManager manager = new SnowpipeStreamingManager(config, suffix)) {
            DataGenerator generator = new DataGenerator(minCustId, maxCustId);
            long startTime = System.currentTimeMillis();

            for (int i = 0; i < numOrders; i++) {
                Order order = generator.generateOrder();
                manager.insertOrder(order);
                orderCount++;

                List<OrderItem> items = generator.generateOrderItems(order.getOrderId());
                manager.insertOrderItems(items);
                itemCount += items.size();

                if ((i + 1) % 500 == 0) {
                    double elapsed = (System.currentTimeMillis() - startTime) / 1000.0;
                    logger.info("[Instance {}] Progress: {}/{} orders ({} items) | {}/sec",
                            instanceId, orderCount, numOrders, itemCount, String.format("%.0f", orderCount / elapsed));
                }
            }

            logger.info("[Instance {}] Complete: {} orders, {} items", instanceId, orderCount, itemCount);
        } catch (Exception e) {
            logger.error("[Instance {}] Error: {}", instanceId, e.getMessage(), e);
        }

        return new int[]{orderCount, itemCount};
    }
}

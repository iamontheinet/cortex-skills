package com.snowflake.demo;

import com.snowflake.ingest.streaming.SnowflakeStreamingIngestChannel;
import com.snowflake.ingest.streaming.SnowflakeStreamingIngestClient;
import com.snowflake.ingest.streaming.SnowflakeStreamingIngestClientFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Properties;

public class SnowpipeStreamingManager implements AutoCloseable {
    private static final Logger logger = LoggerFactory.getLogger(SnowpipeStreamingManager.class);

    private final SnowflakeStreamingIngestClient ordersClient;
    private final SnowflakeStreamingIngestClient orderItemsClient;
    private final SnowflakeStreamingIngestChannel ordersChannel;
    private final SnowflakeStreamingIngestChannel orderItemsChannel;

    public SnowpipeStreamingManager(ConfigManager config, String channelSuffix) throws Exception {
        String database = config.getDatabase();
        String schema = config.getSchema();

        Properties props = config.toStreamingProperties();

        String ordersChannelName = config.getConfigProperty("channel.orders.name") + channelSuffix;
        String orderItemsChannelName = config.getConfigProperty("channel.order_items.name") + channelSuffix;

        String ordersPipe = config.getConfigProperty("pipe.orders.name");
        String orderItemsPipe = config.getConfigProperty("pipe.order_items.name");

        this.ordersClient = SnowflakeStreamingIngestClientFactory.builder(
                "orders_client" + channelSuffix,
                database,
                schema,
                ordersPipe)
                .setProperties(props)
                .build();

        this.orderItemsClient = SnowflakeStreamingIngestClientFactory.builder(
                "items_client" + channelSuffix,
                database,
                schema,
                orderItemsPipe)
                .setProperties(props)
                .build();

        this.ordersChannel = ordersClient.openChannel(ordersChannelName, "0").getChannel();
        this.orderItemsChannel = orderItemsClient.openChannel(orderItemsChannelName, "0").getChannel();

        logger.info("Streaming manager initialized with channels: {}, {}", ordersChannelName, orderItemsChannelName);
    }

    public void insertOrder(Order order) {
        try {
            ordersChannel.appendRow(order.toMap(), "order_" + order.getOrderId());
        } catch (Exception e) {
            logger.error("Error inserting order {}: {}", order.getOrderId(), e.getMessage());
        }
    }

    public void insertOrderItems(List<OrderItem> items) {
        for (OrderItem item : items) {
            try {
                orderItemsChannel.appendRow(item.toMap(), "item_" + item.getOrderItemId());
            } catch (Exception e) {
                logger.error("Error inserting order item {}: {}", item.getOrderItemId(), e.getMessage());
            }
        }
    }

    public String getOrdersLatestOffset() {
        return ordersChannel.getChannelStatus().getLatestOffsetToken();
    }

    public String getOrderItemsLatestOffset() {
        return orderItemsChannel.getChannelStatus().getLatestOffsetToken();
    }

    @Override
    public void close() throws Exception {
        logger.info("Closing streaming channels and clients...");
        if (ordersChannel != null) ordersChannel.close();
        if (orderItemsChannel != null) orderItemsChannel.close();
        if (ordersClient != null) ordersClient.close();
        if (orderItemsClient != null) orderItemsClient.close();
        logger.info("Streaming manager closed.");
    }
}

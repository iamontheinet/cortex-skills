"""Snowpipe Streaming SDK client and channel manager.

Wraps the snowpipe-streaming SDK to provide:
- Client lifecycle (open / close)
- Channel management (open / close)
- Batched row ingestion with retry logic
"""

import logging
import time

from snowflake.ingest.streaming.streaming_ingest_client import StreamingIngestClient

logger = logging.getLogger(__name__)


class SnowpipeStreamingManager:
    """Manages one StreamingIngestClient and its channels for a single target table."""

    def __init__(
        self,
        client_name: str,
        database: str,
        schema: str,
        pipe_name: str,
        sdk_properties: dict,
        max_retries: int = 3,
        retry_delay_ms: int = 1000,
    ):
        self.client_name = client_name
        self.database = database
        self.schema = schema
        self.pipe_name = pipe_name
        self.sdk_properties = sdk_properties
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.client = None
        self.channels = {}

    def open_client(self):
        """Create and return the StreamingIngestClient."""
        logger.info("Opening client %s for pipe %s", self.client_name, self.pipe_name)
        self.client = StreamingIngestClient(
            client_name=self.client_name,
            db_name=self.database,
            schema_name=self.schema,
            pipe_name=self.pipe_name,
            properties=self.sdk_properties,
        )
        return self.client

    def open_channel(self, channel_name: str):
        """Open a channel on the current client."""
        if self.client is None:
            self.open_client()
        channel, status = self.client.open_channel(channel_name=channel_name)
        logger.info("Opened channel %s (status: %s)", channel_name, status)
        self.channels[channel_name] = channel
        return channel

    def send_rows(self, channel_name: str, rows: list, start_offset: str, end_offset: str):
        """Send rows through a channel with retry logic.

        Args:
            channel_name: Name of the previously opened channel.
            rows: List of dicts, each representing one row.
            start_offset: String offset token for the start of this batch.
            end_offset: String offset token for the end of this batch.
        """
        channel = self.channels[channel_name]
        for attempt in range(1, self.max_retries + 1):
            try:
                channel.append_rows(
                    rows=rows,
                    start_offset_token=start_offset,
                    end_offset_token=end_offset,
                )
                logger.info(
                    "Sent %d rows on channel %s [%s..%s]",
                    len(rows), channel_name, start_offset, end_offset,
                )
                return
            except Exception as e:
                if attempt == self.max_retries:
                    raise
                delay = (self.retry_delay_ms / 1000) * (2 ** (attempt - 1))
                logger.warning(
                    "Retry %d/%d for channel %s: %s (waiting %.1fs)",
                    attempt, self.max_retries, channel_name, e, delay,
                )
                time.sleep(delay)

    def close(self):
        """Close all channels and the client."""
        for name, channel in self.channels.items():
            try:
                channel.close(wait_for_flush=True)
                logger.info("Closed channel %s", name)
            except Exception as e:
                logger.warning("Error closing channel %s: %s", name, e)
        self.channels.clear()

        if self.client:
            try:
                self.client.close()
                logger.info("Closed client %s", self.client_name)
            except Exception as e:
                logger.warning("Error closing client %s: %s", self.client_name, e)
            self.client = None

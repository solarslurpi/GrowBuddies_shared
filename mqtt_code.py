"""The focus is on publishing mqtt messages to the Tasmotized power switches.  Receiving readings comes over telegraf.

"""
# from dotenv import load_dotenv
# load_dotenv()


import logging
import random
import string
import paho.mqtt.client as mqtt


from logger_code import LoggerBase

logger = LoggerBase.setup_logger("mqtt_code", logging.DEBUG)
#

# MQTT Error values from https://github.dev/eclipse/paho.mqtt.python/tree/master/src/paho/mqtt/client.py
rc_codes = {
    "MQTT_ERR_AGAIN": -1,
    "MQTT_ERR_SUCCESS": 0,
    "MQTT_ERR_NOMEM": 1,
    "MQTT_ERR_PROTOCOL": 2,
    "MQTT_ERR_INVAL": 3,
    "MQTT_ERR_NO_CONN": 4,
    "MQTT_ERR_CONN_REFUSED": 5,
    "MQTT_ERR_NOT_FOUND": 6,
    "MQTT_ERR_CONN_LOST": 7,
    "MQTT_ERR_TLS": 8,
    "MQTT_ERR_PAYLOAD_SIZE": 9,
    "MQTT_ERR_NOT_SUPPORTED": 10,
    "MQTT_ERR_AUTH": 11,
    "MQTT_ERR_ACL_DENIED": 12,
    "MQTT_ERR_UNKNOWN": 13,
    "MQTT_ERR_ERRNO": 14,
    "MQTT_ERR_QUEUE_SIZE": 15,
    "MQTT_ERR_KEEPALIVE": 16,
}


class MQTTClient:

    def __init__(self, host):
        # The client ID is a unique identifier that is used by the broker to identify this
        # client. If a client ID is not provided, a unique ID is generated and used instead.
        self.host = host
        self.client_id = "".join(
            random.choice(string.ascii_lowercase) for i in range(10)
        )
        # No Exceptions
        self.client = mqtt.Client(client_id=self.client_id, clean_session=False,callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

        # This will be sent to subscribers who asked to receive the LWT for this mqtt client.
        self.client.will_set("/lwt", "offline", qos=1, retain=False)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc) -> int:
        """Callback function that is called when the client connects to the MQTT broker."""
        logger.debug(
            f"Connected to broker {self.host}. ClientID: {self.client_id}. Result code: {rc}"
        )
        if rc != 0:
            logger.error(f"Unexpected error in on_connect: {rc_codes.get(rc, 'Unknown error code')}")
        return rc

    def on_disconnect(self, client, userdata, rc, properties) -> int:
        """Callback function that is called when the client disconnects from the MQTT broker."""
        if rc != 0:
            logger.error(f"Received an unexpected disconnect. Error: {rc_codes.get(rc, 'Unknown error code')}")
        return rc

    def on_message(self, client, userdata, msg) -> None:
        """Callback function that is called when a message is received from the MQTT broker."""
        message = msg.payload.decode('utf-8')
        logger.debug(f"Received MQTT message: {message}")

    def publish(self, topic, message, qos=1):
        """Publish a message to a specified MQTT topic."""
        logger.debug(f"Publishing message '{message}' to topic '{topic}' with QoS {qos}.")
        return self.client.publish(topic, message, qos)

    def disconnect(self):
        self.client.disconnect()

    def start(self):
        try:
            self.client.connect(self.host)
            self.client.loop_start()
        except OSError as e:
            logger.error(f"Connection error: {e}")
            raise  # Reraises the original OSError
        except Exception as e:  # A more generic catch-all for unexpected errors
            logger.error(f"Unexpected error: {e}")
            raise  # Preserves the original exception

    def stop(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Failed to stop the MQTT client: {e}")
            raise

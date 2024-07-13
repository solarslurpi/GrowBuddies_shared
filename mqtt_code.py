import logging
import random
import string
import paho.mqtt.client as paho_mqtt
from logger_code import LoggerBase

# Setup logger
logger = LoggerBase.setup_logger("mqtt_code", logging.DEBUG)


class MQTTClient:
    # paho-mqtt client 2.x was introduced requiring changes.
    # e.g.: ReasonCode was added to on_connect, on_disconnect, and on_subscribe callbacks.  See https://github.com/eclipse/paho.mqtt.python/blob/master/src/paho/mqtt/reasoncodes.py

    def __init__(self, host: str, protocol=paho_mqtt.MQTTv31):
        self.host = host
        self.client_id = ''.join(random.choice(string.ascii_lowercase) for _ in range(10))
        self.protocol = protocol

        if self.protocol == paho_mqtt.MQTTv5:
            self.client = paho_mqtt.Client(callback_api_version=paho_mqtt.CallbackAPIVersion.VERSION2,   client_id=self.client_id, protocol=self.protocol)
            # Set clean_start to ensure session management for MQTTv5
            self.client._clean_start = paho_mqtt.MQTT_CLEAN_START_FIRST_ONLY
        else:
            self.client = paho_mqtt.Client(callback_api_version=paho_mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id, clean_session=False, protocol=self.protocol)
        self.client.will_set("/lwt", "offline", qos=1, retain=False)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message


    def on_connect(self, client, userdata, flags, reason_code, properties):
        '''callback for when the client receives a CONNACK response from the MQTT server.'''
        if reason_code == 0:
            logging.info("Succesfully connected to MQTT broker.")
        else:
            logging.error(f"Error connecting to MQTT broker: {reason_code}")

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        logger.debug(f"Lost connection with reason code: {reason_code} ")

    def on_message(self, client, userdata, msg):
        message = msg.payload.decode('utf-8')
        logger.debug(f"Received mqtt message: {message}")

    def publish(self, topic: str, message: str, qos: int = 1):
        logger.debug(f"Publishing message '{message}' to topic '{topic}' with QoS {qos}.")
        return self.client.publish(topic, message, qos)


    def start(self) -> None:
        '''Starts the MQTT client.  If the client is not connected, it will attempt to connect to the broker.  If the connection fails, an exception is raised.  Once connected, loop_start() is called to manage connection tasks like sending and receiving messages.'''
        if not self.client.is_connected():
            try:
                self.client.connect(self.host)
            except OSError as e:
                logger.error(f"Connection error: {e}")
                raise
            except Exception as e:
                logger.error('Reconnect to mqtt broker failed. ')
                raise
        # The loop_start function creates a new thread (thus not blocking the main thread).  It automatically calls repeatedly calls the loop function in the background.  The loop() function reads incoming messages and processes them as well as handle broker connections.
        self.client.loop_start()



    def stop(self) -> None:
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Failed to stop the MQTT client: {e}")
            raise

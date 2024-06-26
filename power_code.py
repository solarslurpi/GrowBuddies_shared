import asyncio
import logging
# from dotenv import load_dotenv
# load_dotenv()

from mqtt_code import MQTTClient
from logger_code import LoggerBase
from settings_model import Settings

logger = LoggerBase.setup_logger("MistBuddyPower", logging.DEBUG)



class PowerBuddy:
    def __init__(self, tent_name, settings: Settings):
        self.settings = settings
        try:
            host_ip = self.settings.global_settings.host_ip
            self.power_topics = settings.pid_configs[tent_name].MistBuddy.mqtt_power_topics
        except AttributeError as e:
            logger.error(f"Error attempting to get the host_ip and power_topics from settings.  Error: {e}")
            raise e
        try:
            self.mqtt_client = MQTTClient(host_ip)

        except Exception as e:
            logger.error(f"Error creating the MQTT client.  Error: {e}")
            raise e

    async def power_on(self, seconds_on: float) -> None:
        for power_command in self.power_topics:
            try:
                # TURN POWER ON.  The code is turning on a Tasmotized switch.  The code sends a Pulsetime.  This is the amount of time the switch should stay on until turning off.

                # PulseTime<x> where x = 1..111 =  x  0.1 second increments. Thus the range is .1 to 11.1 seconds.
                # PulseTime<x> where x = 112..64900 = - 100.  Thus the range is 12 to 6,4800 seconds.
                # First Publish the Power on command
                self.mqtt_client.publish(power_command, 1, qos=1)
                # Split the topic by the '/'
                parts = power_command.split("/")
                # Replace the last part with 'PulseTime'
                parts[-1] = "PulseTime"
                # Join the parts back together to form the new topic
                pulsetime_command = "/".join(parts)
                # PulseTime command uses an algorithm defined at https://tasmota.github.io/docs/Commands/#control:
                # PulseTime<x> where x = 112..64900 = - 100.  Thus the range is 12 to 6,4800 seconds.
                if seconds_on >= 12:
                    pulsetime_on = seconds_on + 100
                # I must be missing something. .1 increments stop at 11.1 seconds. Add 100 starts at 12 seconds.  What happens between 11.1. and 12 seconds?
                elif seconds_on < 12:
                    # PulseTime<x> where x = 1..111 =  x  0.1 second increments. Thus the range is .1 to 11.1 seconds.
                    pulsetime_on = seconds_on * 10 # e.g.: if pulsetime_on = 30 .1 second increments = 3 seconds.
                # We will use numbers between 112 and 64900 for the PulseTime (e.g.: 112 - 100 = 12 seconds)
                logger.debug(
                    f"=+= POWER ON -> {seconds_on} seconds. Pulsetime value: {pulsetime_on}.=+="
                )
                # LET TASMOTA KNOW HOW LONG TO KEEP THE POWER ON.
                self.mqtt_client.publish(pulsetime_command, pulsetime_on, qos=1)
            except Exception as e:
                error_message = (
                    f"Failed to publish MQTT message for command '{power_command}' "
                    f"or '{pulsetime_command}'. Duration: {seconds_on} seconds. Error: {e}"
                )
                logger.error(error_message)
                raise RuntimeError(error_message)

    def start(self):
        logger.debug("mistbuddy_power_code.start: Starting the MQTT client.")
        self.mqtt_client.start()

    def stop(self):
        self.mqtt_client.stop()
        logger.debug("mistbuddy_power_code.stop: Stopped the MQTT client.")


    async def async_timer(self,interval, stop_event, seconds_on):
        while not stop_event.is_set():
            await self.power_on(seconds_on)
            await asyncio.sleep(interval)

    @property
    def duration(self):
        return self.seconds_on

    @duration.setter
    def duration(self, value):
        # Verify the number is less than 60 seconds.
        if value > 60:
            raise ValueError("PowerBuddy:duration.setter: The duration must be less than 60 seconds.")
        self.seconds_on = value

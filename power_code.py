import asyncio
import logging
from pydantic import ValidationError, BaseModel, field_validator

from mqtt_code import MQTTClient
from logger_code import LoggerBase
from mistbuddy_lite_state_code import ServicesAddress, PowerMessages

logger = LoggerBase.setup_logger("MistBuddyPower", logging.DEBUG)

class PowerOnSeconds(BaseModel):
    seconds_on: float

    @field_validator('seconds_on')
    def seconds_on_must_be_valid(cls, v):
        if not isinstance(v, (float, int)):
            raise TypeError('seconds_on must be a float')
        if not (0.1 <= v <= 11.1 or 12 <= v <= 64800):
            raise ValueError('seconds_on must be between 0.1 and 11.1 seconds or between 12 and 64800 seconds')
        return v



    @classmethod
    def build_pulsetime_command(cls, power_command):
        # The power_command must be in the format 'cmnd/<device_name>/POWER'
        # If it doesn't pass the validation, an error is raised.
        power_command = PowerMessages.match_power_message_or_raise_error(power_command)
        # Split the topic by the '/'
        parts = power_command.split("/")
        # Replace the last part with 'PulseTime'
        parts[-1] = "PulseTime"
        # Join the parts back together to form the new topic
        return "/".join(parts)

class PowerBuddy:
    '''
    Operates the power switch (on/off) for Tasmotized devices associated with the MistBuddy name.
    '''
    def __init__(self, address, power_messages: list[str]):
        '''mqtt messaging is used to send messages to the Tasmotized power switches. The MQTTClient class handles sending the messages.  In order to do that, the IP address (or hostname) of the mqtt broker is needed as well as the mqtt topics. These are located within the instances of the Settings model class.'''
        try:
            # Manually validate
            validated_services_address = ServicesAddress(address=address)
            self.power_messages = PowerMessages(power_messages=power_messages)
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            raise
        # Happens when one of the attributes passed in is None.
        except AttributeError as e:
            logger.error(f"Attribute error: {e}")
            raise
        try:
            self.mqtt_client = MQTTClient(validated_services_address.address)
        except Exception as e:
            logger.error(f"Error creating the MQTT client.  Error: {e}")
            raise

    def power_on(self, power_on_seconds: int | float) -> None:
        try:
            seconds_on = PowerOnSeconds(seconds_on=power_on_seconds).seconds_on
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            raise e
        pulsetime_command = None # Initialize before the loop.
        for power_command in self.power_messages.power_messages:
            try:
                # First Publish the Power on command to the Tasmotized switch.
                self.mqtt_client.publish(power_command, 1, qos=1) # Generates exceptions
                # Next send the pulsetime
                pulsetime_command = PowerOnSeconds.build_pulsetime_command(power_command) # Does not generate exceptions
                # PulseTime uses an algorithm defined at https://tasmota.github.io/docs/Commands/#control:
                pulse_time = self._pulsetime_value(power_on_seconds=seconds_on) # Does not generate exceptions


                # LET TASMOTA KNOW HOW LONG TO KEEP THE POWER ON.
                self.mqtt_client.publish(pulsetime_command, pulse_time, qos=1)
                logger.debug(
                    f"=+= POWER ON -> {seconds_on} seconds. Pulsetime value: {pulse_time}.=+="
                )
            except (ValueError, TypeError) as e:
                    error_message = (
                        f"Invalid MQTT message format for command '{power_command}'  Error: {e}"
                    )
                    logger.error(error_message)
                    raise ValueError(error_message) from e
            except (RuntimeError, OSError) as e:
                error_message = (
                    f"MQTT communication error for command '{power_command}'  Duration: {seconds_on} seconds. Error: {e}"
                )
                logger.error(error_message)
                raise RuntimeError(error_message) from e

    def _pulsetime_value(self, power_on_seconds: float):
        # Follow Tasmota's walgorithm for setting the pulsetime value.
        if power_on_seconds >= 12:
            return power_on_seconds + 100
        elif power_on_seconds < 12:
            return power_on_seconds * 10 # The same as / 0.1

    def start(self):
        try:
            self.mqtt_client.start()
            logger.debug("mqtt client started successfully")
        except Exception as e:
            logger.error(f"Error: {e} Failed to start the MQTT client.")
            raise  # Optionally re-raise the exception if it should be handled further up

    def stop(self):
        try:
            self.mqtt_client.stop()
            logger.debug("mqtt client stopped successfully.")
        except Exception as e:
            logger.error(f"Error: {e} Failed to stop the MQTT client.")
            raise


    async def async_timer(self,interval, stop_event, seconds_on):
        while not stop_event.is_set():
            self.power_on(seconds_on)
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

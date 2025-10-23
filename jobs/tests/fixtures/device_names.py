"""Fixtures needed for the device_component_update tests."""

from nautobot.dcim.models import Device

from .util import (
    add_device,
    add_device_type,
    add_location,
    add_location_type,
    add_role,
)


def add_fixtures():
    """Add fixtures for device_component_update tests."""
    role = add_role("SW", Device)
    location_type = add_location_type("Site", [Device])
    location1 = add_location("S1", location_type)
    location2 = add_location("S2", location_type)

    device_type1 = add_device_type("Manufacturer", "Model 1")
    device_type2 = add_device_type("Manufacturer", "Model 2")

    add_device("device 1", device_type1, location1, role)
    add_device("device 2", device_type2, location1, role)
    add_device("device 3", device_type1, location2, role)
    add_device("device 4", device_type2, location2, role)
    add_device("device abc", device_type2, location2, role)

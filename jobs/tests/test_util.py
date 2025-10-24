"""Unit tests for the utility methods."""

from django.test import TestCase
from nautobot.dcim.models import Device

from ..util import filter_objects
from .fixtures import add_device, add_device_type, add_location, add_location_type, add_role


class TestFilterObjects(TestCase):
    """Unit tests for the filter_objects utility method."""

    def setUp(self):
        """Create some test objects in the database."""
        role = add_role("Device", Device)
        location_type = add_location_type("Site", [Device])
        self.location1 = add_location("Site 1", location_type)
        self.location2 = add_location("Site 2", location_type)
        device_type1 = add_device_type("Manufacturer", "Model 1")

        self.device1 = add_device("device 1", device_type1, self.location1, role)

    def test_none_for_objects(self):
        """Test that an exception is raised if the objects argument is None."""
        self.assertRaises(ValueError, filter_objects, None)

    def test_for_location(self):
        """Test that the result only includes devices from a given location."""
        want = [self.device1]
        got = filter_objects(Device.objects.all(), location=self.location1)
        self.assertQuerySetEqual(got, want)

    def test_for_model_instance(self):
        """Test that providing a model instance instead of a queryset returns that model instance."""
        want = [self.device1]
        got = filter_objects(self.device1)
        self.assertQuerySetEqual(got, want)

    def test_for_model_instance_with_matching_constraint(self):
        """Test that providing a model instance with a location constraint returns that model instance."""
        want = [self.device1]
        got = filter_objects(self.device1, location=self.location1)
        self.assertQuerySetEqual(got, want)

    def test_for_model_instance_without_constraints(self):
        """Test that providing a model instance with a different location constraint returns nothing."""
        want = []
        got = filter_objects(self.device1, location=self.location2)
        self.assertQuerySetEqual(got, want)

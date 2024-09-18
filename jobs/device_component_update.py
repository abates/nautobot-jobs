"""Jobs for updating device components from device type templates."""

from dataclasses import dataclass
from operator import attrgetter
from typing import Iterable, Tuple

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Model
from nautobot.apps.jobs import Job, MultiObjectVar, ObjectVar, register_jobs
from nautobot.apps.models import BaseModel
from nautobot.dcim.models import Device, DeviceType
from nautobot.extras.models import Status

from jobs.base import BaseJob, BaseJobButton


@dataclass
class FieldUpdate:
    """FieldUpdate specifies how to find and update a template's fields.

    Attributes:
        name (str): The field name, e.g. `type` for an interface template.

        default_value (Any): The value to assign if the receiver's field is None. If not set (None)
            then the value must be supplied by the `template_obj` argument to `update`.

        key_field (str): If the field is a relationship, then `key_field` is used for perform the
            query to find the object to assign to the field. For instance, when assigning a `Status`
            object, the `name` field may be used to find the correct status.

        query_from (str, Manager): The query manager to look for the `key_field`. This can be an
            actual manager (such as Status.objects) or it can be a string path. If a string is
            supplied, then the manager is looked up from the destination object. For instance, when
            updating front ports, there can be an associated rear port. The rear port must be looked
            up from the parent device. Therefore the `query_from` could be `device.rear_ports`. The
            query manager is resolved by first looking for the `device` relationship on the front
            port, and then looking for the `rear_ports` manager field on the device. That manager
            is then used to look for a rear port matching the key field.
    """

    name: str
    template_name: str = None
    default_value: str = None
    key_field: str = None
    query_from: str = None

    def get_values(self, dst_obj: Model, template_obj: Model) -> Tuple[Model, Model]:
        """Get the old and new values for the destination object and template.

        Args:
            dst_obj (Model): The object that is being updated.
            template_obj (Model): The template to update from.

        Returns:
            Tuple[Model, Model]: The value of the field for the existing object (dst_obj) and
                the value of the field for the template.
        """
        if self.key_field is None:
            # Field can be set directly
            old_value = getattr(dst_obj, self.name)
            if self.default_value is None:
                return old_value, getattr(template_obj, self.name)
            return old_value, self.default_value

        # Field is a related field and a lookup
        # must be done first
        if isinstance(self.query_from, str):
            query_manager = attrgetter(self.query_from)(dst_obj)
        else:
            query_manager = self.query_from

        try:
            old_key = getattr(getattr(dst_obj, self.name), self.key_field)
            old_value = query_manager.get(**{self.key_field: old_key})
        except ObjectDoesNotExist:
            old_value = None
        new_value = None
        if self.default_value is None:
            new_key = getattr(getattr(template_obj, self.template_name or self.name), self.key_field)
            new_value = query_manager.get(**{self.key_field: new_key})
        elif dst_obj._state.adding:
            new_value = query_manager.get(**{self.key_field: self.default_value})
            old_value = None
        else:
            new_value = old_value

        return old_value, new_value

    def update(self, job: Job, dst_obj: Model, template_obj: Model = None):
        """Update the field on the destination object.

        Args:
            job (Job): The job this update is being executed from. This is used for logging.
            dst_obj (Model): The object receiving the updates.
            template_obj (Model, optional): The template to align the destination object with. Defaults to None.

        Raises:
            ValueError: If no template_obj is set and the FieldUpdate has no default value.
        """
        if self.default_value is None and template_obj is None:
            raise ValueError("Template object must be set when no default value is provided")

        old_value, new_value = self.get_values(dst_obj, template_obj)
        if old_value != new_value:
            setattr(dst_obj, self.name, new_value)
            if not dst_obj._state.adding:
                job.logger.info("Updated %s from %s to %s", self.name, old_value, new_value, extra={"object": dst_obj})


@dataclass
class TemplateUpdate:
    """TemplateUpdate represents a set of instructions on how to update a device.

    The TemplateUpdate includes the template attribute name (such as `interface_templates`) as
    the source as well as the destination attribute name (such as `interfaces`). The source
    and destination can either be simple field names or can be defined as `FieldLookup`
    objects, which can specify additional information for the lookup.

    The template update includes the `update` method which performs the actual update on the
    device to match its components with the device type templates.
    """

    src: str
    dst: str
    key_field: str
    fields: list[FieldUpdate]

    def __post_init__(self):
        """Create field lookups where the field is a simple string name."""
        for i, field in enumerate(self.fields):
            if isinstance(field, str):
                self.fields[i] = FieldUpdate(name=field)

    def update(self, job: Job, device_type: DeviceType, device: Device):
        """Perform the update of the field.

        This method will lookup the source templates, specified by the src attribute,
        and will iterate all the instances of that field. For each instance of the source,
        the destination device will be searched for a pre-existing component using the
        key field. If a pre-existing component is found, then its fields are updated
        to match the source. If no component is found, then a new one is created.

        Args:
            job (Job): The job this update is being run from. The job is used for
                logging.

            device_type (DeviceType): The device type to use when matching up device components
                with templates.

            device (Device): The device to be aligned with the device type.
        """
        src = getattr(device_type, self.src)
        dst = getattr(device, self.dst)
        for template_obj in src.all():
            key = getattr(template_obj, self.key_field)
            try:
                dst_obj: BaseModel = dst.get(**{self.key_field: key})
            except ObjectDoesNotExist:
                field = device._meta.get_field(self.dst)
                dst_obj = dst.model()
                setattr(dst_obj, field.remote_field.name, device)
                job.logger.info("Created %s", dst_obj.__class__.__name__, extra={"object": device})

            for field in self.fields:
                field.update(job, dst_obj, template_obj)

            try:
                dst_obj.validated_save()
            except ValidationError as ex:
                job.logger.info("Validation failed: %s", ex, extra={"object": dst_obj})


TEMPLATE_UPDATES = [
    TemplateUpdate(
        src="interface_templates",
        dst="interfaces",
        key_field="name",
        fields=[
            "name",
            "label",
            "type",
            "mgmt_only",
            FieldUpdate(name="status", key_field="name", default_value="Active", query_from=Status.objects),
        ],
    ),
    TemplateUpdate(
        src="rear_port_templates",
        dst="rear_ports",
        key_field="name",
        fields=["name", "label", "type"],
    ),
    TemplateUpdate(
        src="front_port_templates",
        dst="front_ports",
        key_field="name",
        fields=[
            "name",
            "label",
            "type",
            FieldUpdate(
                name="rear_port", template_name="rear_port_template", key_field="name", query_from="device.rear_ports"
            ),
        ],
    ),
    TemplateUpdate(
        src="console_port_templates",
        dst="console_ports",
        key_field="name",
        fields=["name", "label", "type"],
    ),
    TemplateUpdate(
        src="console_server_port_templates",
        dst="console_server_ports",
        key_field="name",
        fields=["name", "label", "type"],
    ),
    TemplateUpdate(
        src="power_port_templates",
        dst="power_ports",
        key_field="name",
        fields=["name", "label", "type", "maximum_draw", "allocated_draw"],
    ),
    TemplateUpdate(
        src="power_outlet_templates",
        dst="power_outlets",
        key_field="name",
        fields=[
            "name",
            "label",
            "type",
            FieldUpdate(
                name="power_port",
                template_name="power_port_template",
                key_field="name",
                query_from="device.power_ports",
            ),
            "feed_leg",
        ],
    ),
    TemplateUpdate(
        src="device_bay_templates",
        dst="device_bays",
        key_field="name",
        fields=["name", "label"],
    ),
]


class UpdateDeviceFromTemplatesMixin:
    """Common code for both the button receiver and the job entrypoint."""

    def update_device_type(self, device_type: DeviceType, devices: Iterable[Device] = []):
        """Update a list of devices so their components match the device type's templates."""
        if not devices:
            devices = device_type.devices.all()
        self.logger.info("Updating devices from %s", device_type, extra={"object": device_type})
        for device in devices:
            self.logger.info("Updating %s", device, extra={"object": device})
            for template_update in TEMPLATE_UPDATES:
                template_update.update(self, device_type, device)


class DeviceComponentUpdateButton(BaseJobButton, UpdateDeviceFromTemplatesMixin):
    """Device Component Update.

    This is a job button receiver that will call the Device Component Update job
    when clicked from a device detail page.
    """

    class Meta:  # noqa:D106
        has_sensitive_variables = False

    def receive_job_button(self, obj: DeviceType):
        """Run the job when the button has been pushed."""
        super().receive_job_button(obj)
        self.update_device_type(obj)


class DeviceComponentUpdate(BaseJob, UpdateDeviceFromTemplatesMixin):
    """Device Component Update.

    This job will align devices with their device type. If a device
    type's component templates (interfaces, front/rear ports, power ports, etc) have
    changed then this job attempts to create the missing components on a device or
    set of devices. The job attempts to first find pre-existing components to be
    updated. If none are found then new components are created.
    """

    device_type = ObjectVar(label="Device Type", model=DeviceType)
    devices = MultiObjectVar(
        label="Devices",
        model=Device,
        query_params={"device_type_id": "$device_type"},
        required=False,
    )

    class Meta:  # noqa:D106
        has_sensitive_variables = False

    def run(self, device_type: DeviceType, devices: Iterable[Device]):
        """Perform the update for the provided set of devices."""
        self.update_device_type(device_type, devices)


name = "Device Utilities"
register_jobs(DeviceComponentUpdate, DeviceComponentUpdateButton)

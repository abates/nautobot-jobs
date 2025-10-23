"""Base class for cleanup jobs."""

import logging
import textwrap

from nautobot.apps.jobs import ChoiceVar, Job, JobButtonReceiver


class JobDocumentation(type):
    """Meta class for jobs.

    This metaclass will automatically populate the name and description fields
    in the Job class `Meta` class. The values will only be set if not set already
    in `Meta`. For the case of `name`, the class name will be parsed to convert
    from `CamelCase` to `Space Separated`. The description is gathered from the
    long description in the class documentation/pydoc.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the meta class."""
        super().__init__(*args, **kwargs)
        # Don't annotate the BaseJob class
        if self.__name__.startswith("BaseJob"):
            return

        meta = getattr(self, "Meta", None)
        if meta is None:
            meta = type("Meta", (object,), {})
            self.Meta = meta

        if getattr(meta, "description", None) is None and self.__doc__ is not None:
            try:
                _, parsed_description = self.__doc__.split("\n", 1)
            except ValueError:
                parsed_description = self.__doc__
            parsed_description = textwrap.dedent(parsed_description).strip()
            setattr(meta, "description", parsed_description)

        if getattr(meta, "name", None) is None:
            # convert camel case class name to space separated
            setattr(meta, "name", ("".join([c if c.islower() else " " + c for c in self.__name__])).strip())


LOG_LEVEL_CHOICES = (
    (logging.DEBUG, "Debug"),
    (logging.INFO, "Info"),
    (logging.WARNING, "Warning"),
    (logging.ERROR, "Error"),
    (logging.FATAL, "Fatal"),
)


class BaseJob(Job, metaclass=JobDocumentation):
    """Base class for jobs."""

    log_level = ChoiceVar(label="Log Level", choices=LOG_LEVEL_CHOICES, default=logging.INFO)

    def run(self, log_level: int, *args, **kwargs):
        """Set the logger level based on user input."""
        self.logger.setLevel(int(log_level))


class BaseJobButton(JobButtonReceiver, metaclass=JobDocumentation):
    """Base class for job button receivers."""

    def receive_job_button(self, obj):
        """Receive a job button click and set the logger to INFO."""
        self.logger.setLevel(logging.INFO)

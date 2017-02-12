from django import forms


class DictionaryField(forms.Field):
    """
    Dictionary form field that only accepts python dicts.
    """
    def to_python(self, value):
        if value in self.empty_values:
            return None
        elif isinstance(value, dict):
            return value
        else:
            raise forms.ValidationError(self.error_messages['invalid'], code='invalid')


class CharField(forms.CharField):
    """
    Char form field that allows customizing the empty value.

    Mimics the forms.CharField behaviour added in Django 1.11.
    """
    def __init__(self, empty_value='', *args, **kwargs):
        super(CharField, self).__init__(*args, **kwargs)
        self.empty_value = empty_value

    def to_python(self, value):
        "Returns a string."
        if value in self.empty_values:
            return self.empty_value

        return super(CharField, self).to_python(value)


class ChoiceField(forms.ChoiceField):
    """
    Choice form field that allows customizing the empty value.
    """
    def __init__(self, empty_value='', *args, **kwargs):
        super(ChoiceField, self).__init__(*args, **kwargs)
        self.empty_value = empty_value

    def to_python(self, value):
        "Returns a string."
        if value in self.empty_values:
            return self.empty_value

        return super(ChoiceField, self).to_python(value)


class ScheduleMessageForm(forms.Form):
    """
    Form for validating messages reveiced on asgi.schedule.
    """
    METHOD_CHOICES = (
        ("add", "Add Job"),
        ("remove", "Remove Job"),
    )
    TRIGGER_CHOICES = (
        ("cron", "cron"),
        ("date", "date"),
        ("interval", "interval"),
    )

    method = forms.ChoiceField(choices=METHOD_CHOICES)

    reply_channel = CharField(
        max_length=199,
        empty_value=None,
        required=False,
    )
    content = DictionaryField(required=False)
    id = CharField(empty_value=None, required=False)
    trigger = ChoiceField(
        choices=TRIGGER_CHOICES,
        empty_value=None,
        required=False
    )

    # "cron" trigger related fields
    year = CharField(empty_value=None, required=False)
    month = CharField(empty_value=None, required=False)
    day = CharField(empty_value=None, required=False)
    week = CharField(empty_value=None, required=False)
    day_of_week = CharField(empty_value=None, required=False)
    hour = CharField(empty_value=None, required=False)
    minute = CharField(empty_value=None, required=False)
    second = CharField(empty_value=None, required=False)

    # "date" trigger related fields
    run_date = forms.DateTimeField(required=False)

    # "interval" trigger kwargs
    weeks = forms.IntegerField(min_value=1, required=False)
    days = forms.IntegerField(min_value=1, required=False)
    hours = forms.IntegerField(min_value=1, required=False)
    minutes = forms.IntegerField(min_value=1, required=False)
    seconds = forms.IntegerField(min_value=1, required=False)

    # "cron" and "interval" kwargs
    start_date = forms.DateTimeField(required=False)
    end_date = forms.DateTimeField(required=False)

    def clean(self):
        cleaned_data = super(ScheduleMessageForm, self).clean()
        method = cleaned_data.get("method")

        if method == "add":
            self._validate_add_schedule_message(cleaned_data)
        elif method == "remove":
            self._validate_remove_schedule_message(cleaned_data)

    def _validate_add_schedule_message(self, cleaned_data):
        if not cleaned_data.get("reply_channel"):
            self.add_error("reply_channel", forms.ValidationError(
                "'reply_channel' is required when adding a job"))

        if not cleaned_data.get("content"):
            self.add_error("content", forms.ValidationError(
                "'content' is required when adding a job"))

        trigger = cleaned_data.get("trigger")
        if trigger == "cron":
            self._validate_cron(cleaned_data)
        elif trigger == "date":
            self._validate_date(cleaned_data)
        elif trigger == "interval":
            self._validate_interval(cleaned_data)

    def _validate_cron(self, cleaned_data):
        for field in ("year", "month", "day", "week", "day_of_week", "hour", "minute", "second"):
            if cleaned_data.get(field):
                return

        self.add_error(None, forms.ValidationError(
            "Configuring the cron trigger requires at least on of ['year', "
            "'month', 'day', 'week', 'day_of_week', 'hour', 'minute', "
            "'second']."
        ))

    def _validate_date(self, cleaned_data):
        if not cleaned_data.get("run_date"):
            self.add_error("run_date", forms.ValidationError(
                "Configuring the cron trigger requires 'run_date'."
            ))

    def _validate_interval(self, cleaned_data):
        for field in ("weeks", "days", "hours", "minutes", "seconds"):
            if cleaned_data.get(field):
                return

        self.add_error(None, forms.ValidationError(
            "Configuring the date trigger requires at least on of ['weeks', "
            "'days', 'hours', 'minutes', 'seconds']."
        ))

    def _validate_remove_schedule_message(self, cleaned_data):
        id = cleaned_data.get("id")

        if not id:
            self.add_error("id", forms.ValidationError(
                "'id' is required when removing a job."))

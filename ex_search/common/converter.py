import datetime


class InDictConverter:
    @classmethod
    def datetime_to_str(cls, target: dict) -> dict:
        return cls._convert_datetime_to_str_in_dict(targets=target)

    @classmethod
    def _convert_datetime_to_str_in_dict(cls, targets: dict) -> dict:
        converted = {}
        for key, value in targets.items():
            converted[key] = cls._convert_datetime_to_str(value)
        return converted

    @classmethod
    def _convert_datetime_to_str(cls, value):
        if isinstance(value, (datetime.datetime, datetime.date)):
            return str(value)  # value.strftime("%Y-%m-%d %H:%M:%S.%f")
        elif isinstance(value, dict):
            return cls._convert_datetime_to_str_in_dict(value)
        elif isinstance(value, list):
            converted_list = []
            for v in value:
                converted_list.append(cls._convert_datetime_to_str(v))
            return converted_list
        else:
            return value

import os
from abc import ABC, abstractmethod
from enum import Enum
from io import StringIO
from typing import Tuple, Optional, Dict, List


class CustomEnum(Enum):

    @classmethod
    def names_dict(cls) -> Dict[str, "CustomEnum"]:
        return {c.name.lower(): c for c in cls}

    @classmethod
    def from_str(cls, string: str) -> Optional["CustomEnum"]:
        if string:
            final_str = string.strip().lower()

            if final_str:
                return cls.names_dict().get(final_str)

    @classmethod
    def from_value(cls, value: object) -> Optional["CustomEnum"]:
        if value is not None:
            for c in cls:
                if c.value == value:
                    return c


class FileModel(ABC):

    @abstractmethod
    def is_valid(self) -> bool:
        pass

    @abstractmethod
    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        """
        :return: a dict mapping properties from the profile file to the model's.
        The mapped tuples represent the model's property name and type.
        """
        pass

    def get_output_name(self) -> str:
        return ''

    def get_file_properties(self) -> Dict[str, str]:
        prop_map = self.get_file_mapping()
        node = self.get_file_root_node_name()
        props = {}

        if prop_map:
            for key, prop in prop_map.items():
                prop_val = getattr(self, prop[0])

                if prop_val is not None:
                    val_str = str(prop_val)

                    if isinstance(prop_val, bool):
                        val_str = val_str.lower()

                    props[f"{'{}.'.format(node) if node else ''}{key}"] = val_str

        for val in self.__dict__.values():
            if isinstance(val, FileModel):
                sub_props = val.get_file_properties()

                if node and sub_props:
                    sub_props = {f'{node}.{key}': val for key, val in sub_props.items()}

                if sub_props:
                    props.update(sub_props)

        return props

    def to_file_str(self) -> Optional[str]:
        props = self.get_file_properties()

        if props:
            string = StringIO()
            for key, val in sorted(props.items()):
                string.write(f'{key}={val}\n')

            string.seek(0)
            return string.read()

    @abstractmethod
    def get_file_root_node_name(self) -> Optional[str]:
        pass

    def get_nested_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        """
        :return: a dict with all nested file model mappings
        """
        mapping = {}

        for prop, instance in self.__dict__.items():
            if instance and isinstance(instance, FileModel):
                for file_prop, prop_data in instance.get_full_mapping().items():
                    mapping.update({file_prop: (f'{prop}.{prop_data[0]}', prop_data[1], prop_data[2])})

        return mapping

    def get_full_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        full_mapping = {}

        mapping = self.get_file_mapping()

        if mapping:
            full_mapping.update(mapping)

        nested_mapping = self.get_nested_mapping()

        if nested_mapping:
            full_mapping.update(nested_mapping)

        root_node = self.get_file_root_node_name()
        if full_mapping and root_node:
            full_mapping = {f'{root_node}.{k}': v for k, v in full_mapping.items()}

        return full_mapping

    def reset_invalid_nested_members(self):
        for prop, val in self.__dict__.items():
            if isinstance(val, FileModel):
                val.reset_invalid_nested_members()
                if not val.is_valid():
                    setattr(self, prop, None)

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        for p, v in self.__dict__.items():
            if v != getattr(other, p):
                return False

        return True

    def __hash__(self):
        hash_sum = 0

        for p, v in sorted(self.__dict__.items()):
            hash_sum += hash(v)

        return hash_sum

    def __repr__(self):
        return f'{self.__class__.__name__} {self.__dict__}'


class RootFileModel(FileModel, ABC):

    def is_valid(self) -> bool:
        valid = False
        for val in self.__dict__.values():
            if isinstance(val, FileModel):
                if val.is_valid():
                    valid = True
                else:
                    return False

        return valid

    def get_file_root_node_name(self) -> Optional[str]:
        return


class ProfileFile(RootFileModel, ABC):

    def __init__(self, path: Optional[str]):
        self.path: Optional[str] = None
        self.name: Optional[str] = None
        self.set_path(path)

    def set_path(self, path: str):
        self.path = path.strip() if path is not None else None
        self.name = '.'.join(os.path.basename(self.path).split('.')[0:-1]) if self.path else None


class ScriptSettings(FileModel):

    def __init__(self, node_name: str, scripts: Optional[List[str]] = None, wait_execution: Optional[bool] = False,
                 timeout: Optional[float] = None, run_as_root: bool = False):
        self.scripts = scripts
        self.wait_execution = wait_execution
        self.timeout = timeout  # wait timeout
        self.run_as_root = run_as_root
        self._node_name = node_name
        self._file_mapping = {f"{node_name}{f'.{p}' if p else ''}": v for p, v in
                              {'': ('scripts', List[str], None), 'wait': ('wait_execution', bool, True),
                               'timeout': ('timeout', float, None), 'root': ('run_as_root', bool, True)}.items()}

    def get_file_mapping(self) -> Dict[str, Tuple[str, type, Optional[object]]]:
        return self._file_mapping

    def get_output_name(self) -> str:
        return ''

    def is_valid(self) -> bool:
        return bool(self.scripts)

    def get_file_root_node_name(self) -> Optional[str]:
        pass

    def has_valid_timeout(self) -> bool:
        return self.timeout is not None and self.timeout > 0

    def __eq__(self, other):
        if isinstance(other, ScriptSettings):
            return self.__dict__ == other.__dict__

        return False

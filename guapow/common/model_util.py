import functools
from abc import ABC, abstractmethod
from logging import Logger
from typing import List, Optional, Set, Tuple, Type, Dict

from guapow.common import class_util
from guapow.common.model import CustomEnum, ProfileFile, FileModel


def rgetattr(obj, attr, *args):
    def _getattr(obj, attr):
        return getattr(obj, attr, *args)

    return functools.reduce(_getattr, [obj] + attr.split('.'))


def rsetattr(obj, attr, val):
    pre, _, post = attr.rpartition('.')
    return setattr(rgetattr(obj, pre) if pre else obj, post, val)


class InvalidMappedPropertyException(Exception):

    def __init__(self, msg: str):
        self.message = msg


class FileModelPropertyMapper(ABC):

    @abstractmethod
    def supports(self, prop_type: type) -> bool:
        pass

    @abstractmethod
    def map(self, prop_val: str, prop_type: type) -> Optional[object]:
        pass

    @abstractmethod
    def get_raw_type(self) -> type:
        pass


class FileModelCollectionPropertyMapper(FileModelPropertyMapper, ABC):

    @abstractmethod
    def create_collection(self) -> object:
        pass

    @abstractmethod
    def update_collection(self, collection: object, update: object):
        pass


class StringPropertyMapper(FileModelPropertyMapper):

    def supports(self, prop_type: type) -> bool:
        return prop_type == str

    def map(self, prop_val: str, prop_type: type) -> Optional[str]:
        return prop_val

    def get_raw_type(self) -> type:
        return str


class IntPropertyMapper(FileModelPropertyMapper):

    def supports(self, prop_type: type) -> bool:
        return prop_type == int

    def map(self, prop_val: str, prop_type: type) -> Optional[int]:
        try:
            return int(prop_val)
        except ValueError:
            raise InvalidMappedPropertyException("It should be an integer")

    def get_raw_type(self) -> type:
        return int


class FloatPropertyMapper(FileModelPropertyMapper):

    def supports(self, prop_type: type) -> bool:
        return prop_type == float

    def map(self, prop_val: str, prop_type: type) -> Optional[float]:
        try:
            return float(prop_val)
        except ValueError:
            raise InvalidMappedPropertyException("It should be a float")

    def get_raw_type(self) -> type:
        return float


class BoolPropertyMapper(FileModelPropertyMapper):

    FALSE_STRINGS = {'0', 'false'}
    TRUE_STRINGS = {'1', 'true'}

    def supports(self, prop_type: type) -> bool:
        return prop_type == bool

    def map(self, prop_val: str, prop_type: type) -> Optional[bool]:
        lower_val = prop_val.lower()

        if lower_val in self.FALSE_STRINGS:
            return False
        elif lower_val in self.TRUE_STRINGS:
            return True
        else:
            raise InvalidMappedPropertyException(f"It should be a boolean (accepted values: {','.join([*self.FALSE_STRINGS, *self.TRUE_STRINGS])})")

    def get_raw_type(self) -> type:
        return bool


class IntListPropertyMapper(FileModelCollectionPropertyMapper):

    def supports(self, prop_type: type) -> bool:
        return prop_type == List[int]

    def map(self, prop_val: str, prop_type: type) -> Optional[List[int]]:
        int_list = [*{int(n) for n in prop_val.split(',') if n.isdigit()}]
        int_list.sort()
        return int_list

    def create_collection(self) -> object:
        return list()

    def update_collection(self, collection: object, update: object):
        if isinstance(collection, list) and isinstance(update, list):
            collection.extend(update)

    def get_raw_type(self) -> type:
        return list


class StringListPropertyMapper(FileModelCollectionPropertyMapper):

    def supports(self, prop_type: type) -> bool:
        return prop_type == List[str]

    def map(self, prop_val: str, prop_type: type) -> Optional[List[str]]:
        return prop_val.split(',')

    def create_collection(self) -> object:
        return list()

    def update_collection(self, collection: object, update: object):
        if isinstance(collection, list) and isinstance(update, list):
            collection.extend(update)

    def get_raw_type(self) -> type:
        return list


class StringSetPropertyMapper(FileModelCollectionPropertyMapper):

    def supports(self, prop_type: type) -> bool:
        return prop_type == Set[str]

    def map(self, prop_val: str, prop_type: type) -> Optional[Set[str]]:
        return {*prop_val.split(',')}

    def create_collection(self) -> object:
        return set()

    def update_collection(self, collection: object, update: object):
        if isinstance(collection, set) and isinstance(update, set):
            collection.update(update)

    def get_raw_type(self) -> type:
        return set


class CustomEnumPropertyMapper(FileModelPropertyMapper):

    def supports(self, prop_type: type) -> bool:
        return isinstance(prop_type, type) and issubclass(prop_type, CustomEnum)

    def map(self, prop_val: str, prop_type: Type[CustomEnum]) -> Optional[CustomEnum]:
        mapped_val = prop_type.from_str(prop_val)

        if mapped_val:
            return mapped_val

        raise InvalidMappedPropertyException(f'Unknown value: {prop_val}')

    def get_raw_type(self) -> type:
        return CustomEnum


class DictPropertyMapper(FileModelCollectionPropertyMapper):

    def supports(self, prop_type: type) -> bool:
        return prop_type == dict

    def map(self, prop_val: str, prop_type: type) -> Optional[Tuple[str, object]]:
        var_val = [s.strip() for s in prop_val.split(':', 1)]

        if not var_val or not var_val[0] or len(var_val) > 2:
            raise InvalidMappedPropertyException(f'Wrong dict property value defined: {prop_val}')

        if len(var_val) == 1 and var_val[0]:
            return var_val[0], None
        elif len(var_val) == 2 and not var_val[1]:
            return var_val[0], None
        else:
            return var_val[0], var_val[1]

    def create_collection(self) -> object:
        return dict()

    def update_collection(self, collection: object, update: object):
        if isinstance(collection, dict):
            if isinstance(update, tuple):
                collection[update[0]] = update[1]
            elif isinstance(update, dict):
                collection.update(update)

    def get_raw_type(self) -> type:
        return dict


class FileModelFiller:

    def __init__(self, logger: Logger):
        self._log = logger
        self._property_mappers = class_util.instantiate_subclasses(FileModelPropertyMapper)
        self._mapper_type_cache: Dict[type, FileModelPropertyMapper] = {}

    def get_mapper(self, prop_type: type) -> Optional[FileModelPropertyMapper]:
        mapper = self._mapper_type_cache.get(prop_type)

        if not mapper:
            supported_mappers = [m for m in self._property_mappers if m.supports(prop_type)]

            if supported_mappers:
                mapper = supported_mappers[0]
                self._mapper_type_cache[prop_type] = mapper

        return mapper

    def _update_mapped_object_with_mapper(self, prop_path: str, prop_val: str, prop_type: type, root: FileModel, mapper: FileModelPropertyMapper, mapped_obj: dict):
        try:
            mapped_val = mapper.map(prop_val, prop_type)
        except InvalidMappedPropertyException as e:
            self._log.warning(f"Invalid {root.get_output_name()}'s property '{prop_path}' mapping: {e.message}")
            return

        if isinstance(mapper, FileModelCollectionPropertyMapper):
            if mapped_val:
                collection = mapped_obj.get(prop_path)

                if collection is None:
                    collection = mapper.create_collection()
                    mapped_obj[prop_path] = collection

                mapper.update_collection(collection, mapped_val)
        else:
            mapped_obj[prop_path] = mapped_val

    def fill(self, root: FileModel, file_content: str, only_properties: Optional[Set[str]] = None):
        prop_mapping = root.get_full_mapping()

        if prop_mapping:
            mapped_obj = {}

            for line in file_content.split('\n'):
                if line:
                    clean_line = line.strip()

                    if clean_line and not clean_line.startswith('#'):
                        line_split = clean_line.split('=', 1)
                        file_prop = line_split[0].strip()

                        if file_prop:
                            if not only_properties or file_prop in only_properties:
                                model_prop = prop_mapping.get(file_prop)

                                if model_prop:
                                    prop_path, prop_type = model_prop[0], model_prop[1]

                                    if len(line_split) == 1:
                                        prop_default = model_prop[2]

                                        if prop_default is None:
                                            continue

                                        mapper = self.get_mapper(prop_type)

                                        if not mapper or not isinstance(prop_default, mapper.get_raw_type()):
                                            self._log.error(f"Invalid default value type for property '{file_prop}' ({prop_type.__name__}): {prop_default} ({type(prop_default).__name__})")
                                            continue

                                        mapped_obj[prop_path] = prop_default
                                    else:
                                        mapper = self.get_mapper(prop_type)

                                        if mapper:
                                            prop_val = line_split[1].split('#')[0].strip()
                                            self._update_mapped_object_with_mapper(prop_path, prop_val, prop_type, root, mapper, mapped_obj)
                                        else:
                                            self._log.error(f"Unsupported {root.get_output_name()}'s property type: {prop_type}")

            if mapped_obj:
                for prop, val in mapped_obj.items():
                    rsetattr(root, prop, val)

    def fill_profile(self, profile: ProfileFile, profile_str: str, profile_path: Optional[str], add_settings: Optional[str] = None):
        profile.set_path(profile_path)
        final_profile_str = profile_str

        if add_settings:
            final_profile_str = f'{final_profile_str}\n{add_settings}'
            self._log.debug(f"Settings merged into profile '{profile.name}': {add_settings}")

        self.fill(profile, final_profile_str)
        profile.reset_invalid_nested_members()
